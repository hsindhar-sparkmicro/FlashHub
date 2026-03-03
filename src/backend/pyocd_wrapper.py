import subprocess
import logging
from pyocd.core.helpers import ConnectHelper
from pyocd.flash.file_programmer import FileProgrammer
from pyocd.core.exceptions import DebugError

class PyOCDWrapper:
    @staticmethod
    def list_probes():
        """
        Detects all connected probes.
        Returns a list of dictionaries with probe details.
        """
        try:
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
            # Run pyocd list --targets
            result = subprocess.run(
                ["pyocd", "list", "--targets"], 
                capture_output=True, 
                text=True, 
                check=True
            )
            lines = result.stdout.split('\n')
            targets = []
            # Parse output, usually format: "  stm32g071rb        ST..."
            # Skip header if any, usually valid targets are indented or first word
            for line in lines:
                parts = line.strip().split()
                if parts:
                    # heuristic: first column is target name if it doesn't look like a header
                    target = parts[0]
                    if target.lower() not in ["matches", "name", "vendor", "part", "family", "source"]:
                        targets.append(target)
            return sorted(list(set(targets)))
        except subprocess.CalledProcessError as e:
            logging.error(f"Error listing targets: {e}")
            return []
        except FileNotFoundError:
             # Fallback if pyocd not in path
            logging.error("pyocd executable not found.")
            return []

    @staticmethod
    def install_pack(family_name):
        """
        Installs a target pack.
        """
        try:
            # Using Popen or run without capture might capture stdin/out better for long running,
            # but run() check=True is simpler. 
            # Note: pyocd pack install takes time and prints progress to stdout.
            # We might want to capture output to show in GUI.
            subprocess.run(
                ["pyocd", "pack", "install", family_name], 
                check=True
            )
            return True
        except subprocess.CalledProcessError as e:
            logging.error(f"Error installing pack for {family_name}: {e}")
            return False
        except Exception as e:
            logging.error(f"General Error installing pack: {e}")
            return False

    @staticmethod
    def find_packs(query):
        """
        Runs 'pyocd pack find <query>' and returns list of matching packs.
        """
        try:
            result = subprocess.run(
                ["pyocd", "pack", "find", query], 
                capture_output=True, 
                text=True, 
                check=True
            )
            # Output format: "  Part/Family ... Pack"
            return result.stdout.strip()
        except Exception as e:
            return f"Error searching packs: {e}"

    @staticmethod
    def detect_target(probe_id):
        """
        Attempts to detect the connected STM32 target by reading the DBGMCU_IDCODE.
        Returns a suggested target string (e.g., 'stm32g0b0') or None.
        """
        session = None
        try:
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
