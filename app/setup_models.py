"""Download the local speech models once before starting JARVIS."""

def main():
    from openwakeword.utils import download_models
    from app.stt.service import STTService
    from app.wakeword.detector import OpenWakeWordDetector
    from app.config import get_settings

    print("Downloading wake-word models...", flush=True)
    download_models(model_names=["hey_jarvis_v0.1"])
    wake = OpenWakeWordDetector()
    wake._load_model()
    print("Wake-word model ready.", flush=True)
    settings = get_settings()
    STTService(model_size=settings.stt_model, language=settings.stt_language,
               beam_size=settings.stt_beam_size)._ensure_model()
    print("Whisper model ready.", flush=True)


if __name__ == "__main__":
    main()
