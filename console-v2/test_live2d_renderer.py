"""Smoke and motion checks for Yuki's Live2D and sprite idle renderers."""
import sys
import time
import unittest
import os
from unittest.mock import patch
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QImage, QPainter
from PySide6.QtWidgets import QApplication

sys.path.insert(0, str(Path(__file__).resolve().parent))
from live2d_runtime import Live2DRenderer
from idle_animation import MOTION_SECONDS
from pet import PetRenderer, PetState


class Live2DRendererTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
        cls.app = QApplication.instance() or QApplication([])

    def test_renders_transparent_idle_frames_with_subtle_motion(self):
        renderer = Live2DRenderer()
        try:
            state = PetState()
            frames = []
            durations = []
            for offset in (0.0, 1.7, 3.4):
                image = QImage(180, 190, QImage.Format.Format_RGBA8888)
                image.fill(Qt.GlobalColor.transparent)
                painter = QPainter(image)
                started = time.perf_counter()
                self.assertTrue(renderer.render(state, painter, state.started + offset))
                durations.append(time.perf_counter() - started)
                painter.end()
                self.assertGreater(image.width(), 0)
                self.assertEqual(image.pixelColor(0, 0).alpha(), 0)
                self.assertGreater(image.pixelColor(90, 100).alpha(), 0)
                frames.append(image)
            differences = [
                sum(frames[0].pixelColor(x, y) != frames[i].pixelColor(x, y)
                    for y in range(190) for x in range(180))
                for i in (1, 2)
            ]
            self.assertTrue(any(differences), 'idle parameters should deform the rendered model')
            self.assertLess(sum(durations[1:]) / len(durations[1:]), 0.02)
            self.assertLess(max(durations[1:]), 0.033)
        finally:
            renderer.close()

    def test_pet_idle_uses_the_existing_atlas_and_keeps_actions_separate(self):
        renderer = PetRenderer()
        state = PetState()
        image = QImage(180, 190, QImage.Format.Format_RGBA8888)
        painter = QPainter(image)
        with patch.object(renderer, 'motion_image', wraps=renderer.motion_image) as idle:
            renderer.draw_pose(painter, state)
            self.assertEqual(idle.call_count, 1)
            state.action_player.play('blink', now=state.started)
            renderer.draw_pose(painter, state)
            self.assertEqual(idle.call_count, 1)
        painter.end()

    def test_breathing_atlas_has_visible_continuous_changes(self):
        renderer = PetRenderer()
        state = PetState()
        images = []
        for frame in (0, 16, 32, 48):
            state.started = time.monotonic() - frame * MOTION_SECONDS / 64
            image = QImage(180, 190, QImage.Format.Format_RGBA8888)
            image.fill(Qt.GlobalColor.transparent)
            painter = QPainter(image)
            renderer.draw_pose(painter, state)
            painter.end()
            images.append(image)
        changed = sum(images[0].pixelColor(x, y) != images[2].pixelColor(x, y)
                      for y in range(38, 145) for x in range(34, 146))
        self.assertGreater(changed, 300)
        bottom_edges = [max(y for y in range(190) for x in range(180)
                            if image.pixelColor(x, y).alpha() > 0)
                        for image in images]
        self.assertLessEqual(max(bottom_edges) - min(bottom_edges), 1)


if __name__ == '__main__':
    unittest.main()
