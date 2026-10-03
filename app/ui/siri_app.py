import sys
import os
import pathlib
from PySide6 import QtCore, QtGui, QtWidgets
from PySide6.QtWebEngineWidgets import QWebEngineView
from PySide6.QtWebChannel import QWebChannel
from PySide6.QtCore import Slot, Signal, QObject

from app.assistant.brain import JarvisBrain

class PyBackend(QObject):
    """
    Bridge object exposed to JavaScript via Qt WebChannel
    """
    responseReady = Signal(str)
    stateChanged = Signal(str)

    def __init__(self, main_window):
        super().__init__()
        self.main_window = main_window
        self.brain = JarvisBrain()

    @Slot(str)
    def processPrompt(self, prompt_text):
        """Called from JS when user submits a query"""
        # Execute query in brain
        response = self.brain.process_query(prompt_text)
        # Emit signal back to JS UI
        self.responseReady.emit(response)

    @Slot()
    def startListening(self):
        """Trigger voice recording if needed"""
        self.stateChanged.emit("listening")

    @Slot()
    def stopListening(self):
        self.stateChanged.emit("idle")

    @Slot()
    def closeApp(self):
        QtWidgets.QApplication.quit()

    @Slot()
    def minimizeApp(self):
        self.main_window.showMinimized()

    @Slot()
    def maximizeApp(self):
        if self.main_window.isMaximized():
            self.main_window.showNormal()
        else:
            self.main_window.showMaximized()


class SiriMainWindow(QtWidgets.QMainWindow):
    """
    PySide6 Frameless Glassmorphic Siri Window
    """
    def __init__(self):
        super().__init__()
        self.setWindowFlags(QtCore.Qt.FramelessWindowHint | QtCore.Qt.Window)
        self.setAttribute(QtCore.Qt.WA_TranslucentBackground, True)
        self.resize(950, 730)
        self.setMinimumSize(700, 500)
        self.setWindowTitle("JARVIS - Apple Siri Interface")

        # Center on screen
        screen = QtWidgets.QApplication.primaryScreen().geometry()
        x = (screen.width() - self.width()) // 2
        y = (screen.height() - self.height()) // 2
        self.move(x, y)

        # Setup WebEngine View
        self.web_view = QWebEngineView(self)
        self.web_view.page().setBackgroundColor(QtCore.Qt.transparent)

        # Setup QWebChannel Bridge
        self.channel = QWebChannel()
        self.py_backend = PyBackend(self)
        self.channel.registerObject("pyBackend", self.py_backend)
        self.web_view.page().setWebChannel(self.channel)

        # Load local index.html
        web_dir = pathlib.Path(__file__).parent / "web" / "index.html"
        self.web_view.setUrl(QtCore.QUrl.fromLocalFile(str(web_dir.resolve())))

        self.setCentralWidget(self.web_view)

        # Window Drag Support
        self._drag_pos = None

    def mousePressEvent(self, event: QtGui.QMouseEvent):
        if event.button() == QtCore.Qt.LeftButton:
            self._drag_pos = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
            event.accept()

    def mouseMoveEvent(self, event: QtGui.QMouseEvent):
        if event.buttons() & QtCore.Qt.LeftButton and self._drag_pos:
            self.move(event.globalPosition().toPoint() - self._drag_pos)
            event.accept()

    def mouseReleaseEvent(self, event: QtGui.QMouseEvent):
        self._drag_pos = None


def run_siri_app():
    app = QtWidgets.QApplication(sys.argv)
    
    # Enable WebEngine Remote Debugging if needed
    os.environ["QTWEBENGINE_REMOTE_DEBUGGING"] = "9222"
    
    window = SiriMainWindow()
    window.show()
    return app.exec()
