"""Approved model details must not change between articulated walk samples."""
import unittest
from pathlib import Path
from PIL import Image

ROOT = Path(__file__).resolve().parent/'assets/motion-v2'


class ApprovedWalkTests(unittest.TestCase):
    def test_head_hair_and_dress_are_identical_across_every_sample(self):
        for name in ('walk-right', 'walk-left'):
            first = Image.open(ROOT/name/'00.png').convert('RGBA')
            upper = first.crop((0,0,256,198)).tobytes()
            for i in range(60):
                image = Image.open(ROOT/name/f'{i:02}.png').convert('RGBA')
                self.assertEqual(image.size, (256,256))
                self.assertEqual(image.crop((0,0,256,198)).tobytes(), upper)
                self.assertEqual(image.getpixel((0,0))[3], 0)
            self.assertNotEqual(first.tobytes(), Image.open(ROOT/name/'15.png').tobytes())


if __name__ == '__main__':
    unittest.main()
