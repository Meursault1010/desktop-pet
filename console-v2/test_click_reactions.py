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
from pet import DesktopPet
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

    def test_single_is_delayed_shy_and_never_jumps_or_moves_window(self):
        origin = self.pet.pos()
        self.click()
        self.assertTrue(self.pet.click_timer.isActive())
        self.assertIsNone(self.pet.state.action_player.action)
        self.pet.click_timer.stop()
        self.pet.click_timer.timeout.emit()
        self.assertEqual(self.pet.state.action_player.action['id'], 'shy')
        self.assertEqual(self.pet.state.click_reaction.kind, 'shy')
        self.assertIsNone(self.pet.state.jump_started)
        self.assertEqual(self.pet.pos(), origin)

    def test_qt_double_sequence_only_plays_headpat(self):
        with patch.object(self.pet, 'play_click_reaction', wraps=self.pet.play_click_reaction) as play:
            self.click()
            self.pet.mouseDoubleClickEvent(self.event(QMouseEvent.Type.MouseButtonDblClick))
            self.pet.mouseReleaseEvent(self.event(QMouseEvent.Type.MouseButtonRelease))
            self.assertFalse(self.pet.click_timer.isActive())
            self.assertEqual(play.call_args_list, [unittest.mock.call('headpat')])
            self.assertEqual(self.pet.state.action_player.action['id'], 'affection')
            self.assertEqual(self.pet.state.click_reaction.kind, 'headpat')

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

    def test_hide_cancels_single_before_timeout(self):
        self.click()
        self.pet.hide()
        self.assertFalse(self.pet.click_timer.isActive())
        self.pet.finish_single_click()
        self.assertIsNone(self.pet.state.action_player.action)

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
        self.assertGreater(compressed[3], 1.1)
        self.assertLess(compressed[4], .9)
        self.assertLess(rebound[3], 1.)
        self.assertGreater(rebound[4], 1.05)
        self.assertNotEqual(compressed[5], 0)
        self.assertEqual(response.transform(100), (0, 0, 0, 1, 1, 0))


if __name__ == '__main__':
    unittest.main()
