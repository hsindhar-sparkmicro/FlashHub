from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, 
    QLabel, QLineEdit, QPushButton, QListWidget, 
    QMessageBox
)
from src.gui.workers import TargetListWorker

class TargetSelectorDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Select Target Device")
        self.resize(400, 500)
        self.selected_target = None
        self.all_targets = []
        self.init_ui()
        self.load_targets()

    def init_ui(self):
        layout = QVBoxLayout(self)

        # Search
        layout.addWidget(QLabel("Search Target:"))
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Filter (e.g. stm32g0)")
        self.search_input.textChanged.connect(self.filter_targets)
        layout.addWidget(self.search_input)

        # List
        self.target_list = QListWidget()
        self.target_list.itemDoubleClicked.connect(self.select_and_close)
        layout.addWidget(self.target_list)

        # Status Label (loading...)
        self.status_label = QLabel("Loading targets...")
        layout.addWidget(self.status_label)

        # Buttons
        btn_layout = QHBoxLayout()
        select_btn = QPushButton("Select")
        select_btn.clicked.connect(self.select_and_close)
        
        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)
        
        btn_layout.addWidget(select_btn)
        btn_layout.addWidget(cancel_btn)
        layout.addLayout(btn_layout)

    def load_targets(self):
        self.worker = TargetListWorker()
        self.worker.targets_found.connect(self.on_targets_loaded)
        self.worker.start()

    def on_targets_loaded(self, targets):
        self.all_targets = targets
        self.status_label.setText(f"Available Targets: {len(targets)}")
        self.filter_targets("")

    def filter_targets(self, text):
        self.target_list.clear()
        search_text = text.lower()
        for target in self.all_targets:
            if search_text in target.lower():
                self.target_list.addItem(target)

    def select_and_close(self):
        item = self.target_list.currentItem()
        if item:
            self.selected_target = item.text()
            self.accept()
        else:
            # If only one item is visible/filtered allow Enter on search box to select it?
            # For now, just require selection
            pass
