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
        self.assertEqual(self.pet.state.action_player.action['id'],'celebrate')
        self.assertTrue(any(abs(v)>.1 for v in self.music.transform(self.now+.7)))
        self.music.cancel(self.now+1)
        self.assertGreaterEqual(self.music.next_at,self.now+36)
        self.feature(at=self.now+2)
        self.music.tick(self.now+2)
        self.assertFalse(self.music.active)

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
