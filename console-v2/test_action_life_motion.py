"""Secondary motion must stay subtle and preserve authored poses."""
import os
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
import unittest

from PySide6.QtCore import QRect, Qt
from PySide6.QtGui import QColor, QPainter, QPixmap
from PySide6.QtWidgets import QApplication

from action_life_motion import ActionLifeMotion


class ActionLifeMotionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.atlas = QPixmap(256, 256)
        self.atlas.fill(Qt.GlobalColor.transparent)
        painter = QPainter(self.atlas)
        painter.setPen(QColor('#eef8ff'))
        painter.setBrush(QColor('#77aadd'))
        painter.drawEllipse(QRect(78, 24, 100, 94))
        painter.drawRoundedRect(QRect(62, 104, 132, 126), 28, 28)
        painter.end()

    def test_frame_deforms_slightly_without_changing_canvas_or_pose(self):
        motion = ActionLifeMotion()
        source = QRect(0, 0, 256, 256)
        first = motion.render(self.atlas, source, 'read', 0)
        middle = motion.render(self.atlas, source, 'read', .95)
        self.assertEqual((first.width(), first.height()), (256, 256))
        self.assertTrue(bytes(first.constBits()) != bytes(middle.constBits()))
        # The anchored lower edge remains stable; the character is not scaled.
        first_bottom = max(y for y in range(256) for x in range(256)
                          if first.pixelColor(x, y).alpha() > 12)
        middle_bottom = max(y for y in range(256) for x in range(256)
                           if middle.pixelColor(x, y).alpha() > 12)
        self.assertLessEqual(abs(first_bottom-middle_bottom), 1)

    def test_pose_categories_are_supported_and_large_motion_is_untouched(self):
        motion = ActionLifeMotion()
        source = QRect(0, 0, 256, 256)
        for action in ('read', 'sit-neat', 'prone-rest'):
            self.assertIsNotNone(motion.render(self.atlas, source, action, .6))
        self.assertIsNone(motion.render(self.atlas, source, 'lazy-roll-away', .6))
        self.assertIsNone(motion.render(self.atlas, source, 'throw-flight', .6))

    def test_display_scale_and_thirty_hz_reuse(self):
        motion = ActionLifeMotion()
        source = QRect(0, 0, 256, 256)
        first = motion.render(self.atlas, source, 'read', .1, 160)
        self.assertEqual((first.width(), first.height()), (160, 160))
        cached = motion.render(self.atlas, source, 'read', .105, 160)
        self.assertIs(cached, first)
        later = motion.render(self.atlas, source, 'read', .2, 160)
        self.assertIsNot(later, first)


    def test_the_hip_mask_is_limited_to_the_reading_holds(self):
        """An amplitude rule approved for one clip is not a licence for all."""
        source = QRect(0, 0, 256, 256)
        shipped = ActionLifeMotion.UPPER_ONLY
        self.addCleanup(setattr, ActionLifeMotion, 'UPPER_ONLY', shipped)

        def below_waist(action, masked):
            ActionLifeMotion.UPPER_ONLY = shipped & {action} if masked else set()
            motion = ActionLifeMotion()
            image = motion.render(self.atlas, source, action, .95)
            return bytes(image.constBits())[190*256*4:250*256*4]

        for action in ('sit-neat', 'prone-rest', 'work', 'read', 'reading-pose-1'):
            with self.subTest(action=action):
                limited, whole = below_waist(action, True), below_waist(action, False)
                if action in shipped:
                    self.assertNotEqual(limited, whole, f'{action} lost its hip mask')
                else:
                    self.assertEqual(limited, whole, f'{action} picked up a hip mask')


if __name__ == '__main__':
    unittest.main()
