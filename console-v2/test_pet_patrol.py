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
        self.input_idle = patch('pet_patrol.idle_seconds', return_value=100)
        self.input_idle.start()
        self.addCleanup(self.input_idle.stop)
        from PySide6.QtCore import QPoint
        self.cursor = patch('pet_patrol.QCursor.pos', return_value=QPoint(-10000,-10000))
        self.cursor.start()
        self.addCleanup(self.cursor.stop)

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

    def test_affection_after_five_minutes_uses_existing_action_without_motion(self):
        self.life.record_pet_click(self.now-301)
        origin=self.pet.pos()
        self.life.tick(self.now,.03,self.at)
        self.assertEqual(self.pet.state.action_player.action['id'],'affection')
        self.assertEqual(self.pet.pos(),origin)
        self.assertFalse(self.pet.bubble.parts)
        self.finish_action()
        self.assertIsNone(self.pet.state.action_player.action)
        self.life.tick(self.now+30,.03,self.at)
        self.assertNotEqual(self.life.kind,'affection')

    def test_click_resets_affection_deadline(self):
        self.life.record_pet_click(self.now-301)
        self.life.record_pet_click(self.now)
        self.life.next_at=self.now+600
        self.life.tick(self.now+299,.03,self.at)
        self.assertIsNone(self.pet.state.action_player.action)

    def test_affection_waits_for_manual_action_and_respects_quiet_mode(self):
        from dataclasses import replace
        self.life.record_pet_click(self.now-301)
        self.pet.preferences=replace(self.pet.preferences,quiet=True)
        self.life.tick(self.now,.03,self.at)
        self.assertIsNone(self.pet.state.action_player.action)
        self.pet.preferences=replace(self.pet.preferences,quiet=False)
        self.pet.state.action_player.play('read',now=self.now)
        self.life.tick(self.now,.03,self.at)
        self.assertEqual(self.pet.state.action_player.action['id'],'read')

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
        with patch.object(self.life,'icon_destination',return_value=None), patch('pet_patrol.random.choice',side_effect=['stroll', 1]):
            self.life.tick(self.now,.03,self.at)
        self.assertEqual(self.life.phase,'observing')
        self.now = self.life.until+.01
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
        with patch.object(self.life,'icon_destination',return_value=None), patch('pet_patrol.random.choice',side_effect=['roll', 'lazy-roll-toward']):
            self.life.tick(self.now,.03,self.at)
        self.assertEqual(self.life.kind,'roll')
        origin = self.pet.pos()
        self.life.tick((self.now+self.life.until)/2,.03,self.at)
        direction=-1 if self.pet.state.action_player.action['id']=='lazy-roll-toward' else 1
        self.assertGreater((self.pet.y()-origin.y())*direction,0)
        self.assertEqual(self.pet.x(),origin.x())
        self.assertTrue(self.pet.screen_area().contains(self.pet.geometry()))

    def test_due_ambient_and_patrol_share_free_slot_without_starvation(self):
        self.pet.state.ambient.next_at = self.now-1
        with patch.object(self.life, 'icon_destination', return_value=None), \
                patch('pet_patrol.random.choice', return_value='tea'):
            self.life.tick(self.now, .03, self.at)
        self.assertEqual(self.life.phase, 'observing')
        self.life.cancel(self.now)
        self.life.tick(self.now, .03, datetime(2026, 1, 1, 12))
        self.assertEqual(self.life.kind, 'meal')

    def icon(self):
        icon = dict(id='test-icon', name='Test folder',folder=True,rect=dict(x=320,y=230,width=48,height=48))
        self.controller.icon_sleep.icons = [icon]
        return icon

    def test_observe_arrives_without_private_sleep_and_cancels_on_icon_move(self):
        icon = self.icon()
        target = (self.pet.x(),self.pet.y())
        with patch.object(self.life,'icon_destination',return_value=(0,icon,target,self.pet.screen())), \
                patch('pet_patrol.random.random',return_value=.1), patch('pet_patrol.random.choice',return_value='observe'):
            self.life.tick(self.now,.03,self.at)
        self.assertEqual(self.life.phase,'observing')
        self.now = self.life.until+.01
        self.life.tick(self.now,.1,self.at)
        self.pet.move(*self.life.destination)
        self.life.tick(self.now+.1,.1,self.at)
        self.assertEqual(self.pet.state.action_player.action['id'],'curious')
        self.assertFalse(self.pet.state.action_player.loop)
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
        self.now = self.life.until+.01
        self.life.tick(self.now,.1,self.at)
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
                patch.object(self.life,'icon_destination',return_value=None), patch('pet_patrol.random.choice',side_effect=['stroll',1]):
            self.life.tick(self.now,.03,self.at)
        self.assertFalse(self.life.active)

    def test_same_timestamp_user_action_still_keeps_ownership(self):
        self.life.kind = 'tea'
        self.life.play('tea', self.now)
        self.pet.state.action_player.play('read', now=self.now)
        self.life.cancel(self.now)
        self.assertEqual(self.pet.state.action_player.action['id'], 'read')

    def test_play_switch_and_icon_permission_are_independent_of_drag_snap(self):
        self.controller.set_preference('autonomous_icons',False)
        self.icon()
        self.assertIsNone(self.life.icon_destination())
        self.assertFalse(self.pet.preferences.auto_snap)
        self.life.kind = 'tea'
        self.life.play('tea',self.now)
        self.controller.set_preference('autonomous_play',False)
        self.assertFalse(self.life.active)
        self.assertTrue(self.life.blocked())

    def test_completed_story_gets_history_and_cooldown(self):
        self.life.kind = self.life.story = 'tea'
        self.life.play('tea',self.now)
        self.finish_action()
        self.assertFalse(self.life.active)
        self.assertEqual(list(self.life.policy.recent), ['tea'])
        self.assertFalse(self.life.policy.available('tea',self.now+1))

    def test_budget_exhaustion_cancels_walk_without_teleport(self):
        self.life.phase = 'walking'
        self.life.kind = self.life.story = 'stroll'
        self.life.destination = (self.pet.x()+80,self.pet.y())
        self.life.until = self.now+10
        self.life.probe_at = self.now+1
        self.life.policy.motion.append((self.now,60))
        before=self.pet.pos()
        self.life.tick(self.now,.03,self.at)
        self.assertFalse(self.life.active)
        self.assertEqual(self.pet.pos(),before)

    def test_observed_icon_invalidated_before_first_step(self):
        icon=self.icon()
        self.life.phase='observing'
        self.life.kind=self.life.story='observe'
        self.life.target=icon
        self.life.destination=(self.pet.x()+10,self.pet.y())
        self.life.until=self.now+1
        self.controller.icon_sleep.icons=[]
        self.life.tick(self.now,.03,self.at)
        self.assertFalse(self.life.active)

    def test_busy_user_gets_quiet_backoff(self):
        with patch('pet_patrol.idle_seconds',return_value=0),patch('pet_patrol.random.random',return_value=.1):
            self.life.tick(self.now,.03,self.at)
        self.assertFalse(self.life.active)
        self.assertGreaterEqual(self.life.next_at,self.now+30)

    def test_climb_rest_and_descent_return_to_ground_without_snap_manager(self):
        ground = (self.pet.x(), self.pet.y())
        self.life.kind = self.life.story = 'perch'
        self.life.perch = (ground[0], ground[1]-80)
        self.life.arrived(self.now)
        self.assertEqual(self.pet.state.action_player.action['id'], 'play-climb-up')
        middle = self.now+(self.life.until-self.now)/2
        self.life.tick(middle,.03,self.at)
        self.assertTrue(ground[1]-80 < self.pet.y() < ground[1])
        self.assertIsNone(self.controller.icon_sleep.target)
        self.finish_action()
        self.assertEqual(self.life.phase,'perched')
        self.assertEqual(self.pet.y(),ground[1]-80)
        self.life.tick(self.life.until+.01,.03,self.at)
        self.assertEqual(self.pet.state.action_player.action['id'],'play-climb-down')
        self.finish_action()
        self.assertFalse(self.life.active)
        self.assertEqual((self.pet.x(),self.pet.y()),ground)

    def test_manual_action_during_climb_cancels_route_and_keeps_user_pose(self):
        self.life.kind = self.life.story = 'perch'
        self.life.perch = (self.pet.x(), self.pet.y()-80)
        self.life.arrived(self.now)
        before = self.pet.pos()
        self.pet.state.action_player.play('read',now=self.now+.1)
        self.life.tick(self.now+.2,.03,self.at)
        self.assertFalse(self.life.active)
        self.assertEqual(self.pet.pos(),before)
        self.assertEqual(self.pet.state.action_player.action['id'],'read')

    def test_climb_bridge_frames_are_pixel_identical(self):
        from PIL import Image, ImageChops
        root=Path(__file__).parent/'assets'/'actions'
        reference=Image.open(root/'play-climb-up'/'06.png').convert('RGBA')
        for action in ('play-top-rest','play-climb-down'):
            frame=Image.open(root/action/'01.png').convert('RGBA')
            self.assertIsNone(ImageChops.difference(reference,frame).getbbox())

    def test_reading_and_seated_story_holds_match_document(self):
        self.life.kind='read'
        self.life.queue_action('reading-pose-1',self.now)
        self.assertTrue(20 <= self.life.until-self.now <= 50)
        self.life.kind='observe'
        self.life.queue_action('sit-relaxed',self.now)
        self.assertTrue(10 <= self.life.until-self.now <= 25)
        self.life.kind='rest'
        self.life.queue_action('prone-rest',self.now)
        self.assertTrue(15 <= self.life.until-self.now <= 35)

    def test_autonomous_roll_is_only_one_cycle(self):
        self.life.kind=self.life.story='roll'
        self.life.play('lazy-roll-toward',self.now)
        self.assertEqual(self.pet.state.action_player.frame_order[4:],list(range(12)))

    def test_stationary_roll_holds_do_not_consume_motion_budget(self):
        self.life.kind=self.life.story='roll'
        self.life.play('lazy-roll-toward',self.now)
        self.life.tick(self.now,.03,self.at)
        self.life.tick(self.now+.03,.03,self.at)
        self.assertEqual(self.life.policy.remaining(self.now+.03,'默认'),60)

    def test_interaction_cooldown_begins_after_interaction_ends(self):
        for kind,interval in (('menu',(10,20)),('chat',(30,60)),('drag',(20,40))):
            self.life.interrupt(kind,self.now)
            self.life.settle_interruption(self.now+500)
            self.assertTrue(interval[0] <= self.life.next_at-self.now-500 <= interval[1])
            self.assertIsNone(self.life.interruption)

    def test_geometry_change_cancels_without_teleport(self):
        self.life.kind=self.life.story='perch'
        self.life.perch=(self.pet.x(),self.pet.y()-60)
        self.life.arrived(self.now)
        self.life.geometry=self.life.capture_geometry()
        before=self.pet.pos()
        with patch.object(self.life,'capture_geometry',return_value=('changed',)):
            self.life.tick(self.now+.1,.03,self.at)
        self.assertFalse(self.life.active)
        self.assertEqual(self.pet.pos(),before)

    def test_sleep_site_is_short_interruptible_and_does_not_play_private_sleep(self):
        icon=self.icon()
        self.life.icons.scanned_at=self.now
        ground=(self.pet.x(),self.pet.y())
        destination=(ground[0]+20,ground[1])
        with patch.object(self.life,'icon_destination',return_value=(20,icon,destination,self.pet.screen())):
            self.assertTrue(self.life.begin_sleep_site(self.now))
        self.assertEqual(self.life.kind,'sleep_site')
        self.assertLessEqual(self.life.until-self.now,9)
        self.assertIsNone(self.pet.state.action_player.action)
        self.pet.move(*destination)
        self.life.tick(self.now+.1,.03,self.at)
        self.assertFalse(self.life.active)
        self.assertEqual(self.pet.pos().x(),destination[0])
        self.assertIsNone(self.pet.state.action_player.action)

    def test_sleep_site_does_not_wait_for_stale_scan(self):
        self.life.icons.scanned_at=self.now-10
        self.assertFalse(self.life.begin_sleep_site(self.now))
        self.assertFalse(self.life.active)

    def test_missing_icon_glyph_falls_back_from_climb_to_observe(self):
        icon=self.icon()
        with patch.object(self.life,'icon_destination',return_value=(0,icon,(self.pet.x(),self.pet.y()),self.pet.screen())), \
                patch('pet_patrol.random.random',return_value=.1),patch('pet_patrol.random.choice',return_value='perch'):
            self.life.tick(self.now,.03,self.at)
        self.assertEqual(self.life.kind,'observe')
        self.assertIsNone(self.life.perch)

    def test_only_one_replan_is_allowed_when_icon_moves(self):
        icon=self.icon()
        self.life.target=icon
        self.life.kind=self.life.story='observe'
        self.life.phase='walking'
        self.life.destination=(self.pet.x()+10,self.pet.y())
        self.life.screen=self.pet.screen()
        self.life.until=self.now+10
        moved=dict(icon,rect=dict(icon['rect'],x=icon['rect']['x']+10))
        self.assertTrue(self.life.replan_target(moved,self.now))
        self.assertEqual(self.life.replans,1)
        moved_again=dict(moved,rect=dict(moved['rect'],x=moved['rect']['x']+10))
        self.assertFalse(self.life.replan_target(moved_again,self.now+1))

    def test_failed_routes_back_off_without_unbounded_retry(self):
        for i in range(8):
            self.life.cancel(self.now,'路径不可用',failed=True)
            self.assertTrue(30 <= self.life.next_at-self.now <= 120)
        self.assertEqual(self.life.no_target_streak,8)
        self.life.complete(self.now)
        self.assertEqual(self.life.no_target_streak,0)

    def test_sleep_occlusion_releases_on_wake_without_moving_pet(self):
        from PySide6.QtGui import QImage,QColor
        icon=self.icon()
        image=QImage(48,48,QImage.Format.Format_RGBA8888)
        image.fill(QColor('#78abc8'))
        self.life.icons.cache_images[icon['id']]=image
        cycle=self.pet.state.sleep
        cycle.set_rest_site(self.pet,icon,self.life.icons)
        self.assertTrue(cycle.site_mask)
        before=self.pet.pos()
        cycle.wake(self.pet,'点击',self.now)
        self.assertFalse(cycle.site_mask)
        self.assertTrue(self.pet.mask().isEmpty())
        self.assertEqual(self.pet.pos(),before)

    def test_climb_initial_grip_hold_is_stationary(self):
        self.life.kind=self.life.story='perch'
        self.life.perch=(self.pet.x(),self.pet.y()-80)
        self.life.arrived(self.now)
        before=self.pet.pos()
        self.life.tick(self.now+.2,.03,self.at)
        self.assertEqual(self.pet.pos(),before)
