from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, 
    QLabel, QLineEdit, QPushButton, QListWidget, 
    QMessageBox, QInputDialog
)

class ProjectManagerDialog(QDialog):
    def __init__(self, config_manager, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Project Manager")
        self.resize(500, 400)
        self.config_manager = config_manager
        self.init_ui()
        self.load_projects()

    def init_ui(self):
        layout = QVBoxLayout(self)

        # Search Bar
        search_layout = QHBoxLayout()
        search_layout.addWidget(QLabel("Search:"))
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Filter projects...")
        self.search_input.textChanged.connect(self.filter_projects)
        search_layout.addWidget(self.search_input)
        layout.addLayout(search_layout)

        # Project List
        self.project_list = QListWidget()
        layout.addWidget(self.project_list)

        # Buttons
        btn_layout = QHBoxLayout()
        
        new_btn = QPushButton("New Project")
        new_btn.clicked.connect(self.create_new_project)
        btn_layout.addWidget(new_btn)
        
        load_btn = QPushButton("Load Project")
        load_btn.clicked.connect(self.load_selected_project)
        btn_layout.addWidget(load_btn)
        
        delete_btn = QPushButton("Delete Project")
        delete_btn.setStyleSheet("color: red;")
        delete_btn.clicked.connect(self.delete_selected_project)
        btn_layout.addWidget(delete_btn)
        
        close_btn = QPushButton("Close")
        close_btn.clicked.connect(self.reject)
        btn_layout.addWidget(close_btn)

        layout.addLayout(btn_layout)

    def load_projects(self):
        self.project_list.clear()
        projects = self.config_manager.get_projects()
        current_idx = self.config_manager.config.get("current_project_index", 0)
        
        for i, proj in enumerate(projects):
            name = proj.get("name", f"Project {i}")
            if i == current_idx:
                name += " (Active)"
            self.project_list.addItem(name)
            
            # valid check for search
            item = self.project_list.item(i)
            item.setData(100, i) # Store real index

    def filter_projects(self, text):
        count = self.project_list.count()
        for i in range(count):
            item = self.project_list.item(i)
            item.setHidden(text.lower() not in item.text().lower())

    def create_new_project(self):
        name, ok = QInputDialog.getText(self, "New Project", "Enter project name:")
        if ok and name:
            target, ok2 = QInputDialog.getText(
                self, 
                "Target Device", 
                "Enter target device (e.g., stm32g071rb):"
            )
            if ok2:
                self.config_manager.create_project(name, target or "")
                self.load_projects()  # Refresh list
                QMessageBox.information(self, "Success", f"Created new project: {name}")

    def load_selected_project(self):
        item = self.project_list.currentItem()
        if not item:
            return
        
        index = item.data(100)
        self.config_manager.select_project(index)
        QMessageBox.information(self, "Success", f"Loaded project: {item.text()}")
        self.accept() # Close dialog and return accepted

    def delete_selected_project(self):
        item = self.project_list.currentItem()
        if not item:
            return
            
        name = item.text()
        index = item.data(100)
        
        reply = QMessageBox.question(
            self, "Confirm Delete", 
            f"Are you sure you want to delete '{name}'?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        
        if reply == QMessageBox.StandardButton.Yes:
            self.config_manager.delete_project(index)
            self.load_projects() # Refresh list
