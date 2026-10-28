"""Real Qt image/gesture checks for approved sleep transition continuity."""
import os
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import numpy as np
from PIL import Image
from PySide6.QtCore import QPoint, Qt
from PySide6.QtGui import QImage, QPainter
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication

from main import PetApplication
from settings_model import SettingsStore
from pet_sleep import (ASSETS, MANIFEST, SETTLE_SECONDS, WAKE_SECONDS,
                       WAKE_HOLD_SECONDS, SleepCycle, mix_frames)
import test_pet_sleep


def pixels(pixmap):
    image = pixmap.toImage().convertToFormat(QImage.Format.Format_RGBA8888)
    return np.frombuffer(image.bits(), dtype=np.uint8).reshape(image.height(), image.bytesPerLine())[:, :image.width()*4].reshape(image.height(), image.width(), 4).copy()


class SleepAnimationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])
        cls.app.setQuitOnLastWindowClosed(False)

    def test_transition_endpoints_match_breathing_master_exactly(self):
        s=SleepCycle()
        self.assertTrue(np.array_equal(pixels(s.frame(0)), pixels(s.sequence_frame('settle',SETTLE_SECONDS))))
        self.assertTrue(np.array_equal(pixels(s.frame(0)), pixels(s.sequence_frame('wake',0))))

    def test_all_transition_assets_and_pillow_stability(self):
        # Fully interior pillow patch, away from the head/hand boundary.
        reference = np.array(Image.open(ASSETS/'00.png'))[190:225, 274:293]
        for name in ('settle','wake'):
            for i in range(MANIFEST[name]['count']):
                im=Image.open(ASSETS/'transitions'/f'{name}-{i:03}.png')
                self.assertEqual(im.size, tuple(MANIFEST['size']))
                self.assertEqual(im.mode,'RGBA')
                self.assertTrue(np.array_equal(np.array(im)[190:225,274:293],reference),(name,i))

    def test_playback_stretches_motion_and_holds_the_open_eyes(self):
        self.assertAlmostEqual(SETTLE_SECONDS, 2.1)
        self.assertAlmostEqual(WAKE_SECONDS, 1.5)
        self.assertAlmostEqual(WAKE_HOLD_SECONDS, .25)
        cycle = SleepCycle()
        midpoint = cycle.sequence_frame('settle', MANIFEST['settle']['seconds']*.5)
        self.assertTrue(np.array_equal(
            pixels(cycle.transition_frame('settle', SETTLE_SECONDS*.5)),
            pixels(midpoint)))
        last = cycle.sequence_frame('wake', MANIFEST['wake']['seconds'])
        self.assertTrue(np.array_equal(
            pixels(cycle.transition_frame('wake', WAKE_SECONDS-WAKE_HOLD_SECONDS)),
            pixels(last)))

    def test_breath_to_wake_first_frame_has_no_reset_for_every_breath_phase(self):
        for index in range(96):
            p,s=test_pet_sleep.SleepTests().pet();s.phase='asleep';s.last_frame=s.frame(index)
            before=pixels(s.last_frame)
            s.wake(p,'点击',100)
            self.assertTrue(np.array_equal(pixels(s.sample(100)),before),index)

    def test_interrupted_settling_uses_last_visible_pose(self):
        for elapsed in (.01,.3,.8,1.4):
            p,s=test_pet_sleep.SleepTests().pet();s.phase='settling';s.started=100
            s.last_frame=s.sample(100+elapsed)
            before=pixels(s.last_frame)
            s.wake(p,'消息',100+elapsed)
            self.assertTrue(np.array_equal(pixels(s.sample(100+elapsed)),before))
            self.assertIsNotNone(s.interrupted_settle)
            self.assertFalse(s.sample(100+elapsed+s.wake_seconds-.001).isNull())

    def test_weighted_blending_preserves_opaque_pillow(self):
        s=SleepCycle();a=s.frame(25);b=s.sequence_frame('wake',.08)
        for weight in (.05,.3,.5,.75,.95):
            actual=pixels(mix_frames(a,b,weight))
            self.assertTrue(np.all(actual[190:225,274:293,3]==255))

    def test_real_press_plays_wake_and_drag_cancels_sleep_before_release(self):
        with tempfile.TemporaryDirectory(prefix='yuki-sleep-gesture-') as directory:
            controller=PetApplication(self.app,SettingsStore(Path(directory)/'settings.ini'),enable_tray=False)
            try:
                controller.start();pet=controller.pet
                pet.advance_presence(10**10);pet.animator.timer.stop()
                pet.state.sleep.phase='asleep';pet.state.sleep.breath_started=0
                pet.renderer.last_display_image=QImage(180,190,QImage.Format.Format_ARGB32_Premultiplied)
                pet.renderer.last_display_image.fill(0)
                QTest.mousePress(pet,Qt.MouseButton.LeftButton,pos=QPoint(90,100))
                self.assertEqual(pet.state.sleep.phase,'waking')
                self.assertIsNone(pet.renderer.pointer_hold_image)
                pet.play_click_reaction('shy')
                self.assertIsNone(pet.state.action_player.action)
                QTest.mouseMove(pet,QPoint(120,100))
                self.assertTrue(pet.dragged)
                self.assertFalse(pet.state.sleep.transitioning)
                self.assertIsNotNone(pet.state.drag_feedback)
                QTest.mouseRelease(pet,Qt.MouseButton.LeftButton,pos=QPoint(120,100))
                self.assertFalse(pet.state.sleep.transitioning)
            finally:
                controller.cleanup()
                controller.window.deleteLater();controller.pet.deleteLater();controller.deleteLater()
                self.app.processEvents()


if __name__=='__main__':unittest.main()
