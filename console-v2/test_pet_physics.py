"""Throw, collision, lifecycle and manual attachment regression tests."""
import os
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
import math
import unittest
from unittest.mock import patch
from pet_physics import PetPhysics, PointerVelocity


class PhysicsTests(unittest.TestCase):
    def test_segment_callback_observes_reflected_path_and_consumes_throw(self):
        body=PetPhysics();body.launch((795,200),(1000,0))
        segments=[]
        def grab(start,end):
            segments.append((start,end))
            if end[0]<start[0] and start[0]>=790>=end[0]:
                body.cancel()
                return True
            return False
        self.assertFalse(body.step(.1,(0,0,800,600),grab))
        self.assertTrue(any(b[0]>a[0] for a,b in segments))
        self.assertTrue(any(b[0]<a[0] for a,b in segments))
        self.assertFalse(body.active)

    def test_pointer_velocity_and_stale_release(self):
        pointer = PointerVelocity()
        pointer.reset(0, 0, 1)
        for i in range(1, 7):
            pointer.add(i*10, -i*5, 1+i*.015)
        vx, vy = pointer.release(60, -30, 1.09)
        self.assertAlmostEqual(vx, 1000/1.5)
        self.assertAlmostEqual(vy, -500/1.5)
        self.assertEqual(pointer.release(60, -30, 1.5), (0., 0.))

    def test_fast_pointer_is_bounded_and_resize_is_not_sampled(self):
        pointer = PointerVelocity()
        pointer.reset(0, 0, 0)
        pointer.add(10000, 10000, .02)
        self.assertLessEqual(math.hypot(*pointer.release(10000, 10000, .03)), 1600.001)

    def test_fall_bounces_and_settles_once(self):
        body = PetPhysics()
        body.launch((200, 0), (450, -300))
        events = 0
        saw_up_after_landing = False
        for _ in range(1800):
            events += body.step(1/120, (0, 0, 800, 600))
            saw_up_after_landing |= body.impact == 'floor' and body.vy < 0
            self.assertTrue(0 <= body.x <= 800)
            self.assertTrue(0 <= body.y <= 600)
        self.assertTrue(saw_up_after_landing)
        self.assertFalse(body.active)
        self.assertEqual(events, 1)
        self.assertEqual(body.y, 600)

    def test_wall_and_ceiling_reduce_velocity(self):
        for position, velocity, impact, axis in (
            ((1, 200), (-1000, 0), 'left', 'vx'),
            ((799, 200), (1000, 0), 'right', 'vx'),
            ((200, 1), (0, -1000), 'ceiling', 'vy')):
            body = PetPhysics()
            body.launch(position, velocity)
            body.step(.02, (0, 0, 800, 600))
            self.assertEqual(body.impact, impact)
            self.assertLess(abs(getattr(body, axis)), 1000)
            angle, sx, sy = body.transform()
            self.assertAlmostEqual(sx*sy, 1)

    def test_frame_rate_independence(self):
        results = []
        for hz in (30, 60, 120):
            body = PetPhysics()
            body.launch((100, 100), (300, -200))
            for _ in range(hz):
                body.step(1/hz, (0, 0, 2000, 2000))
            results.append((body.x, body.y))
        for result in results[1:]:
            self.assertLess(math.dist(result, results[0]), 2)

    def test_negative_monitor_origin_and_small_screen(self):
        for bounds in ((-1600, -500, -1000, 0), (-100, -100, -100, -100)):
            body = PetPhysics()
            body.launch((bounds[0], bounds[1]), (-900, -900))
            for _ in range(1500):
                body.step(1/60, bounds)
            self.assertFalse(body.active)
            self.assertEqual(body.y, bounds[3])

    def test_pause_before_release_removes_old_momentum(self):
        pointer = PointerVelocity()
        pointer.reset(0, 0, 0)
        pointer.add(100, 0, .05)
        pointer.add(100, 0, .3)
        self.assertEqual(pointer.release(100, 0, .32), (0., 0.))

    def test_authored_physics_clip_starts_on_contact_and_recovers_to_flight(self):
        body = PetPhysics()
        body.launch((100, 100), (400, -300))
        self.assertEqual(body.animation_frame(), ('throw-flight', 0))
        body.hit('right', 700)
        self.assertEqual(body.animation_frame(), ('impact-right', 6))
        body.impact_age = .12
        self.assertEqual(body.animation_frame(), ('impact-right', 6))
        body.impact_age = .9
        self.assertEqual(body.animation_frame(), ('impact-right', 7))

    def test_flight_settles_without_replaying_large_poses_and_squash_is_subtle(self):
        body = PetPhysics()
        body.launch((100, 100), (1000, -300))
        for age in (2, 3, 4, 6):
            body.age = age
            self.assertEqual(body.animation_frame(), ('throw-flight', 11))
        body.hit('right', 1000)
        angle, sx, sy = body.transform()
        self.assertLess(abs(sx-1), .06)
        self.assertLess(abs(sy-1), .06)
        self.assertAlmostEqual(sx*sy, 1)

    def test_repeated_collisions_decay_even_when_later_speed_is_higher(self):
        body = PetPhysics()
        body.launch((100, 100), (800, -300))
        strengths = []
        for count, speed in enumerate((700, 1400, 1600, 900, 1500), 1):
            body.hit('floor', speed)
            strengths.append(body.strength)
            frame = body.animation_frame()[1]
            if count == 2:
                self.assertIn(frame, (6, 7))
            if count >= 3:
                self.assertEqual(frame, 7)
        self.assertTrue(all(b < a for a, b in zip(strengths, strengths[1:])))
        self.assertLess(abs(body.transform()[1]-1), .001)
        body.launch((100, 100), (800, -300))
        self.assertEqual(body.collision_count, 0)
        body.hit('left', 700)
        self.assertEqual(body.strength, 1)


class PetPhysicsIntegration(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from PySide6.QtWidgets import QApplication
        cls.app = QApplication.instance() or QApplication([])
        cls.app.setQuitOnLastWindowClosed(False)

    def setUp(self):
        from pet import DesktopPet
        self.pet = DesktopPet()
        from datetime import datetime
        from daily_routine import current_period
        self.pet.state.routine.period = current_period(datetime(2026, 1, 1, 10))
        self.pet.state.ambient.set_period(self.pet.state.routine.period)
        from unittest.mock import patch
        self.clock_patch = patch.object(self.pet.state.routine, 'update', return_value=False)
        self.clock_patch.start()
        self.pet.show()
        self.pet.animator.timer.stop()

    def tearDown(self):
        self.clock_patch.stop()
        self.pet.close()
        self.pet.deleteLater()
        self.app.sendPostedEvents(None, 0)
        self.app.processEvents()

    def test_regrab_hide_home_and_resize_cancel(self):
        from PySide6.QtCore import QPointF, Qt
        from PySide6.QtGui import QMouseEvent
        from dataclasses import replace
        operations = [lambda: self.pet.hide(), lambda: self.pet.go_home(),
            lambda: self.pet.apply_preferences(replace(self.pet.preferences, size=120)),
            lambda: self.pet.mousePressEvent(QMouseEvent(QMouseEvent.Type.MouseButtonPress,
                QPointF(90, 90), QPointF(self.pet.pos())+QPointF(90, 90),
                Qt.MouseButton.LeftButton, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier))]
        for operation in operations:
            self.pet.show()
            self.pet.start_throw((300, -300))
            operation()
            self.assertFalse(self.pet.state.physics.active)

    def test_manual_drop_snap_wins_otherwise_throws(self):
        from PySide6.QtCore import QPoint, QPointF, Qt
        from PySide6.QtGui import QMouseEvent
        for attached in (True, False):
            self.pet.drag_origin = QPoint(90, 90)
            self.pet.dragged = True
            event = QMouseEvent(QMouseEvent.Type.MouseButtonRelease, QPointF(90, 90),
                QPointF(self.pet.pos())+QPointF(90, 90), Qt.MouseButton.LeftButton,
                Qt.MouseButton.NoButton, Qt.KeyboardModifier.NoModifier)
            with patch('drop_attachment.settle_drop', return_value=attached):
                self.pet.mouseReleaseEvent(event)
            self.assertEqual(self.pet.state.physics.active, not attached)

    def test_catch_without_drag_resumes_falling_on_release(self):
        from PySide6.QtCore import QPointF, Qt
        from PySide6.QtGui import QMouseEvent
        self.pet.start_throw((300, -200))
        for kind in (QMouseEvent.Type.MouseButtonPress, QMouseEvent.Type.MouseButtonRelease):
            event = QMouseEvent(kind, QPointF(90, 90), QPointF(self.pet.pos())+QPointF(90, 90),
                Qt.MouseButton.LeftButton, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier)
            if kind == QMouseEvent.Type.MouseButtonPress:
                self.pet.mousePressEvent(event)
                self.assertFalse(self.pet.state.physics.active)
            else:
                self.pet.mouseReleaseEvent(event)
        self.assertTrue(self.pet.state.physics.active)
        self.assertEqual(self.pet.state.physics.vx, 0)
        self.assertFalse(self.pet.click_timer.isActive())

    def test_manual_throw_still_works_in_quiet_mode(self):
        from dataclasses import replace
        self.pet.apply_preferences(replace(self.pet.preferences, quiet=True))
        self.pet.start_throw((200, -300))
        self.pet.animator.timer.stop()
        self.assertTrue(self.pet.state.physics.active)
        self.pet.advance_physics(.05)
        self.assertNotEqual(self.pet.state.physics.vy, -300)
        self.assertFalse(self.pet.movement_allowed())

    def test_flight_blocks_ambient_and_walking_then_recovers(self):
        self.pet.move(100, 100)
        self.pet.start_throw((200, -200))
        self.pet.animator.timer.stop()
        self.assertFalse(self.pet.movement_allowed())
        self.pet.state.ambient.next_at = 0
        self.pet.animator.update_ambient(100)
        self.assertIsNone(self.pet.state.action_player.action)
        for _ in range(1000):
            if self.pet.state.physics.active:
                self.pet.advance_physics(1/60)
        self.assertFalse(self.pet.state.physics.active)
        self.assertIsNone(self.pet.state.travel_target)
        self.assertTrue(self.pet.movement_allowed())


if __name__ == '__main__':
    unittest.main()
