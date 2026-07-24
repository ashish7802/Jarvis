class VoiceError(Exception):
    """Base exception for voice processing errors."""


class MicrophoneError(VoiceError):
    """Raised when microphone capture is unavailable."""


class AudioFormatError(VoiceError):
    """Raised when audio data is unsupported."""


class TranscriptionError(VoiceError):
    """Raised when speech-to-text processing fails."""


class ModelLoadError(VoiceError):
    """Raised when the Faster-Whisper model cannot be loaded."""


class SpeechError(VoiceError):
    """Raised when text-to-speech synthesis fails."""
