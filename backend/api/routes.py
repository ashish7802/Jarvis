from __future__ import annotations

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse

from backend.config.settings import get_settings
from backend.core.confidence import ConfidenceEngine
from backend.core.conversation import ConversationManager
from backend.core.intent_detection import IntentDetector
from backend.core.prompt_manager import PromptManager
from backend.schemas.chat import ChatRequest, ChatResponse, ConfidenceResult, IntentResult, StreamingChunk
from backend.schemas.health import HealthResponse, VersionResponse
from backend.services.llm_service import LLMService
from backend.voice.schemas import SpeechRequest, SpeechResponse, TranscriptionRequest, TranscriptionResponse, VoiceInfo, WakeRequest, WakeResponse, WakeStatus
from backend.voice.speech_to_text import TranscriptionService
from backend.voice.text_to_speech import TextToSpeechService
from backend.voice.voice_controller import VoiceController
from backend.voice.voice_pipeline import VoicePipeline
from backend.voice.wake_service import WakeService


def get_llm_service() -> LLMService:
    """Create an LLM service instance for dependency injection."""
    return LLMService()


def get_transcription_service() -> TranscriptionService:
    """Create a transcription service instance for dependency injection."""
    return TranscriptionService()


def get_tts_service() -> TextToSpeechService:
    """Create a text-to-speech service instance for dependency injection."""
    return TextToSpeechService()


def get_wake_service() -> WakeService:
    """Create a wake word service instance for dependency injection."""
    return WakeService()


def get_voice_controller() -> VoiceController:
    """Create a voice controller for dependency injection."""
    return VoiceController(pipeline=VoicePipeline())


router = APIRouter()


@router.get("/health", response_model=HealthResponse)
async def health_check() -> HealthResponse:
    """Return the application health summary."""
    settings = get_settings()
    return HealthResponse(status="ok", app_name=settings.app_name, environment=settings.app_env)


@router.get("/version", response_model=VersionResponse)
async def version() -> VersionResponse:
    """Return the application version."""
    settings = get_settings()
    return VersionResponse(app_name=settings.app_name, version="0.1.0")


@router.get("/llm/health")
async def llm_health(service: LLMService = Depends(get_llm_service)) -> dict[str, bool]:
    """Perform a basic health check against the configured LLM provider."""
    try:
        healthy = await service.health_check()
    except Exception:
        healthy = False
    return {"healthy": healthy}


@router.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest, service: LLMService = Depends(get_llm_service)) -> ChatResponse:
    """Handle a standard chat request with intent and confidence analysis."""
    settings = get_settings()
    prompt_manager = PromptManager()
    detector = IntentDetector()
    confidence_engine = ConfidenceEngine()
    conversation = ConversationManager(max_history=8)
    conversation.add_user_message(request.message)

    intent = await detector.detect(request.message)
    confidence = await confidence_engine.evaluate(request.message, intent)

    system_prompt = prompt_manager.get_prompt("system")
    developer_prompt = prompt_manager.get_prompt("developer")
    assistant_prompt = prompt_manager.get_prompt("assistant")
    conversation.set_system_prompt(f"{system_prompt}\n{developer_prompt}\n{assistant_prompt}")

    prompt = f"{conversation.build_messages()[-1]['content']}\n\nUser: {request.message}"
    try:
        content = await service.generate_completion(
            prompt,
            model=request.model or settings.default_model,
            temperature=request.temperature,
            max_tokens=request.max_tokens,
            top_p=request.top_p,
        )
    except Exception:
        content = "I’m unable to respond right now because the provider is unavailable."

    if confidence.uncertainty and intent.intent in {"command", "conversation"}:
        content = "I can help with that, but I need a bit more detail to respond precisely."

    conversation.add_assistant_message(content)
    return ChatResponse(
        content=content,
        intent=intent,
        confidence=confidence,
        provider="groq",
        model=request.model or settings.default_model,
        metadata={"stream": request.stream},
    )


@router.post("/chat/stream")
async def chat_stream(request: ChatRequest, service: LLMService = Depends(get_llm_service)) -> StreamingResponse:
    """Stream chat chunks back to the client."""
    settings = get_settings()

    async def generator() -> None:
        try:
            chunks = await service.stream_tokens(
                request.message,
                model=request.model or settings.default_model,
                temperature=request.temperature,
                max_tokens=request.max_tokens,
                top_p=request.top_p,
            )
            for chunk in chunks:
                yield f"data: {chunk.model_dump_json()}\n\n"
        except Exception:
            yield "data: {\"content\": \"\", \"done\": true}\n\n"

    return StreamingResponse(generator(), media_type="text/event-stream")


@router.post("/chat/intent", response_model=IntentResult)
async def chat_intent(request: ChatRequest) -> IntentResult:
    """Return the detected intent for a message."""
    detector = IntentDetector()
    return await detector.detect(request.message)


@router.post("/chat/clarify", response_model=ConfidenceResult)
async def chat_clarify(request: ChatRequest) -> ConfidenceResult:
    """Return a conservative confidence signal for ambiguous messages."""
    detector = IntentDetector()
    confidence_engine = ConfidenceEngine()
    intent = await detector.detect(request.message)
    confidence = await confidence_engine.evaluate(request.message, intent)
    if confidence.score < 0.5:
        return ConfidenceResult(score=confidence.score, reason="Please clarify your request so I can respond accurately.", uncertainty=True)
    return confidence


@router.get("/models")
async def list_models() -> dict[str, list[str]]:
    """Return the currently supported model identifiers."""
    settings = get_settings()
    return {"models": [settings.default_model, "llama-3.3-70b-versatile", "llama-3.1-8b-instant"]}


@router.post("/voice/transcribe", response_model=TranscriptionResponse)
async def transcribe_voice(request: TranscriptionRequest, service: object = None) -> TranscriptionResponse:
    """Transcribe audio bytes into text."""
    if not request.audio_bytes:
        raise ValueError("audio_bytes is required")
    if isinstance(request.audio_bytes, str):
        payload = request.audio_bytes.encode("utf-8")
    elif isinstance(request.audio_bytes, (bytes, bytearray)):
        payload = bytes(request.audio_bytes)
    else:
        payload = str(request.audio_bytes).encode("utf-8")
    active_service = service if service is not None else get_transcription_service()
    return await active_service.transcribe_audio(payload, language=request.language)


@router.post("/voice/transcribe-file", response_model=TranscriptionResponse)
async def transcribe_voice_file(request: TranscriptionRequest, service: object = None) -> TranscriptionResponse:
    """Transcribe an audio file into text."""
    if not request.audio_path:
        raise ValueError("audio_path is required")
    active_service = service if service is not None else get_transcription_service()
    return await active_service.transcribe_file(request.audio_path, language=request.language)


@router.get("/voice/models")
async def voice_models() -> dict[str, list[str]]:
    """Return the supported Whisper model identifiers."""
    settings = get_settings()
    return {"models": ["tiny", "base", "small", "medium", "large-v3"], "default": settings.whisper_model}


@router.post("/voice/speak", response_model=SpeechResponse)
async def speak(request: SpeechRequest, service: object = None) -> SpeechResponse:
    """Convert text to speech and return audio bytes."""
    active_service = service or get_tts_service()
    return await active_service.speak(request.text, voice=request.voice, rate=request.rate, volume=request.volume, pitch=request.pitch, file_format=request.file_format)


@router.post("/voice/save", response_model=SpeechResponse)
async def save_speech(request: SpeechRequest, service: object = None) -> SpeechResponse:
    """Save synthesized speech to a file and return metadata."""
    active_service = service or get_tts_service()
    if not request.output_path:
        raise ValueError("output_path is required")
    return await active_service.save_to_file(request.text, request.output_path, voice=request.voice, rate=request.rate, volume=request.volume, pitch=request.pitch, file_format=request.file_format)


@router.get("/voice/voices")
async def list_voice_options(service: object = None) -> dict[str, list[dict[str, str | None]]]:
    """Return the supported TTS voices."""
    active_service = service or get_tts_service()
    voices = active_service.list_voices()
    return {"voices": [voice.model_dump() for voice in voices]}


@router.post("/voice/wake/start", response_model=WakeResponse)
async def wake_start(request: WakeRequest, service: object = None) -> WakeResponse:
    """Start isolated wake word listening."""
    active_service = service or get_wake_service()
    event = await active_service.start()
    return WakeResponse(success=event is not None, message="wake listener started", status=active_service.get_status().model_dump_json(), event=event.__dict__ if event else None)


@router.post("/voice/wake/stop", response_model=WakeResponse)
async def wake_stop(service: object = None) -> WakeResponse:
    """Stop isolated wake word listening."""
    active_service = service or get_wake_service()
    await active_service.stop()
    return WakeResponse(success=True, message="wake listener stopped", status="stopped", event=None)


@router.post("/voice/wake/pause", response_model=WakeResponse)
async def wake_pause(service: object = None) -> WakeResponse:
    """Pause isolated wake word listening."""
    active_service = service or get_wake_service()
    await active_service.pause()
    return WakeResponse(success=True, message="wake listener paused", status="paused", event=None)


@router.post("/voice/wake/resume", response_model=WakeResponse)
async def wake_resume(service: object = None) -> WakeResponse:
    """Resume isolated wake word listening."""
    active_service = service or get_wake_service()
    await active_service.resume()
    return WakeResponse(success=True, message="wake listener resumed", status="running", event=None)


@router.get("/voice/wake/status", response_model=WakeStatus)
async def wake_status(service: object = None) -> WakeStatus:
    """Return the current wake listener status."""
    active_service = service or get_wake_service()
    return active_service.get_status()


@router.post("/voice/wake/test", response_model=WakeResponse)
async def wake_test(request: WakeRequest, service: object = None) -> WakeResponse:
    """Smoke-test the wake detector without starting speech recognition."""
    active_service = service or get_wake_service()
    event = await active_service.test_detection()
    return WakeResponse(success=event is not None, message="wake test completed", status="tested", event=event.__dict__ if event else None)


@router.post("/voice/start")
async def voice_start(controller: object = None) -> dict[str, str]:
    """Start the voice pipeline."""
    active_controller = controller or get_voice_controller()
    await active_controller.start()
    return {"status": "running"}


@router.post("/voice/stop")
async def voice_stop(controller: object = None) -> dict[str, str]:
    """Stop the voice pipeline."""
    active_controller = controller or get_voice_controller()
    await active_controller.stop()
    return {"status": "stopped"}


@router.post("/voice/run-once")
async def voice_run_once(controller: object = None) -> dict[str, Any]:
    """Run a single voice interaction cycle."""
    active_controller = controller or get_voice_controller()
    return await active_controller.run_once()


@router.get("/voice/status")
async def voice_status(controller: object = None) -> dict[str, Any]:
    """Return the current voice pipeline status."""
    active_controller = controller or get_voice_controller()
    return active_controller.status()


__all__ = ["router"]
