"""One active voice assistant per Windows login session."""
import ctypes
import os
from ctypes import wintypes


class SingleInstance:
    def __init__(self, name="Local\\JARVISVoiceAssistant"):
        self.name = name
        self.handle = None

    def acquire(self):
        if os.name != "nt":
            return True
        self.kernel = ctypes.WinDLL("kernel32", use_last_error=True)
        self.kernel.CreateMutexW.argtypes = [ctypes.c_void_p, wintypes.BOOL, wintypes.LPCWSTR]
        self.kernel.CreateMutexW.restype = wintypes.HANDLE
        self.kernel.CloseHandle.argtypes = [wintypes.HANDLE]
        self.kernel.CloseHandle.restype = wintypes.BOOL
        self.handle = self.kernel.CreateMutexW(None, False, self.name)
        if not self.handle:
            raise ctypes.WinError(ctypes.get_last_error())
        if ctypes.get_last_error() == 183:
            self.release()
            return False
        return True

    def release(self):
        if self.handle:
            self.kernel.CloseHandle(self.handle)
            self.handle = None
