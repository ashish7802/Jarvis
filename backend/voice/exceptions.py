from __future__ import annotations


class VoiceError(Exception):
    """Base exception for all voice module errors."""
    pass


class MicrophoneError(VoiceError):
    """Raised when there is an issue capturing audio from the microphone."""
    pass


class AudioPlaybackError(VoiceError):
    """Raised when audio playback fails."""
    pass


class WakeWordError(VoiceError):
    """Raised when wake word detection fails or is misconfigured."""
    pass


class STTError(VoiceError):
    """Raised when speech-to-text transcription fails."""
    pass


class TTSError(VoiceError):
    """Raised when text-to-speech synthesis fails."""
    pass


class ModelLoadError(VoiceError):
    """Raised when loading a voice model fails."""
    pass


class TranscriptionError(STTError):
    """Raised when transcription fails."""
    pass


class SpeechError(TTSError):
    """Raised when speech synthesis fails."""
    pass
