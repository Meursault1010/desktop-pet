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


if __name__ == '__main__':
    unittest.main()
