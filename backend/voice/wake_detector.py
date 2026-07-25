from __future__ import annotations

import os
import time
from typing import Any

from loguru import logger

from backend.voice.exceptions import MicrophoneError, VoiceError, WakeWordError


class WakeDetector:
    """Wake detector wrapper implementing official OpenWakeWord streaming inference flow."""

    def __init__(
        self,
        *,
        engine: str | None = None,
        model: str | None = None,
        threshold: float = 0.5,
        device: str | None = None,
    ) -> None:
        self.engine = engine or "openwakeword"
        self.model = model or "hey_jarvis"
        self.threshold = threshold
        self.device = device
        self._model: Any = None
        self._initialized = False

    async def initialize(self) -> None:
        if self._initialized:
            return

        print("Loading OpenWakeWord...")
        openwakeword_mod = None
        try:
            import openwakeword
            openwakeword_mod = openwakeword
            print("[OK] OpenWakeWord initialized")
        except ImportError as exc:
            err_msg = f"ONNX/OpenWakeWord import failure: {exc}"
            logger.error(err_msg)
            print(f"[FAIL] OpenWakeWord failed: {err_msg}")
            raise WakeWordError(err_msg) from exc
        except Exception as exc:
            err_msg = f"ONNX Runtime error: {exc}"
            logger.error(err_msg)
            print(f"[FAIL] OpenWakeWord failed: {err_msg}")
            raise WakeWordError(err_msg) from exc

        print("Loading microphone...")
        try:
            import sounddevice as sd
            devices = sd.query_devices()
            input_devices = [d for d in devices if d.get("max_input_channels", 0) > 0]
            if not input_devices:
                raise MicrophoneError("No input audio devices found on system")
            print("[OK] Microphone ready")
        except Exception as exc:
            err_msg = f"Microphone error: {exc}"
            logger.error(err_msg)
            print(f"[FAIL] Microphone failed: {err_msg}")
            raise MicrophoneError(err_msg) from exc

        print("Loading wake model...")
        try:
            from openwakeword.model import Model
            model_target = self.model
            models_dir = os.path.join(os.path.dirname(openwakeword_mod.__file__), "resources", "models")
            if not os.path.exists(models_dir) or not any(f.startswith(model_target) for f in os.listdir(models_dir)):
                openwakeword_mod.utils.download_models()

            self._model = Model(wakeword_models=[model_target], inference_framework="onnx")
            print("[OK] Model loaded")
        except Exception as exc:
            err_msg = f"Wake model load failure: {exc}"
            logger.error(err_msg)
            print(f"[FAIL] Model failed: {err_msg}")
            raise WakeWordError(err_msg) from exc

        self._initialized = True
        logger.info("engine initialized", extra={"engine": self.engine, "model": self.model})

    async def predict(self, audio_chunk: bytes | Any) -> float:
        if not self._initialized:
            await self.initialize()
        if self._model is None:
            raise VoiceError("Wake model is not initialized")

        import numpy as np
        
        # 1. Correct Input Type: Convert raw audio chunk to 1D int16 NumPy array
        if isinstance(audio_chunk, (bytes, bytearray)):
            audio_data = np.frombuffer(audio_chunk, dtype=np.int16)
        elif isinstance(audio_chunk, np.ndarray):
            audio_data = audio_chunk.astype(np.int16).reshape(-1)
        else:
            audio_data = np.asarray(audio_chunk, dtype=np.int16).reshape(-1)

        # Compute audio frame metrics for diagnostics
        dtype_str = str(audio_data.dtype)
        sample_rate = 16000
        frame_len = len(audio_data)
        min_val = int(audio_data.min()) if frame_len > 0 else 0
        max_val = int(audio_data.max()) if frame_len > 0 else 0
        rms_val = float(np.sqrt(np.mean(audio_data.astype(np.float32) ** 2))) if frame_len > 0 else 0.0

        # 2 & 4. Official OpenWakeWord Inference Call directly on raw audio data
        raw_prediction = self._model.predict(audio_data)

        score = 0.0
        if isinstance(raw_prediction, dict):
            if self.model in raw_prediction:
                score = float(raw_prediction[self.model])
            else:
                for key in raw_prediction:
                    if self.model in key or key in self.model:
                        self.model = key
                        score = float(raw_prediction[key])
                        break
                else:
                    if raw_prediction:
                        key = list(raw_prediction.keys())[0]
                        self.model = key
                        score = float(raw_prediction[key])
        elif isinstance(raw_prediction, (float, int)):
            score = float(raw_prediction)

        detected_str = "YES" if score >= self.threshold else "NO"

        print("------------------------------------------")
        print(f"dtype: {dtype_str}")
        print(f"Sample Rate: {sample_rate} Hz")
        print(f"Frame Length: {frame_len} samples ({len(audio_chunk)} bytes)")
        print(f"RMS Level: {rms_val:.2f}")
        print(f"Min/Max Samples: min={min_val}, max={max_val}")
        print(f"Raw Prediction Dict: {raw_prediction}")
        print(f"Model: {self.model}")
        print(f"Score: {score:.5f}")
        print(f"Threshold: {self.threshold:.2f}")
        print(f"Detected: {detected_str}")
        print("------------------------------------------")

        if score >= self.threshold:
            print("\nWake word detected\n")

        logger.info("wake detection score", extra={"confidence": score, "model": self.model, "rms": rms_val})
        return score

    async def close(self) -> None:
        self._initialized = False
        self._model = None
