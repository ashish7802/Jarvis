"""Native animated HUD artwork & futuristic glassmorphism UI widgets."""
import math

from PySide6.QtCore import QPointF, QRectF, Qt, QTimer, Signal
from PySide6.QtGui import QColor, QIcon, QPainter, QPainterPath, QPen, QPixmap, QRadialGradient, QLinearGradient
from PySide6.QtWidgets import QWidget, QLabel, QSizePolicy, QFrame

ACCENT = "#00e5ff"
ACCENT_SECONDARY = "#7000ff"
ACCENT_SUCCESS = "#00ffaa"

STYLE = """
QMainWindow, QWidget {
    background: transparent;
    color: #e2f1f8;
    font-family: 'Segoe UI Variable', 'Segoe UI', 'Inter', sans-serif;
    font-size: 13px;
}
QLabel {
    background: transparent;
    border: none;
}
QLabel#brand {
    color: #ffffff;
    font-size: 26px;
    font-weight: 800;
    letter-spacing: 4px;
}
QLabel#muted {
    color: #728ca0;
    font-size: 12px;
}
QLabel#eyebrow {
    color: #00e5ff;
    font-size: 10px;
    font-weight: 800;
    letter-spacing: 2px;
}
QLabel#heroTitle {
    color: #ffffff;
    font-size: 22px;
    font-weight: 700;
    letter-spacing: .5px;
}
QLabel#statusBadge {
    color: #00e5ff;
    background: rgba(0, 229, 255, 0.12);
    border: 1px solid rgba(0, 229, 255, 0.4);
    border-radius: 12px;
    padding: 6px 14px;
    font-size: 11px;
    font-weight: 700;
}
QLabel#notice {
    color: #ffd166;
    background: rgba(255, 209, 102, 0.1);
    border: 1px solid rgba(255, 209, 102, 0.35);
    border-radius: 10px;
    padding: 10px 14px;
}
QFrame#panel {
    background: rgba(10, 18, 32, 0.82);
    border: 1px solid rgba(0, 229, 255, 0.2);
    border-radius: 18px;
}
QFrame#userCard {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #0f2742, stop:1 #0b1a2e);
    border: 1px solid rgba(0, 229, 255, 0.35);
    border-left: 4px solid #00e5ff;
    border-radius: 14px;
    padding: 4px;
}
QFrame#assistantCard {
    background: rgba(13, 26, 44, 0.9);
    border: 1px solid rgba(0, 229, 255, 0.2);
    border-radius: 14px;
    padding: 4px;
}
QLabel#message {
    color: #eaf6fc;
    font-size: 13.5px;
    line-height: 1.4;
}
QPushButton {
    background: rgba(16, 32, 54, 0.85);
    color: #d8f3ff;
    border: 1px solid rgba(0, 229, 255, 0.25);
    border-radius: 10px;
    padding: 9px 15px;
    font-size: 12px;
    font-weight: 600;
}
QPushButton:hover {
    background: rgba(0, 229, 255, 0.18);
    border-color: #00e5ff;
    color: #ffffff;
}
QPushButton:pressed {
    background: rgba(0, 229, 255, 0.3);
}
QPushButton:disabled {
    color: #4a6375;
    background: rgba(8, 16, 28, 0.6);
    border-color: rgba(0, 229, 255, 0.08);
}
QPushButton#primary {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #0099cc, stop:1 #00e5ff);
    color: #040c16;
    border: 1px solid #00e5ff;
    font-weight: 700;
}
QPushButton#primary:hover {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #00b4d8, stop:1 #7000ff);
    color: #ffffff;
    border-color: #ffffff;
}
QPushButton#primary:pressed {
    background: #0077b6;
    color: #ffffff;
}
QPushButton#quiet {
    background: transparent;
    border: 1px solid rgba(0, 229, 255, 0.25);
    color: #00e5ff;
    padding: 7px 11px;
}
QPushButton#quiet:hover {
    color: #ffffff;
    background: rgba(0, 229, 255, 0.15);
    border-color: #00e5ff;
}
QLineEdit {
    background: rgba(6, 14, 25, 0.9);
    color: #ffffff;
    border: 1px solid rgba(0, 229, 255, 0.3);
    border-radius: 12px;
    padding: 12px 14px;
    font-size: 13px;
    selection-background-color: #00e5ff;
    selection-color: #040c16;
}
QLineEdit:focus {
    border-color: #00e5ff;
}
QComboBox {
    background: rgba(8, 18, 32, 0.9);
    color: #e2f1f8;
    border: 1px solid rgba(0, 229, 255, 0.25);
    border-radius: 9px;
    padding: 8px 10px;
}
QComboBox:hover {
    border-color: #00e5ff;
}
QComboBox QAbstractItemView {
    background: #071322;
    color: #e2f1f8;
    selection-background-color: #00e5ff;
    selection-color: #040c16;
    border: 1px solid rgba(0, 229, 255, 0.3);
}
QCheckBox {
    color: #b8d4e3;
    spacing: 8px;
}
QCheckBox::indicator {
    width: 16px;
    height: 16px;
    border: 1px solid rgba(0, 229, 255, 0.3);
    border-radius: 4px;
    background: rgba(6, 14, 25, 0.9);
}
QCheckBox::indicator:hover {
    border-color: #00e5ff;
}
QCheckBox::indicator:checked {
    background: #00e5ff;
    border-color: #00e5ff;
}
QScrollArea, QWidget#messages {
    background: transparent;
    border: none;
}
QScrollBar:vertical {
    background: transparent;
    width: 6px;
}
QScrollBar::handle:vertical {
    background: rgba(0, 229, 255, 0.3);
    border-radius: 3px;
    min-height: 25px;
}
QScrollBar::handle:vertical:hover {
    background: #00e5ff;
}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
    height: 0;
}
QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {
    background: none;
}
"""


def app_icon():
    pix = QPixmap(128, 128)
    pix.fill(Qt.GlobalColor.transparent)
    p = QPainter(pix)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(QColor("#050c18"))
    p.drawRoundedRect(QRectF(4, 4, 120, 120), 24, 24)
    p.setPen(QPen(QColor(ACCENT), 4))
    p.drawEllipse(QPointF(64, 64), 46, 46)
    p.setPen(QPen(QColor(ACCENT_SECONDARY), 3))
    p.drawEllipse(QPointF(64, 64), 34, 34)
    p.setPen(QPen(QColor(ACCENT), 4))
    path = QPainterPath(QPointF(42, 48))
    path.lineTo(86, 48)
    path.lineTo(64, 88)
    path.closeSubpath()
    p.drawPath(path)
    p.end()
    return QIcon(pix)


class HudBackground(QWidget):
    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.fillRect(self.rect(), QColor("#040812"))
        glow = QRadialGradient(self.width() * 0.5, self.height() * 0.4, max(self.width(), self.height()) * 0.75)
        glow.setColorAt(0, QColor("#0d1d36"))
        glow.setColorAt(0.5, QColor("#071224"))
        glow.setColorAt(1, QColor("#040812"))
        p.fillRect(self.rect(), glow)
        p.setPen(QPen(QColor(0, 229, 255, 8), 1))
        spacing = 40
        for x in range(0, self.width(), spacing):
            p.drawLine(x, 0, x, self.height())
        for y in range(0, self.height(), spacing):
            p.drawLine(0, y, self.width(), y)
        p.end()


class VoiceOrb(QWidget):
    """Futuristic glowing plasma reactor orb with real-time state feedback."""
    activated = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumSize(120, 120)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.setAccessibleName("Activate Jarvis microphone")
        self.setToolTip("Click to speak; click again or press Escape to cancel.")
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.phase = 0.0
        self.mode = "STARTING"
        self.audio_level = 0.0
        self.display_level = 0.0
        self.draggable = True
        self._drag_origin = None
        self._window_origin = None
        self._dragging = False
        self.timer = QTimer(self)
        self.timer.setInterval(30)
        self.timer.timeout.connect(self._tick)
        self.timer.start()

    def _tick(self):
        if self.isVisible() and not self.window().isMinimized():
            self.phase += 0.04
            target = self.audio_level if self.mode == "LISTENING" else 0.0
            self.display_level += (target - self.display_level) * 0.35
            self.update()

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag_origin = event.globalPosition().toPoint()
            self._window_origin = self.window().pos()
            self._dragging = False
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if self.draggable and self._drag_origin is not None and event.buttons() & Qt.MouseButton.LeftButton:
            current = event.globalPosition().toPoint()
            delta = current - self._drag_origin
            if delta.manhattanLength() > 5:
                self._dragging = True
                self.window().move(self._window_origin + delta)
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton and not self._dragging:
            self.activated.emit()
        self._drag_origin = None
        self._window_origin = None
        self._dragging = False
        super().mouseReleaseEvent(event)

    def keyPressEvent(self, event):
        if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Space):
            self.activated.emit()
        else:
            super().keyPressEvent(event)

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.translate(self.width() / 2, self.height() / 2)
        scale = min(self.width(), self.height(), 480) / 360
        p.scale(scale, scale)

        active = self.mode in ("LISTENING", "SPEAKING")
        thinking = self.mode in ("THINKING", "TRANSCRIBING", "STARTING")

        if self.mode == "PAUSED":
            color = QColor("#546e7a")
        elif self.mode == "ERROR":
            color = QColor("#ff5252")
        elif self.mode == "SPEAKING":
            color = QColor(ACCENT_SUCCESS)
        elif thinking:
            color = QColor(ACCENT_SECONDARY)
        else:
            color = QColor(ACCENT)

        phase = self.phase * (2.2 if thinking else 1.0)

        glow = QRadialGradient(0, 0, 168)
        center = QColor(color)
        center.setAlpha(80 if active else 40)
        glow.setColorAt(0, center)
        glow.setColorAt(0.5, QColor(color.red(), color.green(), color.blue(), 25))
        glow.setColorAt(1, QColor(0, 0, 0, 0))
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(glow)
        p.drawEllipse(QPointF(0, 0), 174, 174)

        p.setBrush(Qt.BrushStyle.NoBrush)
        for radius in (156, 142, 124, 104, 82, 60):
            ring = QColor(color)
            ring.setAlpha(60 if radius > 90 else 130)
            p.setPen(QPen(ring, 0.8))
            p.drawEllipse(QPointF(0, 0), radius, radius)

        for radius, width, count, sweep, speed in (
            (138, 4.5, 3, 75, 25),
            (120, 2.0, 4, 45, -20),
            (100, 5.0, 3, 85, -15),
            (78, 1.5, 6, 30, 30),
        ):
            ring = QColor(color)
            ring.setAlpha(180 if radius > 90 else 120)
            p.setPen(QPen(ring, width, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
            for i in range(count):
                start = phase * speed + i * 360 / count
                p.drawArc(QRectF(-radius, -radius, radius * 2, radius * 2), int(start * 16), sweep * 16)

        for i in range(48):
            angle = i * math.tau / 48
            strength = (0.5 + 0.5 * math.sin(phase * 6 + i * 0.5)) if active else 0.25
            if self.mode == "LISTENING":
                strength = self.display_level * (0.6 + 0.4 * math.sin(phase * 6 + i * 0.5))
            p.setPen(QPen(QColor(color.red(), color.green(), color.blue(), int(90 + strength * 165)), 2.5))
            p.drawLine(
                QPointF(math.cos(angle) * 80, math.sin(angle) * 80),
                QPointF(math.cos(angle) * (85 + strength * 12), math.sin(angle) * (85 + strength * 12)),
            )

        p.setPen(QPen(QColor("#ffffff") if self.mode != "PAUSED" else color, 2))
        triangle = QPainterPath(QPointF(-32, -22))
        triangle.lineTo(32, -22)
        triangle.lineTo(0, 34)
        triangle.closeSubpath()
        p.setBrush(QColor(color.red(), color.green(), color.blue(), int(25 + 15 * math.sin(phase * 3))))
        p.drawPath(triangle)

        p.setPen(QPen(color, 1.5))
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawEllipse(QPointF(0, 0), 48, 48)
        p.end()


class TypedMessage(QLabel):
    """Type-on reveal for assistant responses."""
    advanced = Signal()

    def __init__(self, text, animate=False, parent=None):
        super().__init__(parent)
        self.full_text = text
        self.position = 0
        self.setObjectName("message")
        self.setTextFormat(Qt.TextFormat.PlainText)
        self.setWordWrap(True)
        self.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        self.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Minimum)
        self.timer = QTimer(self)
        self.timer.setInterval(15)
        self.timer.timeout.connect(self._advance)
        if animate and text:
            self.timer.start()
            self._advance()
        else:
            self.setText(text)

    def _advance(self):
        self.position = min(len(self.full_text), self.position + max(4, len(self.full_text) // 80))
        self.setText(self.full_text[:self.position])
        self.advanced.emit()
        if self.position >= len(self.full_text):
            self.timer.stop()

