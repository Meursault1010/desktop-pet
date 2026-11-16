"""Presence transitions must finish, reverse and preserve visibility semantics."""
import os
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
import time
import unittest
from pet_presence import Presence


class PresenceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from PySide6.QtWidgets import QApplication
        cls.app = QApplication.instance() or QApplication([])

    def test_nonzero_monitor_uses_width_not_right_coordinate(self):
        p = Presence()
        p.begin(True,10,(3300,500),(1920,0,1920,1080),(180,190))
        self.assertEqual(p.origin[0],3840)
        self.assertEqual(p.destination,(3300,500))

    def test_peek_does_not_pause_entry(self):
        p = Presence()
        p.begin(True,10,(1500,500),(0,0,1920,1080),(180,190))
        self.assertNotEqual(p.position(10.4),p.position(10.8))
        self.assertNotEqual(p.position(11.7),p.position(10.8))

    def test_reversal_preserves_pose_and_position(self):
        p = Presence()
        p.begin(False,10,(1500,500),(0,0,1920,1080),(180,190))
        before = p.position(10.7)
        pixels = p.frame(10.7).toImage()
        p.begin(True,10.7,(1600,500),(0,0,1920,1080),(180,190))
        self.assertEqual(p.position(10.7),before)
        self.assertEqual(p.frame(10.7).toImage(),pixels)
        self.assertEqual(p.home,(1500,500))
        self.assertTrue(p.update(10.7+p.duration+.01))
        self.assertEqual(p.position(10.7+p.duration+.01),p.home)

    def test_arrival_has_no_scale_collapse_and_finishes_once(self):
        effect = Presence()
        effect.reset(False)
        effect.begin(True, 10, (1700, 800), (0, 0, 1920, 1080), (180, 190))
        start = effect.position(10)
        middle = effect.position(10+effect.duration/2)
        end = effect.position(10+effect.duration)
        self.assertGreater(start[0], middle[0])
        self.assertEqual(end, effect.destination)
        self.assertTrue(effect.update(10+effect.duration))
        self.assertFalse(effect.update(12))
        self.assertEqual(effect.value, 1)

    def test_departure_travels_to_nearest_edge(self):
        effect = Presence()
        effect.begin(False, 10, (30, 600), (0, 0, 1920, 1080), (180, 190))
        self.assertEqual(effect.edge, 'left')
        self.assertLess(effect.destination[0], 0)
        self.assertTrue(effect.update(10+effect.duration))
        self.assertEqual(effect.value, 0)

    def test_walk_segment_uses_constant_speed(self):
        effect = Presence()
        effect.begin(True, 10, (1500, 500), (0, 0, 1920, 1080), (180, 190))
        start = effect.walk_start
        end = effect.walk_end
        first = effect.position(10 + start + (end-start)*.25)[0]
        second = effect.position(10 + start + (end-start)*.50)[0]
        third = effect.position(10 + start + (end-start)*.75)[0]
        self.assertAlmostEqual(second-first, third-second, delta=.01)

    def test_edge_segments_are_continuous_and_constant_speed(self):
        for visible in (True, False):
            effect = Presence()
            effect.begin(visible, 10, (1500, 500), (0, 0, 1920, 1080), (180, 190))
            end = effect.walk_start if visible else effect.walk_end
            a = effect.position(10 + end*.25)[0]
            b = effect.position(10 + end*.50)[0]
            c = effect.position(10 + end*.75)[0]
            self.assertAlmostEqual(b-a, c-b, delta=.01)
            before = effect.position(10 + end - .001)[0]
            after = effect.position(10 + end + .001)[0]
            self.assertLess(abs(after-before), 3.)


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
        self.pet.advance_presence(self.pet.presence.started+self.pet.presence.duration+.01)

    def test_show_hide_and_idempotence(self):
        self.pet.present(True)
        self.assertTrue(self.pet.isVisible())
        self.assertTrue(self.pet.desired_visible())
        self.assertTrue(self.pet.presence.active)
        self.assertFalse(self.pet.movement_allowed())
        self.finish()
        home = self.pet.pos()
        self.pet.present(False)
        self.assertTrue(self.pet.isVisible())
        self.assertFalse(self.pet.desired_visible())
        self.finish()
        self.assertFalse(self.pet.isVisible())
        self.assertEqual(self.pet.pos(),home)
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

    def test_entrance_and_exit_emit_completion_signals(self):
        entered, exited = [], []
        self.pet.presence_entered.connect(lambda: entered.append(True))
        self.pet.presence_exited.connect(lambda: exited.append(True))
        self.pet.present(True)
        self.finish()
        self.assertEqual(entered, [True])
        self.assertTrue(self.pet.isVisible())
        self.pet.present(False)
        self.finish()
        self.assertEqual(exited, [True])
        self.assertFalse(self.pet.isVisible())

    def test_hide_interrupts_physics_and_drag(self):
        self.pet.show()
        self.pet.start_throw((300, -200))
        self.pet.present(False)
        self.assertFalse(self.pet.state.physics.active)
        self.assertIsNone(self.pet.drag_origin)
        self.assertIsNone(self.pet.state.click_reaction.started)
        self.finish()

    def test_render_mid_transition_and_preferences(self):
        from PySide6.QtGui import QImage, QPainter
        from PySide6.QtCore import Qt
        self.pet.present(True)
        sample_time = self.pet.presence.started+.4
        self.pet.advance_presence(sample_time)
        image = QImage(self.pet.size(), QImage.Format.Format_ARGB32_Premultiplied)
        image.fill(Qt.GlobalColor.transparent)
        painter = QPainter(image)
        # Paint the same sampled instant as the window position, rather than
        # combining a future position with the real-clock offscreen start.
        from unittest.mock import patch
        with patch('pet_presence.time.monotonic', return_value=sample_time):
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
