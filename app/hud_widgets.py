"""Native animated HUD artwork; no browser or web view."""
import math

from PySide6.QtCore import QPointF, QRectF, Qt, QTimer, Signal
from PySide6.QtGui import QColor, QIcon, QPainter, QPainterPath, QPen, QPixmap, QRadialGradient
from PySide6.QtWidgets import QWidget, QLabel, QSizePolicy

ACCENT = "#007aff"
STYLE = """
QMainWindow { background: #f5f5f7; }
QWidget { color: #1d1d1f; font-family: 'Segoe UI Variable', 'Segoe UI'; font-size: 13px; }
QLabel { background: transparent; border: none; }
QLabel#brand { color: #1d1d1f; font-size: 24px; font-weight: 700; letter-spacing: 1px; }
QLabel#muted { color: #86868b; font-size: 12px; }
QLabel#eyebrow { color: #86868b; font-size: 11px; font-weight: 600; letter-spacing: 1px; }
QLabel#heroTitle { color: #1d1d1f; font-size: 25px; font-weight: 650; letter-spacing: .2px; }
QLabel#statusBadge { color: #007aff; background: #e8f2ff; border: 1px solid #c7e0ff; border-radius: 12px; padding: 5px 10px; font-size: 11px; font-weight: 600; }
QLabel#notice { color: #9a6700; background: #fff8e6; border: 1px solid #f2d58a; border-radius: 12px; padding: 10px 12px; }
QFrame#chatCard { background: #ffffff; border: 1px solid #e5e5ea; border-radius: 18px; }
QFrame#controls { background: #ffffff; border: 1px solid #e5e5ea; border-radius: 18px; }
QFrame#userBubble { background: #f5f5f7; border: none; border-radius: 14px; }
QFrame#assistantBubble { background: #f0f7ff; border: none; border-radius: 14px; }
QLabel#message { color: #1d1d1f; font-size: 14px; }
QPushButton { background: #ffffff; color: #1d1d1f; border: 1px solid #d2d2d7; border-radius: 10px; padding: 10px 14px; font-size: 13px; }
QPushButton:hover { background: #f5f5f7; border-color: #a1a1a6; }
QPushButton:pressed { background: #e8e8ed; }
QPushButton:disabled { color: #aeaeb2; background: #f5f5f7; border-color: #e5e5ea; }
QPushButton#primary { background: #007aff; color: #ffffff; border-color: #007aff; font-weight: 600; }
QPushButton#primary:hover { background: #006ee6; border-color: #006ee6; }
QPushButton#primary:pressed { background: #005ec4; border-color: #005ec4; }
QPushButton#primary:disabled { color: #ffffff; background: #b6d7ff; border-color: #b6d7ff; }
QPushButton:focus, QLineEdit:focus, QComboBox:focus { border: 2px solid #007aff; }
QPushButton#quiet { background: transparent; border: none; color: #007aff; padding: 5px 8px; }
QPushButton#quiet:hover { color: #005ec4; background: #eef6ff; }
QPushButton#toggle:checked { color: #006ee6; background: #e8f2ff; border-color: #b7d8ff; }
QLineEdit { background: #ffffff; color: #1d1d1f; border: 1px solid #d2d2d7; border-radius: 10px; padding: 12px; selection-background-color: #b7d8ff; }
QComboBox { background: #ffffff; color: #1d1d1f; border: 1px solid #d2d2d7; border-radius: 10px; padding: 9px 10px; }
QComboBox QAbstractItemView { background: #ffffff; color: #1d1d1f; selection-background-color: #e8f2ff; selection-color: #1d1d1f; border: 1px solid #d2d2d7; }
QCheckBox { color: #1d1d1f; spacing: 8px; }
QCheckBox::indicator { width: 17px; height: 17px; border: 1px solid #c7c7cc; border-radius: 5px; background: #ffffff; }
QCheckBox::indicator:hover { border-color: #007aff; }
QCheckBox::indicator:checked { background: #007aff; border-color: #007aff; }
QProgressBar { background: #e5e5ea; border: none; border-radius: 3px; }
QProgressBar::chunk { background: #007aff; border-radius: 3px; }
QScrollArea, QWidget#messages { background: transparent; border: none; }
QScrollBar:vertical { background: transparent; width: 7px; }
QScrollBar::handle:vertical { background: #c7c7cc; border-radius: 3px; min-height: 25px; }
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical { background: none; }
QToolTip { background: #ffffff; color: #1d1d1f; border: 1px solid #d2d2d7; border-radius: 8px; padding: 6px; }
"""


def app_icon():
    pix = QPixmap(128, 128)
    pix.fill(Qt.GlobalColor.transparent)
    p = QPainter(pix)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(QColor("#ffffff"))
    p.drawRoundedRect(QRectF(4, 4, 120, 120), 22, 22)
    p.setPen(QPen(QColor(ACCENT), 5))
    p.drawEllipse(QPointF(64, 64), 44, 44)
    p.setPen(QPen(QColor("#5ac8fa"), 3))
    p.drawEllipse(QPointF(64, 64), 33, 33)
    p.setPen(QPen(QColor("#007aff"), 4))
    path = QPainterPath(QPointF(43, 48))
    path.lineTo(85, 48)
    path.lineTo(64, 86)
    path.closeSubpath()
    p.drawPath(path)
    p.end()
    return QIcon(pix)


class HudBackground(QWidget):
    def paintEvent(self, event):
        p = QPainter(self)
        p.fillRect(self.rect(), QColor("#f5f5f7"))
        glow = QRadialGradient(self.width()/2, self.height()*.42, self.width()*.6)
        glow.setColorAt(0, QColor("#ffffff"))
        glow.setColorAt(1, QColor("#f5f5f7"))
        p.fillRect(self.rect(), glow)
        p.end()


class VoiceOrb(QWidget):
    """Clickable reactor: measured mic response while listening; state motion otherwise."""
    activated = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumSize(100, 100)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.setAccessibleName("Activate Jarvis microphone")
        self.setToolTip("Click to speak; click again or press Escape to cancel. F2 shows controls.")
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.phase = 0.0
        self.mode = "STARTING"
        self.audio_level = 0.0
        self.display_level = 0.0
        self.timer = QTimer(self)
        self.timer.setInterval(33)
        self.timer.timeout.connect(self._tick)
        self.timer.start()

    def _tick(self):
        if self.isVisible() and not self.window().isMinimized():
            self.phase += .035
            target = self.audio_level if self.mode == "LISTENING" else 0
            self.display_level += (target - self.display_level) * .3
            self.update()

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.activated.emit()

    def keyPressEvent(self, event):
        if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Space):
            self.activated.emit()
        else:
            super().keyPressEvent(event)

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.translate(self.width()/2, self.height()/2)
        scale = min(self.width(), self.height(), 470)/360
        p.scale(scale, scale)
        active = self.mode in ("LISTENING", "SPEAKING")
        thinking = self.mode in ("THINKING", "TRANSCRIBING", "STARTING")
        color = QColor("#698d9c" if self.mode == "PAUSED" else "#ffbc71" if self.mode == "ERROR" else ACCENT)
        phase = self.phase * (1.7 if thinking else 1)
        glow = QRadialGradient(0, 0, 164)
        center = QColor(color)
        center.setAlpha(65 if active else 30)
        glow.setColorAt(0, center)
        glow.setColorAt(.55, QColor(20, 116, 158, 15))
        glow.setColorAt(1, QColor(0, 0, 0, 0))
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(glow)
        p.drawEllipse(QPointF(0, 0), 170, 170)
        p.setBrush(Qt.BrushStyle.NoBrush)
        for radius in (158, 149, 129, 115, 95, 70):
            ring = QColor(color)
            ring.setAlpha(55 if radius > 95 else 110)
            p.setPen(QPen(ring, .7))
            p.drawEllipse(QPointF(0, 0), radius, radius)
        for i in range(72):
            angle = i*math.tau/72
            p.setPen(QPen(QColor(0, 122, 255, 45 if i % 6 else 75), 1 if i % 6 else 1.5))
            inner = 152 if i % 6 else 147
            p.drawLine(QPointF(math.cos(angle)*inner, math.sin(angle)*inner),
                       QPointF(math.cos(angle)*156, math.sin(angle)*156))
        for radius, width, count, sweep, speed in ((136, 4, 3, 77, 22), (121, 1.5, 6, 38, -16), (102, 6, 3, 92, -12)):
            ring = QColor(color)
            ring.setAlpha(175 if radius != 121 else 105)
            p.setPen(QPen(ring, width, Qt.PenStyle.SolidLine, Qt.PenCapStyle.FlatCap))
            for i in range(count):
                start = phase*speed + i*360/count
                p.drawArc(QRectF(-radius, -radius, radius*2, radius*2), int(start*16), sweep*16)
        for i in range(36):
            angle = i*math.tau/36
            strength = (.5 + .5*math.sin(phase*5 + i*.6)) if active else .2
            if self.mode == "LISTENING":
                strength = self.display_level * (.7 + .3 * math.sin(phase * 5 + i * .6))
            p.setPen(QPen(QColor(color.red(), color.green(), color.blue(), int(80+strength*160)), 3))
            p.drawLine(QPointF(math.cos(angle)*79, math.sin(angle)*79),
                       QPointF(math.cos(angle)*(84+strength*8), math.sin(angle)*(84+strength*8)))
        p.setPen(QPen(QColor("#ffffff") if self.mode != "PAUSED" else color, 2))
        triangle = QPainterPath(QPointF(-34, -24))
        triangle.lineTo(34, -24)
        triangle.lineTo(0, 37)
        triangle.closeSubpath()
        p.setBrush(QColor(0, 122, 255, 18+int(12*(1+math.sin(phase*3)))))
        p.drawPath(triangle)
        p.setPen(QPen(color, 1))
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawEllipse(QPointF(0, 0), 52, 52)
        for sign in (-1, 1):
            p.setPen(QPen(QColor("#a1a1a6"), 1))
            p.drawLine(QPointF(sign*163, -8), QPointF(sign*172, -8))
            p.drawLine(QPointF(sign*163, 8), QPointF(sign*172, 8))
        p.end()


class TypedMessage(QLabel):
    """Type-on reveal. Complete answers remain selectable after the animation."""
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
        self.timer.setInterval(20)
        self.timer.timeout.connect(self._advance)
        if animate and text:
            self.timer.start()
            self._advance()
        else:
            self.setText(text)

    def _advance(self):
        self.position = min(len(self.full_text), self.position+max(3, len(self.full_text)//120))
        self.setText(self.full_text[:self.position])
        self.advanced.emit()
        if self.position >= len(self.full_text):
            self.timer.stop()
