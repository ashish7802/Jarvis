import asyncio
import sys

from loguru import logger

from backend.voice.voice_controller import VoiceController
from backend.voice.voice_pipeline import VoicePipeline


async def main() -> None:
    pipeline = VoicePipeline()
    controller = VoiceController(pipeline=pipeline)
    print("==========================================")
    print(" Altron Assistant Voice Loop Active ")
    print(" Say 'Hey Altron' to trigger wake word ")
    print(" Press Ctrl+C to stop ")
    print("==========================================")
    await controller.start()

    try:
        while True:
            print("\n[Waiting for wake word...]")
            res = await controller.run_once()
            if res.get("wake_detected"):
                print(f" Recognized Speech: '{res.get('recognized_text')}'")
                print(f" Altron Response: '{res.get('llm_response')}'")
            await asyncio.sleep(0.5)
    except KeyboardInterrupt:
        print("\nStopping Altron Voice Assistant...")
    finally:
        await controller.stop()
        print("Stopped.")


if __name__ == "__main__":
    asyncio.run(main())
