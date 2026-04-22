import sys
from pathlib import Path

# ---------------------------------------------------------------------------
# CLI fast-path: if --cli is the first argument, hand off immediately without
# importing Qt at all (no display required).
# ---------------------------------------------------------------------------
if len(sys.argv) > 1 and sys.argv[1] == "--cli":
    # Strip the "--cli" flag so cli.py's own parser sees only its args.
    sys.argv.pop(1)
    from cli import main as cli_main
    cli_main()
    sys.exit(0)

from PyQt6.QtWidgets import QApplication
from PyQt6.QtNetwork import QLocalSocket, QLocalServer
from PyQt6.QtCore import QIODevice
from PyQt6.QtGui import QIcon
from src.gui.main_window import MainWindow

INSTANCE_ID = "FlashHubSingleInstanceIdentifier"

def resource_path(*parts: str) -> Path:
    base_path = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent))
    return base_path.joinpath(*parts)


def create_app_icon() -> QIcon:
    icon_path = resource_path("images", "flashhub_icon.svg")
    if icon_path.exists():
        icon = QIcon(str(icon_path))
        if not icon.isNull():
            return icon
    return QIcon()


def main() -> None:
    app = QApplication(sys.argv)
    app.setDesktopFileName("FlashHub")
    icon = create_app_icon()
    if not icon.isNull():
        app.setWindowIcon(icon)
    
    # Check for existing instance
    socket = QLocalSocket()
    socket.connectToServer(INSTANCE_ID)
    if socket.waitForConnected(500):
        # Already running, send focus command
        # Write generic data, the server just needs to know someone connected
        socket.disconnectFromServer()
        sys.exit(0)
    
    # If we got here, we are the first instance
    # Create local server
    server = QLocalServer()
    # Handle cleanup of stale lock file if server crashed previously
    server.removeServer(INSTANCE_ID)
    server.listen(INSTANCE_ID)
    
    # Optional: Set a global style or theme here
    app.setStyle("Fusion")
    
    window = MainWindow()
    if not icon.isNull():
        window.setWindowIcon(icon)
    
    def handle_new_connection() -> None:
        # Someone tried to run a second instance
        new_socket = server.nextPendingConnection()
        new_socket.close()
        
        # Bring main window to front
        window.setWindowState(window.windowState() & ~2) # Un-minimize
        window.show()
        window.raise_()
        window.activateWindow()
        
    server.newConnection.connect(handle_new_connection)
    
    window.show()
    
    sys.exit(app.exec())

if __name__ == "__main__":
    main()
