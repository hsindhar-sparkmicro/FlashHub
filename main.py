import sys
from PyQt6.QtWidgets import QApplication
from PyQt6.QtNetwork import QLocalSocket, QLocalServer
from PyQt6.QtCore import QIODevice
from src.gui.main_window import MainWindow

INSTANCE_ID = "FlashHubSingleInstanceIdentifier"

def main():
    app = QApplication(sys.argv)
    
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
    
    def handle_new_connection():
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
