# JARVIS

A Windows-native, voice-first personal assistant.

### Animated desktop HUD

JARVIS now opens as a native Qt desktop app with a cyan, animated reactor and
a minimal HUD. There is no browser, local website, or web view. The core changes
its motion while listening, understanding, thinking and replying.

- Say **"hey Jarvis"**, wait for the acknowledgement, then ask your question.
  You can also click the core or press **Ctrl+Space** inside the app.
- **Soft voice** mode is the default: a noise-relative recording threshold,
  450 ms onset buffer and capped amplification help capture quieter questions.
  Open controls with **F2** to choose **Balanced** or **Noisy room**; the choice
  is saved across restarts. Exact commands **"soft voice mode"**, **"balanced
  mode"** and **"noisy room mode"** change it without a cloud AI request.
- The core reacts to measured microphone volume while recording. The hidden
  controls include a live input meter and clipping/connection feedback. Wake
  microphone disconnects are retried automatically. Soft mode works best in
  a quiet room; it cannot recover speech drowned out by noise or guarantee
  whisper/far-field recognition. Use Noisy room near a fan or traffic.
- **Escape** or a second core click cancels the current turn. Recording and
  playback stop promptly; an in-flight transcription or cloud request must
  finish before the next question, and its late answer is discarded. You can
  keep typing a draft while Jarvis is busy. Short spoken replies are synthesized
  together to avoid a separate network delay between every sentence.
- **Auto language** understands Hindi, Roman Hindi/Hinglish and English and
  follows the latest question. Hindi words in replies use Devanagari so the
  Hindi voice pronounces them naturally; English technical terms stay readable.
  Say **"Hindi mein baat karo"**, **"speak English"**, **"Hinglish mein baat karo"**
  or **"meri language mein baat karo"**. F2 also offers a saved Language selector.
  Hindi/Hinglish mode locks recognition to Hindi; English locks it to English;
  Auto restores language detection. Speech is transcribed, not translated.
  For better Hindi recognition on a CPU, `STT_MODEL=small` with
  `STT_BEAM_SIZE=1` is available; it needs roughly 485 MB of downloaded model
  data. Run `python -m app.setup_models` before building/installing after a
  model change. The installer includes downloaded models for offline startup.
- Conversation appears when you speak, with a type-on answer animation. It
  hides after 45 seconds of inactivity. **"Show chat"** keeps it visible;
  **"hide chat"** hides it. Hidden chat still remains in this session's memory.
- Controls stay hidden by default. Say **"show controls"**, **"controls dikhao"**,
  or **"settings dikhao"** to reveal them. **"Hide controls"** closes them.
  **F2** is the keyboard fallback. Hindi equivalents such as **"सेटिंग्स दिखाओ"**
  and **"चैट दिखाओ"** work after speech recognition.
- The controls panel contains microphone pause/resume, spoken replies on/off,
  typed messages, new chat and diagnostic logs. Pausing closes the wake microphone
  stream. Click the core or press Ctrl+Space to resume a paused microphone;
  then speak after the ready status returns. **"Clear chat"** clears both the
  visible transcript and conversation memory.
- Closing the window stops the assistant. **Ctrl+Shift+J** also exits. Launching
  a second copy brings the existing window forward instead of opening another mic.
- After `powershell -File .\install_desktop.ps1`, the app is installed in
  `%LOCALAPPDATA%\Programs\JARVIS` and opens at Windows sign-in **and unlock**.
  The per-user Task Scheduler entry uses the interactive desktop, runs on battery,
  and retries failed launches. No password or administrator rights are needed.
  `--headless` remains available for optional background-only use.

Desktop checks: `python -m pytest -q` covers the UI with fake audio/cloud services.
`python -m app.main --desktop-check` opens a real desktop, verifies model loading,
local controls, a calculation, a real AI reply and spoken playback, then exits.
It writes `desktop-check.json` and a screenshot to the app's logs directory.
`python smoke_pipeline.py` additionally checks actual mic access and uses
synthesized audio to test wake-word recognition and Whisper. None of these
checks establish recognition accuracy for every person's voice.
`python smoke_hearing.py` checks quiet synthetic questions through the recorder
and real Whisper, a wake phrase at one tenth amplitude, and stationary noise.
It saves a `hearing-check.json` result and removes its synthesized audio files.
`python smoke_languages.py` checks real Hindi/English recognition, Gemini replies,
spoken playback and Roman Hinglish handling using synthetic sample questions.

If a configured wake-word model fails to load, the desktop uses click-to-talk
and shows a diagnostic message instead of silently reacting to arbitrary noise.
The explicit `energy` backend and the legacy headless fallback remain available.

### Conversation and reliability improvements

- Basic arithmetic and percentages use a bounded local calculator, rather than
  relying on generated answers. Try **"what is 17 times 23"**, **"calculate 0.1
  plus 0.2"**, or **"what is 12.5 percent of 240"**. Division by zero produces a
  clear explanation; unsupported calculations go to Gemini. These answers,
  time, and date stay in context for **"repeat that"** and follow-up questions.
- She gives spoken feedback when no question was heard, recognition fails, or
  the microphone cannot be accessed. The next wake request is preserved even
  if it arrives immediately after a previous answer.
- Speech recognition processes audio in memory, preserves the volume of both
  float32 and float64 input, and normalizes supported PCM/sample rates. Silent
  or invalid input is not sent to Whisper. No temporary microphone WAV is saved.
- The acknowledgement is prepared during startup, so its first playback can
  use the phrase cache. The launcher checks the same executable it starts.
- Uses follow-up context and concise spoken answers, and acknowledges when
  current information cannot be verified. Conversation memory keeps complete
  exchanges (up to 31 messages by default) and excludes failed Gemini requests.
- Say **"repeat that"**, **"clear conversation"**, **"what time is it"**, or
  **"what's today's date"** after the wake-word acknowledgement. Time and date
  come from the PC's clock. Memory lasts for this running session only.
- Speech recognition detects the spoken language automatically. English and
  Hindi use the local multilingual Whisper model; Devanagari replies use a
  Hindi voice. Choose English or Hindi in the Language selector if automatic
  detection is unreliable for your voice. `LANGUAGE_MODE` sets the initial
  preference; the desktop remembers later changes. Hinglish accuracy depends
  on the model and recording quality.
- The microphone thread no longer blocks on conversation processing. Detection
  resets after playback and reconnects after microphone interruptions.
- Temporary Gemini connection/server errors retry once, with a 15-second
  timeout per attempt. Authentication/model/quota errors give specific spoken
  guidance, and cancelled requests cannot produce a late spoken reply.
- TTS retries synthesis once, cancels outstanding work on shutdown, removes
  incomplete audio files, and caches a small number of short phrases in memory.
- A Windows session mutex prevents multiple copies of the updated app from
  listening simultaneously. Close older JARVIS builds before using this one;
  old versions do not implement that guard. Ctrl+Shift+J remains the exit hotkey.

These changes reduce known failure modes; recognition and cloud services can
still fail. Run `python -m pytest -q` and `python smoke_pipeline.py` to check
the implementation and the real audio/AI pipeline respectively.

### Quick start on this computer

The local virtual environment, speech models, and app-local C++ runtime are
configured. Gemini uses the `google-genai` SDK and `gemini-3.6-flash`.

1. Keep your Gemini API key in `.env` as `GEMINI_API_KEY=...`, with
   `AI_PROVIDER=gemini` and `AI_MODEL=gemini-3.6-flash`.
2. Double-click `start_jarvis.bat`. The HUD opens and displays initialization
   progress. After running `install_desktop.ps1`, it opens at sign-in and unlock automatically.
3. After the greeting, say **"hey Jarvis"**, wait for **"Yes, Sir?"**, then
   speak your question. Press **Ctrl + Shift + J** to stop.

Useful checks from the project folder:

```bat
.venv\Scripts\python.exe -m app.check_gemini
.venv\Scripts\python.exe -m app.main --check
.venv\Scripts\python.exe smoke_pipeline.py
.venv\Scripts\python.exe smoke_conversation.py
```

`smoke_pipeline.py` briefly checks microphone access, then uses synthesized
test speech to verify wake detection and Whisper before requesting and
playing an AI reply. It does not verify recognition of your particular voice.
`smoke_conversation.py` verifies that the real Gemini provider remembers a
synthetic project codename from a previous turn, without using personal data.

For a fresh clone, install the dependencies and run `python -m app.setup_models`
once with internet access. Windows also needs the
[Microsoft Visual C++ x64 runtime](https://learn.microsoft.com/en-us/cpp/windows/latest-supported-vc-redist).
This computer uses an existing runtime copied into the ignored `.cache/runtime`
folder. Downloads are required for initial model setup; cached wake detection
and STT run locally afterwards. `build.bat` includes these models and any local
runtime in `dist/JARVIS/`. The editable `.env` remains next to `JARVIS.exe`.
Rebuilds assemble a fresh package before moving it into place and keep the old
folder under `.cache/previous-build-*`. This avoids OneDrive cleanup failures
damaging an existing installation. Existing packaged configuration is preserved.
Use `pip install -r requirements-lock.txt` to reproduce the versions verified
on this Windows/Python 3.12 installation, including pytest and PyInstaller.

- Opens the native desktop HUD at Windows login when its login/unlock task is installed.
- Waits for the wake word **"Jarvis"**, then listens, thinks, speaks.
- Native animated desktop window, with no browser or console window.

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

1. From this repository, run `powershell -File .\install_desktop.ps1` after
   building. This copies the app to `%LOCALAPPDATA%\Programs\JARVIS`, adds a
   Start menu shortcut and registers launch at sign-in and unlock.
2. Open **JARVIS** from the Start menu. The native animated window opens, the
   greeting plays through your speakers, and JARVIS waits for "hey Jarvis".
3. Press **Ctrl + Shift + J** at any time for an emergency shutdown.

JARVIS stores its logs and TTS cache in
`%APPDATA%\JARVIS\` when running as a packaged EXE, and in `./logs/`
and `./tts_cache/` when running from source.

### Optional: register auto-start

```bat
python -m app.system.startup --install
```

This registers the current user's login/unlock task for the installed EXE (or
the `dist` EXE if no local installation exists). For an installation outside
OneDrive, run `powershell -File .\install_desktop.ps1` after building. To remove:

```bat
python -m app.system.startup --uninstall
```

---

## Configuration

Copy `.env.example` to `.env` and edit:

```bat
copy .env.example .env
```

The packaged EXE looks for `.env` next to `JARVIS.exe`, or you can point it elsewhere via
`JARVIS_ENV_FILE`.

Key values:

| Variable | Default | Purpose |
|---|---|---|
| `AI_PROVIDER` | `mock` | `openai`, `gemini`, or `mock` |
| `AI_MODEL` | (provider default) | e.g. `gpt-4o-mini`, `gemini-3.6-flash` |
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
- **`gemini`** — requires `GEMINI_API_KEY`. Uses the Google Gen
  AI SDK.

Set `AI_PROVIDER` to the one you want. JARVIS does **not** silently
fall back if a key is missing — the failure surfaces so the user can
fix configuration.

---

## Wake Word

The default backend is **openWakeWord** — fully local, no API key,
no signup. JARVIS listens for **"hey jarvis"** by default using a
pretrained model downloaded by `python -m app.setup_models`.

Two backends are available; pick one via `WAKEWORD_BACKEND`:

1. **`openwakeword`** (default) — fully local. Uses
   [`openwakeword`](https://github.com/dscripka/openWakeWord) with
   `onnxruntime` as the inference backend. The package ships several
   pretrained model definitions — `hey_jarvis`, `alexa`, `hey_mycroft`,
   `hey_rhasspy`, `timer`, `weather` — set `OPENWAKEWORD_MODEL` to
   any of them, or to a path to a custom `.tflite`/`.onnx` model.
   After the initial model download, no internet, API key, or account is required.
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

openWakeWord provides a pretrained `hey_jarvis` model, so
**no training is required** out of the box. If you find its accuracy
unsatisfactory on your voice/mic, you can train a custom model by
following the [openWakeWord training notebook](https://github.com/dscripka/openWakeWord/blob/main/notebooks/train_custom_model.ipynb),
export the resulting `.tflite` (or `.onnx`), and set
`OPENWAKEWORD_MODEL=C:\path\to\your_model.tflite`.

---

## STT (Speech-to-Text)

Uses **faster-whisper** locally.

- Model: `base` (int8, CPU). Loaded once on startup and held in
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

JARVIS starts at sign-in (after 10 seconds) and workstation unlock (after
3 seconds) using a per-user Windows scheduled task. Unlocking an existing
session is different from a new sign-in; both are handled.

```bat
python -m app.system.startup --install     :: install
python -m app.system.startup --status      :: check
python -m app.system.startup --uninstall   :: remove
```

The task launches the native EXE on your interactive desktop without a console
or stored password. Battery power and network availability do not block the
window from opening. `python -m app.system.startup --run` exercises the same
registered action without signing you out. `--status` reports the actual task,
its target, enabled flag, last result, and trigger XML. The old Startup shortcut
is removed only after the task is successfully registered.

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
pip install -r requirements.txt pytest pyinstaller
copy .env.example .env
:: edit .env
python -m app.setup_models    :: download local models once (internet required)
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

After building, install the app outside OneDrive and register automatic startup:

```powershell
.\install_desktop.ps1
```

Close the installed app before updating. The installer preserves its `.env`,
keeps the previous installation as a backup, and adds a Start menu shortcut.
`build.ps1 -Clean` clears packaging caches when native dependencies change.

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
- **Not opening at sign-in/unlock** — run `python -m app.system.startup --status`.
  Verify the task is enabled and its target exists. Use `--run` to test the
  registered launch action, or rerun `install_desktop.ps1` to repair the local
  installation and task. Logs are under `%APPDATA%\JARVIS\logs`.

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
