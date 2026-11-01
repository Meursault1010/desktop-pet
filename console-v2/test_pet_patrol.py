"""Errands, meal receipts, desktop visibility and manual-input priority."""
import os
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
from dataclasses import replace
from datetime import datetime
from pathlib import Path
import math
import random
import tempfile
import time
import unittest
from unittest.mock import patch
from PySide6.QtWidgets import QApplication
from PySide6.QtGui import QRegion
from main import PetApplication
from settings_model import Preferences, SettingsStore
from daily_routine import current_period
from locomotion import walking_speed
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

    def test_patrol_is_persistent_and_stop_restores_daily_schedule(self):
        preferences=self.pet.preferences
        self.life.start_once(self.now)
        self.assertTrue(self.life.exploring)
        self.assertFalse(self.life.active)
        self.life.cancel(self.now+1)
        self.assertTrue(self.life.exploring)
        self.assertLessEqual(self.life.next_at,self.now+9)
        self.life.stop(self.now+2)
        self.assertFalse(self.life.exploring)
        self.assertFalse(self.life.active)
        self.assertEqual(self.pet.preferences,preferences)

    def engage_back_layer(self):
        self.life.depth.mode='back'
        self.life.depth.override=True
        self.life.depth.region=QRegion()
        self.pet.masker.set('depth',QRegion(0,0,1,1))

    def assert_depth_released(self):
        self.assertEqual(self.life.depth.mode,'front')
        self.assertIsNone(self.life.depth.region)
        self.assertFalse(self.life.depth.override)
        self.assertTrue(self.pet.mask().isEmpty())

    def test_user_wake_releases_stale_back_layer(self):
        self.life.start_once(self.now)
        self.engage_back_layer()
        self.pet.wake_icon_sleep()
        self.assert_depth_released()

    def test_user_interrupt_releases_stale_back_layer(self):
        self.life.start_once(self.now)
        self.engage_back_layer()
        self.life.interrupt('click',self.now+1)
        self.assert_depth_released()

    def test_blocked_tick_releases_stale_back_layer(self):
        self.life.start_once(self.now)
        self.engage_back_layer()
        self.pet.preferences=replace(self.pet.preferences,quiet=True)
        self.life.tick(self.now+1,.03,self.at)
        self.assert_depth_released()

    def test_quiet_preference_releases_stale_back_layer(self):
        self.life.start_once(self.now)
        self.engage_back_layer()
        self.pet.apply_preferences(replace(self.pet.preferences,quiet=True))
        self.assert_depth_released()

    def test_restarting_patrol_releases_stale_back_layer(self):
        self.life.start_once(self.now)
        self.engage_back_layer()
        self.life.start_once(self.now+1)
        self.assert_depth_released()

    def test_stop_schedules_a_follow_up_icon_errand(self):
        self.icon()
        self.life.policy.quiet_until=self.now+300
        self.life.start_once(self.now)
        self.life.stop(self.now)
        self.assertLessEqual(self.life.next_at-self.now,8)
        self.assertTrue(self.life.icon_followup)
        self.assertLessEqual(self.life.policy.quiet_until,self.now)
        self.assertIn('图标',self.life.next_intent)

    def test_stop_follow_up_goes_to_an_icon_even_when_idle_recently(self):
        icon=self.icon()
        self.life.start_once(self.now)
        self.life.stop(self.now)
        due=self.life.next_at+.01
        with patch.object(self.life,'icon_destination',return_value=(0,icon,(self.pet.x(),self.pet.y()),self.pet.screen())), \
                patch.object(self.life,'beside_icon',return_value=(self.pet.x(),self.pet.y())), \
                patch('pet_patrol.random.choice',return_value='observe'), \
                patch('pet_patrol.random.random',return_value=.99), \
                patch('pet_patrol.idle_seconds',return_value=0):
            self.life.tick(due,.03,self.at)
        self.assertEqual(self.life.kind,'observe')
        self.assertIs(self.life.target,icon)
        self.assertTrue(self.life.active)

    def test_patrol_randomly_selects_walks_and_all_existing_icon_stories(self):
        self.life.start_once(self.now)
        self.life.first_walk=False
        kinds=set()
        from PySide6.QtCore import QRect
        icon={'id':'sample','rect':(400,200,48,48)}
        for chosen in ('observe','read','lean','orbit','peek','perch'):
            self.life.cancel(self.now)
            self.life.next_at=0
            with patch.object(self.life,'icon_destination',return_value=(30,icon,(310,220),self.pet.screen())), \
                 patch.object(self.life,'route_exposed',return_value=True), \
                 patch.object(self.life,'beside_icon',return_value=(310,220)), \
                 patch('pet_patrol.random.random',return_value=0), \
                 patch('pet_patrol.random.choice',side_effect=lambda values: chosen if chosen in values else values[0]), \
                 patch('pet_patrol.logical_rect',return_value=((400,200,48,48),self.pet.screen())):
                self.life.tick(self.now,.03,self.at)
                # Perch may safely fall back when no usable support image exists.
                self.assertIn(self.life.kind,(chosen,'observe',''))
                self.assertTrue(self.life.exploring)
                kinds.add(chosen)
        self.assertEqual(len(kinds),6)

    def test_patrol_samples_new_destinations_and_preserves_safety(self):
        self.life.start_once(self.now)
        samples={self.life.random_destination() for _ in range(40)}
        self.assertGreater(len(samples-{None}),5)
        with patch.object(self.life,'route_exposed',return_value=False):
            self.assertIsNone(self.life.random_destination())
        self.pet.preferences=replace(self.pet.preferences,paused=True)
        self.life.tick(self.now,.03,self.at)
        self.assertFalse(self.life.active)
        self.assertTrue(self.life.exploring)
        self.life.stop(self.now)
        with self.assertRaises(ValueError):
            self.life.start_once(self.now)

    def test_explicit_patrol_walks_before_ambient_can_take_the_slot(self):
        self.life.start_once(self.now)
        self.pet.state.ambient.next_at = 0
        with patch.object(self.pet.state.routine,'update',return_value=False):
            self.pet.animator.update_ambient(self.now+.1)
        self.assertIsNone(self.pet.state.action_player.action)
        with patch.object(self.life,'icon_destination',return_value=None), \
             patch.object(self.life,'random_destination',return_value=(370,200)):
            self.life.tick(self.now+.3,.03,self.at)
        self.assertEqual(self.life.kind,'stroll')
        self.life.tick(self.life.until+.01,.03,self.at)
        self.assertEqual(self.life.phase,'walking')
        origin=self.pet.pos()
        for index in range(12):
            self.life.tick(self.now+3+index*.03,.03,self.at)
        self.assertNotEqual(self.pet.pos(),origin)
        self.assertGreater(self.pet.state.gait_clock,0)
        self.assertIsNone(self.pet.state.action_player.action)

    def test_invalid_icon_falls_back_to_walk_but_never_crosses_obstacles(self):
        self.life.start_once(self.now)
        self.life.first_walk=False
        icon={'id':'sample','rect':(400,200,48,48)}
        with patch.object(self.life,'icon_destination',return_value=(30,icon,(310,220),self.pet.screen())), \
             patch.object(self.life,'beside_icon',return_value=None), \
             patch.object(self.life,'random_destination',return_value=(370,200)), \
             patch('pet_patrol.random.random',return_value=0), \
             patch('pet_patrol.random.choice',return_value='observe'):
            self.life.tick(self.now+.3,.03,self.at)
        self.assertEqual(self.life.kind,'stroll')
        self.assertEqual(self.life.phase,'observing')
        self.assertIsNone(self.life.target)
        with patch.object(self.life,'route_exposed',return_value=False):
            self.life.fallback_stroll(self.now+1,'no icon space')
        self.assertFalse(self.life.active)
        self.assertTrue(self.life.exploring)

    def test_free_patrol_crosses_windows_but_icon_interactions_stay_exposed(self):
        destination=(self.pet.x()+80,self.pet.y())
        with patch.object(self.life,'exposed',return_value=False):
            self.assertFalse(self.life.route_exposed(destination,self.pet.screen()))
            self.life.start_once(self.now)
            self.life.kind='stroll'
            self.assertTrue(self.life.route_exposed(destination,self.pet.screen()))
            self.assertFalse(self.life.route_exposed((-10000,0),self.pet.screen()))
            self.life.kind='observe'
            self.assertFalse(self.life.route_exposed(destination,self.pet.screen()))
            self.assertTrue(self.life.route_exposed(destination,self.pet.screen(),through_windows=True))

    def test_start_patrol_wakes_sleep_before_waiting_for_wake_transition(self):
        self.pet.state.sleep.phase='asleep'
        self.pet.state.sleep.started=self.now-10
        self.life.start_once(self.now)
        self.assertTrue(self.life.exploring)
        self.assertEqual(self.pet.state.sleep.phase,'waking')
        self.life.tick(self.now+.1,.03,self.at)
        self.assertFalse(self.life.active)
        self.pet.state.sleep.phase='awake'
        self.life.next_at=0
        self.pet.state.routine.period=dict(self.pet.state.routine.period,walk=0)
        self.life.completed['lunch']='2026-01-01/lunch'
        with patch.object(self.life,'icon_destination',return_value=None), \
             patch.object(self.life,'random_destination',return_value=(370,200)):
            self.life.tick(self.now+2,.03,datetime(2026,1,1,13))
        self.assertEqual(self.life.kind,'stroll')
        self.assertTrue(self.life.active)

    def finish_action(self):
        until = self.life.until
        self.pet.state.action_player.frame(until+.1)
        self.life.tick(until+.1,.03,self.at)

    def test_free_walks_never_move_up_without_support(self):
        self.life.start_once(self.now)
        origin_y=self.pet.y()
        positions=[self.life.random_destination() for _ in range(100)]
        self.assertTrue(any(p is not None for p in positions))
        self.assertTrue(all(p is None or p[1]>=origin_y for p in positions))
        self.life.phase='walking'
        self.life.kind='stroll'
        self.life.destination=(self.pet.x(),origin_y-40)
        self.life.screen=self.pet.screen()
        self.life.until=self.now+10
        self.life.probe_at=self.now+10
        self.life.tick(self.now,.03,self.at)
        self.assertEqual(self.pet.y(),origin_y)
        self.assertFalse(self.life.active)

    def test_explicit_start_leaves_existing_manual_icon_hold(self):
        self.life.icons.target=self.icon()
        self.life.icons.phase='sleeping'
        self.life.start_once(self.now)
        self.assertIsNone(self.life.icons.target)
        self.assertTrue(self.life.exploring)

    def test_all_six_icon_poses_are_used_and_top_poses_climb_then_descend(self):
        from PySide6.QtGui import QImage,QColor
        from icon_sleep import NEW_POSES
        icon=self.icon()
        image=QImage(48,48,QImage.Format.Format_RGBA8888)
        image.fill(QColor('#78abc8'))
        self.life.icons.cache_images[icon['id']]=image
        for pose in NEW_POSES:
            with self.subTest(pose=pose):
                self.life.stop(self.now)
                self.life.policy.recent.clear()
                self.life.policy.stories.clear()
                self.life.policy.icons.clear()
                self.pet.move(250,200)
                self.life.start_once(self.now)
                self.life.first_walk=False
                self.life.next_at=0
                self.life.next_passage=self.now+10000
                self.life.record_pet_click(self.now)
                with patch.object(self.life,'icon_destination',return_value=(0,icon,(250,200),self.pet.screen())), \
                     patch('pet_patrol.random.random',return_value=.4), \
                     patch('pet_patrol.random.choice',side_effect=lambda values:'lean' if 'lean' in values else pose):
                    self.life.tick(self.now+.3,.03,self.at)
                self.assertEqual(self.life.kind,'lean')
                self.assertGreaterEqual(self.life.destination[1],200)
                self.pet.move(*self.life.destination)
                ground=(self.pet.x(),self.pet.y())
                self.life.arrived(self.now+1)
                climbed=self.life.climb is not None
                if climbed:
                    self.assertEqual(self.pet.state.action_player.action['id'],'play-climb-up')
                    self.finish_action()
                self.assertEqual(self.life.phase,'resting')
                self.assertEqual(self.life.icons.side,pose)
                self.assertFalse(self.life.blocked())
                if climbed:
                    self.life.tick(self.life.until+.1,.03,self.at)
                    self.assertEqual(self.pet.state.action_player.action['id'],'play-climb-down')
                    self.finish_action()
                    self.assertEqual((self.pet.x(),self.pet.y()),ground)
                    self.assertFalse(self.life.active)
                self.now+=100

    def test_autonomous_edge_grip_approaches_at_same_height_and_releases_on_stop(self):
        from edge_geometry import Landing
        from unittest.mock import Mock
        edge=self.pet.state.edge_attachment
        landing=Landing('climb-left',(400,200),'left',(450,260),100,(180,700),260)
        candidate=(landing,None,self.pet.screen(),self.pet.screen_area().getRect())
        self.life.start_once(self.now)
        self.pet.snap_preview.surfaces_at=self.now
        with patch.object(self.pet.snap_preview,'request_surfaces'),patch.object(edge,'choices',return_value=[candidate]):
            self.assertTrue(self.life.begin_edge(self.now))
        self.assertEqual(self.life.destination[1],self.pet.y())
        self.pet.move(*self.life.destination)
        self.life.arrived(self.now+1)
        self.assertTrue(edge.active)
        self.assertEqual(self.life.phase,'edge_hold')
        self.assertFalse(self.life.blocked())
        self.assertLessEqual(edge.crawl_target,edge.parameter)
        self.life.stop(self.now+2)
        self.assertFalse(edge.active)

    def test_passive_window_edge_walks_at_same_height_and_releases(self):
        from edge_geometry import Landing
        from window_edges import WindowSurface
        screen = self.pet.screen()
        rect = screen.geometry().getRect()
        area = screen.availableGeometry().getRect()
        surface = WindowSurface(4321, 999, (300, 150, 300, 400), rect, area, False, False)
        landing = Landing('climb-left', (400, 200), 'left', (450, 260), 100, (180, 700), 260)
        candidate = (landing, surface, screen, (300, 150, 300, 400))
        preview = self.pet.snap_preview
        preview.surfaces, preview.surfaces_at = [surface], self.now
        edge = self.pet.state.edge_attachment
        with patch.object(preview, 'request_surfaces'), patch.object(edge, 'choices', return_value=[candidate]):
            self.assertTrue(self.life.begin_edge(self.now))
        self.assertFalse(self.life.exploring)
        self.assertEqual(self.life.kind, 'edge')
        self.assertIsNone(self.life.target)
        self.assertEqual(self.life.destination[1], self.pet.y())
        self.pet.move(*self.life.destination)
        self.life.arrived(self.now+1)
        self.assertTrue(edge.active)
        self.assertEqual(self.life.phase, 'edge_hold')
        self.assertIn('窗口边框', self.life.next_intent)
        self.assertLessEqual(self.life.until, self.now+1+28)
        self.life.cancel(self.now+2)
        self.assertFalse(edge.active)
        self.assertFalse(self.life.active)

    def test_passive_window_edge_requires_switch_and_real_stable_window(self):
        from edge_geometry import Landing
        from window_edges import WindowSurface
        screen = self.pet.screen()
        rect = screen.geometry().getRect()
        area = screen.availableGeometry().getRect()
        landing = Landing('climb-left', (400, 200), 'left', (450, 260), 100, (180, 700), 260)
        surface = WindowSurface(4321, 999, (300, 150, 300, 400), rect, area, False, False)
        candidate = (landing, surface, screen, (300, 150, 300, 400))
        preview = self.pet.snap_preview
        preview.surfaces, preview.surfaces_at = [surface], self.now
        edge = self.pet.state.edge_attachment
        with patch.object(preview, 'request_surfaces'), patch.object(edge, 'choices', return_value=[candidate]):
            self.pet.preferences = replace(self.pet.preferences, autonomous_windows=False)
            self.assertFalse(self.life.begin_edge(self.now))
            self.pet.preferences = replace(self.pet.preferences, autonomous_windows=True)
            screen_edge = (Landing('climb-left', (400, 200), 'left', (450, 260), 100, (180, 700), 260),
                           None, screen, area)
            with patch.object(edge, 'choices', return_value=[screen_edge]):
                self.assertFalse(self.life.begin_edge(self.now))
            fullscreen = WindowSurface(4321, 999, (300, 150, 300, 400), rect, area, False, True)
            with patch.object(edge, 'choices', return_value=[(landing, fullscreen, screen, (300, 150, 300, 400))]):
                self.assertFalse(self.life.begin_edge(self.now))
            maximized = WindowSurface(4321, 999, (300, 150, 300, 400), rect, area, True, False)
            with patch.object(edge, 'choices', return_value=[(landing, maximized, screen, (300, 150, 300, 400))]):
                self.assertFalse(self.life.begin_edge(self.now))

    def test_window_switch_off_keeps_active_patrol_screen_edges(self):
        self.pet.move(80, 200)
        self.life.start_once(self.now)
        self.pet.preferences = replace(self.pet.preferences, autonomous_windows=False)
        edge = self.pet.state.edge_attachment
        edge.options.update(windows=False, screens=True)
        preview = self.pet.snap_preview
        preview.surfaces, preview.surfaces_at = [], self.now
        with patch.object(preview, 'request_surfaces'):
            self.assertTrue(self.life.begin_edge(self.now))
        self.assertEqual(self.life.kind, 'edge')
        self.life.cancel(self.now+1)

    def test_passive_window_edge_aborts_when_window_disappears_before_arrival(self):
        from edge_geometry import Landing
        from window_edges import WindowSurface
        screen = self.pet.screen()
        rect = screen.geometry().getRect()
        area = screen.availableGeometry().getRect()
        surface = WindowSurface(4321, 999, (300, 150, 300, 400), rect, area, False, False)
        landing = Landing('climb-left', (400, 200), 'left', (450, 260), 100, (180, 700), 260)
        candidate = (landing, surface, screen, (300, 150, 300, 400))
        preview = self.pet.snap_preview
        preview.surfaces, preview.surfaces_at = [surface], self.now
        edge = self.pet.state.edge_attachment
        with patch.object(preview, 'request_surfaces'), patch.object(edge, 'choices', return_value=[candidate]):
            self.assertTrue(self.life.begin_edge(self.now))
        preview.surfaces = []
        self.life.arrived(self.now+1)
        self.assertFalse(self.life.active)
        self.assertFalse(edge.active)

    def test_idle_companionship_can_choose_a_window_edge_without_patrol(self):
        from edge_geometry import Landing
        from window_edges import WindowSurface
        screen = self.pet.screen()
        rect = screen.geometry().getRect()
        area = screen.availableGeometry().getRect()
        surface = WindowSurface(4321, 999, (300, 150, 300, 400), rect, area, False, False)
        landing = Landing('climb-left', (400, 200), 'left', (450, 260), 100, (180, 700), 260)
        candidate = (landing, surface, screen, (300, 150, 300, 400))
        preview = self.pet.snap_preview
        preview.surfaces, preview.surfaces_at = [surface], self.now
        edge = self.pet.state.edge_attachment
        self.pet.preferences = replace(self.pet.preferences, autonomous_icons=False)
        self.life.next_at = 0
        self.pet.state.action_player.stop()
        self.pet.state.ambient.current = None
        with patch.object(self.life, 'icon_destination', return_value=None), \
                patch.object(preview, 'request_surfaces'), patch.object(edge, 'choices', return_value=[candidate]), \
                patch('pet_patrol.random.random', return_value=.1):
            self.life.tick(self.now, .03, self.at)
        self.assertEqual(self.life.kind, 'edge')
        self.assertFalse(self.life.exploring)
        self.assertEqual(self.life.phase, 'observing')
        self.assertIsNone(self.life.target)

    def test_idle_companionship_skips_window_edge_when_switch_is_off(self):
        from window_edges import WindowSurface
        screen = self.pet.screen()
        surface = WindowSurface(4321, 999, (300, 150, 300, 400),
                                screen.geometry().getRect(), screen.availableGeometry().getRect(), False, False)
        preview = self.pet.snap_preview
        preview.surfaces, preview.surfaces_at = [surface], self.now
        self.pet.preferences = replace(self.pet.preferences, autonomous_windows=False)
        self.life.next_at = 0
        self.pet.state.action_player.stop()
        self.pet.state.ambient.current = None
        with patch.object(self.life, 'icon_destination', return_value=None), \
                patch.object(self.life, 'begin_edge') as begin_edge, \
                patch('pet_patrol.random.choice', return_value='tea'):
            self.life.tick(self.now, .03, self.at)
        begin_edge.assert_not_called()
        self.assertNotEqual(self.life.kind, 'edge')

    def test_back_layer_can_interact_with_hidden_icon_without_front_layer_teleport(self):
        icon=self.icon()
        self.life.start_once(self.now)
        self.life.target=icon
        self.life.kind='lean'
        with patch.object(self.life,'exposed',return_value=False):
            self.assertFalse(self.life.route_exposed((300,200),self.pet.screen()))
            self.life.depth.mode='back'
            self.assertTrue(self.life.route_exposed((300,200),self.pet.screen()))
        self.life.cancel(self.now+1)
        self.assertEqual(self.life.depth.mode,'back')

    def test_hidden_visits_choose_icons_behind_the_top_window(self):
        exposed=self.icon()
        hidden=dict(id='hidden-icon',name='Hidden folder',folder=True,
                    rect=dict(x=500,y=300,width=48,height=48))
        self.life.icons.icons=[exposed,hidden]
        self.life.start_once(self.now)
        self.life.depth.mode='back'
        self.life.depth.surfaces=[(1,((430,250,200,200),None,self.pet.screen()))]
        candidate=self.life.icon_destination(hidden=True)
        self.assertEqual(candidate[1]['id'],'hidden-icon')
        self.assertIsNotNone(self.life.icon_destination())

    def test_back_layer_errand_ignores_the_normal_icon_chance(self):
        from PySide6.QtGui import QColor,QImage
        exposed=self.icon()
        hidden=dict(id='hidden-icon',name='Hidden folder',folder=True,
                    rect=dict(x=500,y=300,width=48,height=48))
        self.life.icons.icons=[exposed,hidden]
        image=QImage(48,48,QImage.Format.Format_RGBA8888)
        image.fill(QColor('#78abc8'))
        self.life.icons.cache_images[hidden['id']]=image
        self.life.start_once(self.now)
        self.life.first_walk=False
        self.life.next_at=0
        self.life.next_passage=self.now+10000
        self.life.depth.mode='back'
        self.life.last_depth='front'
        self.life.depth.surfaces=[(1,((430,250,200,200),None,self.pet.screen()))]
        with patch.object(self.life.depth,'update'), \
                patch('pet_patrol.random.random',return_value=.99):
            self.life.tick(self.now,.03,self.at)
        self.assertEqual(self.life.kind,'perch')
        self.assertEqual(self.life.target['id'],'hidden-icon')
        self.assertIsNotNone(self.life.backstage)
        self.assertTrue(self.life.active)
        self.assertEqual(self.life.phase,'observing')
        self.assertIn('窗口',self.life.reason)

    def test_reveal_extends_a_hidden_perch_but_covered_windows_do_not(self):
        icon=self.icon()
        self.life.start_once(self.now)
        self.life.kind=self.life.story='perch'
        self.life.target=icon
        self.life.screen=self.pet.screen()
        self.life.phase='perched'
        self.life.until=self.now+2
        self.life.probe_at=self.now+100
        self.life.depth.mode='back'
        self.life.last_depth='back'
        self.life.backstage={'revealed_at':None,'probe_at':0.,'planned_at':self.now}
        self.life.backstage_next=self.now+100
        self.life.depth.surfaces=[(1,((300,200,200,200),None,self.pet.screen()))]
        with patch.object(self.life.depth,'update'):
            self.life.tick(self.now,.03,self.at)
        self.assertIsNone(self.life.backstage['revealed_at'])
        self.assertEqual(self.life.until,self.now+2)
        self.life.depth.surfaces=[]
        with patch.object(self.life.depth,'update'):
            self.life.tick(self.now+1,.03,self.at)
        self.assertEqual(self.life.backstage['revealed_at'],self.now+1)
        self.assertEqual(self.life.until,self.now+1+12)
        self.assertIn('窗口',self.life.reason)

    def test_stepping_behind_windows_queues_a_hidden_visit(self):
        self.life.start_once(self.now)
        self.life.next_at=self.now+1000
        self.life.depth.mode='back'
        self.life.last_depth='front'
        with patch.object(self.life.depth,'update'):
            self.life.tick(self.now,.03,self.at)
        self.assertEqual(self.life.backstage_next,self.now)

    def test_screen_passage_changes_depth_only_after_full_exit_and_returns(self):
        self.life.start_once(self.now)
        passage=self.life.passage
        with patch('patrol_depth.visible_surfaces',return_value=[]):
            for expected in ('back','front'):
                old=self.life.depth.mode
                self.assertTrue(passage.begin(self.now))
                for index in range(1500):
                    done=passage.tick(self.now+index*.1,.1)
                    if passage.phase=='leaving':
                        self.assertEqual(self.life.depth.mode,old)
                    elif passage.phase=='returning':
                        self.assertEqual(self.life.depth.mode,expected)
                    if done:
                        break
                self.assertFalse(passage.active)
                self.assertEqual(self.life.depth.mode,expected)
                self.assertTrue(self.pet.screen().geometry().contains(self.pet.geometry()))
                self.now+=160

    def test_interrupted_exit_recovers_pet_without_switching_layer(self):
        self.life.start_once(self.now)
        self.life.passage.begin(self.now)
        self.pet.move(*self.life.passage.destination)
        self.life.cancel(self.now+.1)
        self.assertFalse(self.life.passage.active)
        self.assertTrue(self.pet.screen_area().contains(self.pet.geometry()))
        self.assertEqual(self.life.depth.mode,'front')

    def test_real_screen_side_support_moves_up_only_after_grasp(self):
        self.pet.move(80,200)
        self.life.start_once(self.now)
        edge=self.pet.state.edge_attachment
        edge.options.update(windows=False,screens=True)
        self.pet.snap_preview.surfaces=[]
        self.pet.snap_preview.surfaces_at=self.now
        with patch.object(self.pet.snap_preview,'request_surfaces'):
            self.assertTrue(self.life.begin_edge(self.now))
        self.assertEqual(self.life.destination[1],200)
        self.pet.move(*self.life.destination)
        self.life.arrived(self.now+1)
        y=self.pet.y()
        edge.timer.stop();edge.animation.stop()
        edge.last_tick=edge.started
        with patch('edge_attachment.time.monotonic',return_value=edge.started+.1):
            edge.animate()
        self.assertLess(self.pet.y(),y)
        self.assertTrue(edge.side.startswith('climb'))

    def test_demo_edge_retries_a_pending_scan_then_grips_at_pet_height(self):
        from dataclasses import replace
        self.pet.preferences = replace(self.pet.preferences, auto_snap=False)
        self.pet.move(80,200)
        edge = self.pet.state.edge_attachment
        edge.options.update(windows=False, screens=True)
        preview = self.pet.snap_preview
        preview.surfaces, preview.surfaces_at = [], 0.
        self.life.demo_edge(self.now)
        self.assertTrue(self.life.demo)
        self.assertTrue(self.life.exploring)
        with patch.object(preview, 'request_surfaces'):
            self.life.tick(self.now+.06,.03,self.at)
        # No scan has reported yet: wait and retry instead of giving up.
        self.assertFalse(self.life.active)
        self.assertGreater(self.life.edge_retry_at, 0)
        preview.surfaces_at = self.now+1.5
        with patch.object(preview, 'request_surfaces'):
            self.life.tick(self.now+.9,.03,self.at)
        self.assertEqual(self.life.kind, 'edge')
        self.assertEqual(self.life.destination[1], 200)
        self.assertFalse(self.life.edge_retry_at)

    def test_window_grip_is_invalidated_when_support_moves_before_arrival(self):
        from window_edges import WindowSurface
        from dataclasses import replace
        self.life.start_once(self.now)
        edge=self.pet.state.edge_attachment
        edge.options.update(windows=True,screens=False)
        screen=self.pet.screen()
        surface=WindowSurface(1234,999,(400,100,300,500),screen.geometry().getRect(),screen.availableGeometry().getRect(),False,False)
        self.pet.snap_preview.surfaces=[surface]
        self.pet.snap_preview.surfaces_at=self.now
        with patch.object(self.pet.snap_preview,'request_surfaces'),patch('edge_attachment.inspect_foreground',return_value=None):
            self.assertTrue(self.life.begin_edge(self.now))
            self.assertTrue(self.life.edge_valid())
            self.pet.snap_preview.surfaces=[replace(surface,rect=(420,100,300,500))]
            self.assertFalse(self.life.edge_valid())
            self.pet.move(*self.life.destination)
            self.life.arrived(self.now+1)
        self.assertFalse(edge.active)

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
        with patch.object(self.life,'icon_destination',return_value=None), \
                patch.object(self.life,'random_destination',return_value=(370,200)), \
                patch('pet_patrol.random.choice',side_effect=['stroll', 1]):
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

    def test_walk_starts_without_an_authored_glance(self):
        with patch.object(self.life,'icon_destination',return_value=None), \
                patch.object(self.life,'random_destination',return_value=(370,200)), \
                patch('pet_patrol.random.choice',return_value='stroll'):
            self.life.tick(self.now,.03,self.at)
        self.assertEqual(self.life.phase,'observing')
        self.assertIsNone(self.pet.state.action_player.action)
        self.life.tick(self.life.until+.01,.03,self.at)
        self.assertEqual(self.life.phase,'walking')
        self.assertIsNone(self.pet.state.action_player.action)

    def test_random_stroll_destinations_fit_the_travel_budget(self):
        state = random.getstate()
        self.addCleanup(random.setstate, state)
        random.seed(7)
        for _ in range(40):
            destination = self.life.random_destination()
            if destination is None:
                continue
            seconds = math.dist((self.pet.x(), self.pet.y()), destination)/max(
                1, walking_speed(self.pet.preferences.speed))
            self.assertTrue(self.life.allows_travel(seconds))

    def test_free_walk_span_is_longer_and_stays_within_budget(self):
        state = random.getstate()
        self.addCleanup(random.setstate, state)
        random.seed(11)
        distances = []
        for _ in range(80):
            destination = self.life.random_destination()
            if destination is None:
                continue
            distances.append(math.dist((self.pet.x(), self.pet.y()), destination))
            seconds = distances[-1]/max(1, walking_speed(self.pet.preferences.speed))
            self.assertTrue(self.life.allows_travel(seconds))
        self.assertTrue(distances)
        self.assertGreater(max(distances), 400)

    def test_first_patrol_walk_prefers_an_icon_over_a_random_stroll(self):
        icon = self.icon()
        self.life.start_once(self.now)
        self.assertTrue(self.life.first_walk)
        with patch.object(self.life, 'icon_destination',
                          return_value=(0, icon, (self.pet.x(), self.pet.y()), self.pet.screen())), \
                patch.object(self.life, 'beside_icon', return_value=(self.pet.x(), self.pet.y())), \
                patch.object(self.life, 'route_exposed', return_value=True), \
                patch('pet_patrol.random.choice', return_value='observe'), \
                patch('pet_patrol.random.random', return_value=.99):
            self.life.tick(self.life.next_at+.01, .03, self.at)
        self.assertEqual(self.life.kind, 'observe')
        self.assertIs(self.life.target, icon)

    def test_walk_runs_continuously_without_a_look_pause(self):
        with patch.object(self.life,'icon_destination',return_value=None), \
                patch.object(self.life,'random_destination',return_value=(370,200)), \
                patch('pet_patrol.random.choice',return_value='stroll'):
            self.life.tick(self.now,.03,self.at)
        start = self.life.until+.01
        self.life.tick(start,.03,self.at)
        self.assertEqual(self.life.phase,'walking')
        before = self.pet.pos()
        for step in range(1, 11):
            self.life.tick(start+step*.3,.3,self.at)
        self.assertNotEqual(self.pet.pos(),before)
        self.assertEqual(self.life.phase,'walking')
        self.assertFalse(hasattr(self.life,'pause_until'))
        self.assertIsNone(self.pet.state.action_player.action)

    def test_pointer_near_gets_a_short_notice_then_idle(self):
        from PySide6.QtCore import QPoint
        near = QPoint(self.pet.x()+self.pet.width()//2+20,
                      self.pet.y()+self.pet.height()//2)
        self.life.next_at = 0
        self.life.next_pointer_reaction = 0
        with patch('pet_patrol.QCursor.pos', return_value=near):
            self.life.tick(self.now,.03,self.at)
        self.assertEqual(self.life.phase,'reacting')
        self.assertIn(self.pet.state.action_player.action['id'],('curious','listen'))
        self.assertGreater(self.life.next_pointer_reaction,self.now)
        end = self.life.until+.01
        self.life.tick(end,.03,self.at)
        self.assertEqual(self.life.phase,'idle')
        self.assertIsNone(self.pet.state.action_player.action)
        self.assertGreaterEqual(self.life.next_at,end+4)

    def test_target_change_gets_notice_and_cooldown(self):
        self.life.cancel(self.now)
        self.life.next_environment_reaction = 0
        self.assertTrue(self.life.react_change(self.now,'curious','目标变了'))
        self.assertEqual(self.life.phase,'reacting')
        self.life.cancel(self.now+1)
        self.assertFalse(self.life.react_change(self.now+2,'listen','又变了'))

    def test_notice_never_overwrites_user_action(self):
        self.pet.state.action_player.play('read', now=self.now)
        self.assertFalse(self.life.react(self.now,'curious','注意到你','鼠标靠近'))
        self.assertEqual(self.pet.state.action_player.action['id'],'read')


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
        self.pet.move(self.pet.x(),100)
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
        self.assertIsNotNone(self.life.arrive_at)
        self.now = self.life.arrive_at+.01
        self.life.tick(self.now,.1,self.at)
        self.assertEqual(self.pet.state.action_player.action['id'],'sit-relaxed')
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
        if self.life.arrive_at:
            self.now = self.life.arrive_at+.01
            self.life.tick(self.now,.1,self.at)
        if self.life.climb:
            self.assertEqual(self.pet.state.action_player.action['id'],'play-climb-up')
            self.finish_action()
            destination=self.life.destination
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

    def test_chain_step_waits_for_a_short_beat(self):
        self.life.kind='tea'
        self.life.steps=['sit-neat']
        self.life.play('tea',self.now)
        until=self.life.until
        self.pet.state.action_player.frame(until+.1)
        self.life.tick(until+.1,.03,self.at)
        self.assertIsNone(self.pet.state.action_player.action)
        self.assertIsNotNone(self.life.step_at)
        self.assertTrue(.10 <= self.life.step_at-(until+.1) <= .22)
        self.life.tick(self.life.step_at-.001,.03,self.at)
        self.assertIsNone(self.pet.state.action_player.action)
        self.life.tick(self.life.step_at+.001,.03,self.at)
        self.assertEqual(self.pet.state.action_player.action['id'],'sit-neat')

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

    def test_icons_across_the_desktop_become_errand_candidates(self):
        # The old speed*7 radius (about 280px) excluded every icon once the pet
        # wandered to the far side of the desktop.
        icon=dict(id='far-icon',name='Far folder',folder=True,
                  rect=dict(x=700,y=500,width=48,height=48))
        self.life.icons.icons=[icon]
        self.assertEqual(self.pet.x(),250)
        self.assertIsNotNone(self.life.icon_destination())

    def test_icon_errand_may_walk_toward_an_icon_above_the_pet(self):
        for kind in ('observe','perch','peek'):
            with self.subTest(kind=kind):
                self.life.cancel(self.now)
                self.pet.move(250,400)
                self.life.target=self.icon()
                self.life.kind=self.life.story=kind
                self.life.phase='walking'
                self.life.screen=self.pet.screen()
                self.life.destination=(self.pet.x(),self.pet.y()-60)
                self.life.until=self.now+10
                self.life.probe_at=self.now+10
                with patch.object(self.life,'route_exposed',return_value=True):
                    self.life.tick(self.now,.03,self.at)
                self.assertTrue(self.life.active)
                self.assertEqual(self.life.phase,'walking')
                self.assertLess(self.pet.y(),400)

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
        # The window reaches the perch by the sixth of ten beats, so sample
        # while the hop is still in the air rather than at the clip's midpoint.
        rising = self.now+(self.life.until-self.now)*.25
        self.life.tick(rising,.03,self.at)
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
        reference=Image.open(root/'play-climb-up'/'10.png').convert('RGBA')
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
        self.pet.move(self.pet.x(),100)
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
