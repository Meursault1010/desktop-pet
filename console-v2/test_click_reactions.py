"""Mouse classification and bounded spring feedback must not interfere with drag."""
import os
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
import time
import unittest
from unittest.mock import patch
from PySide6.QtCore import QPointF, Qt
from PySide6.QtGui import QMouseEvent
from PySide6.QtWidgets import QApplication
from click_reaction import ClickReaction
from pet import DesktopPet, FRAME_INTERVAL_MS
from settings_model import Preferences


class ClickTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])
        cls.app.setQuitOnLastWindowClosed(False)

    def setUp(self):
        self.pet = DesktopPet(Preferences())
        self.pet.show()
        self.pet.animator.timer.stop()

    def tearDown(self):
        self.pet.close()
        self.pet.deleteLater()
        self.app.sendPostedEvents(None, 0)
        self.app.processEvents()

    def event(self, kind, x=125, y=65):
        point = QPointF(x, y)
        origin = QPointF(self.pet.pos())
        buttons = Qt.MouseButton.NoButton if kind == QMouseEvent.Type.MouseButtonRelease else Qt.MouseButton.LeftButton
        return QMouseEvent(kind, point, point+origin, Qt.MouseButton.LeftButton, buttons, Qt.KeyboardModifier.NoModifier)

    def click(self):
        self.pet.mousePressEvent(self.event(QMouseEvent.Type.MouseButtonPress))
        self.pet.mouseReleaseEvent(self.event(QMouseEvent.Type.MouseButtonRelease))

    def test_single_is_immediate_shy_and_never_jumps_or_moves_window(self):
        origin = self.pet.pos()
        self.click()
        self.assertFalse(self.pet.click_timer.isActive())
        self.assertEqual(self.pet.state.action_player.action['id'], 'shy')
        self.assertEqual(self.pet.state.click_reaction.kind, 'shy')
        player = self.pet.state.action_player
        self.assertEqual(player.frame_order, [2])
        self.assertEqual(player.frame(player.started+.5), 2)
        self.assertEqual(player.motion_sample(player.started+.5), (('shy',2),('shy',2),0.))
        self.assertIsNone(self.pet.state.jump_started)
        self.assertEqual(self.pet.pos(), origin)

    def test_qt_double_sequence_only_plays_shy_jelly_once(self):
        with patch.object(self.pet, 'play_click_reaction', wraps=self.pet.play_click_reaction) as play:
            self.click()
            self.pet.mouseDoubleClickEvent(self.event(QMouseEvent.Type.MouseButtonDblClick))
            self.pet.mouseReleaseEvent(self.event(QMouseEvent.Type.MouseButtonRelease))
            self.assertFalse(self.pet.click_timer.isActive())
            self.assertEqual(play.call_args_list, [unittest.mock.call('shy'), unittest.mock.call('shy')])
            self.assertEqual(self.pet.state.action_player.action['id'], 'shy')
            self.assertEqual(self.pet.state.click_reaction.kind, 'shy')

    def test_drag_and_hide_cancel_pending_reactions(self):
        self.click()
        self.pet.mousePressEvent(self.event(QMouseEvent.Type.MouseButtonPress))
        self.pet.mouseMoveEvent(self.event(QMouseEvent.Type.MouseMove, 155, 95))
        self.assertTrue(self.pet.dragged)
        self.assertFalse(self.pet.click_timer.isActive())
        self.assertIsNone(self.pet.state.click_reaction.started)
        self.assertIsNone(self.pet.state.action_player.action)
        self.pet.hide()
        self.assertFalse(self.pet.click_timer.isActive())
        self.assertIsNone(self.pet.drag_origin)
        self.assertIsNone(self.pet.state.drag_feedback)

    def test_press_is_gesture_neutral_and_drag_uses_smoother_refresh(self):
        self.pet.state.click_reaction.trigger('shy', 120)
        self.pet.mousePressEvent(self.event(QMouseEvent.Type.MouseButtonPress))
        self.assertIsNone(self.pet.state.click_reaction.started)
        self.assertEqual(self.pet.animator.timer.interval(), FRAME_INTERVAL_MS)
        self.pet.mouseMoveEvent(self.event(QMouseEvent.Type.MouseMove, 155, 95))
        self.assertTrue(self.pet.dragged)
        self.assertEqual(self.pet.animator.timer.interval(), FRAME_INTERVAL_MS)
        self.assertIsNone(self.pet.state.click_reaction.started)
        self.pet.end_drag_feedback()
        self.assertEqual(self.pet.animator.timer.interval(), FRAME_INTERVAL_MS)

    def test_press_preserves_action_frame_until_drag_is_classified(self):
        from PySide6.QtGui import QImage, QPainter
        self.pet.state.action_player.play('read')
        self.pet.state.click_reaction.trigger('headpat',150,now=time.monotonic()-.08)
        image=QImage(180,190,QImage.Format.Format_ARGB32_Premultiplied)
        image.fill(0)
        painter=QPainter(image)
        self.pet.renderer.draw(painter,self.pet.state)
        painter.end()
        visible=self.pet.renderer.last_display_image
        self.pet.mousePressEvent(self.event(QMouseEvent.Type.MouseButtonPress))
        self.assertIs(self.pet.renderer.pointer_hold_image,visible)
        self.assertIsNone(self.pet.state.click_reaction.started)
        held=image.copy();held.fill(0)
        painter=QPainter(held)
        with patch.object(self.pet.renderer,'draw_pose',side_effect=AssertionError('intermediate pose')):
            self.pet.renderer.draw(painter,self.pet.state)
        painter.end()
        self.assertEqual(held,image,'press must preserve the actually rendered pixels')
        self.pet.mouseMoveEvent(self.event(QMouseEvent.Type.MouseMove,155,95))
        self.assertIsNone(self.pet.renderer.pointer_hold_image)
        self.assertTrue(self.pet.dragged)

    def test_drag_never_resizes_native_window_or_reanchors_pointer(self):
        self.pet.mousePressEvent(self.event(QMouseEvent.Type.MouseButtonPress))
        size=self.pet.size()
        anchor=self.pet.drag_origin
        with patch.object(self.pet,'setFixedSize',side_effect=AssertionError('native resize during drag')):
            self.pet.mouseMoveEvent(self.event(QMouseEvent.Type.MouseMove,155,95))
            self.assertEqual(self.pet.drag_origin,anchor)
            self.assertEqual(self.pet.size(),size)
            self.assertTrue(self.pet.state.drag_feedback.compact)
            self.pet.end_drag_feedback()
        self.assertEqual(self.pet.size(),size)

    def test_hide_cancels_single_before_timeout(self):
        self.click()
        self.pet.hide()
        self.assertFalse(self.pet.click_timer.isActive())
        with patch.object(self.pet, 'play_click_reaction') as play:
            self.pet.finish_single_click()
            play.assert_not_called()

    def test_spring_is_bounded_directional_and_returns_to_rest(self):
        response = ClickReaction()
        for kind in ('press', 'shy', 'headpat'):
            for x in (-1000, 0, 90, 180, 1000):
                for repeat in range(30):
                    response.trigger(kind, x, now=100)
                for step in range(181):
                    dx, dy, angle, sx, sy, shear = response.transform(100+step/100)
                    self.assertLessEqual(abs(dx), 6)
                    self.assertLessEqual(abs(dy), 4)
                    self.assertLessEqual(abs(angle), 3)
                    self.assertTrue(.8 <= sx <= 1.25)
                    self.assertTrue(.8 <= sy <= 1.25)
                    self.assertAlmostEqual(sx*sy, 1.)
                    self.assertLessEqual(abs(shear), .065)
                self.assertEqual(response.transform(102), (0, 0, 0, 1, 1, 0))
        response.trigger('shy', 0, now=100)
        left = response.transform(100.9)
        response.trigger('shy', 180, now=100)
        right = response.transform(100.9)
        self.assertAlmostEqual(left[0], -right[0])
        self.assertGreater(left[0], 0)

    def test_jelly_compresses_then_stretches_without_shrinking(self):
        response = ClickReaction()
        response.trigger('headpat', 150, now=100)
        compressed = response.transform(100.07)
        rebound = response.transform(100.25)
        self.assertGreater(compressed[3], 1.04)
        self.assertLess(compressed[4], .96)
        self.assertLess(rebound[3], 1.)
        self.assertGreater(rebound[4], 1.)
        self.assertNotEqual(compressed[5], 0)
        self.assertEqual(response.transform(100), (0, 0, 0, 1, 1, 0))

    def test_shy_expression_has_large_jelly_without_accumulation(self):
        response = ClickReaction()
        response.trigger('shy', 150, now=100)
        _, _, _, sx, sy, _ = response.transform(100.09)
        self.assertGreater(sx, 1.18)
        self.assertLess(sy, .85)
        self.assertAlmostEqual(sx*sy, 1.)


if __name__ == '__main__':
    unittest.main()
