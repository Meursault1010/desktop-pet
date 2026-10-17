import unittest
import random
from copy import deepcopy
from unittest.mock import patch
from action_player import ActionPlayer, ground_idle_timeline, lazy_roll_timeline

class ActionTests(unittest.TestCase):
    def setUp(self):
        self.data={'sample':{'id':'sample','durations':[100,200,300]}}
        self.mock=patch('action_player.catalog',return_value=self.data)
        self.mock.start();self.addCleanup(self.mock.stop)
        self.player=ActionPlayer()

    def test_boundaries_and_end(self):
        self.player.play('sample',now=0)
        self.assertEqual(self.player.frame(0),0)
        self.assertEqual(self.player.frame(.15),1)
        self.assertEqual(self.player.frame(.4),2)
        self.assertIsNone(self.player.frame(.7))
        self.assertIsNone(self.player.action)

    def test_loop_and_speed(self):
        self.player.play('sample',loop=True,speed=2,now=0)
        self.assertEqual(self.player.frame(.32),0)
        self.assertEqual(self.player.frame(.4),1)

    def test_stop_and_replace(self):
        self.player.play('sample',now=0)
        self.player.play('sample',now=1)
        self.assertEqual(self.player.frame(1),0)
        self.player.stop();self.assertIsNone(self.player.frame(1))

    def test_intro_is_not_repeated(self):
        self.data['sample']['loop_start']=1
        self.player.play('sample',loop=True,now=0)
        self.assertEqual(self.player.frame(.05),0)
        self.assertEqual(self.player.frame(.601),1)
        self.assertEqual(self.player.frame(1.101),1)
        self.assertEqual(self.player.frame(.85),2)
        for t in range(601,10000,37):
            self.assertGreaterEqual(self.player.frame(t/1000),1)

    def test_reject_unsafe_arguments(self):
        for action,loop,speed in [('../bad',False,1),([],False,1),('sample','yes',1),('sample',False,float('nan')),('sample',False,3),('sample',False,True)]:
            with self.assertRaises(ValueError):self.player.play(action,loop,speed)

    def test_idle_variation_preserves_entry_exit_and_valid_frames(self):
        for key in ('sit-neat','sit-relaxed','sit-swing','prone-chin','prone-rest'):
            action={'id':key,'ground_idle':True,'frames':36,'durations':[260]*36}
            schedules=set()
            for seed in range(20):
                order,durations=ground_idle_timeline(action, random.Random(seed))
                self.assertEqual(order[:3],[0,1,2])
                self.assertEqual(order[-3:],[33,34,35])
                self.assertTrue(all(3<=i<=8 for i in order[3:-3]))
                self.assertEqual(len(order),len(durations))
                self.assertTrue(all(d>0 for d in durations))
                schedules.add(tuple(order))
            self.assertGreater(len(schedules),10)

    def test_random_idle_uses_mapped_atlas_frames_and_actual_end(self):
        action={'id':'sit-neat','ground_idle':True,'frames':36,'durations':[260]*36}
        self.data['sit-neat']=action
        original=deepcopy(action)
        self.player.play('sit-neat',now=10)
        self.assertEqual(action,original)
        elapsed=0
        for frame,duration in zip(self.player.frame_order,self.player.action['durations']):
            self.assertEqual(self.player.frame(10+(elapsed+duration/2)/1000),frame)
            elapsed+=duration
        self.assertIsNone(self.player.frame(10+elapsed/1000+.001))

    def test_lazy_roll_keeps_angles_ordered_and_finishes(self):
        action={'id':'lazy-roll-toward','lazy_roll':True,'frames':12,'durations':[420]*12}
        variants=set()
        for seed in range(20):
            order,durations=lazy_roll_timeline(action,random.Random(seed))
            self.assertIn(len(order),(23,34))
            self.assertEqual(order[-1],11)
            self.assertEqual(order[:-1],list(range(11))*(len(order)//11))
            self.assertEqual(len(order),len(durations))
            self.assertTrue(all(d>=100 for d in durations))
            variants.add(tuple(durations))
        self.assertEqual(len(variants),20)
        self.data[action['id']]=action
        self.player.play(action['id'],now=20)
        self.assertFalse(self.player.loop)
        elapsed=0
        for frame,duration in zip(self.player.frame_order,self.player.action['durations']):
            self.assertEqual(self.player.frame(20+(elapsed+duration/2)/1000),frame)
            elapsed+=duration
        self.assertIsNone(self.player.frame(20+elapsed/1000+.001))

if __name__=='__main__':unittest.main()
