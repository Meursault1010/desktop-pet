"""World contact invariants and smooth authored traversal, both directions."""
import os
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
import unittest
import numpy as np
from PySide6.QtGui import QImage
from PySide6.QtWidgets import QApplication
from climb_rig import hand_sample,pull_progress,_image,STRIDE
from locomotion import contact_progress


class ContactRigTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.app=QApplication.instance() or QApplication([])

    def test_planted_hand_is_fixed_in_world_in_both_directions(self):
        for direction in (-1,1):
            for half in range(-3,4):
                anchors=[]
                for i in range(1,50):
                    distance=(half+i/50)*STRIDE/2
                    shifts,support=hand_sample(distance,direction)
                    anchors.append(direction*distance+shifts[support])
                self.assertLess(max(anchors)-min(anchors),1e-10)

    def test_hand_transfers_and_pull_speed_are_continuous(self):
        for distance in (-16,-8,0,8,16):
            before=hand_sample(distance-1e-6)[0];after=hand_sample(distance+1e-6)[0]
            self.assertLess(max(abs(a-b) for a,b in zip(before,after)),.0001)
            self.assertAlmostEqual(pull_progress(distance),distance)
            self.assertLess(abs(pull_progress(distance+.0001)-pull_progress(distance)),1e-7)

    def test_climb_art_outside_arm_region_remains_identical(self):
        for name in ('climb-left','climb-right'):
            images=[_image(name,i,1).toImage() for i in (0,30,60,90)]
            # The lower hair, skirt and legs come from the same source pixels.
            self.assertTrue(all(im.copy(0,128,256,128)==images[0].copy(0,128,256,128) for im in images))
            self.assertNotEqual(images[0],images[1])

    @staticmethod
    def _pixels(image):
        image=image.convertToFormat(QImage.Format.Format_ARGB32)
        data=np.frombuffer(image.constBits(),np.uint8)
        return data.reshape(image.height(),image.bytesPerLine())[:,:image.width()*4].reshape(image.height(),image.width(),4).astype(int)

    def test_climb_face_is_rigid_while_the_hand_moves(self):
        for name in ('climb-left','climb-right'):
            first=self._pixels(_image(name,0,1).toImage())
            second=self._pixels(_image(name,30,1).toImage())
            diff=np.abs(first-second).max(2)
            if name=='climb-left':
                face,arm=diff[55:95,120:160],diff[25:120,170:200]
            else:
                face,arm=diff[55:95,100:140],diff[25:120,56:92]
            self.assertLessEqual(int(face.max()),2,name)
            self.assertGreater(int(arm.max()),50,name)

    def test_icon_climb_keeps_grip_hold_and_monotone_travel(self):
        for phases in ((0.,0.,.25,.65,.90,1.),(0.,0.,.20,.55,.85,1.)):
            values=[contact_progress(phases,i,t/100) for i in range(5) for t in range(101)]
            self.assertTrue(all(a<=b+1e-10 for a,b in zip(values,values[1:])))
            self.assertTrue(all(contact_progress(phases,0,t/20)==0 for t in range(21)))
            self.assertEqual(contact_progress(phases,5,0.),1.)
            for i in range(1,5):
                left=(contact_progress(phases,i-1,1)-contact_progress(phases,i-1,1-1e-5))/1e-5
                right=(contact_progress(phases,i,1e-5)-contact_progress(phases,i,0))/1e-5
                self.assertAlmostEqual(left,right,places=4)


if __name__=='__main__':unittest.main()
