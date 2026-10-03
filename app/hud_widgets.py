"""Native animated HUD artwork; no browser or web view."""
import math

from PySide6.QtCore import QPointF, QRectF, Qt, QTimer, Signal
from PySide6.QtGui import QColor, QIcon, QPainter, QPainterPath, QPen, QPixmap, QRadialGradient
from PySide6.QtWidgets import QWidget, QLabel, QSizePolicy

ACCENT = "#42ddff"
STYLE = """
QMainWindow, QWidget { background: transparent; color: #e8f8ff; font-family: 'Segoe UI Variable', 'Segoe UI'; font-size: 13px; }
QLabel { background: transparent; border: none; }
QLabel#brand { color: #e8f8ff; font-size: 25px; font-weight: 700; letter-spacing: 3px; }
QLabel#muted { color: #7898aa; font-size: 12px; }
QLabel#eyebrow { color: #6f9eb1; font-size: 10px; font-weight: 700; letter-spacing: 1.8px; }
QLabel#heroTitle { color: #e8f8ff; font-size: 24px; font-weight: 650; letter-spacing: .2px; }
QLabel#statusBadge { color: #8df1ff; background: #102a39; border: 1px solid #215b70; border-radius: 12px; padding: 6px 11px; font-size: 11px; font-weight: 700; }
QLabel#notice { color: #ffdc91; background: #332b1e; border: 1px solid #725a2d; border-radius: 10px; padding: 10px 12px; }
QFrame#panel { background: rgba(10, 28, 43, 225); border: 1px solid #173d52; border-radius: 16px; }
QFrame#chatCard { background: #102a3b; border: 1px solid #20526a; border-radius: 14px; }
QFrame#userBubble { background: #102b40; border: 1px solid #1a4760; border-radius: 13px; }
QFrame#assistantBubble { background: #0e3544; border: 1px solid #1b5967; border-radius: 13px; }
QLabel#message { color: #e4f6ff; font-size: 14px; }
QPushButton { background: #102a3b; color: #d9f4ff; border: 1px solid #24516a; border-radius: 10px; padding: 10px 14px; font-size: 12px; font-weight: 600; }
QPushButton:hover { background: #15394c; border-color: #42ddff; }
QPushButton:pressed { background: #0a202f; }
QPushButton:disabled { color: #587385; background: #0b1d2a; border-color: #193446; }
QPushButton#primary { background: #0b7089; color: #f1fdff; border-color: #36cbe8; font-weight: 700; }
QPushButton#primary:hover { background: #1087a2; border-color: #8df1ff; }
QPushButton#primary:pressed { background: #07556a; }
QPushButton#primary:disabled { color: #8ba8b4; background: #194051; border-color: #28576b; }
QPushButton#quiet { background: transparent; border: 1px solid #20485c; color: #77dff2; padding: 8px 10px; }
QPushButton#quiet:hover { color: #d9fbff; background: #102b3b; }
QPushButton#toggle:checked { color: #a4f1ff; background: #103c4b; border-color: #329db1; }
QLineEdit { background: #091c29; color: #e8f8ff; border: 1px solid #24516a; border-radius: 10px; padding: 13px; selection-background-color: #17647b; }
QComboBox { background: #0b2231; color: #e8f8ff; border: 1px solid #24516a; border-radius: 9px; padding: 9px 10px; }
QComboBox QAbstractItemView { background: #0b2231; color: #e8f8ff; selection-background-color: #17647b; selection-color: #ffffff; border: 1px solid #24516a; }
QCheckBox { color: #c3dce7; spacing: 8px; }
QCheckBox::indicator { width: 16px; height: 16px; border: 1px solid #376076; border-radius: 4px; background: #091c29; }
QCheckBox::indicator:hover { border-color: #42ddff; }
QCheckBox::indicator:checked { background: #087895; border-color: #42ddff; }
QScrollArea, QWidget#messages { background: transparent; border: none; }
QScrollBar:vertical { background: transparent; width: 7px; }
QScrollBar::handle:vertical { background: #24516a; border-radius: 3px; min-height: 25px; }
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical { background: none; }
QMenu { background: #0b2231; color: #e8f8ff; border: 1px solid #24516a; }
QMenu::item:selected { background: #17647b; }
QToolTip { background: #0b2231; color: #e8f8ff; border: 1px solid #24516a; border-radius: 8px; padding: 6px; }
"""


def app_icon():
    pix = QPixmap(128, 128)
    pix.fill(Qt.GlobalColor.transparent)
    p = QPainter(pix)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(QColor("#071521"))
    p.drawRoundedRect(QRectF(4, 4, 120, 120), 22, 22)
    p.setPen(QPen(QColor(ACCENT), 5))
    p.drawEllipse(QPointF(64, 64), 44, 44)
    p.setPen(QPen(QColor("#9af2ff"), 3))
    p.drawEllipse(QPointF(64, 64), 33, 33)
    p.setPen(QPen(QColor("#42ddff"), 4))
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
        p.fillRect(self.rect(), QColor("#06121d"))
        glow = QRadialGradient(self.width()*.53, self.height()*.42, self.width()*.8)
        glow.setColorAt(0, QColor("#102c3c"))
        glow.setColorAt(.55, QColor("#091b29"))
        glow.setColorAt(1, QColor("#06121d"))
        p.fillRect(self.rect(), glow)
        p.setPen(QPen(QColor(52, 143, 171, 12), 1))
        spacing = 36
        for x in range(0, self.width(), spacing):
            p.drawLine(x, 0, x, self.height())
        for y in range(0, self.height(), spacing):
            p.drawLine(0, y, self.width(), y)
        p.end()


class VoiceOrb(QWidget):
    """Clickable reactor: measured mic response while listening; state motion otherwise."""
    activated = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumSize(100, 100)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.setAccessibleName("Activate Jarvis microphone")
        self.setToolTip("Click to speak; click again or press Escape to cancel. Right-click for options.")
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
        self.timer.setInterval(33)
        self.timer.timeout.connect(self._tick)
        self.timer.start()

    def _tick(self):
        if self.isVisible() and not self.window().isMinimized():
            self.phase += .035
            target = self.audio_level if self.mode == "LISTENING" else 0
            self.display_level += (target - self.display_level) * .3
            self.update()

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag_origin = event.globalPosition().toPoint()
            self._window_origin = self.window().pos()
            self._dragging = False
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if (
            self.draggable
            and
            self._drag_origin is not None
            and event.buttons() & Qt.MouseButton.LeftButton
        ):
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
        p.translate(self.width()/2, self.height()/2)
        scale = min(self.width(), self.height(), 470)/360
        p.scale(scale, scale)
        active = self.mode in ("LISTENING", "SPEAKING")
        thinking = self.mode in ("THINKING", "TRANSCRIBING", "STARTING")
        color = QColor("#698d9c" if self.mode == "PAUSED" else "#ffc36e" if self.mode == "ERROR" else ACCENT)
        phase = self.phase * (1.7 if thinking else 1)
        glow = QRadialGradient(0, 0, 164)
        center = QColor(color)
        center.setAlpha(65 if active else 30)
        glow.setColorAt(0, center)
        glow.setColorAt(.55, QColor(14, 152, 178, 22))
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
            p.setPen(QPen(QColor(45, 205, 233, 45 if i % 6 else 90), 1 if i % 6 else 1.5))
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
        p.setBrush(QColor(66, 221, 255, 18+int(12*(1+math.sin(phase*3)))))
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
