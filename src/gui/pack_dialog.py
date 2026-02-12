from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, 
    QLabel, QLineEdit, QPushButton, QTextEdit
)
from PyQt6.QtCore import QThread, pyqtSignal
from src.backend.pyocd_wrapper import PyOCDWrapper

class PackSearchWorker(QThread):
    result_ready = pyqtSignal(str)

    def __init__(self, query):
        super().__init__()
        self.query = query

    def run(self):
        result = PyOCDWrapper.find_packs(self.query)
        self.result_ready.emit(result)

class PackInstallWorker(QThread):
    finished = pyqtSignal(bool, str)
    
    def __init__(self, target):
        super().__init__()
        self.target = target

    def run(self):
        success = PyOCDWrapper.install_pack(self.target)
        self.finished.emit(success, f"Install {'succeeded' if success else 'failed'} for {self.target}")

class PackInstallerDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("PyOCD Pack Installer")
        self.resize(600, 400)
        self.search_worker = None
        self.install_worker = None
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)

        # Search
        search_layout = QHBoxLayout()
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("e.g. stm32g0")
        search_btn = QPushButton("Search Packs")
        search_btn.clicked.connect(self.search_packs)
        
        search_layout.addWidget(QLabel("Target Family:"))
        search_layout.addWidget(self.search_input)
        search_layout.addWidget(search_btn)
        layout.addLayout(search_layout)

        # Output Area
        self.output_area = QTextEdit()
        self.output_area.setReadOnly(True)
        self.output_area.setPlaceholderText("Search results will appear here...")
        layout.addWidget(self.output_area)

        # Install Section
        install_layout = QHBoxLayout()
        self.install_input = QLineEdit()
        self.install_input.setPlaceholderText("Exact device to install (e.g. stm32g0b1)")
        
        install_btn = QPushButton("Install Pack")
        install_btn.setStyleSheet("background-color: #007ACC; color: white;")
        install_btn.clicked.connect(self.install_pack)
        
        install_layout.addWidget(QLabel("Install Target:"))
        install_layout.addWidget(self.install_input)
        install_layout.addWidget(install_btn)
        layout.addLayout(install_layout)

    def closeEvent(self, event):
        # Prevent closing if threads are running
        if (self.search_worker and self.search_worker.isRunning()) or \
           (self.install_worker and self.install_worker.isRunning()):
            # Ideally we could wait or prompt, but for simplicity let's wait a bit or ignore?
            # A safer approach is to not allow the dialog to be destroyed immediately
            # or simply wait() on them (which might freeze UI).
            
            # Better UI: Check if running, if so, ignore close and warn user.
            from PyQt6.QtWidgets import QMessageBox
            QMessageBox.warning(self, "Tasks Running", "Please wait for current operations to finish before closing.")
            event.ignore()
        else:
            event.accept()

    def search_packs(self):
        query = self.search_input.text()
        if not query: return
        
        self.output_area.setText("Searching...")
        self.search_worker = PackSearchWorker(query)
        self.search_worker.result_ready.connect(self.on_search_result)
        self.search_worker.start()

    def on_search_result(self, text):
        self.output_area.setText(text)

    def install_pack(self):
        target = self.install_input.text()
        if not target: return
        
        self.output_area.append(f"\nInstalling pack for {target} (this may take a while)...")
        self.install_worker = PackInstallWorker(target)
        self.install_worker.finished.connect(self.on_install_finished)
        self.install_worker.start()

    def on_install_finished(self, success, msg):
        self.output_area.append(f"\n{msg}")
