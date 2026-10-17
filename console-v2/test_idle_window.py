"""Real Qt timer regression for the user's quiet + paused configuration."""
import os
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
import time
import unittest

from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication
from PySide6.QtGui import QColor, QPixmap
from pet import DesktopPet, PetRenderer
from settings_model import Preferences


class IdleWindowTests(unittest.TestCase):
    def test_identical_frames_do_not_pump_brightness_or_alpha(self):
        app = QApplication.instance() or QApplication([])
        renderer = PetRenderer()
        for alpha in (255, 128):
            atlas = QPixmap(2048, 2048)
            atlas.fill(QColor(200, 200, 200, alpha))
            renderer.atlases = {key: atlas for key in ('open', 'half', 'closed')}
            for fraction in (0, .1, .25, .5, .75, .9, 1):
                color = renderer.motion_image(fraction*.075, 1).toImage().pixelColor(128, 128)
                self.assertLessEqual(abs(color.alpha()-alpha), 1, (fraction, color.getRgb()))
                self.assertLessEqual(abs(color.red()-200), 2, (fraction, color.getRgb()))

    def test_open_eyes_still_move_every_sample(self):
        app = QApplication.instance() or QApplication([])
        renderer = PetRenderer()
        images = []
        for i in range(145):
            image = renderer.motion_image(i/30, 1).toImage()
            images.append(bytes(image.constBits()))
        self.assertEqual(len(set(images[:144])), 144)
        self.assertEqual(images[0], images[144])
        for frame in (1, 4, 10):
            image = renderer.motion_image(.7, frame).toImage()
            self.assertEqual(image.pixelColor(0, 0).alpha(), 0)
            self.assertGreater(image.pixelColor(128, 128).alpha(), 0)

    def test_quiet_paused_pet_still_animates_without_moving(self):
        app = QApplication.instance() or QApplication([])
        app.setQuitOnLastWindowClosed(False)
        pet = DesktopPet(Preferences(quiet=True, paused=True))
        try:
            pet.show()
            app.processEvents()
            position = pet.pos()
            pet.state.idle.next_blink = time.monotonic() + .12
            frames = set()
            images = set()
            for _ in range(55):
                QTest.qWait(20)
                frames.add(pet.state.idle.frame)
                image = pet.grab().toImage()
                images.add(bytes(image.constBits()))
            self.assertTrue(pet.animator.timer.isActive())
            self.assertIn(1, frames)
            self.assertIn(10, frames)
            self.assertGreater(len(images), 1)
            self.assertEqual(pet.pos(), position)
            self.assertTrue(pet.preferences.paused)
            self.assertTrue(pet.preferences.quiet)
        finally:
            pet.hide()
            pet.deleteLater()
            app.processEvents()


if __name__ == '__main__':
    unittest.main()
