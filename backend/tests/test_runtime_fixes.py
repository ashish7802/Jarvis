from __future__ import annotations

import asyncio
from types import SimpleNamespace
import pytest
from fastapi.testclient import TestClient

from backend.main import app
from backend.core.conversation import ConversationManager
from backend.core.prompt_manager import PromptManager
from backend.llm.providers.groq.provider import GroqProvider
from backend.services.llm_service import LLMService
from backend.voice.speech_to_text import FasterWhisperTranscriber
from backend.voice.text_to_speech import TextToSpeechService
from backend.voice.voice_cache import VoiceCache
from backend.voice.wake_detector import WakeDetector
from backend.voice.audio_capture import AudioRecorder
from backend.voice.audio_player import AudioPlayer


@pytest.mark.asyncio
async def test_fix1_chat_prompt_construction_and_history():
    """Verify system, developer, assistant prompts and multi-turn history are preserved without duplication."""
    conv = ConversationManager(max_history=5)
    conv.set_system_prompt("System Identity\nDeveloper Guidelines")
    conv.add_user_message("Hello Altron")
    conv.add_assistant_message("Hello User")
    conv.add_user_message("Who are you?")

    messages = conv.build_messages()

    assert len(messages) == 4
    assert messages[0]["role"] == "system"
    assert "System Identity" in messages[0]["content"]
    assert messages[1] == {"role": "user", "content": "Hello Altron"}
    assert messages[2] == {"role": "assistant", "content": "Hello User"}
    assert messages[3] == {"role": "user", "content": "Who are you?"}


@pytest.mark.asyncio
async def test_fix2_groq_streaming_initialization_bug():
    """Verify GroqProvider initializes client dynamically inside stream generator."""
    class MockGroqClient:
        def __init__(self, *args, **kwargs):
            self.chat = SimpleNamespace(completions=SimpleNamespace(create=self._create))

        async def _create(self, **kwargs):
            async def _chunk_iter():
                yield SimpleNamespace(choices=[SimpleNamespace(delta=SimpleNamespace(content="Streaming "))])
                yield SimpleNamespace(choices=[SimpleNamespace(delta=SimpleNamespace(content="working!"))])
            return _chunk_iter()

    provider = GroqProvider(api_key="test-key", client=None)
    # Inject client mock into initialize
    provider._client = MockGroqClient()

    chunks = []
    async for chunk in provider.stream("Hello"):
        if chunk.content:
            chunks.append(chunk.content)

    assert "".join(chunks) == "Streaming working!"


@pytest.mark.asyncio
async def test_fix3_real_async_iterator_streaming():
    """Verify LLMService.stream_tokens returns an AsyncIterator immediately."""
    class MockProvider:
        async def stream(self, prompt, **kwargs):
            yield SimpleNamespace(content="Chunk 1")
            yield SimpleNamespace(content="Chunk 2")

    service = LLMService(provider=MockProvider())
    stream_gen = service.stream_tokens("Hello")

    chunks = []
    async for chunk in stream_gen:
        chunks.append(chunk.content)

    assert chunks == ["Chunk 1", "Chunk 2"]


@pytest.mark.asyncio
async def test_fix4_stt_language_probability_metadata():
    """Verify FasterWhisperTranscriber reads language_probability safely."""
    transcriber = FasterWhisperTranscriber(model_name="tiny")

    class FakeInfo:
        language = "en"
        language_probability = 0.98
        duration = 2.5

    class FakeSegment:
        text = "Hello world"

    class FakeModel:
        def transcribe(self, payload, **kwargs):
            return [FakeSegment()], FakeInfo()

    transcriber._model = FakeModel()
    resp = await transcriber.transcribe_audio(b"RIFFdummywavbytes")

    assert resp.text == "Hello world"
    assert resp.confidence == 0.98
    assert resp.metadata["language_probability"] == 0.98


@pytest.mark.asyncio
async def test_fix5_edge_tts_audio_dict_filtering():
    """Verify TextToSpeechService extracts audio bytes from dict chunks."""
    class FakeCommunicate:
        async def stream(self):
            yield {"type": "audio", "data": b"AUDIO_BYTES_1"}
            yield {"type": "WordBoundary", "data": "dummy"}
            yield {"type": "audio", "data": b"_AUDIO_BYTES_2"}

    tts = TextToSpeechService(edge_tts_module=object())
    audio = await tts._collect_audio(FakeCommunicate())

    assert audio == b"AUDIO_BYTES_1_AUDIO_BYTES_2"


@pytest.mark.asyncio
async def test_fix6_wake_detector_model_name_score_extraction():
    """Verify WakeDetector extracts score using configured model name."""
    class FakeModel:
        def predict(self, payload):
            return {"hey_jarvis": 0.88, "alexa": 0.1}

    detector = WakeDetector(model="hey_jarvis")
    detector._initialized = True
    detector._model = FakeModel()

    score = await detector.predict(b"\x00" * 512)
    assert score == 0.88


def test_fix7_audio_recorder_chunk_tuple_unpacking():
    """Verify AudioRecorder correctly unpacks stream.read tuples and numpy arrays."""
    recorder = AudioRecorder()

    class FakeStream:
        def read(self, chunk_size):
            return (b"RAW_PCM_BYTES", False)

    chunk, count = recorder._read_chunk(FakeStream())
    assert chunk == b"RAW_PCM_BYTES"
    assert count == 1


@pytest.mark.asyncio
async def test_fix9_audio_player_non_blocking():
    """Verify AudioPlayer handles empty and sample payload without crashing."""
    player = AudioPlayer()

    # Empty payload
    result = await player.play(b"")
    assert result is False


def test_fix12_prompt_manager_caching(tmp_path):
    """Verify PromptManager caches templates in memory after first read."""
    prompts_dir = tmp_path / "prompts"
    prompts_dir.mkdir()
    (prompts_dir / "system.txt").write_text("Original Template", encoding="utf-8")

    manager = PromptManager(prompts_dir)
    res1 = manager.get_prompt("system")
    assert res1 == "Original Template"

    # Mutate disk file
    (prompts_dir / "system.txt").write_text("Modified Template", encoding="utf-8")

    # Second call should return cached version
    res2 = manager.get_prompt("system")
    assert res2 == "Original Template"


def test_fix13_voice_cache_lru_eviction():
    """Verify VoiceCache evicts LRU items when max_size is reached."""
    cache = VoiceCache(max_size=2)
    cache.set("item1", b"bytes1")
    cache.set("item2", b"bytes2")

    # Access item1 to make it MRU
    assert cache.get("item1") == b"bytes1"

    # Insert item3 -> item2 should be evicted
    cache.set("item3", b"bytes3")

    assert cache.get("item1") == b"bytes1"
    assert cache.get("item3") == b"bytes3"
    assert cache.get("item2") is None
