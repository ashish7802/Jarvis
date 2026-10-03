"""Stable identifiers and discovery for selectable microphone inputs."""
from dataclasses import dataclass

import sounddevice as sd


@dataclass(frozen=True)
class InputDevice:
    identifier: str
    name: str
    host_api: str
    index: int

    @property
    def label(self) -> str:
        return f"{self.name} — {self.host_api}"


def list_input_devices() -> list[InputDevice]:
    try:
        devices = sd.query_devices()
        host_apis = sd.query_hostapis()
    except sd.PortAudioError as exc:
        raise ValueError(f"Windows couldn't list microphone inputs: {exc}") from exc
    inputs = []
    for index, device in enumerate(devices):
        if int(device.get("max_input_channels", 0)) < 1:
            continue
        host_api = host_apis[int(device["hostapi"])]["name"]
        name = str(device["name"])
        inputs.append(InputDevice(f"{host_api}\n{name}", name, host_api, index))
    return inputs


def resolve_input_device(identifier: str | None) -> int | None:
    if not identifier:
        return None
    for device in list_input_devices():
        if device.identifier == identifier:
            return device.index
    raise ValueError("The selected microphone is no longer available. Choose another input device.")


def recommended_input_device(devices: list[InputDevice] | None = None) -> str:
    devices = list_input_devices() if devices is None else devices
    physical = [
        device for device in devices
        if not any(word in device.name.casefold() for word in ("virtual", "voice changer", "stereo mix"))
    ]
    for device in physical:
        name = device.name.casefold()
        if "microphone array" in name or "mic array" in name:
            return device.identifier
    for device in physical:
        name = device.name.casefold()
        if "microphone" in name or " mic" in name or name.startswith("mic"):
            return device.identifier
    try:
        default_index = int(sd.default.device[0])
    except (TypeError, ValueError, IndexError, AttributeError):
        return ""
    return next((device.identifier for device in devices if device.index == default_index), "")
