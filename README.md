# Altron

A production-ready AI voice assistant built with FastAPI, modern LLMs, speech recognition, text-to-speech, and multi-agent orchestration.

Altron is designed as an extensible AI assistant capable of understanding user intent, orchestrating AI agents, managing conversations, and integrating external tools through a scalable backend architecture.

---

## Features

- 🤖 Multi-Agent AI Architecture
- 🧠 LLM Integration (Groq, OpenAI, Gemini)
- 🎤 Speech-to-Text Pipeline
- 🔊 Text-to-Speech Responses
- 💬 Conversation Management
- 🛠️ Tool Calling & AI Workflows
- 🎯 Intent Detection
- 📊 Confidence Evaluation
- ❓ Clarification Handling
- ⚡ Streaming Chat Responses
- 📦 REST API with FastAPI
- 🐳 Docker Support
- 📝 Prompt Template Management

---

## Tech Stack

- Python
- FastAPI
- Groq API
- OpenAI API
- Google Gemini
- Edge-TTS
- Faster Whisper
- SQLAlchemy
- PostgreSQL
- Redis
- Docker

---

## API Endpoints

- Chat API
- Streaming API
- Intent Detection
- Clarification API
- Model Management
- Health Check

---

## Project Structure

```
backend/
api/
core/
providers/
services/
voice/
tests/
```

---

## Installation

```bash
git clone https://github.com/ashish7802/altron.git

cd altron

python -m venv .venv

pip install -r requirements.txt
```

---

## Run

```bash
uvicorn backend.main:app --reload
```

---

## Testing

```bash
pytest -q
```

---

## Roadmap

- [x] FastAPI Backend
- [x] LLM Integration
- [x] Prompt Engine
- [x] Intent Detection
- [x] Conversation Management
- [x] Voice Pipeline
- [ ] Memory System
- [ ] Plugin Marketplace
- [ ] Desktop Client
- [ ] Agent Collaboration

---

## License

MIT License
