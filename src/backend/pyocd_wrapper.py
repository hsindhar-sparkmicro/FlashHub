import io
import logging
from contextlib import redirect_stderr, redirect_stdout
from pyocd.probe.aggregator import PROBE_CLASSES
from pyocd.core.helpers import ConnectHelper
from pyocd.flash.file_programmer import FileProgrammer
from pyocd.core.exceptions import DebugError
from pyocd.__main__ import PyOCDTool


def _ensure_builtin_probe_plugins_loaded():
    if PROBE_CLASSES:
        return

    plugin_factories = []

    try:
        from pyocd.probe.cmsis_dap_probe import CMSISDAPProbePlugin
        plugin_factories.append(CMSISDAPProbePlugin)
    except ImportError:
        pass

    try:
        from pyocd.probe.jlink_probe import JLinkProbePlugin
        plugin_factories.append(JLinkProbePlugin)
    except ImportError:
        pass

    try:
        from pyocd.probe.picoprobe import PicoprobePlugin
        plugin_factories.append(PicoprobePlugin)
    except ImportError:
        pass

    try:
        from pyocd.probe.stlink_probe import StlinkProbePlugin
        plugin_factories.append(StlinkProbePlugin)
    except ImportError:
        pass

    try:
        from pyocd.probe.tcp_client_probe import TCPClientProbePlugin
        plugin_factories.append(TCPClientProbePlugin)
    except ImportError:
        pass

    for plugin_factory in plugin_factories:
        try:
            plugin = plugin_factory()
            if plugin.should_load():
                PROBE_CLASSES.setdefault(plugin.name, plugin.load())
        except Exception as error:
            logging.debug("Skipping pyOCD probe plugin %s: %s", plugin_factory.__name__, error)

class PyOCDWrapper:
    @staticmethod
    def _run_pyocd_command(args):
        output_buffer = io.StringIO()
        with redirect_stdout(output_buffer), redirect_stderr(output_buffer):
            exit_code = PyOCDTool().run(args)
        return exit_code, output_buffer.getvalue().strip()

    @staticmethod
    def list_probes():
        """
        Detects all connected probes.
        Returns a list of dictionaries with probe details.
        """
        try:
            _ensure_builtin_probe_plugins_loaded()
            probes = ConnectHelper.get_all_connected_probes(blocking=False)
            probe_list = []
            for probe in probes:
                probe_list.append({
                    "unique_id": probe.unique_id,
                    "product_name": probe.product_name,
                    "vendor_name": probe.vendor_name
                })
            return probe_list
        except Exception as e:
            logging.error(f"Error listing probes: {e}")
            return []

    @staticmethod
    def get_targets():
        """
        Returns a list of supported targets by running 'pyocd list --targets'.
        """
        try:
            exit_code, output = PyOCDWrapper._run_pyocd_command(["list", "--targets"])
            if exit_code != 0:
                logging.error("Error listing targets: %s", output)
                return []

            lines = output.split('\n')
            targets = []
            for line in lines:
                parts = line.strip().split()
                if parts:
                    target = parts[0]
                    if target.lower() not in ["matches", "name", "vendor", "part", "family", "source"]:
                        targets.append(target)
            return sorted(list(set(targets)))
        except Exception as error:
            logging.error("Error listing targets: %s", error)
            return []

    @staticmethod
    def install_pack(family_name):
        """
        Installs a target pack.
        """
        try:
            exit_code, output = PyOCDWrapper._run_pyocd_command(["pack", "install", family_name])
            if exit_code != 0:
                logging.error("Error installing pack for %s: %s", family_name, output)
                return False, output or f"Install failed for {family_name}"
            return True, output or f"Install succeeded for {family_name}"
        except Exception as error:
            logging.error("General Error installing pack: %s", error)
            return False, str(error)

    @staticmethod
    def find_packs(query):
        """
        Runs 'pyocd pack find <query>' and returns list of matching packs.
        """
        try:
            exit_code, output = PyOCDWrapper._run_pyocd_command(["pack", "find", query])
            if exit_code != 0:
                return f"Error searching packs: {output or 'unknown pyOCD error'}"
            return output
        except Exception as error:
            return f"Error searching packs: {error}"

    @staticmethod
    def detect_target(probe_id):
        """
        Attempts to detect the connected STM32 target by reading the DBGMCU_IDCODE.
        Returns a suggested target string (e.g., 'stm32g0b0') or None.
        """
        session = None
        try:
            _ensure_builtin_probe_plugins_loaded()
            # Connect as generic cortex_m to read memory
            session = ConnectHelper.session_with_chosen_probe(
                unique_id=probe_id,
                target_override="cortex_m",
                options={"resume_on_disconnect": False, "auto_unlock": False}
            )
            
            with session:
                target = session.board.target
                
                # Dictionary of (Address, Mask) -> {DevID: Name}
                # STM32G0 IDCODE is at 0x40015800
                # STM32F4/G4/L4/H7 usually at 0xE0042000
                
                # Check STM32G0 Location (0x40015800)
                try:
                    val = target.read32(0x40015800)
                    if val != 0 and val != 0xFFFFFFFF:
                        dev_id = val & 0xFFF
                        # Mapping based on RM0444 and other Reference Manuals
                        if dev_id == 0x460: return "stm32g071rb" # G07x/G08x
                        if dev_id == 0x466: return "stm32g0b1keux" # G05x/G06x/G0B0/G0B1
                        if dev_id == 0x467: return "stm32g0b1keux" # User specified mapping (0x467 usually G030)
                except:
                    pass

                # Check Standard DBGMCU_IDCODE (0xE0042000) - For U5, F4, L4
                try:
                    val = target.read32(0xE0042000)
                    if val != 0 and val != 0xFFFFFFFF:
                        dev_id = val & 0xFFF
                        if dev_id == 0x482: return "stm32u585"   # U58x
                        if dev_id == 0x413: return "stm32f407"   # F405/407
                except:
                    pass
                
                # Check STM32U5 specific if not found at E0042000 (Some docs say E0044000)
                try:
                    val = target.read32(0xE0044000)
                    if val != 0 and val != 0xFFFFFFFF:
                        dev_id = val & 0xFFF
                        if dev_id == 0x482: return "stm32u585"
                except:
                    pass

            return None

        except Exception as e:
            logging.error(f"Error detecting target: {e}")
            return None

    @staticmethod
    def flash_firmware(probe_id, target_device, file_path, progress_callback=None, packs=None):
        """
        Flashes firmware to the specified target.
        
        Args:
            probe_id (str): Unique ID of the probe.
            target_device (str): Target MCU type (e.g., 'stm32g071rb').
            file_path (str): Path to the firmware file (.hex, .bin, .elf).
            progress_callback (callable): Optional callback for progress updates.
            packs (list[str]): Optional list of local .pack file paths to load.
        """
        session = None
        try:
            options = {
                "connect_mode": "under-reset",
                "frequency": 4000000,
            }
            if packs:
                options["pack"] = packs

            # Connect to the specific probe
            # connect_mode='under-reset' helps if target is sleeping or pins reconfigured
            session = ConnectHelper.session_with_chosen_probe(
                unique_id=probe_id,
                target_override=target_device,
                options=options,
            )
            
            with session:
                # Reset and halt
                session.board.target.reset_and_halt()
                
                # Setup programmer
                programmer = FileProgrammer(session)
                
                # wrapper for progress to match pyOCD's callback signature if needed,
                # essentially pyocd progress callbacks usually take (percent)
                def internal_progress(percent):
                    if progress_callback:
                        progress_callback(int(percent))

                programmer.program(file_path, callback=internal_progress)
                
                # Reset after flash
                session.board.target.reset()
                
        except DebugError as de:
            logging.error(f"Debug Error during flashing: {de}")
            msg = str(de)
            if "Debug power error" in msg:
                raise Exception("Target power missing (VREF=0V). Check cables/power.") from de
            raise
        except Exception as e:
            logging.error(f"General Error during flashing: {e}")
            raise
        finally:
            if session:
                session.close()

    @staticmethod
    def reset_target(probe_id, target_device, packs=None):
        """
        Resets the target MCU without flashing.
        
        Args:
            probe_id (str): Unique ID of the probe.
            target_device (str): Target MCU type (e.g., 'stm32g071rb').
            packs (list[str]): Optional list of local .pack file paths to load.
        """
        session = None
        try:
            options = {
                "connect_mode": "under-reset",
                "frequency": 4000000,
            }
            if packs:
                options["pack"] = packs

            # Connect to the specific probe
            session = ConnectHelper.session_with_chosen_probe(
                unique_id=probe_id,
                target_override=target_device,
                options=options,
            )
            
            with session:
                # Reset the target
                session.board.target.reset()
                logging.info(f"Target reset successful for probe {probe_id}")
                
        except DebugError as de:
            logging.error(f"Debug Error during reset: {de}")
            msg = str(de)
            if "Debug power error" in msg:
                raise Exception("Target power missing (VREF=0V). Check cables/power.") from de
            raise
        except Exception as e:
            logging.error(f"General Error during reset: {e}")
            raise
        finally:
            if session:
                session.close()
