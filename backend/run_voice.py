import asyncio

from backend.voice.voice_controller import VoiceController
from backend.voice.voice_pipeline import VoicePipeline


async def main() -> None:
    pipeline = VoicePipeline()
    controller = VoiceController(pipeline=pipeline)
    print("Waiting for wake word...")
    print("Say:")
    print("Hey Altron")
    await controller.start()
    print("Listening...")
    print("Recognizing...")
    print("Thinking...")
    await controller.run_once()
    print("Speaking...")
    print("Done.")
    await controller.stop()


if __name__ == "__main__":
    asyncio.run(main())
