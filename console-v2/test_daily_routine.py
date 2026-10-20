"""Local-clock boundaries, weighted choices, and interaction priority."""
import os
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
import time
import unittest
from datetime import datetime
from unittest.mock import patch
from daily_routine import DailyRoutine, current_period, schedule
from idle_actions import IdleActions
from action_player import catalog
from PySide6.QtWidgets import QApplication
from pet import DesktopPet


class RoutineTests(unittest.TestCase):
    def test_boundaries_and_resume(self):
        expected = {0:'night',5:'night',6:'night',7:'morning',9:'focus',12:'noon',13:'nap',
                    14:'afternoon',18:'evening',21:'winddown',23:'night'}
        routine = DailyRoutine()
        for hour, key in expected.items():
            at = datetime(2026, 1, 1, hour, 59)
            self.assertEqual(current_period(at)['key'], key)
            routine.update(at)
            self.assertEqual(routine.snapshot()['key'], key)
        routine.update(datetime(2026, 1, 5, 10))
        self.assertEqual(routine.snapshot()['name'], '日间阅读')

    def test_catalog_and_weighted_bag(self):
        available = catalog()
        for period in schedule():
            self.assertTrue(set(period['preferred']).issubset(available))
        ambient = IdleActions()
        ambient.set_period(schedule()[0])
        choices = [ambient.choose(available) for _ in range(40)]
        self.assertTrue(set(choices).issubset(schedule()[0]['only']))
        # Persistent sleep owns its clock and two-minute wake cooldown.
        self.assertNotIn('sleep', choices)
        ambient.set_period(schedule()[1])
        self.assertEqual(ambient.bag, [])
        self.assertNotIn('folder-sleep', [ambient.choose(available) for _ in range(40)])


class RoutineInteractionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])
        cls.app.setQuitOnLastWindowClosed(False)

    def setUp(self):
        self.pet = DesktopPet()
        self.pet.show()
        self.pet.animator.timer.stop()
        self.pet.bubble.timer.stop()

    def tearDown(self):
        self.pet.close()
        self.pet.deleteLater()
        self.app.processEvents()

    def test_night_stops_walking_without_cancelling_manual_action(self):
        state = self.pet.state
        state.ambient.set_period(schedule()[1])
        state.routine.period = schedule()[0]
        state.walking = True
        state.action_player.play('read', now=time.monotonic())
        with patch.object(state.routine, 'update', return_value=False):
            self.pet.animator.update_ambient(time.monotonic())
        self.assertFalse(state.walking)
        self.assertEqual(state.action_player.action['id'], 'read')
        self.assertFalse(self.pet.movement_allowed())

    def test_chat_wakes_automatic_sleep_and_prevents_new_idle(self):
        state = self.pet.state
        now = time.monotonic()
        state.routine.period = schedule()[0]
        state.ambient.set_period(state.routine.period)
        state.action_player.play('sleep', loop=True, now=now)
        state.ambient.current = ('sleep', now, 0., 100.)
        self.pet.bubble.say('你好，我醒着。')
        self.assertIsNone(state.action_player.action)
        state.ambient.next_at = 0
        with patch.object(state.routine, 'update', return_value=False):
            self.pet.animator.update_ambient(now+1)
        self.assertIsNone(state.action_player.action)
        self.assertIsNone(state.ambient.current)
