from PyQt6.QtWidgets import (
    QDialog,
    QFrame,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
)


class ToolSettingsDialog(QDialog):
    ACCENT_BUTTON_STYLE = (
        "QPushButton {"
        " background-color: #2f80ed;"
        " color: white;"
        " border: 1px solid #2f80ed;"
        " border-radius: 4px;"
        " padding: 4px 12px;"
        "}"
        "QPushButton:hover { background-color: #1f6fd1; border-color: #1f6fd1; }"
        "QPushButton:pressed { background-color: #175cb0; border-color: #175cb0; }"
    )

    def __init__(self, cli_path="", parent=None):
        super().__init__(parent)
        self.setWindowTitle("STM32CubeProgrammer CLI Settings")
        self.resize(600, 120)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 10, 14, 14)
        layout.setSpacing(12)

        accent_line = QFrame()
        accent_line.setFixedHeight(3)
        accent_line.setFrameShape(QFrame.Shape.NoFrame)
        accent_line.setStyleSheet("background-color: #2f80ed;")
        layout.addWidget(accent_line)

        content_layout = QVBoxLayout()
        content_layout.setContentsMargins(14, 0, 0, 0)
        content_layout.setSpacing(12)

        content_layout.addWidget(QLabel("STM32CubeProgrammer CLI Path:"))

        path_layout = QHBoxLayout()
        self.path_input = QLineEdit(cli_path)
        self.path_input.setPlaceholderText("Select STM32_Programmer_CLI executable")
        path_layout.addWidget(self.path_input)

        browse_btn = QPushButton("Browse")
        browse_btn.setStyleSheet(self.ACCENT_BUTTON_STYLE)
        browse_btn.clicked.connect(self.browse_cli_path)
        path_layout.addWidget(browse_btn)
        content_layout.addLayout(path_layout)

        buttons_layout = QHBoxLayout()
        buttons_layout.addStretch()

        ok_btn = QPushButton("OK")
        ok_btn.setStyleSheet(self.ACCENT_BUTTON_STYLE)
        ok_btn.clicked.connect(self.accept)
        buttons_layout.addWidget(ok_btn)

        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)
        buttons_layout.addWidget(cancel_btn)
        content_layout.addLayout(buttons_layout)

        layout.addLayout(content_layout)

    def browse_cli_path(self):
        file_path, _ = QFileDialog.getOpenFileName(self, "Select STM32CubeProgrammer CLI")
        if file_path:
            self.path_input.setText(file_path)

    def get_cli_path(self):
        return self.path_input.text().strip()