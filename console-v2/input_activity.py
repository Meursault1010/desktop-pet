"""Read only Windows' last-input timestamp, never keys or typed text."""
import ctypes
import sys
from ctypes import wintypes


class LastInput(ctypes.Structure):
    _fields_ = [('cbSize', wintypes.UINT), ('dwTime', wintypes.DWORD)]


def idle_seconds():
    if sys.platform != 'win32':
        return None
    info = LastInput()
    info.cbSize = ctypes.sizeof(info)
    try:
        if not ctypes.windll.user32.GetLastInputInfo(ctypes.byref(info)):
            return None
        # Both timestamps use the same wrapping 32-bit millisecond clock.
        now = ctypes.windll.kernel32.GetTickCount() & 0xffffffff
        return ((now-info.dwTime) & 0xffffffff)/1000
    except (OSError, AttributeError):
        return None
