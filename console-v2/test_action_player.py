import unittest
import random
from copy import deepcopy
from unittest.mock import patch
from action_player import ActionPlayer, ground_idle_timeline, lazy_roll_timeline, ROLL_ENTRY, pose_ref

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
            self.assertEqual(order[:4],list(ROLL_ENTRY))
            rolling = order[4:]
            self.assertIn(len(rolling),(23,34))
            self.assertEqual(order[-1],11)
            self.assertEqual(rolling[:-1],list(range(11))*(len(rolling)//11))
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

    def test_motion_sampling_preserves_holds_endpoints_speed_and_loop_intro(self):
        self.player.play('sample', now=10)
        before, after, weight = self.player.motion_sample(10.09)
        self.assertEqual((before,after), (('sample',0),('sample',1)))
        self.assertTrue(0 < weight < 1)
        self.assertEqual(self.player.motion_sample(10.1)[0],('sample',1))
        self.assertEqual(self.player.motion_sample(10.59), (('sample',2),('sample',2),0))
        self.assertIsNone(self.player.motion_sample(10.6+.001))
        self.data['sample']['loop_start']=1
        self.player.play('sample',loop=True,speed=2,now=10)
        self.assertEqual(self.player.motion_sample(10.299)[1],('sample',1))
        self.assertEqual(self.player.motion_sample(10.301)[0],('sample',1))

    def test_long_rest_does_not_spend_whole_hold_moving(self):
        self.data['sample']['durations']=[2200,200,300]
        self.player.play('sample',now=0)
        self.assertEqual(self.player.motion_sample(1.8)[2],0)
        self.assertGreater(self.player.motion_sample(2.1)[2],0)
        self.assertEqual(pose_ref('lazy-roll-away',12),('prone-rest',0))
        self.assertEqual(pose_ref('lazy-roll-away',15),('prone-rest',4))
        self.assertEqual(pose_ref('lazy-roll-away',0),('lazy-roll-away',0))

    def test_lazy_roll_has_smooth_monotonic_travel_after_the_resting_intro(self):
        self.data['lazy-roll-toward'] = {
            'id':'lazy-roll-toward','lazy_roll':True,'frames':12,
            'durations':[480,280,280,300,320,320,320,300,280,300,320,520]}
        self.player.play('lazy-roll-toward', now=10)
        duration = self.player.action['durations']
        intro = sum(duration[:4])/1000
        self.assertEqual(self.player.roll_progress(10+intro*.5),0)
        total = sum(duration)/1000
        samples = [self.player.roll_progress(10+i*total/300)
                   for i in range(301)]
        self.assertEqual(samples, sorted(samples))
        self.assertGreater(samples[-1],.9)
        self.assertEqual(self.player.roll_progress(10+sum(duration)/1000+1),1)

    def test_lazy_roll_travel_is_gated_by_turning_frames(self):
        self.data['lazy-roll-toward'] = {
            'id':'lazy-roll-toward','lazy_roll':True,'frames':12,
            'durations':[480,280,280,300,320,320,320,300,280,300,320,520]}
        self.player.play('lazy-roll-toward', now=10)
        elapsed = 0
        samples = {}
        for slot, (frame, duration) in enumerate(zip(self.player.frame_order,
                                                     self.player.action['durations'])):
            if frame in (0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11):
                samples.setdefault(frame, []).append(
                    self.player.roll_progress(10+(elapsed+duration*.5)/1000))
            elapsed += duration
        self.assertEqual(samples[0][0], 0)
        # The 1->2 blend already shows the body turning onto its back.
        self.assertGreater(samples[1][0], 0)
        turning = [samples[frame][0] for frame in range(2, 8)]
        self.assertEqual(turning, sorted(turning))
        settled = [samples[frame][0] for frame in range(8, 11)]
        self.assertEqual(len(set(settled)), 1)
        self.assertEqual(samples[11][-1], 1)

    def test_lazy_roll_rest_intervals_stay_fixed_for_both_directions_and_speeds(self):
        for action_id in ('lazy-roll-toward', 'lazy-roll-away'):
            self.data[action_id] = {
                'id':action_id,'lazy_roll':True,'frames':12,'durations':[420]*12}
            for seed in range(6):
                for speed in (.5, 1., 2.):
                    with patch('action_player.random.randint', side_effect=random.Random(seed).randint):
                        self.player.play(action_id, speed=speed, now=10)
                    elapsed = 0
                    order = self.player.frame_order
                    for slot, (frame, duration) in enumerate(zip(order, self.player.action['durations'])):
                        following = order[min(slot+1, len(order)-1)]
                        values = [self.player.roll_progress(10+(elapsed+duration*t)/1000/speed)
                                  for t in (.05, .5, .95)]
                        stationary = ((0, 8, 9, 10, 11) if action_id.endswith('toward')
                                      else (0, 1, 2, 10, 11))
                        if frame in ROLL_ENTRY or frame in stationary:
                            self.assertAlmostEqual(values[0], values[-1], places=8,
                                                   msg=str((action_id,frame,following,speed)))
                        else:
                            self.assertGreater(values[-1], values[0])
                        elapsed += duration

if __name__=='__main__':unittest.main()
