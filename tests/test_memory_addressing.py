import os

import pytest

from app.assistant.addressing import is_directed_to_jarvis
from app.assistant.memory import ConversationMemory
from app.audio.devices import InputDevice, recommended_input_device


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("Jarvis, are you there?", True),
        ("Can you explain this error?", True),
        ("Mujhe batao kya hua", True),
        ("Batao, kya time hua hai?", True),
        ("The meeting is tomorrow", False),
        ("I wonder what that person meant", False),
        ("I asked him to explain the answer", False),
        ("We can you believe what happened", False),
        ("", False),
    ],
)
def test_local_addressing_gate(text, expected):
    assert is_directed_to_jarvis(text) is expected


def test_recommended_device_prefers_physical_microphone_array():
    devices = [
        InputDevice("WASAPI\nVoice Changer", "Voice Changer Virtual Audio Device", "WASAPI", 1),
        InputDevice("WASAPI\nRealtek Mic", "Realtek Microphone", "WASAPI", 2),
        InputDevice("WASAPI\nIntel Array", "Microphone Array (Intel)", "WASAPI", 3),
    ]
    assert recommended_input_device(devices) == "WASAPI\nIntel Array"


@pytest.mark.skipif(os.name != "nt", reason="Conversation encryption uses Windows DPAPI")
def test_conversation_memory_is_encrypted_persistent_and_clearable(tmp_path):
    memory_path = tmp_path / "conversation.sqlite3"
    memory = ConversationMemory(memory_path)
    memory.add_turn("Private prompt 9842", "Private answer 7361")
    assert memory.count() == 1
    assert memory.recent_turns() == [("Private prompt 9842", "Private answer 7361")]
    raw_database = memory_path.read_bytes()
    assert b"Private prompt 9842" not in raw_database
    assert b"Private answer 7361" not in raw_database
    memory.clear()
    assert memory.count() == 0
    assert memory.recent_turns() == []
