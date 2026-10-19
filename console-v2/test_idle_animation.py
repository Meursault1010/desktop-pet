import random
import unittest
from idle_animation import IdleAnimation, MOTION_SECONDS, motion_phase


class IdleAnimationTests(unittest.TestCase):
    def test_continuous_motion_has_no_wait_and_wraps_seamlessly(self):
        self.assertEqual(motion_phase(0), motion_phase(MOTION_SECONDS))
        for index in range(48):
            self.assertNotEqual(motion_phase(index/10), motion_phase(index/10+.033))
        first, second, weight = motion_phase(MOTION_SECONDS-.001)
        self.assertEqual((first, second), (63, 0))
        self.assertGreater(weight, .98)

    def test_intervals_vary_and_stay_in_range(self):
        idle = IdleAnimation(random.Random(21), now=0)
        intervals = []
        for now in range(10):
            idle.reset(now)
            intervals.append(idle.next_blink - now)
        self.assertTrue(all(2.8 <= interval <= 6.8 for interval in intervals))
        self.assertGreater(len(set(intervals)), 1)

    def test_blink_phases_and_return_to_rest(self):
        idle = IdleAnimation(random.Random(4), now=0)
        idle.next_blink = 0
        self.assertEqual(idle.update(0), 4)
        self.assertEqual(idle.update(.07), 10)
        end = sum(duration for _, duration in idle.clip)
        self.assertEqual(idle.update(end + .01), 1)
        self.assertGreater(idle.next_blink, end)

    def test_single_and_double_blinks_both_occur(self):
        idle = IdleAnimation(random.Random(42), now=0)
        lengths = {len(idle.blink_clip()) for _ in range(100)}
        self.assertEqual(lengths, {3, 6})

    def test_long_timer_gap_restarts_without_freezing_idle(self):
        idle = IdleAnimation(random.Random(2), now=0)
        idle.next_blink = 0
        idle.update(0)
        self.assertEqual(idle.update(60), 1)
        self.assertGreater(idle.next_blink, 60)
        idle.update(60.1)
        self.assertFalse(idle.clip)

    def test_movement_pause_does_not_reset_idle_schedule(self):
        idle = IdleAnimation(random.Random(2), now=0)
        idle.next_blink = 0
        idle.update(0)
        next_blink = idle.next_blink
        idle.update(.03)
        self.assertEqual(idle.next_blink, next_blink)


if __name__ == '__main__':
    unittest.main()
