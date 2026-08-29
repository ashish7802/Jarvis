from __future__ import annotations

import numpy as np

from app.wakeword.detector import EnergyGateWakeWord, OpenWakeWordDetector, build_wake_word


def test_build_returns_none_when_disabled():
    assert build_wake_word(enabled=False, keyword="jarvis") is None


def test_energy_gate_constructs_without_audio():
    w = EnergyGateWakeWord(keyword="jarvis")
    assert w.keyword == "jarvis"


def test_energy_gate_start_stop(monkeypatch):
    # Patch sounddevice so this test is hermetic.
    import app.wakeword.detector as mod

    class FakeStream:
        def __init__(self, *a, **kw):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def read(self, n):
            return np.zeros((n, 1), dtype="int16"), False

    monkeypatch.setattr(mod.sd, "InputStream", FakeStream)
    w = EnergyGateWakeWord(keyword="jarvis")
    w.start()
    w.stop()
    assert w._thread is None or not w._thread.is_alive()  # noqa: SLF001


def test_build_defaults_to_openwakeword(monkeypatch):
    """Default backend is openWakeWord when it loads successfully."""
    # Make sure we don't actually load the real model in CI — patch
    # OpenWakeWordDetector so it just constructs a sentinel.
    import app.wakeword.detector as mod

    class FakeOww:
        name = "openwakeword"

        def __init__(self, *a, **kw):
            self.started = False

        def start(self):
            self.started = True

        def stop(self):
            self.started = False

        def set_enabled(self, _enabled):
            pass

        def set_callback(self, _cb):
            pass

    monkeypatch.setattr(mod, "OpenWakeWordDetector", FakeOww)
    w = build_wake_word(enabled=True, keyword="jarvis")
    assert isinstance(w, FakeOww)


def test_build_falls_back_to_energy_when_openwakeword_fails(monkeypatch):
    """If the openWakeWord model fails to load, fall back to energy-gate."""
    import app.wakeword.detector as mod

    def _raising_ctor(*a, **kw):
        raise RuntimeError("no model")

    monkeypatch.setattr(mod, "OpenWakeWordDetector", _raising_ctor)
    w = build_wake_word(enabled=True, keyword="jarvis")
    assert isinstance(w, EnergyGateWakeWord)


def test_build_honours_explicit_energy_backend(monkeypatch):
    """Setting WAKEWORD_BACKEND=energy uses the energy-gate directly."""
    w = build_wake_word(
        enabled=True, keyword="jarvis", wakeword_backend="energy"
    )
    assert isinstance(w, EnergyGateWakeWord)


def test_build_honours_explicit_porcupine_backend_with_key(monkeypatch):
    """Porcupine backend is still reachable when a key + package exist."""
    import app.wakeword.detector as mod

    class FakePorcupine:
        name = "porcupine"

        def __init__(self, *a, **kw):
            pass

        def start(self):
            pass

        def stop(self):
            pass

        def set_enabled(self, _enabled):
            pass

        def set_callback(self, _cb):
            pass

    monkeypatch.setattr(mod, "PorcupineWakeWord", FakePorcupine)
    w = build_wake_word(
        enabled=True,
        keyword="jarvis",
        wakeword_backend="porcupine",
        porcupine_access_key="dummy",
    )
    assert isinstance(w, FakePorcupine)


def test_build_porcupine_backend_falls_back_to_energy_when_key_missing(monkeypatch):
    """Porcupine requested but no key → try openWakeWord, fall back to energy."""
    import app.wakeword.detector as mod

    def _raising_ctor(*a, **kw):
        raise RuntimeError("no model")

    monkeypatch.setattr(mod, "OpenWakeWordDetector", _raising_ctor)
    w = build_wake_word(
        enabled=True,
        keyword="jarvis",
        wakeword_backend="porcupine",
        porcupine_access_key="",
    )
    assert isinstance(w, EnergyGateWakeWord)


def test_openwakeword_constructor_attributes():
    """The detector stores its config without loading the model."""
    w = OpenWakeWordDetector(
        model="hey_jarvis", threshold=0.42, patience_frames=3
    )
    assert w.model == "hey_jarvis"
    assert w.threshold == 0.42
    assert w.patience_frames == 3
    assert w._oww_model is None  # noqa: SLF001 - lazy load


def test_openwakeword_disabled_does_not_call_callback(monkeypatch):
    """While disabled, even loud audio must not fire the callback."""
    import app.wakeword.detector as mod

    class FakeOwwModel:
        def predict(self, x):
            return {self.label: 0.99}

    w = OpenWakeWordDetector(model="hey_jarvis", threshold=0.5)
    w._oww_model = FakeOwwModel()  # noqa: SLF001
    w._model_label = "hey_jarvis"  # noqa: SLF001
    fired = []
    w.set_callback(lambda: fired.append(1))
    w.set_enabled(False)
    # Feed enough samples for one or more OWW chunks (1280 samples each).
    audio = np.ones((1280 * 3,), dtype=np.int16) * 10_000
    w.process(audio)
    assert fired == []
