"""Single owner for the shared native window mask.

Depth occlusion, icon sleep, rest sites and peek cutouts all need to shape the
same QWidget mask. Features register a region under their own key; the visible
mask is the intersection, so one feature releasing cannot erase another's
cutout. An empty intersection becomes a 1x1 sentinel because Qt treats an
empty native mask as "no mask".
"""
from PySide6.QtCore import QRect
from PySide6.QtGui import QRegion

SENTINEL = QRegion(QRect(0, 0, 1, 1))


class WindowMask:
    def __init__(self, pet):
        self.pet = pet
        self.requests = {}
        self.applied = None

    def set(self, owner, region):
        region = QRegion(region)
        if owner in self.requests and self.requests[owner] == region:
            return
        self.requests[owner] = region
        self.apply()

    def clear(self, owner):
        if self.requests.pop(owner, None) is not None:
            self.apply()

    def clear_all(self):
        self.requests.clear()
        self.applied = None
        self.pet.clearMask()

    def reapply(self):
        self.applied = None
        self.apply()

    def apply(self):
        effective = None
        for region in self.requests.values():
            effective = region if effective is None else effective.intersected(region)
        if effective is None:
            if self.applied is not None:
                self.applied = None
                self.pet.clearMask()
            return
        if effective.isEmpty():
            effective = SENTINEL
        if effective != self.applied:
            self.applied = effective
            self.pet.setMask(effective)
