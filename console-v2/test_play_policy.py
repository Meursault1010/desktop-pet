import unittest
from play_policy import PlayPolicy


class PlayPolicyTests(unittest.TestCase):
    def test_rolling_budget_is_bounded_and_expires(self):
        p = PlayPolicy()
        for i in range(600):
            p.advance(i*.1, .1, moving=True)
        self.assertAlmostEqual(p.remaining(60, '默认'), 0.)
        self.assertLessEqual(len(p.motion), 61)
        self.assertEqual(p.remaining(700, '少动'), 30.)

    def test_recent_stories_and_icons_cannot_repeat(self):
        p = PlayPolicy()
        p.complete('lean', 'icon', 10, 180)
        self.assertFalse(p.available('lean', 11))
        self.assertIsNone(p.score('icon', 10, 360, 1, 1, 11))
        self.assertIsNotNone(p.score('other', 10, 360, 1, 1, 11))
        p.complete('read', 'other', 20, 180)
        self.assertFalse(p.available('tea', 21))
        self.assertTrue(p.available('tea', 201))

    def test_fatigue_and_failures_are_hard_filters(self):
        p = PlayPolicy()
        p.energy = 10
        self.assertFalse(p.available('roll', 10))
        self.assertTrue(p.available('rest', 10))
        p.fail('gone', 10)
        self.assertIsNone(p.score('gone', 1, 360, 1, 1, 11))
        self.assertIsNotNone(p.score('gone', 1, 360, 1, 1, 131))

    def test_wall_clock_or_resume_never_creates_unbounded_energy_change(self):
        p = PlayPolicy()
        p.advance(10000, 10000, moving=True)
        self.assertGreater(p.energy, 74)
        self.assertGreater(p.remaining(10000, '默认'), 59)


if __name__ == '__main__':
    unittest.main()
