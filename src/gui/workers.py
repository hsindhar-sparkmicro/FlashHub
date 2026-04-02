from PyQt6.QtCore import QThread, pyqtSignal
from src.backend.pyocd_wrapper import PyOCDWrapper
from src.backend.stm32cubeprogrammer_wrapper import STM32CubeProgrammerWrapper
# from src.backend.openocd_wrapper import OpenOCDWrapper # Removed
import traceback

class FlashWorker(QThread):
    progress = pyqtSignal(str, int)  # probe_id, percent
    task_finished = pyqtSignal(str, bool, str)  # probe_id, success, message
    log_message = pyqtSignal(str) # General log messages

    def __init__(self, probe_id, target_device, firmware_path, flash_tool="pyocd", tool_path="", packs=None):
        super().__init__()
        self.probe_id = probe_id
        self.target_device = target_device
        self.firmware_path = firmware_path
        self.flash_tool = flash_tool
        self.tool_path = tool_path
        self.packs = packs

    def run(self):
        try:
            self.log_message.emit(f"Starting flash for Probe {self.probe_id} on {self.target_device}...")
            
            def update_progress(percent):
                self.progress.emit(self.probe_id, percent)

            if self.flash_tool == "stm32cubeprogrammer":
                STM32CubeProgrammerWrapper.flash_firmware(
                    self.probe_id,
                    self.target_device,
                    self.firmware_path,
                    cli_path=self.tool_path,
                    progress_callback=update_progress,
                )
            else:
                PyOCDWrapper.flash_firmware(
                    self.probe_id,
                    self.target_device,
                    self.firmware_path,
                    progress_callback=update_progress,
                    packs=self.packs,
                )
            
            self.task_finished.emit(self.probe_id, True, "Flashing complete.")
            self.log_message.emit(f"Flash successful for Probe {self.probe_id}")
            
        except Exception as e:
            error_msg = f"Error: {str(e)}"
            self.log_message.emit(error_msg)
            # self.log_message.emit(traceback.format_exc())
            self.task_finished.emit(self.probe_id, False, error_msg)

class ProbeDiscoveryWorker(QThread):
    probes_found = pyqtSignal(list)

    def run(self):
        probes = PyOCDWrapper.list_probes()
        self.probes_found.emit(probes)

class TargetListWorker(QThread):
    targets_found = pyqtSignal(list)

    def run(self):
        targets = PyOCDWrapper.get_targets()
        self.targets_found.emit(targets)

class TargetListWorker(QThread):
    targets_found = pyqtSignal(list)

    def run(self):
        targets = PyOCDWrapper.get_targets()
        self.targets_found.emit(targets)

class PackInstallWorker(QThread):
    finished = pyqtSignal(bool, str) # success, message

    def __init__(self, family_name):
        super().__init__()
        self.family_name = family_name

    def run(self):
        success = PyOCDWrapper.install_pack(self.family_name)
        msg = f"Pack installation for '{self.family_name}' {'succeeded' if success else 'failed'}."
        self.finished.emit(success, msg)

class TargetDetectionWorker(QThread):
    target_detected = pyqtSignal(str, str) # probe_id, detected_target_name

    def __init__(self, probe_id):
        super().__init__()
        self.probe_id = probe_id

    def run(self):
        # Only use PyOCD detection as requested
        detected = PyOCDWrapper.detect_target(self.probe_id)
        
        if detected:
            self.target_detected.emit(self.probe_id, detected)
        else:
            self.target_detected.emit(self.probe_id, "")

class ResetWorker(QThread):
    reset_finished = pyqtSignal(str, bool, str)  # probe_id, success, message
    log_message = pyqtSignal(str)

    def __init__(self, probe_id, target_device, flash_tool="pyocd", tool_path="", packs=None):
        super().__init__()
        self.probe_id = probe_id
        self.target_device = target_device
        self.flash_tool = flash_tool
        self.tool_path = tool_path
        self.packs = packs

    def run(self):
        try:
            self.log_message.emit(f"Resetting target on Probe {self.probe_id}...")
            
            if self.flash_tool == "stm32cubeprogrammer":
                STM32CubeProgrammerWrapper.reset_target(
                    self.probe_id,
                    self.target_device,
                    cli_path=self.tool_path,
                )
            else:
                PyOCDWrapper.reset_target(self.probe_id, self.target_device, packs=self.packs)
            
            self.reset_finished.emit(self.probe_id, True, "Reset complete.")
            self.log_message.emit(f"Reset successful for Probe {self.probe_id}")
            
        except Exception as e:
            error_msg = f"Reset error: {str(e)}"
            self.log_message.emit(error_msg)
            self.reset_finished.emit(self.probe_id, False, error_msg)
