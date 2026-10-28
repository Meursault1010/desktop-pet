"""Guard the shared climb/top-rest pose against the left-calf alpha hole."""
import unittest
from pathlib import Path

import numpy as np
from PIL import Image

from repair_top_rest_leg import enclosed_hole

ROOT = Path(__file__).resolve().parent
POSES = (('play-top-rest', 0), ('play-top-rest', 1),
         ('play-climb-up', 5), ('play-climb-down', 0))
AFFECTED_BRIDGES = ('play-climb-up_4--play-climb-up_5.png',
                    'play-climb-up_5--play-climb-up_0.png',
                    'play-climb-down_0--play-climb-down_1.png',
                    'play-climb-down_5--play-climb-down_0.png')


def hole_area(frame):
    return int(enclosed_hole(np.array(frame.convert('RGBA'))[:, :, 3]).sum())


def frame(action, index):
    atlas = Image.open(ROOT/'assets/actions'/action/'atlas.png').convert('RGBA')
    return atlas.crop((index % 4*256, index//4*256,
                       (index % 4+1)*256, (index//4+1)*256))


class TopRestLegTests(unittest.TestCase):
    def test_shared_top_rest_pose_has_a_filled_left_calf(self):
        for action, index in POSES:
            with self.subTest(action=action, frame=index):
                self.assertLess(hole_area(frame(action, index)), 40)

    def test_climb_bridges_keep_the_left_calf(self):
        for name in AFFECTED_BRIDGES:
            path = ROOT/'assets/action-motion'/name
            strip = Image.open(path).convert('RGBA')
            for index in range(25):
                cell = strip.crop((index % 5*256, index//5*256,
                                   (index % 5+1)*256, (index//5+1)*256))
                with self.subTest(file=path.name, frame=index):
                    self.assertLess(hole_area(cell), 200)


if __name__ == '__main__':
    unittest.main()
