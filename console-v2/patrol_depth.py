"""Persistent native front/back depth, switched only at offscreen passages.

Only the pet is repositioned in z order. Clipping against opaque windows also
keeps the back layer hidden when Qt or another app refreshes native ordering.
"""
import ctypes as C
from ctypes import wintypes as W
import math
import sys
from concurrent.futures import ThreadPoolExecutor
from functools import lru_cache
from PySide6.QtCore import QRect
from PySide6.QtGui import QGuiApplication, QRegion
from edge_attachment import logical_surface
from window_edges import visible_surfaces


_surface_scanner=ThreadPoolExecutor(max_workers=1,thread_name_prefix='yuki-depth-scan')


def _scan_surfaces():
    # Native enumeration can take >100ms. No Qt objects or window mutations
    # belong on this worker; all geometry conversion and masks stay on the UI.
    try:return visible_surfaces(limit=80,opaque_only=True),''
    except (OSError,RuntimeError,ValueError):
        return [],'窗口位置暂不可用，继续从前方经过'


@lru_cache(maxsize=160)
def _clip_rectangle(x, y, width, height):
    left, top = math.floor(x), math.floor(y)
    return QRect(left, top, math.ceil(x+width)-left, math.ceil(y+height)-top)


def set_pet_topmost(handle, enabled):
    if sys.platform != 'win32' or QGuiApplication.platformName() == 'offscreen':
        return
    user = C.WinDLL('user32', use_last_error=True)
    user.SetWindowPos.argtypes = [W.HWND, W.HWND, C.c_int, C.c_int,
                                  C.c_int, C.c_int, W.UINT]
    user.SetWindowPos.restype = W.BOOL
    if not user.SetWindowPos(handle, W.HWND(-1 if enabled else -2), 0, 0, 0, 0, 0x13):
        raise OSError(C.get_last_error(), '无法调整宠物自身显示层级')


def set_pet_behind(handle, anchor=None):
    """Place only our native window below applications, above the shell."""
    set_pet_topmost(handle, False)
    if sys.platform != 'win32' or QGuiApplication.platformName() == 'offscreen' or not anchor:
        return
    user = C.WinDLL('user32', use_last_error=True)
    user.SetWindowPos.argtypes = [W.HWND, W.HWND, C.c_int, C.c_int, C.c_int, C.c_int, W.UINT]
    user.SetWindowPos.restype = W.BOOL
    if not user.SetWindowPos(handle, anchor, 0, 0, 0, 0, 0x13):
        raise OSError(C.get_last_error(), '无法将宠物放到应用窗口后方')


class PatrolDepth:
    def __init__(self, pet):
        self.pet = pet
        self.region = None
        self.mode = 'front'
        self.surfaces = []
        self.scan_at = 0.
        self.override = False
        self.error = ''
        self.applied = None
        self.scan = None

    def cross_edge(self, screen):
        """The sole autonomous layer switch: the complete pet is offscreen."""
        bounds = screen.geometry()
        body = QRect(self.pet.x(), self.pet.y(), self.pet.width(), self.pet.height())
        if bounds.intersects(body):
            raise ValueError('人物完全走出屏幕后才能切换层级')
        self.mode = 'back' if self.mode == 'front' else 'front'
        self.applied = None

    def update(self, now):
        p = self.pet
        if now >= self.scan_at and self.scan is None:
            self.scan_at = now+.35
            self.scan=_surface_scanner.submit(_scan_surfaces)
        if self.scan is not None and self.scan.done():
            surfaces,self.error=self.scan.result()
            self.scan=None
            try:
                screens=QGuiApplication.screens()
                self.surfaces=[(surface.handle,logical_surface(surface,screens)) for surface in surfaces]
            except (OSError,RuntimeError,ValueError):
                self.surfaces=[]
                self.error='窗口位置暂不可用，继续从前方经过'
        anchor = self.surfaces[-1][0] if self.surfaces else None
        layer = (self.mode, anchor if self.mode == 'back' else None)
        if layer != self.applied:
            try:
                if self.mode == 'back':
                    set_pet_behind(int(p.winId()), anchor)
                else:
                    set_pet_topmost(int(p.winId()), True)
                self.override = True
                self.applied = layer
            except OSError as error:
                self.error = str(error)
        region = None
        if self.mode == 'back' and self.surfaces:
            x, y, width, height = p.x(), p.y(), p.width(), p.height()
            body = QRect(x, y, width, height)
            pet_screen = p.screen()
            for _, (bounds, _, screen) in self.surfaces:
                if screen != pet_screen:
                    continue
                window = _clip_rectangle(*bounds)
                if body.intersects(window):
                    if region is None:
                        region = QRegion(QRect(0, 0, width, height))
                    region = region.subtracted(QRegion(window.translated(-x, -y)))
        if region is not None:
            if self.region != region:
                p.masker.set('depth', region)
            self.region = region
        elif self.region is not None:
            p.masker.clear('depth')
            self.region = None

    @property
    def engaged(self):
        return self.override or self.region is not None or self.mode != 'front'

    def release(self):
        if self.scan is not None:
            self.scan.cancel()
            self.scan=None  # Ignore a late result after this walk has ended.
        self.pet.masker.clear('depth')
        if self.override:
            try:
                restore = getattr(self.pet, 'apply_window_layer', None)
                if restore is not None:
                    restore()
                else:
                    set_pet_topmost(int(self.pet.winId()), self.pet.preferences.always_on_top)
            except OSError:
                pass
        self.region = None
        self.mode = 'front'
        self.surfaces = []
        self.scan_at = 0.
        self.override = False
        self.applied = None
