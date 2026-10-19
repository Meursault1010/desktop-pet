"""Presence transitions must finish, reverse and preserve visibility semantics."""
import os
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
import time
import unittest
from pet_presence import Presence


class PresenceTests(unittest.TestCase):
    def test_arrival_has_no_scale_collapse_and_finishes_once(self):
        effect = Presence()
        effect.reset(False)
        effect.begin(True, 10)
        for i in range(10):
            effect.update(10+i*.08)
            opacity, lift, sx, sy = effect.body()
            self.assertTrue(0 <= opacity <= 1)
            self.assertAlmostEqual(sx*sy, 1)
            self.assertGreater(sy, .97)
        self.assertTrue(effect.update(11))
        self.assertFalse(effect.update(12))
        self.assertEqual(effect.value, 1)

    def test_reverse_has_continuous_opacity(self):
        effect = Presence()
        effect.begin(False, 10)
        effect.update(10.3)
        before = effect.value
        effect.begin(True, 10.3)
        self.assertEqual(effect.value, before)
        effect.update(11)
        self.assertEqual(effect.value, 1)


class PresenceIntegration(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from PySide6.QtWidgets import QApplication
        cls.app = QApplication.instance() or QApplication([])
        cls.app.setQuitOnLastWindowClosed(False)

    def setUp(self):
        from pet import DesktopPet
        self.pet = DesktopPet()

    def tearDown(self):
        self.pet.close()
        self.pet.deleteLater()
        self.app.sendPostedEvents(None, 0)
        self.app.processEvents()

    def finish(self):
        self.pet.advance_presence(time.monotonic()+2)

    def test_show_hide_and_idempotence(self):
        self.pet.present(True)
        self.assertTrue(self.pet.isVisible())
        self.assertTrue(self.pet.desired_visible())
        self.assertTrue(self.pet.presence.active)
        self.assertFalse(self.pet.movement_allowed())
        self.finish()
        self.pet.present(False)
        self.assertTrue(self.pet.isVisible())
        self.assertFalse(self.pet.desired_visible())
        self.finish()
        self.assertFalse(self.pet.isVisible())
        self.assertFalse(self.pet.presence_timer.isActive())
        self.pet.present(False)
        self.assertFalse(self.pet.presence_timer.isActive())

    def test_toggle_during_departure_and_external_hide(self):
        self.pet.show()
        self.pet.present(False)
        self.pet.advance_presence(self.pet.presence.started+.3)
        self.pet.present(True)
        self.finish()
        self.assertTrue(self.pet.isVisible())
        self.assertFalse(self.pet.presence.active)
        self.pet.present(False)
        self.pet.hide()
        self.assertFalse(self.pet.presence_timer.isActive())
        self.assertFalse(self.pet.presence.active)

    def test_hide_interrupts_physics_and_drag(self):
        self.pet.show()
        self.pet.start_throw((300, -200))
        self.pet.present(False)
        self.assertFalse(self.pet.state.physics.active)
        self.assertIsNone(self.pet.drag_origin)
        self.assertFalse(self.pet.click_timer.isActive())
        self.finish()

    def test_render_mid_transition_and_preferences(self):
        from PySide6.QtGui import QImage, QPainter
        from PySide6.QtCore import Qt
        self.pet.present(True)
        self.pet.advance_presence(self.pet.presence.started+.4)
        image = QImage(self.pet.size(), QImage.Format.Format_ARGB32_Premultiplied)
        image.fill(Qt.GlobalColor.transparent)
        painter = QPainter(image)
        self.pet.render(painter, self.pet.rect().topLeft())
        painter.end()
        self.assertTrue(any(image.pixelColor(x,y).alpha() for x in range(0,180,10) for y in range(0,190,10)))
        self.assertEqual(self.pet.preferences.opacity, 100)

    def test_window_flag_change_preserves_departure(self):
        from dataclasses import replace
        self.pet.show()
        self.pet.present(False)
        self.pet.apply_preferences(replace(self.pet.preferences, always_on_top=False, opacity=70))
        self.assertFalse(self.pet.desired_visible())
        self.finish()
        self.assertFalse(self.pet.isVisible())
        self.assertEqual(self.pet.preferences.opacity, 70)


if __name__ == '__main__':
    unittest.main()
