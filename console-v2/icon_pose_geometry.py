"""Contact geometry shared by generated icon poses, breathing and edge checks.

Coordinates are normalized to the actual sprite canvas, never its cropped
bounding box. Top-supported poses keep their contact fixed while breathing.
The legacy shoulder-supported poses retain their existing transform.
"""
from dataclasses import dataclass
import math


@dataclass(frozen=True)
class PoseGeometry:
    contact: tuple[float, float]
    support: str = 'top'
    target_x: float = .5

    def __post_init__(self):
        if self.support not in ('top', 'side'):
            raise ValueError('Unknown support type')
        for value in (*self.contact, self.target_x):
            if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or not 0 <= value <= 1:
                raise ValueError('Pose coordinates must be finite normalized numbers')


def sprite_rect(size, geometry, pulse=0., amount=1.):
    """Return x, y, w, h with an invariant contact point throughout a breath."""
    width, height = size
    w, base_h = width * .94, height * .88
    h = base_h * (1 + .009 * amount * pulse)
    left = width * .03
    # The contact's resting position is kept exactly, not rounded every frame.
    contact_y = height * .10 + base_h * geometry.contact[1]
    return left, contact_y - h * geometry.contact[1], w, h


def silhouette_envelope(size, bounds, geometry):
    """Union the extreme breathing transforms for safe full-cycle placement."""
    l, t, r, b = bounds
    rectangles = [sprite_rect(size, geometry, pulse=p) for p in (-1., 1.)]
    return (min(x + w*l for x,y,w,h in rectangles),
            min(y + h*t for x,y,w,h in rectangles),
            max(x + w*r for x,y,w,h in rectangles),
            max(y + h*b for x,y,w,h in rectangles))


def target_contact(rect, geometry):
    x, y, w, h = rect
    return x + w * geometry.target_x, y if geometry.support == 'top' else y + h * .5


def icon_surface(rect, image):
    """Use the real icon's opaque top, ignoring transparent image padding.

    A one-pixel-wide protrusion must not place a seated character off the main
    support. Average a narrow band of opaque pixels near the top silhouette.
    This reads the supplied glyph only; no desktop capture or Shell writes.
    """
    from PySide6.QtGui import QImage
    if image is None or image.isNull():
        return rect
    source = image.convertToFormat(QImage.Format.Format_RGBA8888)
    data = bytes(source.constBits()); stride = source.bytesPerLine()
    points = [(x,y) for y in range(source.height()) for x in range(source.width())
              if data[y*stride+x*4+3] >= 64]
    if not points:
        return rect
    top = min(y for x,y in points)
    band = [x for x,y in points if y <= top + max(1, source.height()//12)]
    left, right = min(band), max(band) + 1
    x, y, w, h = rect
    return (x + w*left/source.width(), y + h*top/source.height(),
            w*(right-left)/source.width(), h*(source.height()-top)/source.height())
