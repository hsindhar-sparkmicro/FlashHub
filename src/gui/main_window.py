import os
from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, 
    QLabel, QLineEdit, QPushButton, QComboBox, 
    QTextEdit, QTableWidget, QTableWidgetItem, 
    QHeaderView, QFileDialog, QMessageBox, QProgressBar,
    QInputDialog
)
from PyQt6.QtCore import Qt, QTimer
from src.utils.config_manager import ConfigManager
from src.gui.workers import FlashWorker, ProbeDiscoveryWorker, TargetDetectionWorker, ResetWorker
from src.gui.pack_dialog import PackInstallerDialog
from src.gui.project_dialog import ProjectManagerDialog
from src.gui.target_selector_dialog import TargetSelectorDialog
from src.gui.flow_layout import FlowLayout

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.base_window_title = "FlashHub - STM32 Firmware Flasher"
        self.setWindowTitle(self.base_window_title)
        self.resize(1000, 700)
        
        self.config_manager = ConfigManager()
        self.config = self.config_manager.get_current_project()
        self.workers = {} # Keep track of running threads
        self.discovery_worker = None
        self.detect_worker = None
        self.save_btn = None
        self.is_dirty = False
        self._suspend_dirty_tracking = False

        self.init_ui()
        # self.check_openocd() # OpenOCD removed by user request
        self.load_settings()
        
        # Auto-refresh probes on startup
        self.refresh_probes()

    def closeEvent(self, event):
        # Cleanup all threads on exit
        if self.discovery_worker and self.discovery_worker.isRunning():
            self.discovery_worker.terminate()
            self.discovery_worker.wait()
            
        if self.detect_worker and self.detect_worker.isRunning():
            self.detect_worker.terminate()
            self.detect_worker.wait()
            
        for worker in self.workers.values():
            if worker.isRunning():
                worker.terminate() # or a safer stop signal
                worker.wait()
        
        event.accept()
        
    # def check_openocd(self):
    #     if OpenOCDWrapper.is_installed():
    #         self.log("OpenOCD detected. Auto-detection enabled.")
    #     else:
    #         self.log("Warning: OpenOCD is not installed or not in PATH. Auto-detection will fallback to limited pyOCD method.")

    def init_ui(self):
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)

        # --- Top Bar: Project Management ---
        project_layout = QHBoxLayout()
        self.project_label = QLabel(f"Project: {self.config.get('name', 'Unknown')}")
        self.project_label.setStyleSheet("font-weight: bold; font-size: 14px;")
        
        new_project_btn = QPushButton("New Project")
        new_project_btn.clicked.connect(self.create_new_project)
        
        manage_btn = QPushButton("Manage Projects")
        manage_btn.clicked.connect(self.open_project_manager)
        
        project_layout.addWidget(self.project_label)
        project_layout.addStretch()
        project_layout.addWidget(new_project_btn)
        project_layout.addWidget(manage_btn)
        main_layout.addLayout(project_layout)

        # --- Project / Settings Section ---
        settings_layout = QHBoxLayout()
        
        # Target Device
        self.target_input = QLineEdit()
        self.target_input.setPlaceholderText("e.g. stm32g071rb")
        self.target_input.setToolTip("Enter the target MCU type (pyOCD target name)")
        self.target_input.textChanged.connect(self.on_config_changed)
        
        target_layout = QVBoxLayout()
        target_input_layout = QHBoxLayout()
        target_input_layout.addWidget(self.target_input)
        
        self.select_target_btn = QPushButton("Select Target")
        self.select_target_btn.setToolTip("Open list of supported targets")
        self.select_target_btn.clicked.connect(self.open_target_selector)
        target_input_layout.addWidget(self.select_target_btn)
        
        target_layout.addWidget(QLabel("Target Device:"))
        target_layout.addLayout(target_input_layout)
        
        # Firmware File - Removed global inputs
        # firmware_layout = QVBoxLayout()
        # firmware_input_layout = QHBoxLayout()
        
        # self.firmware_path_input = QLineEdit()
        # self.firmware_path_input.setPlaceholderText("Path to .hex, .bin, or .elf")
        # self.firmware_browse_btn = QPushButton("Browse")
        # self.firmware_browse_btn.clicked.connect(self.browse_firmware)
        
        # firmware_input_layout.addWidget(self.firmware_path_input)
        # firmware_input_layout.addWidget(self.firmware_browse_btn)
        
        # firmware_layout.addWidget(QLabel("Firmware:"))
        # firmware_layout.addLayout(firmware_input_layout)

        settings_layout.addLayout(target_layout)
        # settings_layout.addLayout(firmware_layout) # Global firmware removed

        main_layout.addLayout(settings_layout)
        
        # Pack Installer Button
        self.pack_btn = QPushButton("Install Target Packs")
        self.pack_btn.clicked.connect(self.open_pack_installer)
        main_layout.addWidget(self.pack_btn)

        # --- Probes Section ---
        probes_header = QHBoxLayout()
        probes_header.addWidget(QLabel("Configuration"))
        
        self.refresh_btn = QPushButton("Refresh Probes")
        self.refresh_btn.clicked.connect(self.refresh_probes)
        probes_header.addWidget(self.refresh_btn)
        
        self.reset_all_btn = QPushButton("Reset All Connected")
        self.reset_all_btn.setStyleSheet("background-color: #FF9800; color: white;")
        self.reset_all_btn.clicked.connect(self.reset_all_probes)
        probes_header.addWidget(self.reset_all_btn)
        
        self.flash_all_btn = QPushButton("Flash All Connected")
        self.flash_all_btn.setStyleSheet("background-color: #607D8B; color: white;")
        self.flash_all_btn.clicked.connect(self.start_batch_flash)
        probes_header.addWidget(self.flash_all_btn)
        
        main_layout.addLayout(probes_header)

        # Probes Table
        self.probes_table = QTableWidget()
        self.probes_table.setColumnCount(6) # ID, Alias, Firmware, Browse, Reset, Status
        self.probes_table.setHorizontalHeaderLabels(["Probe ID", "Alias Name", "Firmware Path", "Select", "Reset", "Status"])
        # self.probes_table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
        self.probes_table.setColumnWidth(0, 150) # ID
        self.probes_table.setColumnWidth(1, 150) # Alias
        self.probes_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch) # Path stretches
        self.probes_table.setColumnWidth(4, 80) # Reset button
        self.probes_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        main_layout.addWidget(self.probes_table)

        # --- Flash Dashboard (Large Buttons) ---
        main_layout.addWidget(QLabel("Flash Dashboard"))
        
        # Scroll Area for buttons if many
        from PyQt6.QtWidgets import QScrollArea
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_content = QWidget()
        self.dashboard_layout = FlowLayout(scroll_content)
        scroll_area.setWidget(scroll_content)
        scroll_area.setMinimumHeight(200)
        
        main_layout.addWidget(scroll_area)

        # --- Log Section ---
        logs_header_layout = QHBoxLayout()
        logs_header_layout.addWidget(QLabel("Logs"))
        
        from PyQt6.QtWidgets import QCheckBox
        self.timestamp_check = QCheckBox("Show Timestamp")
        # self.timestamp_check.setChecked(True) # Optional default
        logs_header_layout.addWidget(self.timestamp_check)
        
        logs_header_layout.addStretch()
        
        clear_logs_btn = QPushButton("Clear")
        clear_logs_btn.setFixedWidth(80)
        clear_logs_btn.clicked.connect(self.clear_logs)
        logs_header_layout.addWidget(clear_logs_btn)
        
        main_layout.addLayout(logs_header_layout)

        self.log_area = QTextEdit()
        self.log_area.setReadOnly(True)
        self.log_area.setStyleSheet("font-family: monospace;")
        main_layout.addWidget(self.log_area)

        # --- Save Config Button ---
        self.save_btn = QPushButton("Save Project Configuration")
        self.save_btn.clicked.connect(self.save_settings)
        main_layout.addWidget(self.save_btn)

    def update_project_visual_state(self):
        project_name = self.config.get('name', 'Unknown') if self.config else 'Unknown'
        unsaved_suffix = " *Unsaved" if self.is_dirty else ""
        self.project_label.setText(f"Project: {project_name}{unsaved_suffix}")

        if self.save_btn:
            save_text = "Save Project Configuration *" if self.is_dirty else "Save Project Configuration"
            self.save_btn.setText(save_text)
            self.save_btn.setStyleSheet("font-weight: bold;" if self.is_dirty else "")

        title_suffix = " *" if self.is_dirty else ""
        self.setWindowTitle(f"{self.base_window_title}{title_suffix}")

    def set_dirty(self, is_dirty):
        if self._suspend_dirty_tracking:
            return

        if self.is_dirty != is_dirty:
            self.is_dirty = is_dirty
            self.update_project_visual_state()

    def on_config_changed(self):
        self.set_dirty(True)

    def log(self, message):
        from datetime import datetime
        if getattr(self, 'timestamp_check', None) and self.timestamp_check.isChecked():
            timestamp = datetime.now().strftime("[%H:%M:%S] ")
            self.log_area.append(f"{timestamp}{message}")
        else:
            self.log_area.append(message)

    def clear_logs(self):
        self.log_area.clear()


    def load_settings(self):
        self._suspend_dirty_tracking = True
        self.config = self.config_manager.get_current_project() # Refresh config object
        self.target_input.setText(self.config.get("target_device", "stm32g071rb"))
        # self.firmware_path_input.setText(self.config.get("firmware_path", "")) # Deprecated
        self.apply_project_config_to_table()
        self._suspend_dirty_tracking = False
        self.is_dirty = False
        self.update_project_visual_state()

    def collect_probe_table_config(self):
        probe_config = {}
        for row in range(self.probes_table.rowCount()):
            pid_item = self.probes_table.item(row, 0)
            if not pid_item:
                continue

            pid = pid_item.text()
            alias_widget = self.probes_table.cellWidget(row, 1)
            fw_widget = self.probes_table.cellWidget(row, 2)

            probe_config[pid] = {
                "alias": alias_widget.text() if alias_widget else "",
                "firmware": fw_widget.text() if fw_widget else ""
            }

        return probe_config

    def persist_probe_table_config(self):
        probe_config = self.collect_probe_table_config()
        if probe_config:
            self.config_manager.update_current_project_probes_config(probe_config)

    def apply_project_config_to_table(self):
        was_suspended = self._suspend_dirty_tracking
        self._suspend_dirty_tracking = True
        for row in range(self.probes_table.rowCount()):
            pid_item = self.probes_table.item(row, 0)
            if not pid_item:
                continue

            pid = pid_item.text()
            p_conf = self.config_manager.get_probe_config(pid)

            alias_widget = self.probes_table.cellWidget(row, 1)
            fw_widget = self.probes_table.cellWidget(row, 2)

            if alias_widget:
                alias_widget.setText(p_conf.get("alias", alias_widget.text()))
            if fw_widget:
                fw_widget.setText(p_conf.get("firmware", ""))

        self._suspend_dirty_tracking = was_suspended
        self.rebuild_dashboard()

    def save_settings(self):
        # Check if project name is generic default
        current_name = self.config.get("name", "Default Project")
        if current_name == "Default Project":
            name, ok = QInputDialog.getText(self, "Project Name", "Enter a name for this new project:")
            if ok and name:
                # Update name
                self.config_manager.update_current_project("name", name)
                self.project_label.setText(f"Project: {name}")
            elif not ok:
                # User cancelled save/rename
                return
        
        # Save probe table state to current project
        self.persist_probe_table_config()

        self.config_manager.update_current_project("target_device", self.target_input.text())
        # self.config_manager.update_current_project("firmware_path", self.firmware_path_input.text())
        self.log("Settings saved.")
        self.config = self.config_manager.get_current_project()
        self.set_dirty(False)
        self.rebuild_dashboard() # Update buttons

    def on_probes_found(self, probes):
        self.probes_table.setRowCount(0)
        self.config = self.config_manager.get_current_project() # Refresh mainly for probe configs check
        
        if not probes:
            self.log("No probes found.")
            self.rebuild_dashboard()
            return

        self.log(f"Found {len(probes)} probes.")
        self.probes_table.setRowCount(len(probes))
        
        for i, probe in enumerate(probes):
            pid = probe['unique_id']
            # Load config for this probe
            p_conf = self.config_manager.get_probe_config(pid)
            alias_val = p_conf.get("alias", f"Probe {i+1}")
            fw_val = p_conf.get("firmware", "")

            # 0: ID
            self.probes_table.setItem(i, 0, QTableWidgetItem(pid))
            
            # 1: Alias (Editable QLineEdit)
            alias_edit = QLineEdit(alias_val)
            alias_edit.setPlaceholderText("Alias Name")
            alias_edit.textChanged.connect(self.on_config_changed)
            self.probes_table.setCellWidget(i, 1, alias_edit)
            
            # 2: Firmware (QLineEdit)
            fw_edit = QLineEdit(fw_val)
            fw_edit.setPlaceholderText("Firmware Path")
            fw_edit.textChanged.connect(self.on_config_changed)
            self.probes_table.setCellWidget(i, 2, fw_edit)
            
            # 3: Browse Button
            browse_btn = QPushButton("...")
            browse_btn.setFixedWidth(40)
            browse_btn.clicked.connect(lambda checked, r=i: self.browse_firmware_for_row(r))
            self.probes_table.setCellWidget(i, 3, browse_btn)
            
            # 4: Reset Button
            reset_btn = QPushButton("Reset")
            reset_btn.setFixedWidth(70)
            reset_btn.clicked.connect(lambda checked, p=pid: self.reset_probe(p))
            self.probes_table.setCellWidget(i, 4, reset_btn)
            
            # 5: Progress/Status Widget (Container for label + progress bar)
            container = QWidget()
            layout = QHBoxLayout(container)
            layout.setContentsMargins(5, 0, 5, 0)
            
            pbar = QProgressBar()
            pbar.setValue(0)
            pbar.setVisible(False)
            pbar.setObjectName(f"pbar_{pid}")
            
            lbl = QLabel("Ready")
            lbl.setObjectName(f"status_{pid}")
            
            layout.addWidget(lbl)
            layout.addWidget(pbar)
            
            self.probes_table.setCellWidget(i, 5, container)
            
        self.rebuild_dashboard()

    def browse_firmware_for_row(self, row):
        file_path, _ = QFileDialog.getOpenFileName(
             self, "Select Firmware", "", "Firmware Files (*.hex *.bin *.elf);;All Files (*)"
        )
        if file_path:
            fw_widget = self.probes_table.cellWidget(row, 2)
            if fw_widget:
                fw_widget.setText(file_path)
                self.on_config_changed()

    def rebuild_dashboard(self):
        # Clear existing buttons
        while self.dashboard_layout.count():
            item = self.dashboard_layout.takeAt(0)
            widget = item.widget()
            if widget:
                widget.deleteLater()
        
        colors = ['#2196F3', '#4CAF50', '#F44336', '#FF9800', 
                  '#9C27B0', '#00BCD4', '#FFC107', '#3F51B5', '#009688', '#673AB7']

        # Create new buttons based on table
        for row in range(self.probes_table.rowCount()):
            pid_item = self.probes_table.item(row, 0)
            if not pid_item: continue
            pid = pid_item.text()
            
            alias_widget = self.probes_table.cellWidget(row, 1)
            alias = alias_widget.text() if alias_widget else pid
            
            btn_color = colors[row % len(colors)]
            hover_color = "#333333" # Simple dark hover or calculate lighter version, but fixed is easier

            btn = QPushButton(f"Flash\n{alias}")
            btn.setFixedSize(150, 150) # Square button
            btn.setStyleSheet(f"""
                QPushButton {{
                    font-size: 16px; 
                    font-weight: bold; 
                    background-color: {btn_color}; 
                    color: white;
                    border-radius: 12px;
                    padding: 10px;
                }}
                QPushButton:hover {{ background-color: {hover_color}; }}
                QPushButton:disabled {{ background-color: #B0BEC5; }}
            """)
            btn.clicked.connect(lambda checked, p=pid: self.flash_single_probe(p))
            self.dashboard_layout.addWidget(btn)

    def flash_single_probe(self, probe_id):
        # Find row for data
        target = self.target_input.text()
        fw_path = ""
        alias = ""
        
        for row in range(self.probes_table.rowCount()):
            pid_item = self.probes_table.item(row, 0)
            if pid_item and pid_item.text() == probe_id:
                 fw_path = self.probes_table.cellWidget(row, 2).text()
                 alias = self.probes_table.cellWidget(row, 1).text()
                 break
        
        if not fw_path or not os.path.exists(fw_path):
             QMessageBox.warning(self, "Error", f"Invalid firmware path for {alias or probe_id}")
             return
             
        self.start_flash_worker(probe_id, target, fw_path)

    def start_batch_flash(self):
        target = self.target_input.text()
        self.flash_all_btn.setEnabled(False)
        
        probes_to_flash = []
        for row in range(self.probes_table.rowCount()):
             pid_item = self.probes_table.item(row, 0)
             if pid_item:
                 pid = pid_item.text()
                 fw = self.probes_table.cellWidget(row, 2).text()
                 if fw and os.path.exists(fw):
                     probes_to_flash.append((pid, fw))
        
        if not probes_to_flash:
            QMessageBox.information(self, "Info", "No probes with valid firmware configuration found.")
            self.flash_all_btn.setEnabled(True)
            return

        self.active_workers_count = len(probes_to_flash)
        for pid, fw in probes_to_flash:
            self.start_flash_worker(pid, target, fw)

    def start_flash_worker(self, probe_id, target, firmware):
        # Update UI for specific probe
        self.update_probe_status(probe_id, "Flashing...", 0, show_bar=True)
        
        worker = FlashWorker(probe_id, target, firmware)
        worker.progress.connect(self.update_flash_progress)
        worker.task_finished.connect(self.on_flash_finished)
        
        # Proper cleanup: remove from dict ONLY when thread really finishes
        # Check lambda to safely capture probe_id
        worker.finished.connect(lambda: self.cleanup_worker(probe_id))
        
        worker.log_message.connect(self.log)
        
        self.workers[probe_id] = worker
        worker.start()

    def cleanup_worker(self, probe_id):
        if probe_id in self.workers:
            del self.workers[probe_id]

    def update_probe_status(self, probe_id, text, percent=0, show_bar=False):
        for row in range(self.probes_table.rowCount()):
            pid_item = self.probes_table.item(row, 0)
            if pid_item and pid_item.text() == probe_id:
                container = self.probes_table.cellWidget(row, 5)
                pbar = container.findChild(QProgressBar, f"pbar_{probe_id}")
                status = container.findChild(QLabel, f"status_{probe_id}")
                
                if status: status.setText(text)
                if pbar: 
                    pbar.setVisible(show_bar)
                    pbar.setValue(percent)
                break
    
    def update_flash_progress(self, probe_id, percent):
        self.update_probe_status(probe_id, "Flashing...", percent, show_bar=True)

    def on_flash_finished(self, probe_id, success, message):
        status_text = "Success" if success else "Failed"
        # If failed, show error in tooltip or log? It's already logged.
        
        self.update_probe_status(probe_id, status_text, 100, show_bar=False)
        
        # NOTE: Do NOT delete worker here. It is deleted in cleanup_worker connected to QThread.finished
            
        if hasattr(self, 'active_workers_count') and self.active_workers_count > 0:
            self.active_workers_count -= 1
        
        # If all done
        if not hasattr(self, 'active_workers_count') or self.active_workers_count == 0:
            self.flash_all_btn.setEnabled(True)
            self.log("Batch flashing process completed.")

    def reset_probe(self, probe_id):
        """Reset a single probe without flashing"""
        target = self.target_input.text()
        
        if not target:
            QMessageBox.warning(self, "Error", "Please specify a target device first.")
            return
        
        # Update status
        self.update_probe_status(probe_id, "Resetting...", 0, show_bar=False)
        
        # Create and start reset worker
        worker = ResetWorker(probe_id, target)
        worker.reset_finished.connect(self.on_reset_finished)
        worker.log_message.connect(self.log)
        worker.finished.connect(lambda: self.cleanup_worker(f"reset_{probe_id}"))
        
        self.workers[f"reset_{probe_id}"] = worker
        worker.start()
    
    def on_reset_finished(self, probe_id, success, message):
        """Handle reset completion"""
        status_text = "Reset OK" if success else "Reset Failed"
        self.update_probe_status(probe_id, status_text, 0, show_bar=False)
        
        # Handle batch reset completion
        if hasattr(self, 'active_reset_count') and self.active_reset_count > 0:
            self.active_reset_count -= 1
            if self.active_reset_count == 0:
                self.reset_all_btn.setEnabled(True)
                self.log("Batch reset process completed.")
    
    def reset_all_probes(self):
        """Reset all connected probes"""
        target = self.target_input.text()
        
        if not target:
            QMessageBox.warning(self, "Error", "Please specify a target device first.")
            return
        
        self.reset_all_btn.setEnabled(False)
        
        # Get all connected probes
        probes_to_reset = []
        for row in range(self.probes_table.rowCount()):
            pid_item = self.probes_table.item(row, 0)
            if pid_item:
                probes_to_reset.append(pid_item.text())
        
        if not probes_to_reset:
            QMessageBox.information(self, "Info", "No probes found.")
            self.reset_all_btn.setEnabled(True)
            return
        
        self.active_reset_count = len(probes_to_reset)
        self.log(f"Resetting {len(probes_to_reset)} probes...")
        
        for pid in probes_to_reset:
            self.reset_probe(pid)

    def open_target_selector(self):
        dialog = TargetSelectorDialog(self)
        if dialog.exec():
            selected = dialog.selected_target
            if selected:
                self.target_input.setText(selected)
                self.on_config_changed()

    def refresh_probes(self):
        self.refresh_btn.setEnabled(False)
        self.log("Scanning for probes...")
        
        self.discovery_worker = ProbeDiscoveryWorker()
        self.discovery_worker.probes_found.connect(self.on_probes_found)
        self.discovery_worker.finished.connect(lambda: self.refresh_btn.setEnabled(True))
        self.discovery_worker.start()

    def create_new_project(self):
        name, ok = QInputDialog.getText(self, "New Project", "Enter project name:")
        if ok and name:
            # Persist current project table edits before switching projects
            self.persist_probe_table_config()
            target, ok2 = QInputDialog.getText(
                self, 
                "Target Device", 
                "Enter target device (e.g., stm32g071rb):",
                text=self.target_input.text()
            )
            if ok2:
                self.config_manager.create_project(name, target or "")
                self.load_settings()
                self.log(f"Created and switched to new project: {name}")
                # Clear probes table for new project
                self.probes_table.setRowCount(0)
                self.rebuild_dashboard()

    def open_project_manager(self):
        # Persist current project table edits before project switch
        self.persist_probe_table_config()
        dialog = ProjectManagerDialog(self.config_manager, self)
        if dialog.exec():
            self.load_settings()
            self.log(f"Switched to project: {self.config.get('name')}")

    def open_pack_installer(self):
        msg = ("Note: Flashing requires appropriate target support packs.\n"
               "If detection or flashing fails, verify the pack for your specific MCU series is installed here.")
        QMessageBox.information(self, "Pack Info", msg)
        
        dialog = PackInstallerDialog(self)
        dialog.exec()

