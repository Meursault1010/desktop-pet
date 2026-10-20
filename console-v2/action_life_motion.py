"""Small, pose-aware secondary motion for existing PNG action frames."""
import math
from functools import lru_cache

import cv2
import numpy as np
from PySide6.QtGui import QImage, QPixmap


@lru_cache(maxsize=1)
def _coordinates(size):
    return np.meshgrid(np.arange(size, dtype=np.float32),
                       np.arange(size, dtype=np.float32))


class ActionLifeMotion:
    """Add restrained breathing and delayed hair motion without pose blending."""

    PRONE = {'prone-chin', 'prone-rest'}
    SEATED = {'sit-neat', 'sit-relaxed', 'sit-swing', 'eat', 'work',
              'reading-pose-1', 'reading-pose-2'}
    EXCLUDED = {'lazy-roll-away', 'lazy-roll-toward', 'throw-flight',
                'impact-left', 'impact-right', 'impact-ceiling', 'impact-floor'}

    def __init__(self):
        self.cache = {}

    def render(self, atlas, source, action_id, elapsed):
        if action_id in self.EXCLUDED or action_id in {'sleep', 'sleep-enter', 'sleep-wake'}:
            return None
        frame = (atlas.copy(source) if isinstance(atlas, QImage) else atlas.copy(source).toImage()).convertToFormat(
            QImage.Format.Format_RGBA8888_Premultiplied)
        size = frame.width()
        rgba = np.frombuffer(frame.bits(), dtype=np.uint8,
                             count=size * size * 4).reshape(size, size, 4)
        key = (action_id, size, atlas.cacheKey(), source.x(), source.y())
        bounds = self.cache.get(key)
        if bounds is None:
            ys, xs = np.nonzero(rgba[:, :, 3] > 12)
            if not len(xs):
                return frame
            bounds = (int(xs.min()), int(ys.min()), int(xs.max()+1), int(ys.max()+1))
            self.cache[key] = bounds
            if len(self.cache) > 256:
                self.cache.pop(next(iter(self.cache)))
        x0, y0, x1, y1 = bounds
        width, height = max(1, x1-x0), max(1, y1-y0)
        xx, yy = _coordinates(size)
        nx = (xx-x0)/width
        ny = (yy-y0)/height
        phase = 2*math.pi*(elapsed % 3.8)/3.8
        breath = math.sin(phase)
        is_prone = action_id in self.PRONE
        is_seated = action_id in self.SEATED
        # Keep the deformation centered on the torso for each authored pose.
        chest_y = .53 if is_prone else .46 if is_seated else .51
        chest = np.exp(-((ny-chest_y)/.19)**2) * np.exp(-((nx-.51)/.29)**2)
        amplitude = .58 if is_prone else .82 if is_seated else 1.05
        alpha = rgba[:, :, 3].astype(np.float32)/255
        anchor = np.clip((1-ny)/.12, 0, 1)
        dy = -amplitude*breath*chest*anchor*alpha
        dx = (nx-.51)*width*.012*breath*chest*alpha

        # Let the outer hair trail the torso by a fraction of a beat.
        hair_region = np.clip((ny-.34)/.24, 0, 1)*np.clip((.96-ny)/.2, 0, 1)
        sides = np.clip((np.abs(nx-.5)-.31)/.2, 0, 1)
        hair = hair_region*sides*alpha
        lag = (ny-.34)*1.9
        dx += .72*np.sin(phase-lag)*hair
        dy += .34*np.sin(phase-lag+.6)*hair

        map_x = np.clip(xx-dx, 0, size-1).astype(np.float32)
        map_y = np.clip(yy-dy, 0, size-1).astype(np.float32)
        warped = cv2.remap(rgba, map_x, map_y, cv2.INTER_LINEAR,
                           borderMode=cv2.BORDER_CONSTANT)
        return QImage(warped.data, size, size, size*4,
                      QImage.Format.Format_RGBA8888_Premultiplied).copy()
