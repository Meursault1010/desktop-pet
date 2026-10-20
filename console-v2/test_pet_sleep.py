"""Exercise sleep priority and clocks without waiting for real sleep windows."""
import unittest
from datetime import datetime
from types import SimpleNamespace as NS
from unittest.mock import Mock, patch
from pet_sleep import SleepCycle, sleep_time, SETTLE_SECONDS


class SleepTests(unittest.TestCase):
    def pet(self):
        cycle=SleepCycle()
        s=NS(sleep=cycle,physics=NS(active=False),edge_attachment=None,icon_sleep=None,
             patrol=Mock(),music=Mock(),action_player=NS(action=None,stop=Mock()),
             ambient=NS(current=None,next_at=0),walking=True,travel_target=1,
             travel_position=1,roll_path=1,gait_until=1)
        pet=NS(state=s,drag_origin=None,presence=NS(active=False),controller=NS(quick_pending=None),
               bubble=NS(parts=[],kind='ambient',clear=Mock()),renderer=NS(pointer_hold_image=None),
               preferences=NS(paused=False),isVisible=lambda:True,state_changed=Mock())
        return pet,cycle

    def test_boundaries(self):
        for hour,minute,expected in [(0,0,True),(6,59,True),(7,0,False),(12,59,False),
                                     (13,0,True),(13,59,True),(14,0,False),(23,59,False)]:
            self.assertEqual(sleep_time(datetime(2026,1,1,hour,minute)),expected)

    @patch('pet_sleep.sleep_time',return_value=True)
    def test_continuous_sleep_wake_and_two_minutes_of_quiet(self,_):
        p,s=self.pet();s.tick(p,100);self.assertEqual(s.phase,'settling')
        s.tick(p,100+SETTLE_SECONDS-.01);self.assertEqual(s.phase,'settling')
        s.tick(p,100+SETTLE_SECONDS+.001);self.assertEqual(s.phase,'asleep')
        s.tick(p,1000);self.assertEqual(s.phase,'asleep')
        s.wake(p,'点击',1001);self.assertEqual(s.phase,'waking')
        s.tick(p,1002);self.assertEqual(s.phase,'awake')
        s.tick(p,1120);self.assertFalse(s.active)
        s.tick(p,1121);self.assertTrue(s.active)
        self.assertIsNone(p.state.travel_target)
        p.bubble.clear.assert_called()

    @patch('pet_sleep.sleep_time', return_value=True)
    def test_early_wake_and_drag_release_do_not_wait_for_animation(self, _):
        p,s=self.pet();s.tick(p,100)
        s.wake(p,'点击',100.4)
        self.assertAlmostEqual(s.interrupted_settle,.25)
        self.assertAlmostEqual(s.wake_seconds,.55)
        s.tick(p,100.8);self.assertEqual(s.phase,'waking')
        s.interrupt_for_drag()
        self.assertEqual(s.phase,'awake')
        self.assertFalse(s.transitioning)
        self.assertEqual(s.awake_until,220.4)
        p.state.physics.active=True
        s.tick(p,100.9)
        self.assertFalse(s.transitioning)

    @patch('pet_sleep.sleep_time', return_value=True)
    def test_wake_does_not_restart_on_repeated_click_or_message(self, _):
        p,s=self.pet();s.tick(p,100);s.tick(p,102)
        s.wake(p,'点击',103);s.wake(p,'消息',103.4)
        self.assertEqual(s.started,103)
        self.assertEqual(s.awake_until,223.4)
        s.tick(p,104);self.assertEqual(s.phase,'awake')

    @patch('pet_sleep.sleep_time',return_value=True)
    def test_conversation_extends_quiet_timer_and_repeated_interaction_resets_it(self,_):
        p,s=self.pet();s.wake(p,now=100)
        p.controller.quick_pending='chat';s.tick(p,200)
        self.assertEqual(s.awake_until,320)
        p.controller.quick_pending=None;s.wake(p,now=250);s.tick(p,369)
        self.assertFalse(s.active);s.tick(p,370);self.assertTrue(s.active)

    @patch('pet_sleep.sleep_time',return_value=True)
    def test_no_sleep_while_attached_or_manual_action_or_dragging(self,_):
        for field,value in [('edge_attachment',NS(active=True)),('icon_sleep',NS(target='icon')),
                            ('action_player',NS(action={'id':'read'},stop=Mock()))]:
            p,s=self.pet();setattr(p.state,field,value);s.tick(p,100)
            self.assertFalse(s.active,field)
        p,s=self.pet();p.drag_origin=1;s.tick(p,100);self.assertFalse(s.active)

    def test_clock_exit_and_sudden_resume(self):
        p,s=self.pet()
        with patch('pet_sleep.sleep_time',return_value=True):s.tick(p,100)
        with patch('pet_sleep.sleep_time',return_value=False):s.tick(p,1000)
        self.assertEqual(s.phase,'waking');s.tick(p,1001);self.assertEqual(s.phase,'awake')


if __name__=='__main__':unittest.main()
