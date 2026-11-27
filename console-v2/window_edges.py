"""Read-only foreground-window bounds, in physical pixels.

No screenshots, document titles, URLs, browser content or keyboard hooks.
This module never repositions/activates/resizes a foreign window.
Qt integration must convert physical coordinates per monitor before placement.
"""
import ctypes as C
from ctypes import wintypes as W
from dataclasses import dataclass
from functools import lru_cache
import os
import sys


@dataclass(frozen=True)
class WindowSurface:
    handle: int
    process_id: int
    rect: tuple[int, int, int, int]
    monitor: tuple[int, int, int, int]
    work_area: tuple[int, int, int, int]
    maximized: bool
    fullscreen: bool


def covers_monitor(rect, monitor, tolerance=2):
    """A borderless video/browser window is fullscreen only on its own monitor."""
    x,y,w,h=rect; mx,my,mw,mh=monitor
    return (x<=mx+tolerance and y<=my+tolerance and
            x+w>=mx+mw-tolerance and y+h>=my+mh-tolerance)


def _rect(value):
    return value.left,value.top,value.right-value.left,value.bottom-value.top


class _MonitorInfo(C.Structure):
    _fields_=[('size',W.DWORD),('monitor',W.RECT),('work',W.RECT),('flags',W.DWORD)]


@lru_cache(maxsize=1)
def _window_api():
    """Bind Win32 functions once; every read still uses current window state."""
    user=C.WinDLL('user32',use_last_error=True)
    dwm=C.WinDLL('dwmapi')
    user.GetForegroundWindow.restype=W.HWND
    user.GetAncestor.argtypes=[W.HWND,W.UINT];user.GetAncestor.restype=W.HWND
    user.IsWindowVisible.argtypes=[W.HWND];user.IsIconic.argtypes=[W.HWND]
    user.IsZoomed.argtypes=[W.HWND]
    user.GetWindowThreadProcessId.argtypes=[W.HWND,C.POINTER(W.DWORD)]
    user.GetClassNameW.argtypes=[W.HWND,W.LPWSTR,C.c_int]
    user.GetWindowRect.argtypes=[W.HWND,C.POINTER(W.RECT)]
    user.MonitorFromWindow.argtypes=[W.HWND,W.DWORD];user.MonitorFromWindow.restype=W.HMONITOR
    user.GetMonitorInfoW.argtypes=[W.HMONITOR,C.POINTER(_MonitorInfo)]
    dwm.DwmGetWindowAttribute.argtypes=[W.HWND,W.DWORD,C.c_void_p,W.DWORD]
    set_context=getattr(user,'SetThreadDpiAwarenessContext',None)
    if set_context:
        set_context.argtypes=[C.c_void_p];set_context.restype=C.c_void_p
    callback=C.WINFUNCTYPE(W.BOOL,W.HWND,W.LPARAM)
    user.EnumWindows.argtypes=[callback,W.LPARAM]
    return user,dwm,set_context,callback


def inspect_foreground(excluded_processes=(), handle=None):
    """Return a visible foreground app surface or None when it is unavailable."""
    if sys.platform!='win32': return None
    user,dwm,set_context,_=_window_api()
    hwnd=handle or user.GetForegroundWindow()
    if not hwnd: return None
    hwnd=user.GetAncestor(hwnd,2) or hwnd  # GA_ROOT; respect the active modal.
    if not user.IsWindowVisible(hwnd) or user.IsIconic(hwnd): return None
    pid=W.DWORD();user.GetWindowThreadProcessId(hwnd,C.byref(pid))
    if pid.value == os.getpid(): return None
    if pid.value in excluded_processes:
        # The Electron workbench is the one eligible surface in its process.
        # Reminder popups, overlays and other host windows stay excluded.
        if (str(pid.value) != os.environ.get('PET_CONTROL_PID') or
                str(int(hwnd)) != os.environ.get('PET_WORKBENCH_HWND')):
            return None
    name=C.create_unicode_buffer(256)
    user.GetClassNameW(hwnd,name,len(name))
    if name.value in ('Progman','WorkerW','Shell_TrayWnd','Shell_SecondaryTrayWnd',
                      '#32768','tooltips_class32','SysShadow'): return None
    cloaked=W.DWORD()
    if dwm.DwmGetWindowAttribute(hwnd,14,C.byref(cloaked),C.sizeof(cloaked))==0 and cloaked.value:
        return None
    # Native coordinates are requested explicitly, without changing process DPI.
    previous=None
    if set_context:
        previous=set_context(C.c_void_p(-4))  # PER_MONITOR_AWARE_V2
    try:
        rectangle=W.RECT()
        if dwm.DwmGetWindowAttribute(hwnd,9,C.byref(rectangle),C.sizeof(rectangle))!=0:
            if not user.GetWindowRect(hwnd,C.byref(rectangle)): return None
        info=_MonitorInfo();info.size=C.sizeof(info)
        if not user.GetMonitorInfoW(user.MonitorFromWindow(hwnd,2),C.byref(info)): return None
        bounds=_rect(rectangle)
        if bounds[2]<80 or bounds[3]<60: return None
        monitor=_rect(info.monitor)
        return WindowSurface(int(hwnd),pid.value,bounds,monitor,_rect(info.work),
                             bool(user.IsZoomed(hwnd)),covers_monitor(bounds,monitor))
    finally:
        if previous: set_context(previous)


def foreground_process():
    if sys.platform!='win32': return None
    user,_,_,_=_window_api()
    pid=W.DWORD();user.GetWindowThreadProcessId(user.GetForegroundWindow(),C.byref(pid))
    return pid.value


def visible_surfaces(excluded_processes=(),limit=40, *, opaque_only=False):
    """Topmost first, without reading any titles or page contents."""
    if sys.platform!='win32':return []
    user,_,_,callback=_window_api()
    result=[];seen=set()
    def visit(hwnd,_):
        if opaque_only:
            from desktop_icons import transparent_overlay
            if transparent_overlay(user,hwnd):
                return True
        surface=inspect_foreground(excluded_processes,handle=hwnd)
        if surface and surface.handle not in seen:
            result.append(surface);seen.add(surface.handle)
        return len(result)<limit
    proc=callback(visit)
    user.EnumWindows(proc,0)
    return result
