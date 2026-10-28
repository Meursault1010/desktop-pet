"""Baked whole-frame walk atlas: assets, frame mapping and rendering."""
import os
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
import unittest

import numpy as np
from PySide6.QtCore import QRectF
from PySide6.QtGui import QImage, QPainter
from PySide6.QtWidgets import QApplication

import walk_atlas
from locomotion import walk_stride


def render(name, clock, size=256):
    image = QImage(size, size, QImage.Format.Format_RGBA8888)
    image.fill(0)
    painter = QPainter(image)
    walk_atlas.paint(painter, QRectF(0, 0, size, size), name, clock)
    painter.end()
    return image


def pixels(image):
    image = image.convertToFormat(QImage.Format.Format_RGBA8888)
    data = np.frombuffer(image.constBits(), np.uint8)
    data = data.reshape(image.height(), image.bytesPerLine())
    return data[:, :image.width() * 4].reshape(
        image.height(), image.width(), 4
    ).copy()


class WalkAtlasTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def test_frames_and_baseline(self):
        frames = walk_atlas.frames()
        self.assertEqual(len(frames), walk_atlas.FRAMES)
        stride = walk_stride('walk-right')
        for index, frame in enumerate(frames):
            self.assertFalse(frame.isNull())
            self.assertEqual((frame.width(), frame.height()), (256, 256))
            clock = (index + .5) / walk_atlas.FRAMES * stride
            array = pixels(render('walk-right', clock))
            self.assertLess(int(array[0, 0, 3]), 32)
            self.assertGreater(int(array[:, :, 3].max()), 200)
            rows = np.where(array[:, :, 3].max(axis=1) > 20)[0]
            self.assertEqual(int(rows.max()), 248)

    def test_frame_index_follows_distance(self):
        stride = walk_stride('walk-right')
        self.assertEqual(walk_atlas.frame_index(0, 'walk-right'), 0)
        self.assertEqual(walk_atlas.frame_index(stride * .125, 'walk-right'), 1)
        self.assertEqual(walk_atlas.frame_index(stride * .5, 'walk-right'), 4)
        self.assertEqual(walk_atlas.frame_index(stride * .999, 'walk-right'), 7)
        self.assertEqual(walk_atlas.frame_index(stride, 'walk-right'), 0)

    def test_left_is_horizontal_mirror(self):
        right_asset = pixels(walk_atlas.frames()[0].toImage())
        left_asset = pixels(walk_atlas._directional('walk-left')[0].toImage())
        self.assertTrue(np.array_equal(left_asset, right_asset[:, ::-1, :]))
        right = pixels(render('walk-right', 0)).astype(int)
        left = pixels(render('walk-left', 0)).astype(int)
        self.assertLess(np.abs(left - right[:, ::-1, :]).mean(), 2.0)

    def test_all_eight_poses_render_distinctly(self):
        stride = walk_stride('walk-right')
        seen = set()
        for index in range(walk_atlas.FRAMES):
            clock = (index + .5) / walk_atlas.FRAMES * stride
            seen.add(pixels(render('walk-right', clock)).tobytes())
        self.assertEqual(len(seen), walk_atlas.FRAMES)

    def test_display_size_render_has_content(self):
        image = render('walk-right', 0, 160)
        array = pixels(image)
        self.assertGreater(int(array[:, :, 3].max()), 200)
        self.assertGreater(int((array[:, :, 3] > 20).sum()), 4000)


if __name__ == '__main__':
    unittest.main()
