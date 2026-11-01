"""Dance recovery ownership, seated-only breathing, and cancellation behavior."""
import os
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
import random,time,unittest
from dataclasses import replace
from unittest.mock import patch
from PySide6.QtWidgets import QApplication
from action_player import ActionPlayer,catalog,dance_rest_timeline
from dance_recovery import ACTION_ID

class RecoveryTimelineTests(unittest.TestCase):
    def test_entry_matches_final_dance_drawing(self):
        from pathlib import Path
        from PIL import Image
        folder=Path(__file__).resolve().parent/'assets/actions'
        dance=catalog()['music-waltz'];index=dance['frames']-1
        x=index%dance['columns']*256;y=index//dance['columns']*256
        with Image.open(folder/'music-waltz/atlas.png') as atlas,Image.open(folder/'dance-rest/01.png') as entry:
            self.assertEqual(atlas.crop((x,y,x+256,y+256)).tobytes(),entry.tobytes())

    def test_lower_once_rest_seated_then_rise(self):
        action={'durations':[350,500,450,280,300,300,350,650,650,130]}
        for seed in range(12):
            order,durations=dance_rest_timeline(action,random.Random(seed))
            self.assertEqual(order[:8],list(range(8)))
            self.assertEqual(order[-7:],[6,5,4,3,2,1,0])
            self.assertTrue(set(order[8:-7])<={7,8,9})
            self.assertTrue(all(d==130 for i,d in zip(order,durations) if i==9))
            self.assertEqual(len(order),len(durations))
            self.assertGreater(sum(durations),15000)

class RecoveryLiveTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app=QApplication.instance() or QApplication([])
    def setUp(self):
        from pet import DesktopPet
        from settings_model import Preferences
        self.pet=DesktopPet(replace(Preferences(),random_movement=False,auto_snap=False))
        self.pet.show();self.pet.animator.timer.stop();self.pet.bubble.timer.stop()
        self.now=time.monotonic();self.player=self.pet.state.action_player;self.recovery=self.pet.dance_recovery
    def tearDown(self):
        self.pet.close();self.pet.deleteLater();self.app.processEvents()
    def test_manual_completed_dance_starts_recovery_at_same_position(self):
        self.player.play('music-waltz',now=self.now)
        self.recovery.tick(self.now)
        duration=sum(self.player.action['durations'])/1000;position=self.pet.pos()
        # A real tick lands after the boundary; an exact one can fall a hair short.
        self.recovery.tick(self.now+duration+.01)
        self.assertEqual(self.player.action['id'],ACTION_ID)
        self.assertEqual(self.pet.pos(),position)
        self.assertFalse(self.player.loop)
        self.assertFalse(self.pet.movement_allowed())
    def test_cancel_or_replacement_does_not_start_recovery(self):
        self.player.play('music-waltz',now=self.now);self.recovery.tick(self.now)
        self.player.stop();self.recovery.tick(self.now+.1);self.recovery.tick(self.now+50)
        self.assertIsNone(self.player.action)
        self.player.play('music-waltz',now=self.now);self.recovery.tick(self.now)
        self.player.play('read',now=self.now+.2);self.recovery.tick(self.now+50)
        self.assertEqual(self.player.action['id'],'read')
    def test_drag_interrupts_recovery_and_preserves_position(self):
        self.assertTrue(self.recovery.start(self.now));position=self.pet.pos()
        self.pet.drag_origin=object();self.recovery.tick(self.now+.5)
        self.assertIsNone(self.player.action);self.assertEqual(self.pet.pos(),position)
        self.pet.drag_origin=None
    def test_renderer_uses_clean_drawings_and_common_ground(self):
        from PySide6.QtGui import QImage,QPainter
        self.recovery.start(self.now)
        slots=self.player.frame_order;durations=self.player.action['durations'];elapsed=0
        for slot,duration in enumerate(durations):
            now=self.now+(elapsed+duration/2)/1000;elapsed+=duration
            image=QImage(180,190,QImage.Format.Format_RGBA8888);image.fill(0)
            painter=QPainter(image)
            try:
                with patch('pet.time.monotonic',return_value=now),patch('pet.sample_pose',side_effect=AssertionError('no interpolation')),patch.object(self.pet.renderer.action_motion,'render',side_effect=AssertionError('no warping')):
                    self.pet.renderer.draw_pose(painter,self.pet.state)
            finally:painter.end()
            ys=[y for y in range(190) if any(image.pixelColor(x,y).alpha()>128 for x in range(180))]
            self.assertTrue(ys);self.assertGreaterEqual(max(ys),178);self.assertLessEqual(max(ys),183)
            self.assertGreater(min(ys),0)
