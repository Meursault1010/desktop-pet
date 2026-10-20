"""Errands, meal receipts, desktop visibility and manual-input priority."""
import os
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
from dataclasses import replace
from datetime import datetime
from pathlib import Path
import tempfile
import time
import unittest
from unittest.mock import patch
from PySide6.QtWidgets import QApplication
from main import PetApplication
from settings_model import Preferences, SettingsStore
from daily_routine import current_period
from pet_patrol import Patrol, due_meal


class MealTests(unittest.TestCase):
    def test_windows_receipts_and_new_day(self):
        for hour, key in ((7,'breakfast'),(8,'breakfast'),(12,'lunch'),(13,'lunch'),(18,'dinner'),(19,'dinner')):
            at = datetime(2026,1,1,hour)
            meal = due_meal(at, {})
            self.assertEqual(meal[0], key)
            self.assertIsNone(due_meal(at, {key:meal[1]}))
            self.assertIsNotNone(due_meal(datetime(2026,1,2,hour), {key:meal[1]}))
        for hour in (0,6,9,11,14,17,20,23):
            self.assertIsNone(due_meal(datetime(2026,1,1,hour), {}))


class PatrolTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])
        cls.app.setQuitOnLastWindowClosed(False)

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix='yuki-patrol-')
        self.store = SettingsStore(Path(self.tmp.name)/'settings.ini')
        self.store.save(replace(Preferences(),auto_snap=False))
        self.controller = PetApplication(self.app,self.store,enable_tray=False,create_console=False)
        self.pet = self.controller.pet
        self.pet.show()
        self.pet.animator.timer.stop()
        self.pet.bubble.timer.stop()
        self.pet.move(250,200)
        self.life = self.controller.patrol
        self.now = time.monotonic()
        self.at = datetime(2026,1,1,10)
        self.pet.state.routine.period = current_period(self.at)
        self.pet.state.ambient.set_period(self.pet.state.routine.period)
        self.life.next_at = 0
        self.visibility = patch.object(self.life,'exposed',return_value=True)
        self.visibility.start()
        self.scan = patch.object(self.controller.icon_sleep,'refresh')
        self.scan.start()

    def tearDown(self):
        self.controller.cleanup()
        self.scan.stop()
        self.visibility.stop()
        self.pet.deleteLater()
        self.controller.deleteLater()
        self.app.processEvents()
        self.tmp.cleanup()

    def finish_action(self):
        until = self.life.until
        self.pet.state.action_player.frame(until+.1)
        self.life.tick(until+.1,.03,self.at)

    def test_meal_finishes_once_and_survives_restart(self):
        self.at = datetime(2026,1,1,12)
        self.life.tick(self.now,.03,self.at)
        self.assertEqual(self.life.kind,'meal')
        self.assertEqual(self.pet.state.action_player.action['id'],'eat')
        self.assertEqual(self.life.completed['lunch'],'')
        self.finish_action()
        fresh = Patrol(self.pet,self.controller.icon_sleep,self.store)
        self.assertEqual(fresh.completed['lunch'],'2026-01-01/lunch')
        self.assertIsNone(due_meal(self.at,fresh.completed))

    def test_interrupted_meal_is_not_recorded_as_completed(self):
        self.life.tick(self.now,.03,datetime(2026,1,1,12))
        self.pet.bubble.say('来聊天。')
        self.assertFalse(self.life.active)
        self.assertEqual(self.life.completed['lunch'],'')
        self.assertIsNone(self.pet.state.action_player.action)

    def test_snack_has_long_cooldown_and_no_night_snacking(self):
        self.life.next_snack = 0
        self.life.tick(self.now,.03,self.at)
        self.assertEqual(self.life.kind,'snack')
        self.assertGreaterEqual(self.life.next_snack-self.now,1200)
        self.life.cancel(self.now)
        self.pet.bubble.clear()
        self.life.next_at = self.life.next_snack = 0
        self.life.tick(self.now+5,.03,datetime(2026,1,1,23))
        self.assertFalse(self.life.active)

    def test_walk_uses_gait_and_cancels_for_chat(self):
        with patch.object(self.life,'icon_destination',return_value=None), patch('pet_patrol.random.random',return_value=.9):
            self.life.tick(self.now,.03,self.at)
        self.assertEqual(self.life.phase,'walking')
        previous = self.pet.pos()
        self.life.tick(self.now+.1,.1,self.at)
        self.assertNotEqual(self.pet.pos(),previous)
        self.assertGreater(self.pet.state.gait_distance,0)
        self.pet.bubble.say('在这里陪我。')
        self.assertFalse(self.life.active)
        self.assertIsNone(self.life.destination)

    def test_quiet_pause_and_disable_cancel_automatic_plans(self):
        for field in ('quiet','paused','random_movement'):
            self.life.kind = 'roll'
            self.life.play('lazy-roll-toward',self.now)
            self.controller.set_preference(field,field != 'random_movement')
            self.assertFalse(self.life.active)
            self.assertIsNone(self.pet.state.action_player.action)
            self.controller.set_preference(field,field == 'random_movement')

    def test_roll_moves_and_stays_inside_screen(self):
        with patch.object(self.life,'icon_destination',return_value=None), patch('pet_patrol.random.random',return_value=.1):
            self.life.tick(self.now,.03,self.at)
        self.assertEqual(self.life.kind,'roll')
        origin = self.pet.pos()
        self.life.tick((self.now+self.life.until)/2,.03,self.at)
        direction=-1 if self.pet.state.action_player.action['id']=='lazy-roll-toward' else 1
        self.assertGreater((self.pet.y()-origin.y())*direction,0)
        self.assertEqual(self.pet.x(),origin.x())
        self.assertTrue(self.pet.screen_area().contains(self.pet.geometry()))

    def test_due_ambient_yields_no_slot_to_optional_patrol_but_meals_still_run(self):
        self.pet.state.ambient.next_at = self.now-1
        with patch.object(self.life, 'icon_destination') as choose_icon:
            self.life.tick(self.now, .03, self.at)
            choose_icon.assert_not_called()
        self.assertFalse(self.life.active)
        self.assertGreater(self.life.next_at, self.now+79)
        self.life.tick(self.now, .03, datetime(2026, 1, 1, 12))
        self.assertEqual(self.life.kind, 'meal')

    def icon(self):
        icon = dict(id='test-icon', name='Test folder',folder=True,rect=dict(x=320,y=230,width=48,height=48))
        self.controller.icon_sleep.icons = [icon]
        return icon

    def test_nap_arrives_before_sleeping_and_cancels_on_icon_move(self):
        icon = self.icon()
        target = (self.pet.x(),self.pet.y())
        with patch.object(self.life,'icon_destination',return_value=(0,icon,target,self.pet.screen())), \
                patch('pet_patrol.random.random',return_value=.1), patch('pet_patrol.random.choice',return_value='nap'):
            self.life.tick(self.now,.03,self.at)
        self.assertEqual(self.life.phase,'walking')
        self.assertIsNone(self.pet.state.action_player.action)
        self.life.tick(self.now+.1,.1,self.at)
        self.assertEqual(self.pet.state.action_player.action['id'],'sleep')
        self.assertTrue(self.pet.state.action_player.loop)
        self.controller.icon_sleep.icons = [dict(icon,rect=dict(x=400,y=230,width=48,height=48))]
        self.life.tick(self.now+2,.1,self.at)
        self.assertFalse(self.life.active)

    def test_user_action_is_not_overwritten_or_stopped(self):
        self.life.kind = 'roll'
        self.life.play('lazy-roll-toward',self.now)
        self.pet.state.action_player.play('read',now=self.now+1)
        self.life.tick(self.now+1.1,.03,self.at)
        self.assertFalse(self.life.active)
        self.assertEqual(self.pet.state.action_player.action['id'],'read')

    def test_lean_reaches_exact_contact_then_releases_for_drag(self):
        icon = self.icon()
        target = (self.pet.x(),self.pet.y())
        with patch.object(self.life,'icon_destination',return_value=(0,icon,target,self.pet.screen())), \
                patch('pet_patrol.random.random',return_value=.1), \
                patch('pet_patrol.random.choice',side_effect=['lean','left']):
            self.life.tick(self.now,.03,self.at)
        destination = self.life.destination
        self.pet.move(*destination)
        self.life.tick(self.now+.1,.1,self.at)
        self.assertEqual(self.life.phase,'resting')
        self.assertEqual((self.pet.x(),self.pet.y()),destination)
        self.assertIsNotNone(self.controller.icon_sleep.target)
        self.pet.wake_icon_sleep()
        self.assertFalse(self.life.active)
        self.assertIsNone(self.controller.icon_sleep.target)

    def test_roll_finishes_into_living_prone_rest(self):
        self.life.kind = 'roll'
        self.life.play('lazy-roll-toward',self.now)
        self.finish_action()
        self.assertEqual(self.life.kind,'rest')
        self.assertEqual(self.pet.state.action_player.action['id'],'prone-rest')
        self.assertGreaterEqual(self.pet.state.action_player.frame(self.pet.state.action_player.started+.01),0)

    def test_covered_route_never_starts_walking(self):
        with patch.object(self.life,'exposed',return_value=False), \
                patch.object(self.life,'icon_destination',return_value=None), patch('pet_patrol.random.random',return_value=.9):
            self.life.tick(self.now,.03,self.at)
        self.assertFalse(self.life.active)
