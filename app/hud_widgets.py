"""Native animated HUD artwork; no browser or web view."""
import math

from PySide6.QtCore import QPointF, QRectF, Qt, QTimer, Signal
from PySide6.QtGui import QColor, QIcon, QPainter, QPainterPath, QPen, QPixmap, QRadialGradient
from PySide6.QtWidgets import QWidget, QLabel, QSizePolicy

ACCENT = "#64eaff"
STYLE = """
QMainWindow { background: #030b12; }
QWidget { color: #c9f2fa; font-family: 'Segoe UI'; font-size: 13px; }
QLabel { background: transparent; border: none; }
QLabel#brand { color: #94f3ff; font-family: 'Consolas'; font-size: 23px; font-weight: 600; letter-spacing: 7px; }
QLabel#muted { color: #72a2b5; font-size: 12px; }
QLabel#eyebrow { color: #70b8cc; font-family: 'Consolas'; font-size: 11px; letter-spacing: 2px; }
QLabel#heroTitle { color: #a8f6ff; font-family: 'Consolas'; font-size: 23px; letter-spacing: 5px; }
QLabel#statusBadge { color: #8beeff; font-family: 'Consolas'; font-size: 11px; letter-spacing: 1px; }
QLabel#notice { color: #ffd393; background: #1c1b19; border: 1px solid #785531; padding: 10px; }
QFrame#chatCard { background: rgba(6, 23, 34, 210); border-top: 1px solid #28596a; border-bottom: 1px solid #163a4b; }
QFrame#controls { background: #071823; border: 1px solid #24546a; }
QFrame#userBubble { background: transparent; border: none; border-left: 2px solid #ba8750; }
QFrame#assistantBubble { background: transparent; border: none; border-left: 2px solid #51d5ef; }
QLabel#message { color: #d8f6fc; font-size: 14px; }
QPushButton { background: #0a2430; color: #9beafa; border: 1px solid #285365; padding: 10px 12px; font-size: 12px; }
QPushButton:hover { background: #123a49; border-color: #66d8ed; }
QPushButton:pressed { background: #071a24; }
QPushButton:disabled { color: #4e7080; background: #0a1821; border-color: #233f4a; }
QPushButton:focus, QLineEdit:focus { border: 1px solid #a2f5ff; }
QPushButton#quiet { background: transparent; border: none; color: #7aafc0; padding: 4px 8px; }
QPushButton#quiet:hover { color: #c9fbff; background: #13313e; }
QPushButton#toggle:checked { color: #acfbff; background: #134152; border-color: #4399ae; }
QLineEdit { background: #04121d; color: #d8f6fc; border: 1px solid #295365; padding: 12px; selection-background-color: #285666; }
QComboBox { background: #0a2430; color: #b9f8ff; border: 1px solid #285365; padding: 8px; }
QComboBox QAbstractItemView { background: #0a2430; color: #d8f6fc; selection-background-color: #285666; }
QProgressBar { background: #04121d; border: 1px solid #285365; border-radius: 3px; }
QProgressBar::chunk { background: #64eaff; border-radius: 2px; }
QScrollArea, QWidget#messages { background: transparent; border: none; }
QScrollBar:vertical { background: transparent; width: 5px; }
QScrollBar::handle:vertical { background: #2c6277; min-height: 25px; }
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical { background: none; }
QToolTip { background: #0b2734; color: #d8f6fc; border: 1px solid #43879a; padding: 6px; }
"""


def app_icon():
    pix = QPixmap(128, 128)
    pix.fill(Qt.GlobalColor.transparent)
    p = QPainter(pix)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(QColor("#061724"))
    p.drawRoundedRect(QRectF(4, 4, 120, 120), 22, 22)
    p.setPen(QPen(QColor(ACCENT), 5))
    p.drawEllipse(QPointF(64, 64), 44, 44)
    p.setPen(QPen(QColor("#2a8caa"), 3))
    p.drawEllipse(QPointF(64, 64), 33, 33)
    p.setPen(QPen(QColor("#c7faff"), 4))
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
        p.fillRect(self.rect(), QColor("#030b12"))
        glow = QRadialGradient(self.width()/2, self.height()*.42, self.width()*.6)
        glow.setColorAt(0, QColor("#0a2435"))
        glow.setColorAt(1, QColor("#030b12"))
        p.fillRect(self.rect(), glow)
        p.setPen(QPen(QColor(65, 152, 181, 12), 1))
        for x in range(0, self.width(), 42):
            p.drawLine(x, 0, x, self.height())
        for y in range(0, self.height(), 42):
            p.drawLine(0, y, self.width(), y)
        p.setPen(QPen(QColor("#31647b"), 1))
        for x, y, dx, dy in ((13, 13, 1, 1), (self.width()-14, 13, -1, 1),
                              (13, self.height()-14, 1, -1), (self.width()-14, self.height()-14, -1, -1)):
            p.drawLine(x, y, x+26*dx, y)
            p.drawLine(x, y, x, y+26*dy)
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
        for i in range(120):
            angle = i*math.tau/120
            p.setPen(QPen(QColor("#407f98"), 1 if i % 5 else 1.8))
            inner = 152 if i % 5 else 146
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
        p.setPen(QPen(QColor("#b9f8ff") if self.mode != "PAUSED" else color, 2))
        triangle = QPainterPath(QPointF(-34, -24))
        triangle.lineTo(34, -24)
        triangle.lineTo(0, 37)
        triangle.closeSubpath()
        p.setBrush(QColor(79, 224, 255, 18+int(12*(1+math.sin(phase*3)))))
        p.drawPath(triangle)
        p.setPen(QPen(color, 1))
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawEllipse(QPointF(0, 0), 52, 52)
        for sign in (-1, 1):
            p.setPen(QPen(QColor("#8d795b"), 1))
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
