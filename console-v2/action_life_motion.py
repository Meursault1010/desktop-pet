"""Small, pose-aware secondary motion for existing PNG action frames."""
import math
from functools import lru_cache

import cv2
import numpy as np
from PySide6.QtCore import Qt
from PySide6.QtGui import QImage


@lru_cache(maxsize=4)
def _coordinates(size):
    return np.meshgrid(np.arange(size, dtype=np.float32),
                       np.arange(size, dtype=np.float32))


class ActionLifeMotion:
    """Add restrained breathing and delayed hair motion without pose blending."""

    PRONE = {'prone-chin', 'prone-rest'}
    SEATED = {'sit-neat', 'sit-relaxed', 'sit-swing', 'eat', 'work',
              'reading-pose-1', 'reading-pose-2', 'play-sit', 'play-top-rest'}
    EXCLUDED = {'lazy-roll-away', 'lazy-roll-toward', 'throw-flight',
                'play-climb-up', 'play-climb-down',
                'impact-left', 'impact-right', 'impact-ceiling', 'impact-floor'}
    # The reading holds hold a book in the lap, so their breath stops at the hip.
    # Every other idle keeps the original whole-torso field: the mask was tuned
    # for these four and must not leak into the everyday poses.
    UPPER_ONLY = {'read', 'reading-pose-1', 'reading-pose-2', 'reading-pose-3'}

    def __init__(self):
        self.cache = {}
        self.last_key = None
        self.last_image = None

    def render(self, atlas, source, action_id, elapsed, target_size=None, scale=1., center=None, spread=.19, bob=0., sway=0., period=3.8, lean=0.):
        if action_id in self.EXCLUDED or action_id in {'sleep', 'sleep-enter', 'sleep-wake'}:
            return None
        # The secondary motion is slow; recomputing it at 60Hz doubles paint
        # cost for no visible gain. Check the 30Hz bucket before touching pixels.
        bucket = round(elapsed*30)
        width = source.width() if target_size is None else target_size
        frame_key = (action_id, width, atlas.cacheKey(), source.getRect())
        motion_key = (bucket, scale, center, spread, bob, sway, period, lean)
        key = (frame_key, motion_key)
        if key == self.last_key:
            return self.last_image
        frame = (atlas.copy(source) if isinstance(atlas, QImage) else atlas.copy(source).toImage()).convertToFormat(
            QImage.Format.Format_RGBA8888_Premultiplied)
        if target_size is not None and target_size != frame.width():
            frame = frame.scaled(target_size, target_size,
                                 Qt.AspectRatioMode.IgnoreAspectRatio,
                                 Qt.TransformationMode.SmoothTransformation)
        size = frame.width()
        unit = size/256
        rgba = np.frombuffer(frame.bits(), dtype=np.uint8,
                             count=size * size * 4).reshape(size, size, 4)
        bounds = self.cache.get(frame_key)
        if bounds is None:
            ys, xs = np.nonzero(rgba[:, :, 3] > 12)
            if not len(xs):
                return frame
            bounds = (int(xs.min()), int(ys.min()), int(xs.max()+1), int(ys.max()+1))
            self.cache[frame_key] = bounds
            if len(self.cache) > 256:
                self.cache.pop(next(iter(self.cache)))
        x0, y0, x1, y1 = bounds
        width, height = max(1, x1-x0), max(1, y1-y0)
        xx, yy = _coordinates(size)
        nx = (xx-x0)/width
        ny = (yy-y0)/height
        phase = 2*math.pi*(elapsed % period)/period
        breath = math.sin(phase)
        is_prone = action_id in self.PRONE
        is_seated = action_id in self.SEATED
        # Keep the deformation centered on the torso for each authored pose.
        chest_y = center if center is not None else .53 if is_prone else .46 if is_seated else .51
        chest = np.exp(-((ny-chest_y)/spread)**2) * np.exp(-((nx-.51)/.29)**2)
        amplitude = (.58 if is_prone else .82 if is_seated else 1.05)*scale
        alpha = rgba[:, :, 3].astype(np.float32)/255
        anchor = np.clip((1-ny)/.12, 0, 1)
        # The field is built on canvas coordinates, not on coverage: weighting it
        # by alpha pinned the transparent rows above the head, so a large bob
        # shaved the top of the silhouette instead of lifting it.
        upper = np.clip((.74-ny)/.28, 0, 1) if action_id in self.UPPER_ONLY else 1.
        dy = -amplitude*breath*chest*anchor*upper*unit
        dy += -bob*breath*upper*unit
        dx = (nx-.51)*width*.012*breath*chest*upper
        dx += lean*breath*upper*unit

        # Let the outer hair trail the torso by a fraction of a beat. On the
        # reading holds it rides the same upper-body mask, otherwise the drape
        # over the skirt swings and the lower half stops reading as planted.
        hair_region = np.clip((ny-.34)/.24, 0, 1)*np.clip((.96-ny)/.2, 0, 1)
        sides = np.clip((np.abs(nx-.5)-.31)/.2, 0, 1)
        hair = hair_region*sides*alpha*upper
        lag = (ny-.34)*1.9
        dx += (.72*scale+sway)*np.sin(phase-lag)*hair*unit
        dy += (.34*scale+.5*sway)*np.sin(phase-lag+.6)*hair*unit

        if action_id == 'play-top-rest':
            # A tiny irregular leg swing below the fixed seat, not a new pose
            # or a rotation of the whole character. Keep the hip anchored.
            legs = np.clip((ny-.70)/.22,0,1)*np.clip((.58-nx)/.12,0,1)*alpha
            swing = math.sin(elapsed*math.tau/3.1)+.3*math.sin(elapsed*math.tau/4.7)
            dx += 1.5*swing*legs*unit

        map_x = np.clip(xx-dx, 0, size-1).astype(np.float32)
        map_y = np.clip(yy-dy, 0, size-1).astype(np.float32)
        warped = cv2.remap(rgba, map_x, map_y, cv2.INTER_LINEAR,
                           borderMode=cv2.BORDER_CONSTANT)
        image = QImage(warped.data, size, size, size*4,
                       QImage.Format.Format_RGBA8888_Premultiplied).copy()
        self.last_key = key
        self.last_image = image
        return image
