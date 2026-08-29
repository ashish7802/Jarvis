# JARVIS

A Windows-native, voice-first personal assistant.

- Starts on Windows login, runs silently in the background (no window).
- Waits for the wake word **"Jarvis"**, then listens, thinks, speaks.
- No browser, no console window, no visible UI in production.

```
JARVIS.exe (Windows GUI subsystem, no console)
   └─ AssistantEngine (single thread + wake-word background thread)
        ├─ Wake Word (openWakeWord local, with energy-gate fallback)
        ├─ STT (faster-whisper, local)
        ├─ AI (provider abstraction: openai | gemini | mock)
        └─ TTS (edge-tts, Microsoft cloud, plays locally)
```

Wake-word, microphone capture, and STT are **local**. AI and TTS may call
cloud endpoints depending on configuration.

---

## Installation

### Requirements

- Windows 10 / 11
- A working microphone and speakers (the system default input/output
  devices are used automatically)
- Python 3.11+ (only required for development or building the EXE)

### Install the packaged EXE (recommended for users)

1. Copy `dist\JARVIS\` to a stable location, e.g.
   `C:\Apps\JARVIS\`.
2. Double-click `JARVIS.exe`. The greeting plays through your speakers
   and JARVIS waits for "Jarvis". **No window appears.**
3. Press **Ctrl + Shift + J** at any time for an emergency shutdown.

JARVIS stores its logs and TTS cache in
`%APPDATA%\JARVIS\` when running as a packaged EXE, and in `./logs/`
and `./tts_cache/` when running from source.

### Optional: register auto-start

```bat
python -m app.system.startup --install
```

This places a shortcut in the user's Startup folder
(`shell:startup`) pointing at the packaged `JARVIS.exe`. To remove:

```bat
python -m app.system.startup --uninstall
```

---

## Configuration

Copy `.env.example` to `.env` and edit:

```bat
copy .env.example .env
```

The packaged EXE looks for `.env` in its working directory (the folder
that holds `JARVIS.exe`), or you can point it elsewhere via
`JARVIS_ENV_FILE`.

Key values:

| Variable | Default | Purpose |
|---|---|---|
| `AI_PROVIDER` | `mock` | `openai`, `gemini`, or `mock` |
| `AI_MODEL` | (provider default) | e.g. `gpt-4o-mini`, `gemini-1.5-flash` |
| `OPENAI_API_KEY` | _empty_ | Required when `AI_PROVIDER=openai` |
| `GEMINI_API_KEY` | _empty_ | Required when `AI_PROVIDER=gemini` |
| `TTS_PROVIDER` | `edge` | `edge` or `mock` |
| `TTS_VOICE` | `en-US-GuyNeural` | Any edge-tts voice id |
| `WAKE_WORD_ENABLED` | `true` | Disable to skip wake-word detection |
| `WAKE_WORD` | `jarvis` | Keyword name (informational) |
| `WAKEWORD_BACKEND` | `openwakeword` | `openwakeword` (default), `energy`, or `porcupine` |
| `OPENWAKEWORD_MODEL` | `hey_jarvis` | Pretrained model name or path to a custom `.tflite`/`.onnx` |
| `OPENWAKEWORD_THRESHOLD` | `0.5` | Detection threshold (0.0 – 1.0) |
| `PORCUPINE_ACCESS_KEY` | _empty_ | Optional, only used if `WAKEWORD_BACKEND=porcupine` |
| `PORCUPINE_KEYWORD_PATH` | _empty_ | Optional `.ppn` file path |
| `STARTUP_GREETING_ENABLED` | `true` | Set `false` for silent boot |
| `STARTUP_GREETING` | `Good morning, Sir.` | Spoken after the startup delay |
| `STARTUP_GREETING_DELAY` | `5` | Seconds to wait before greeting |
| `HOTKEY_EXIT` | `Ctrl+Shift+J` | Emergency-stop hotkey |
| `LOG_LEVEL` | `INFO` | `DEBUG`, `INFO`, `WARNING`, `ERROR` |

---

## AI Provider

JARVIS supports three providers:

- **`mock`** — offline canned answers, useful for testing the pipeline
  without an API key.
- **`openai`** — requires `OPENAI_API_KEY`. Uses the OpenAI Chat
  Completions API.
- **`gemini`** — requires `GEMINI_API_KEY`. Uses the Google Generative
  AI SDK.

Set `AI_PROVIDER` to the one you want. JARVIS does **not** silently
fall back if a key is missing — the failure surfaces so the user can
fix configuration.

---

## Wake Word

The default backend is **openWakeWord** — fully local, no API key,
no signup. JARVIS listens for **"hey jarvis"** by default using a
pretrained model that ships with the `openwakeword` package.

Two backends are available; pick one via `WAKEWORD_BACKEND`:

1. **`openwakeword`** (default) — fully local. Uses
   [`openwakeword`](https://github.com/dscripka/openWakeWord) with
   `onnxruntime` as the inference backend. The package ships several
   pretrained models — `hey_jarvis`, `alexa`, `hey_mycroft`,
   `hey_rhasspy`, `timer`, `weather` — set `OPENWAKEWORD_MODEL` to
   any of them, or to a path to a custom `.tflite`/`.onnx` model.
   No internet, no API key, no account required.
2. **`energy`** — simple energy-gate fallback. Detects a short burst
   of loud audio as a proxy for the wake word. Fully local, no
   dependencies beyond NumPy and sounddevice. Used automatically if
   the openWakeWord model fails to load.
3. **`porcupine`** (legacy) — the previous default. Requires
   `pvporcupine` and a Picovoice access key from
   <https://console.picovoice.ai/>. Set `PORCUPINE_ACCESS_KEY` in
   `.env`. New users should not need this — openWakeWord covers the
   same use case without signup.

### Tuning detection

- `OPENWAKEWORD_THRESHOLD` (default `0.5`) controls the model's
  decision threshold. Higher = fewer false positives, lower = more
  sensitive. If JARVIS keeps firing on background noise, raise it to
  `0.6`–`0.7`. If it never fires when you say "hey jarvis", lower it
  to `0.3`–`0.4`.
- Microphone frames are processed **locally** for wake-word detection
  — no audio is uploaded for this step.

### Training a custom "hey jarvis" model

openWakeWord already ships a pretrained `hey_jarvis` model, so
**no training is required** out of the box. If you find its accuracy
unsatisfactory on your voice/mic, you can train a custom model by
following the [openWakeWord training notebook](https://github.com/dscripka/openWakeWord/blob/main/notebooks/train_custom_model.ipynb),
export the resulting `.tflite` (or `.onnx`), and set
`OPENWAKEWORD_MODEL=C:\path\to\your_model.tflite`.

---

## STT (Speech-to-Text)

Uses **faster-whisper** locally.

- Model: `base` (int8, CPU). Loaded once on first use and held in
  memory; not reloaded per command.
- Audio format: 16 kHz, mono, int16.
- No raw microphone recordings are stored on disk.

To change the model size, edit `_build_stt` in `app/main.py`.

---

## TTS (Text-to-Speech)

Uses **edge-tts** (Microsoft cloud) and plays through the local
sounddevice player.

- This **is a network service**, not offline. First-use synthesis
  needs internet.
- Synthesised MP3 files are deleted immediately after playback so the
  TTS cache does not grow.
- JARVIS disables wake-word detection while it is speaking, so its
  own voice cannot trigger a new wake event (self-trigger guard).

To switch voice, set `TTS_VOICE` in `.env` (e.g.
`en-US-JennyNeural`, `en-GB-RyanNeural`).

---

## Startup

JARVIS can start automatically on Windows login via a shortcut in the
Startup folder.

```bat
python -m app.system.startup --install     :: install
python -m app.system.startup --status      :: check
python -m app.system.startup --uninstall   :: remove
```

The shortcut points at the packaged `JARVIS.exe`, **not** at Python
or `run_dev.bat`. The shortcut is created with `WindowStyle = 7`
(hidden) so JARVIS launches with no visible UI.

---

## Emergency Stop

**Ctrl + Shift + J** — releases the microphone, stops TTS playback,
unregisters the global hotkey, and exits the process cleanly. This
hotkey is essential because the production EXE has no visible window.

---

## Development

Run from source:

```bat
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env
:: edit .env
python -m app.main            :: dev mode, console visible
python -m app.main --check    :: initialise everything then exit
python -m app.main --dev      :: explicit dev mode
```

Run a quick end-to-end test against real audio:

```bat
python smoke_live.py
```

Run the automated test suite:

```bat
pytest -q
```

---

## Production Build

```bat
build.bat
```

Produces `dist\JARVIS\JARVIS.exe` (PyInstaller, `--noconsole`,
one-folder). The folder is self-contained — end users do **not** need
Python installed.

After building, you can install the auto-start shortcut:

```bat
python -m app.system.startup --install
```

---

## Troubleshooting

- **Microphone unavailable** — Windows may have denied mic access to
  Python / the EXE. Check
  `Settings → Privacy → Microphone` and ensure desktop apps have
  permission. Also confirm your mic is the system default input.
- **Speaker unavailable** — confirm the system default output device
  is connected and not muted. JARVIS uses the system default.
- **Wake word unavailable** — confirm `WAKE_WORD_ENABLED=true` in
  `.env`. The default backend is `openwakeword` (no API key needed)
  using the `hey_jarvis` pretrained model. If the model fails to
  load, the energy-gate fallback is used automatically — speak the
  wake word louder and closer to the mic. Tune sensitivity with
  `OPENWAKEWORD_THRESHOLD`. For the legacy Porcupine backend, set
  `WAKEWORD_BACKEND=porcupine`, `pip install pvporcupine`, and set
  `PORCUPINE_ACCESS_KEY`.
- **API key missing / invalid** — startup will surface the
  configuration error in `logs/jarvis.log`. Set the correct key in
  `.env` for the provider you chose in `AI_PROVIDER`.
- **Network unavailable** — TTS (edge-tts) requires internet.
  Commands still work locally for STT and wake-word, but spoken
  replies will fail.
- **TTS failure** — check `logs/jarvis.log` for the underlying
  exception. JARVIS logs the error and continues; no spoken reply
  is delivered for that command.
- **Startup shortcut issue** — re-run
  `python -m app.system.startup --install`. Inspect the shortcut
  properties to confirm `Target` is the packaged `JARVIS.exe`,
  not `python.exe` or `run_dev.bat`.

---

## Privacy & Security

- `.env` is git-ignored. API keys are not committed.
- A secret-scrubbing log filter redacts obvious `key=value` pairs in
  log output, so API keys are not leaked via logs.
- Wake-word detection is local. STT runs locally (faster-whisper).
- AI and TTS calls may use cloud services depending on configuration.
- No raw microphone recordings are stored permanently.

---

## License

Personal project. Use at your own risk.
