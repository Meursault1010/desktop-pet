"""Posture scheduling, sleep ownership and interruptible calm rests."""
import os
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
import json
import random
import unittest
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
from PySide6.QtWidgets import QApplication
from action_player import ActionPlayer, catalog
from idle_actions import IdleActions, IDLE_ACTIONS
from idle_states import CONFIG, STATES, posture_for, snapshot
from daily_routine import schedule
from pet import DesktopPet


class IdleStateTests(unittest.TestCase):
    def test_shared_taxonomy_and_both_catalogs_agree(self):
        root = Path(__file__).parent
        public = json.loads((root/'frontend/public/actions/catalog.json').read_text(encoding='utf-8'))
        self.assertEqual(list(STATES), ['sleep', 'stand', 'sit', 'prone'])
        self.assertEqual(CONFIG, json.loads((root/'frontend/public/actions/idle-states.json').read_text(encoding='utf-8')))
        for action in public:
            self.assertTrue(action['atlas'].endswith('/atlas.webp'))
            self.assertTrue(action['poster'].endswith('/poster.webp'))
        mirror = [{**action, 'atlas': action['atlas'].removesuffix('.webp') + '.png',
                   'poster': action['poster'].removesuffix('.webp') + '.png'} for action in public]
        self.assertEqual(list(catalog().values()), mirror)
        seen = []
        for state in STATES.values():
            for key in state['actions']:
                seen.append(key)
                self.assertEqual(catalog()[key]['idle_state'], state['id'])
                self.assertEqual(catalog()[key]['idle_automatic'], key in IDLE_ACTIONS)
                self.assertEqual(catalog()[key]['category'], state['name']+'待机')
        self.assertEqual(len(seen), len(set(seen)))
        self.assertEqual(posture_for('eat'), 'sit')
        self.assertEqual(posture_for('work'), 'sit')
        self.assertEqual(posture_for('reading-pose-3'), 'stand')
        self.assertEqual(posture_for('lazy-roll-away'), 'prone')
        self.assertIsNone(posture_for('dragged'))

    def test_three_awake_postures_get_a_turn_and_every_action_is_reachable(self):
        for seed in range(25):
            with patch('idle_actions.random', random.Random(seed)):
                idle = IdleActions()
                picks = [idle.choose(catalog()) for _ in IDLE_ACTIONS]
            self.assertEqual({posture_for(key) for key in picks[:3]}, {'stand', 'sit', 'prone'})
            self.assertEqual(set(picks), set(IDLE_ACTIONS))

    def test_sleep_cannot_bypass_recent_wake_cooldown_through_idle_lottery(self):
        for period in schedule():
            idle = IdleActions()
            idle.set_period(period)
            for _ in range(60):
                self.assertNotEqual(posture_for(idle.choose(catalog())), 'sleep')

    def test_ground_rest_extends_only_neutral_holds_and_stops_normally(self):
        for key in ('sit-neat', 'sit-relaxed', 'sit-swing', 'prone-chin', 'prone-rest'):
            player = ActionPlayer()
            idle = IdleActions()
            with patch('action_player.random', random.Random(15)), patch('idle_actions.random.uniform', return_value=30):
                duration = idle.play(player, key, 100)
            self.assertAlmostEqual(duration, 30)
            self.assertEqual(idle.posture, posture_for(key))
            self.assertEqual(player.action['durations'][:3], catalog()[key]['durations'][:3])
            self.assertEqual(player.action['durations'][-3:], catalog()[key]['durations'][-3:])
            self.assertIsNotNone(player.frame(129.9))
            self.assertIsNone(player.frame(130.1))
            self.assertNotEqual(sum(catalog()[key]['durations'])/1000, duration)

    def test_seated_reading_has_bounded_breathing_dwell(self):
        for key in ('reading-pose-1', 'reading-pose-2'):
            player = ActionPlayer()
            duration = IdleActions().play(player, key, 100)
            self.assertTrue(18 <= duration <= 28)
            self.assertEqual(player.frame(100+duration/2), 0)
            self.assertIsNone(player.frame(100+duration+.01))


class IdlePostureInteractionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def test_status_and_snapshot_follow_sleep_idle_and_manual_owners(self):
        pet = DesktopPet()
        pet.animator.timer.stop()
        pet.show()
        try:
            pet.advance_presence(10**10)
            for key in ('tea', 'sit-neat', 'prone-rest'):
                pet.state.ambient.play(pet.state.action_player, key, 100)
                value = snapshot(pet.state)
                activity = pet.activity()
                self.assertEqual(value['state'], posture_for(key))
                self.assertTrue(value['automatic'])
                self.assertIn(STATES[posture_for(key)]['name']+'待机', pet.status_text())
                self.assertEqual(activity['label'], pet.status_text())
                self.assertEqual(activity['key'], 'idle')
                self.assertEqual(activity['posture'], posture_for(key))
                self.assertEqual(activity['detail'], pet.state.action_player.action['name'])
            pet.state.action_player.play('read', now=101)
            self.assertFalse(snapshot(pet.state)['automatic'])
            with patch.object(pet.state.routine, 'update', return_value=False):
                pet.animator.update_ambient(102)
            self.assertEqual(pet.state.action_player.action['id'], 'read')
            pet.state.sleep.phase = 'asleep'
            self.assertEqual(snapshot(pet.state)['state'], 'sleep')
            pet.state.sleep.phase = 'awake'
            pet.state.action_player.stop()
            pet.state.ambient.current = None
            self.assertEqual(snapshot(pet.state)['state'], 'stand')
            self.assertEqual(pet.activity()['key'], 'idle')
            self.assertEqual(pet.activity()['label'], pet.status_text())
            pet.preferences = replace(pet.preferences, paused=True)
            self.assertEqual(pet.activity()['key'], 'paused')
            pet.preferences = replace(pet.preferences, paused=False)
            pet.state.sleep.phase = 'asleep'
            self.assertEqual(pet.activity()['key'], 'sleeping')
            self.assertEqual(pet.activity()['posture'], 'sleep')
            pet.state.sleep.phase = 'awake'
            pet.hide()
            self.assertEqual(pet.activity()['key'], 'hidden')
        finally:
            pet.close()
            pet.deleteLater()
            self.app.processEvents()

    def test_walking_is_reported_from_the_gait_instead_of_the_legacy_flag(self):
        pet = DesktopPet()
        pet.animator.timer.stop()
        pet.show()
        try:
            pet.advance_presence(10**10)
            pet.state.walking = False
            pet.move(120, 120)
            pet.advance_to((240, 120), 0.05)
            self.assertTrue(pet.state.walking)
            self.assertEqual(pet.activity()['key'], 'walking')
            self.assertEqual(pet.activity()['label'], '移动中')
            self.assertEqual(snapshot(pet.state)['name'], '互动')
            pet.state.gait_until = 0
            pet.state.gait_energy = 0
            pet.state.gait_energy_at = 0
            pet.state.walking = False
            self.assertEqual(pet.activity()['key'], 'idle')
            self.assertEqual(pet.activity()['label'],
                             '站立待机 · ' + pet.state.routine.period['name'])
        finally:
            pet.close()
            pet.deleteLater()
            self.app.processEvents()

    def test_patrol_activity_reports_its_live_phase(self):
        pet = DesktopPet()
        pet.animator.timer.stop()
        pet.show()
        try:
            pet.advance_presence(10**10)
            pet.state.patrol = SimpleNamespace(active=True, exploring=False,
                                               label='吃饭时间', phase='walking')
            activity = pet.activity()
            self.assertEqual(activity['key'], 'patrol')
            self.assertEqual(activity['label'], '吃饭时间')
            self.assertEqual(activity['detail'], '正在走过去')
            pet.state.patrol.phase = 'doing'
            self.assertEqual(pet.activity()['detail'], '正在互动')
            pet.state.patrol = None
        finally:
            pet.close()
            pet.deleteLater()
            self.app.processEvents()


if __name__ == '__main__':
    unittest.main()
