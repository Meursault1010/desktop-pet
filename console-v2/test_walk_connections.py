"""Rendered lower limbs must remain joined throughout the grounded cycle."""
import os
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
import unittest
import cv2
import numpy as np
from PySide6.QtWidgets import QApplication
from PySide6.QtGui import QImage,QPainter
from PySide6.QtCore import QRectF
from walk_rig import paint


class WalkConnectionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app=QApplication.instance() or QApplication([])

    def test_no_disconnected_leg_or_shoe_over_full_cycle(self):
        for name in ('walk-left','walk-right'):
            for i in range(120):
                image=QImage(256,256,QImage.Format.Format_RGBA8888)
                image.fill(0)
                painter=QPainter(image)
                # Ground shadows are separate soft ellipses, not body parts.
                paint(painter,QRectF(0,0,256,256),name,i/120*40,shadows=False)
                painter.end()
                pixels=np.frombuffer(image.constBits(),np.uint8).reshape(256,256,4)
                mask=np.uint8(pixels[:,:,3]>40)
                _,labels,stats,_=cv2.connectedComponentsWithStats(mask)
                body=int(labels[180,128])
                # Tiny antialias specks are allowed, a detached shoe or leg is not.
                for label in range(1,len(stats)):
                    if label!=body:
                        self.assertLess(stats[label,cv2.CC_STAT_AREA],16,(name,i))


if __name__=='__main__':
    unittest.main()
