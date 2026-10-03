# JARVIS - Apple Siri UI Voice Assistant

Apple Siri jesa ek modern glassmorphic AI Voice Assistant UI (PySide6 + HTML5 Canvas WebEngine).

---

## 🌟 Features / Highlights

- 🔮 **Apple Siri Fluid Glowing Orb**: 60fps dynamic multi-color liquid canvas wave orb (cyan `#00F2FE`, magenta `#FF007F`, purple `#7F00FF`, ocean blue `#4FACFE`).
- 💎 **Apple Glassmorphism UI**: High-end translucent dark frosted glass window (`backdrop-filter: blur(40px)`).
- 🌈 **iOS 18 Screen-Edge Siri Glow**: Glowing animated border around the screen/container during active voice listening.
- 🎙️ **Voice & Speech Recognition**: Integrated Web Speech API and voice synthesis with Siri voice selection & sound chime.
- ⚡ **JARVIS AI Backend**: Real-time system health checks (CPU, RAM, OS specs), date/time, joke generator, app launcher (Chrome, YouTube, Notepad, Calculator).
- 💬 **Apple Siri Suggestion Chips**: Quick prompt chips ("What's the time?", "System Health", "Tell me a joke", "Who is JARVIS?").

---

## 🚀 How to Run

### 1. Run Desktop Application (PySide6 Siri GUI)
```bash
python main.py
```

### 2. Run Web Interface in Browser
```bash
python main.py --web
```
This will start a local HTTP server at `http://127.0.0.1:8000` and automatically open your web browser.

---

## 📁 File Structure

```
jarvis/
├── main.py                     # Main Launcher (Desktop GUI or Web mode)
├── app/
│   ├── assistant/
│   │   └── brain.py            # JARVIS AI & System Diagnostic Logic
│   └── ui/
│       ├── siri_app.py         # PySide6 Frameless Glass Window & WebChannel Bridge
│       └── web/
│           ├── index.html      # Siri Glass Container & Suggestion Chips
│           ├── style.css       # Apple iOS 18 Edge Glow & Glassmorphic CSS
│           ├── siri_orb.js     # 60fps Liquid Wave Orb Renderer (Canvas 2D)
│           ├── app.js          # Speech Recognition & Siri State Machine
│           └── qwebchannel.js  # PySide6 JavaScript Bridge
```
