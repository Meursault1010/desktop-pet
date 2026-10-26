import unittest
from types import SimpleNamespace
from music_timing import dance_speed, follow_tempo


class TimingTests(unittest.TestCase):
    def test_tempo_is_bounded_and_invalid_values_are_safe(self):
        self.assertEqual(dance_speed(120), .5)
        self.assertAlmostEqual(dance_speed(60), .4)
        self.assertAlmostEqual(dance_speed(240), .6)
        self.assertEqual(dance_speed(float('nan')), .5)

    def test_tempo_change_preserves_position_and_approaches_target(self):
        p = SimpleNamespace(started=0., speed=.5)
        previous = 0.
        for i in range(1, 401):
            now = i*.016
            position = (now-p.started)*p.speed
            start, end = follow_tempo(p, 144, now, .016)
            self.assertAlmostEqual((now-start)*p.speed, position)
            self.assertGreaterEqual(position, previous)
            self.assertGreaterEqual(end, now)
            previous = position
        self.assertGreater(p.speed, .59)
        self.assertLessEqual(p.speed, .6)
