import os
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
from dataclasses import replace
from datetime import datetime
from pathlib import Path
import tempfile
import time
import unittest
from unittest.mock import patch
from PySide6.QtWidgets import QApplication
from main import PetApplication
from daily_routine import current_period
from settings_model import Preferences, SettingsStore


class MusicTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app=QApplication.instance() or QApplication([])
        cls.app.setQuitOnLastWindowClosed(False)

    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(prefix='yuki-music-')
        store=SettingsStore(Path(self.tmp.name)/'settings.ini')
        store.save(replace(Preferences(),auto_snap=False))
        self.controller=PetApplication(self.app,store,enable_tray=False,create_console=False)
        self.pet=self.controller.pet
        self.pet.show()
        self.pet.animator.timer.stop()
        self.pet.bubble.timer.stop()
        self.music=self.controller.music
        self.now=time.monotonic()
        self.music.next_at=0
        self.pet.state.routine.period=current_period(datetime(2026,1,1,10))
        self.pet.state.action_player.stop()
        ready = patch('pet_music.dance_ready',return_value=True)
        ready.start()
        self.addCleanup(ready.stop)

    def tearDown(self):
        self.controller.cleanup()
        self.pet.deleteLater()
        self.controller.deleteLater()
        self.app.processEvents()
        self.tmp.cleanup()

    def feature(self,kind='rhythm',at=None,onset=True,sudden=False):
        at=self.now if at is None else at
        with patch('pet_music.time.monotonic',return_value=at):
            self.music.receive(dict(kind=kind,bpm=120,level=.4,bands=[.2,.3,.1],onset=onset,sudden=sudden))

    def dance(self):
        for i in range(11):self.feature(at=self.now-5+i*.5)
        self.music.tick(self.now)

    def test_stable_music_dances_with_motion_and_cooldown(self):
        self.dance()
        self.assertEqual(self.music.active,'dance')
        self.assertEqual(self.pet.state.action_player.action['id'],'music-waltz')
        self.assertEqual(self.music.transform(self.now+.7),(0.,0.,0.))
        self.assertEqual(self.pet.animator.timer.interval(),16)
        self.assertTrue(self.pet.state.action_player.loop)
        self.assertTrue(self.now+30 <= self.music.until <= self.now+50)
        self.music.cancel(self.now+1)
        self.assertEqual(self.pet.animator.timer.interval(),16)
        self.assertGreaterEqual(self.music.next_at,self.now+4)
        self.feature(at=self.now+2)
        self.music.tick(self.now+2)
        self.assertFalse(self.music.active)

    def test_music_cancellation_keeps_same_timestamp_manual_action(self):
        self.dance()
        self.pet.state.action_player.play('read',now=self.music.owned_start)
        self.music.cancel(self.now+.1)
        self.assertEqual(self.pet.state.action_player.action['id'],'read')

    def test_scheduled_sleep_preempts_owned_dance(self):
        self.dance()
        with patch('pet_sleep.sleep_time',return_value=True), \
                patch.object(self.controller.patrol,'begin_sleep_site',return_value=False):
            self.pet.state.sleep.tick(self.pet,self.now+.1)
        self.assertEqual(self.pet.state.sleep.phase,'settling')
        self.assertFalse(self.music.active)

    def test_atlas_loading_defers_dance_without_consuming_cooldown(self):
        with patch('pet_music.dance_ready',return_value=False):
            self.dance()
        self.assertFalse(self.music.active)
        self.assertIsNone(self.pet.state.action_player.action)
        self.assertEqual(self.music.next_at,0)
        self.feature(at=self.now+.1)
        self.music.tick(self.now+.1)
        self.assertEqual(self.music.active,'dance')

    def test_tempo_following_and_late_beat_keep_continuous_pose(self):
        self.dance()
        player = self.pet.state.action_player
        self.music.feature.update(bpm=144)
        now = self.now+.05
        before = (now-player.started)*player.speed
        self.music.tick(now)
        self.assertAlmostEqual((now-player.started)*player.speed, before)
        self.assertGreater(player.speed, 1.)
        self.assertEqual(self.music.owned_start, player.started)
        self.music.cancel(now)
        self.music.next_at = 0
        self.feature(at=now)
        self.music.feature.update(bpm=96, beat_at=now-.06)
        self.music.tick(now)
        self.assertEqual(player.speed,.8)
        self.assertAlmostEqual(player.started,now-.06)
        self.assertTrue(now+30 <= self.music.until <= now+50)

    def test_authored_dance_renders_transparently_without_extra_warps(self):
        from music_dance_asset import preload, ready
        from PySide6.QtGui import QImage, QPainter
        decoded=preload().result(timeout=20)
        self.assertTrue(ready())
        from action_player import catalog
        meta=catalog()['music-waltz']
        from music_dance_asset import metadata
        pages=metadata()
        self.assertEqual(decoded.width(),pages['columns']*256)
        self.assertLessEqual(decoded.sizeInBytes(),32*1024*1024)
        self.assertEqual(decoded.pixelColor(0,0).alpha(),0)
        self.dance()
        image=QImage(180,190,QImage.Format.Format_RGBA8888_Premultiplied)
        image.fill(0)
        painter=QPainter(image)
        try:
            with patch('pet.time.monotonic',return_value=self.now+4.2), \
                 patch('pet.sample_pose',side_effect=AssertionError('dance is already interpolated')), \
                 patch.object(self.pet.renderer.action_motion,'render',side_effect=AssertionError('double warp')):
                self.pet.renderer.draw_pose(painter,self.pet.state)
        finally:
            painter.end()
        self.assertTrue(any(image.pixelColor(x,y).alpha()>0 for y in range(20,185,8) for x in range(10,175,8)))

    def test_complete_phrase_sits_to_rest_and_sleep_blocks_music(self):
        self.dance()
        end=self.music.until
        self.feature(at=end)
        self.music.tick(end)
        self.assertFalse(self.music.active)
        self.assertEqual(self.pet.state.action_player.action['id'],'dance-rest')
        self.pet.state.action_player.stop()
        self.music.next_at=0
        self.pet.state.sleep.phase='asleep'
        self.dance()
        self.assertFalse(self.music.active)
        self.assertIsNone(self.pet.state.action_player.action)

    def test_beats_need_sustained_audio_and_gaps_have_grace(self):
        self.feature(at=self.now-5)
        self.feature('silent',at=self.now-4.8)
        self.assertIsNotNone(self.music.sounding_since)
        for dt in (-4.5,-4,-3.5,-3,-2.5,-2,-1.5,-1,-.5,0):self.feature(at=self.now+dt)
        self.music.tick(self.now)
        self.assertEqual(self.music.active,'dance')
        self.feature('silent',at=self.now+.2)
        self.music.tick(self.now+.2)
        self.assertTrue(self.music.active)
        self.feature('silent',at=self.now+1.4)
        self.music.tick(self.now+1.4)
        self.assertTrue(self.music.active)
        self.feature('silent',at=self.now+3.2)
        self.music.tick(self.now+3.2)
        self.assertFalse(self.music.active)

    def test_first_beat_does_not_dance_and_sudden_sound_notices(self):
        self.feature()
        self.music.tick(self.now)
        self.assertFalse(self.music.active)
        self.feature('sudden',sudden=True)
        self.music.tick(self.now)
        self.assertEqual(self.music.active,'notice')
        self.assertEqual(self.pet.state.action_player.action['id'],'curious')

    def test_manual_action_is_preserved_and_chat_interrupts(self):
        self.dance()
        self.pet.state.action_player.play('read',now=self.now+.1)
        self.feature(at=self.now+.2)
        self.music.tick(self.now+.2)
        self.assertFalse(self.music.active)
        self.assertEqual(self.pet.state.action_player.action['id'],'read')
        self.pet.state.action_player.stop()
        self.music.next_at=0
        self.dance()
        self.pet.bubble.say('你好。')
        self.assertFalse(self.music.active)

    def test_quiet_off_pause_and_drag_take_priority(self):
        for key in ('quiet','paused','music_reactions'):
            self.pet.preferences=replace(Preferences(),**{key:key!='music_reactions'})
            self.dance()
            self.assertFalse(self.music.active)
        self.pet.preferences=Preferences()
        self.pet.drag_origin=object()
        self.dance()
        self.assertFalse(self.music.active)
        self.pet.drag_origin=None

    def test_night_and_existing_patrol_do_not_dance(self):
        self.pet.state.routine.period=current_period(datetime(2026,1,1,23))
        self.dance()
        self.assertFalse(self.music.active)
        self.pet.state.routine.period=current_period(datetime(2026,1,1,10))
        self.controller.patrol.kind='snack'
        self.controller.patrol.phase='doing'
        self.music.next_at=0
        self.dance()
        self.assertFalse(self.music.active)

    def test_session_ends_at_a_closed_phrase_after_tempo_changes(self):
        self.dance()
        player=self.pet.state.action_player
        phrase=sum(player.action['durations'])/1000
        self.assertAlmostEqual(self.music.dance_end_position/phrase,round(self.music.dance_end_position/phrase))
        self.music.feature.update(bpm=144)
        self.music.tick(self.now+.1)
        predicted_position=(self.music.until-player.started)*player.speed
        self.assertAlmostEqual(predicted_position,self.music.dance_end_position)

    def test_long_session_rests_and_resumes(self):
        self.dance()
        end=self.music.until
        self.feature(at=self.now+15)
        self.pet.state.action_player.frame(self.now+15)
        self.music.tick(self.now+15)
        self.assertEqual(self.music.active,'dance')
        self.assertEqual(self.music.until,end)
        self.feature(at=end)
        self.music.tick(end)
        self.assertFalse(self.music.active)
        self.assertEqual(self.pet.state.action_player.action['id'],'dance-rest')
        recovery_end=end+sum(self.pet.state.action_player.action['durations'])/1000
        self.assertGreaterEqual(self.music.next_at,recovery_end)
        resume=self.music.next_at
        self.pet.state.action_player.frame(resume)
        for at in (resume-5,resume-4,resume-3,resume-2,resume-1,resume):
            self.feature(at=at,onset=False)
        self.music.tick(resume-.1)
        self.assertFalse(self.music.active)
        self.music.tick(resume)
        self.assertEqual(self.music.active,'dance')

    def test_between_beats_yields_only_automatic_idle(self):
        self.pet.state.action_player.play('sit-neat',now=self.now-2)
        self.pet.state.ambient.current=('sit-neat',self.now-2,None,20)
        for i in range(11):self.feature(at=self.now-5+i*.5,onset=False)
        self.music.tick(self.now)
        self.assertEqual(self.music.active,'dance')
        self.assertIsNone(self.pet.state.ambient.current)

    def test_plain_sound_without_rhythm_does_not_dance(self):
        for i in range(11):self.feature('active',at=self.now-5+i*.5,onset=False)
        self.music.tick(self.now)
        self.assertNotEqual(self.music.active,'dance')

    def test_capture_stall_stops_dance(self):
        self.dance()
        self.music.tick(self.now+2.6)
        self.assertFalse(self.music.active)

    def test_manual_action_cannot_be_preempted_when_starting(self):
        self.pet.state.action_player.play('read',now=self.now-1)
        self.dance()
        self.assertFalse(self.music.active)
        self.assertEqual(self.pet.state.action_player.action['id'],'read')

    def test_recent_rhythm_survives_temporary_classifier_drop(self):
        for i in range(10):self.feature(at=self.now-5+i*.5,onset=False)
        self.feature('active',at=self.now,onset=False)
        self.music.tick(self.now)
        self.assertEqual(self.music.active,'dance')

    def test_snapshot_explains_quiet_mode(self):
        self.pet.preferences=replace(Preferences(),quiet=True)
        state=self.music.snapshot()
        self.assertTrue(state['suspended'])
        self.assertTrue(state['suspend_reason'])
        self.assertFalse(state['listening'])
