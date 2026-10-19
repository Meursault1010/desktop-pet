"""Small ctypes bridge for the PSD2Live software renderer used by the pet."""
import ctypes
import math
import random
import time
from pathlib import Path

from PySide6.QtCore import QRectF
from PySide6.QtGui import QImage


class Live2DRenderer:
    SCALE = 2
    WIDTH = 180 * SCALE
    HEIGHT = 190 * SCALE

    def __init__(self):
        root = Path(__file__).resolve().parent / 'assets' / 'live2d'
        self.library = ctypes.CDLL(str(root / 'p2l_runtime.dll'))
        self._bind()
        self._source = (root / 'Yuki_Live2D.p2lrt').read_bytes()
        self._source_buffer = (ctypes.c_uint8 * len(self._source)).from_buffer_copy(self._source)
        self._error = ctypes.create_string_buffer(1024)
        self.rig = self.library.p2l_rig_load(
            self._source_buffer, len(self._source), self._error, len(self._error))
        if not self.rig:
            raise RuntimeError(self._error.value.decode('utf-8', errors='replace'))
        if self.library.p2l_abi_version() != (1 << 16 | 4):
            raise RuntimeError('Unsupported PSD2Live runtime ABI')
        count = self.library.p2l_parameter_count(self.rig)
        self.parameters = {}
        for index in range(count):
            key = self.library.p2l_parameter_id(self.rig, index).decode('ascii')
            self.parameters[key] = index
        self.values = self.library.p2l_parameter_values(self.rig)
        self.started = time.monotonic()
        self.last_update = self.started
        self.last_gaze = self.started
        self.gaze_from = (0.0, 0.0)
        self.gaze_to = (0.0, 0.0)
        self.next_gaze = self.started + 2.0
        self._image = QImage(self.WIDTH, self.HEIGHT, QImage.Format.Format_RGBA8888)
        self._pixels = (ctypes.c_uint8 * (self.WIDTH * self.HEIGHT * 4)).from_buffer(
            self._image.bits())
        self._transform = (ctypes.c_float * 6)(
            0.32, 0.0, 0.0, 0.32, 16.0, 59.0)

    def _bind(self):
        lib = self.library
        lib.p2l_abi_version.restype = ctypes.c_uint32
        lib.p2l_rig_load.argtypes = [ctypes.POINTER(ctypes.c_uint8), ctypes.c_size_t,
                                     ctypes.c_char_p, ctypes.c_size_t]
        lib.p2l_rig_load.restype = ctypes.c_void_p
        lib.p2l_rig_free.argtypes = [ctypes.c_void_p]
        lib.p2l_parameter_count.argtypes = [ctypes.c_void_p]
        lib.p2l_parameter_count.restype = ctypes.c_uint32
        lib.p2l_parameter_id.argtypes = [ctypes.c_void_p, ctypes.c_uint32]
        lib.p2l_parameter_id.restype = ctypes.c_char_p
        lib.p2l_parameter_values.argtypes = [ctypes.c_void_p]
        lib.p2l_parameter_values.restype = ctypes.POINTER(ctypes.c_float)
        lib.p2l_update_stages.argtypes = [ctypes.c_void_p, ctypes.c_float, ctypes.c_uint32]
        lib.p2l_render.argtypes = [ctypes.c_void_p, ctypes.POINTER(ctypes.c_uint8),
                                   ctypes.c_uint32, ctypes.c_uint32,
                                   ctypes.POINTER(ctypes.c_float), ctypes.c_uint32]
        lib.p2l_render.restype = ctypes.c_bool

    def _set(self, key, value):
        index = self.parameters.get(key)
        if index is not None:
            self.values[index] = value

    def render(self, state, painter, now=None):
        now = time.monotonic() if now is None else now
        elapsed = now - self.started
        dt = min(max(now - self.last_update, 0.0), 1 / 30)
        self.last_update = now

        gaze = self.gaze_to
        if now >= self.next_gaze:
            self.gaze_from = gaze
            self.gaze_to = (random.uniform(-0.24, 0.24), random.uniform(-0.14, 0.16))
            self.last_gaze = now
            self.next_gaze = now + random.uniform(2.5, 6.0)
        blend = min(1.0, (now - self.last_gaze) / 0.65)
        blend = blend * blend * (3 - 2 * blend)
        gx = self.gaze_from[0] + (self.gaze_to[0] - self.gaze_from[0]) * blend
        gy = self.gaze_from[1] + (self.gaze_to[1] - self.gaze_from[1]) * blend

        blink = 0.03 if state.idle.frame == 10 else 0.48 if state.idle.frame == 4 else 1.0
        breath = 0.5 + 0.5 * math.sin(elapsed * 0.78)
        self._set('ParamAngleX', 2.3 * math.sin(elapsed * 0.31))
        self._set('ParamAngleY', 1.25 * math.sin(elapsed * 0.23 + 1.1))
        self._set('ParamAngleZ', 0.72 * math.sin(elapsed * 0.42))
        self._set('ParamBodyAngleX', 0.7 * math.sin(elapsed * 0.31 - 0.3))
        self._set('ParamBodyAngleY', 0.45 * math.sin(elapsed * 0.23 + 0.5))
        self._set('ParamBodyAngleZ', 0.75 * math.sin(elapsed * 0.42 - 0.4))
        self._set('ParamEyeLOpen', blink)
        self._set('ParamEyeROpen', blink)
        self._set('ParamEyeBallX', gx)
        self._set('ParamEyeBallY', gy)
        self._set('ParamBreath', breath)
        self._set('ParamHairFront', 0.38 * math.sin(elapsed * 0.83))
        self._set('ParamHairBack', 0.3 * math.sin(elapsed * 0.64 + 0.7))

        self.library.p2l_update_stages(self.rig, dt, 16)
        if not self.library.p2l_render(self.rig, self._pixels, self.WIDTH, self.HEIGHT,
                                       self._transform, 1):
            return False
        painter.drawImage(QRectF(0, 0, self.WIDTH / self.SCALE, self.HEIGHT / self.SCALE),
                          self._image)
        return True

    def close(self):
        if self.rig:
            self.library.p2l_rig_free(self.rig)
            self.rig = None
