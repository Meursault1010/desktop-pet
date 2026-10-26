"""Shared-window mask composition across independent features."""
import os
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
import unittest
from PySide6.QtCore import QRect
from PySide6.QtGui import QRegion
from pet_mask import WindowMask


class FakePet:
    def __init__(self):
        self.mask=QRegion()
        self.set_calls=[]
        self.clear_calls=0

    def setMask(self,region):
        self.mask=QRegion(region)
        self.set_calls.append(QRegion(region))

    def clearMask(self):
        self.mask=QRegion()
        self.clear_calls+=1


class WindowMaskTests(unittest.TestCase):
    def setUp(self):
        self.pet=FakePet()
        self.masker=WindowMask(self.pet)

    def test_owners_intersect_and_survive_each_other(self):
        left=QRegion(QRect(0,0,100,100))
        right=QRegion(QRect(20,0,100,100))
        self.masker.set('depth',left)
        self.masker.set('icon_sleep',right)
        self.assertEqual(self.pet.mask,left.intersected(right))
        self.masker.clear('depth')
        self.assertEqual(self.pet.mask,right)
        self.masker.clear('icon_sleep')
        self.assertTrue(self.pet.mask.isEmpty())
        self.assertEqual(self.pet.clear_calls,1)

    def test_empty_intersection_becomes_a_visible_sentinel(self):
        self.masker.set('depth',QRegion(QRect(0,0,10,10)))
        self.masker.set('icon_sleep',QRegion(QRect(20,0,10,10)))
        self.assertEqual(self.pet.mask,QRegion(QRect(0,0,1,1)))
        self.masker.clear('icon_sleep')
        self.assertEqual(self.pet.mask,QRegion(QRect(0,0,10,10)))

    def test_clear_all_ends_every_request(self):
        self.masker.set('depth',QRegion(QRect(0,0,100,100)))
        self.masker.set('peek',QRegion(QRect(50,0,100,100)))
        self.masker.clear_all()
        self.assertTrue(self.pet.mask.isEmpty())
        self.assertEqual(self.masker.requests,{})
        self.masker.set('peek',QRegion(QRect(10,0,20,20)))
        self.assertEqual(self.pet.mask,QRegion(QRect(10,0,20,20)))

    def test_reapply_restores_the_native_mask_after_window_rebuild(self):
        region=QRegion(QRect(10,10,40,40))
        self.masker.set('icon_sleep',region)
        self.pet.clearMask()  # native rebuild drops the window region
        self.assertTrue(self.pet.mask.isEmpty())
        self.masker.reapply()
        self.assertEqual(self.pet.mask,region)

    def test_unchanged_request_does_not_touch_the_window_again(self):
        region=QRegion(QRect(0,0,50,50))
        for _ in range(4):
            self.masker.set('icon_sleep',region)
        self.assertEqual(len(self.pet.set_calls),1)


if __name__=='__main__':unittest.main()
