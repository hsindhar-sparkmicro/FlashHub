import subprocess
import re
import shutil
import logging

class OpenOCDWrapper:
    @staticmethod
    def is_installed():
        return shutil.which("openocd") is not None

    @staticmethod
    def detect_target():
        """
        Runs openocd with a generic config to probe the chain.
        Returns a string if an STM32 family is detected (e.g., 'stm32g0').
        """
        if not OpenOCDWrapper.is_installed():
            logging.error("OpenOCD is not installed or not in PATH.")
            return None

        # Command to init and exit. config finding might be tricky depending on install
        # We assume standard scripts location.
        # using 'interface/stlink.cfg' covers V2, V2-1, V3
        cmd = [
            "openocd",
            "-f", "interface/stlink.cfg",
            "-c", "transport select hla_swd",
            "-c", "init",
            "-c", "shutdown"
        ]

        try:
            # openocd returns non-zero if it fails to connect, but might still print device info
            result = subprocess.run(cmd, capture_output=True, text=True)
            output = result.stderr + result.stdout

            # Look for "Info : STM32G0xx..."
            # AND "Info : device id = 0x..."
            
            detected_target = None

            # Try to match device ID first (more specific)
            # Example: "Info : device id = 0x10016466" -> 0x466 is G0B1/G0B0
            id_match = re.search(r"device id = (0x[0-9a-fA-F]+)", output)
            if id_match:
                raw_id = int(id_match.group(1), 16)
                dev_id = raw_id & 0xFFF
                
                # Mapping based on DBGMCU_IDCODE
                # G0 Series
                if dev_id == 0x460: detected_target = "stm32g071rb"
                elif dev_id == 0x466: detected_target = "stm32g0b1keux" # Commonly G0B1/G0C1
                # Some references imply 0x467 could be shared or misidentified for G0B0 in some contexts
                # or user simply wants it mapped this way.
                elif dev_id == 0x467: detected_target = "stm32g0b1keux" 
                # F4 Series
                elif dev_id == 0x413: detected_target = "stm32f407"
                elif dev_id == 0x463: detected_target = "stm32f429"
                # U5 Series
                elif dev_id == 0x482: detected_target = "stm32u585"
                
                if detected_target:
                    logging.info(f"OpenOCD: matched device id {hex(dev_id)} to {detected_target}")
                    return detected_target

            # Fallback to family string parsing
            match = re.search(r"Info : STM32([A-Za-z0-9]+)xx", output)
            if match:
                partial = match.group(1).lower() # e.g. "g0"
                # If we couldn't match ID, maybe return generic. 
                # But 'stm32g0' isn't a valid target name. 
                # We'll try to guess a common one or return it and let user fix.
                logging.info(f"OpenOCD: matched family {partial}")
                return f"stm32{partial}" 

        except Exception as e:
            logging.error(f"OpenOCD detection failed: {e}")
            return None

        return None
