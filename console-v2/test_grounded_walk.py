"""Regression checks for pace, contact continuity and external repositioning."""
import os
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
import math
import unittest
from unittest.mock import patch

from PySide6.QtCore import QPointF,QRectF,Qt
from PySide6.QtGui import QImage,QPainter,QTransform
from PySide6.QtWidgets import QApplication

from locomotion import gait_advance,walk_stride,walking_speed
from pet import DesktopPet
from settings_model import Preferences
from walk_rig import rig,sample,paint,HOME


class GroundedWalkTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.app=QApplication.instance() or QApplication([])

    def test_no_half_step_stalls_or_depth_frequency_acceleration(self):
        for vector in ((1.,0.),(.6,.8),(0.,1.)):
            clock=0.
            increments=[]
            for _ in range(180):
                distance,following=gait_advance(clock,'walk-right',65,1/60,1.,vector)
                increments.append(distance)
                clock=following
            self.assertAlmostEqual(clock,180*walking_speed(65)/60)
            self.assertLess(max(increments)-min(increments),1e-10)
            # A complete short-step cycle still covers meaningful distance.
            self.assertGreaterEqual(walk_stride('walk-right'),24)

    def test_rigid_limb_transforms_and_actual_floor_contacts_are_continuous(self):
        data=rig()[2]
        stride=walk_stride('walk-right')
        for vector in ((1.,0.),(.6,.8),(.6,-.8),(0.,1.)):
            for phase in (.5,1.):
                a=sample((phase-1e-6)*stride,stride,vector)[0]
                b=sample((phase+1e-6)*stride,stride,vector)[0]
                for before,after in zip(a,b):
                    self.assertLess(max(abs(x-y) for x,y in zip(before[:3],after[:3])),.01)
            for tick in range(120):
                samples,_,_=sample(tick/120*stride,stride,vector)
                for leg,(angle,dx,dy,target) in enumerate(samples):
                    px,py=data[leg]['pivot']
                    matrix=QTransform()
                    matrix.translate(dx+px,dy+py);matrix.rotate(angle);matrix.translate(-px,-py)
                    # The actual painter matrix preserves limb dimensions.
                    a,b=matrix.map(QPointF(110,230)),matrix.map(QPointF(130,245))
                    self.assertAlmostEqual(math.hypot(a.x()-b.x(),a.y()-b.y()),25,places=7)
                    points=[matrix.map(QPointF(x,y)) for x,y in data[leg]['boundary']]
                    # A rotated shoe's visible bottom matches the planted plane.
                    self.assertLess(abs(max(p.y() for p in points)-target[1]),.03)

    def test_render_does_not_clip_or_reload_assets(self):
        rig()
        with patch('walk_rig.QPixmap',side_effect=AssertionError('unexpected asset decode')):
            for vector in ((1.,0.),(.6,.8),(.6,-.8),(0.,1.)):
                for tick in range(12):
                    im=QImage(256,256,QImage.Format.Format_ARGB32_Premultiplied)
                    im.fill(Qt.GlobalColor.transparent)
                    painter=QPainter(im)
                    paint(painter,QRectF(0,0,256,256),'walk-right',tick/12*40,vector)
                    painter.end()
                    self.assertTrue(all(im.pixelColor(x,255).alpha()<10 for x in range(256)))

    def test_stall_target_adjustment_and_one_pixel_external_move_do_not_pull_back(self):
        pet=DesktopPet(Preferences(random_movement=False));pet.animator.timer.stop();pet.move(100,100)
        try:
            for _ in range(20):pet.advance_to((800,100),1/60,65)
            before=pet.state.gait_clock
            pet.state.gait_until=0  # A delayed paint must not reset an active route.
            pet.advance_to((800,101),1/60,65)
            self.assertGreater(pet.state.gait_clock,before)
            self.assertAlmostEqual(pet.state.gait_clock-before,walking_speed(65)/60)
            # One-pixel repositioning was previously swallowed by a 1.1px tolerance.
            pet.move(pet.x()+1,pet.y())
            start=(pet.x(),pet.y())
            pet.advance_to((800,start[1]),.01,20)
            self.assertGreaterEqual(pet.x(),start[0])
            self.assertAlmostEqual(pet.state.travel_position[0],start[0]+walking_speed(20)*.01)
            # Continuing across frame boundaries keeps exact accumulated travel.
            clock=pet.state.gait_clock
            for _ in range(100):pet.advance_to((800,start[1]),.016,20)
            self.assertAlmostEqual(pet.state.gait_clock-clock,walking_speed(20)*1.6)
        finally:pet.hide();pet.deleteLater()

    def test_walk_energy_ramps_in_and_settles_to_neutral_legs(self):
        pet=DesktopPet(Preferences(random_movement=False));pet.animator.timer.stop();pet.move(100,100)
        try:
            state=pet.state
            state.gait_energy=1.;state.gait_energy_at=100.
            self.assertAlmostEqual(state.current_gait_energy(100.11),.5,places=6)
            self.assertEqual(state.current_gait_energy(100.019),1.)
            self.assertFalse(state.gait_settled(100.2))
            self.assertTrue(state.gait_settled(100.4))
            stride=walk_stride('walk-right')
            first=sample(0,stride,(1.,0.),energy=0)[0]
            later=sample(stride*.37,stride,(1.,0.),energy=0)[0]
            for a,b in zip(first,later):
                self.assertAlmostEqual(a[0],b[0],places=6)
                self.assertAlmostEqual(a[1],b[1],places=6)
                self.assertAlmostEqual(a[2],b[2],places=6)
                self.assertEqual(a[3],b[3])
            for leg in range(2):self.assertEqual(first[leg][3],HOME[leg])
            self.assertAlmostEqual(sample(stride*.25,stride,(1.,0.),energy=0)[2],0.)
            for _ in range(12):pet.advance_to((800,100),1/60,65)
            self.assertGreater(state.gait_energy,.9)
        finally:pet.hide();pet.deleteLater()

    def test_direction_change_and_target_arrival_keep_phase_and_position(self):
        pet=DesktopPet(Preferences(random_movement=False));pet.animator.timer.stop();pet.move(200,200)
        try:
            for _ in range(25):pet.advance_to((700,200),.016,65)
            x,clock=pet.x(),pet.state.gait_clock
            pet.advance_to((100,200),.016,65)
            self.assertLess(pet.x(),x)
            self.assertGreater(pet.state.gait_clock,clock)
            self.assertEqual(pet.state.direction,-1)
            steps=math.ceil(abs(pet.x()-100)/(walking_speed(65)*.016))+10
            for _ in range(steps):
                if pet.advance_to((100,200),.016,65):break
            self.assertEqual((pet.x(),pet.y()),(100,200))
            clock=pet.state.gait_clock
            for _ in range(5):self.assertTrue(pet.advance_to((100,200),.016,65))
            self.assertEqual((pet.x(),pet.y()),(100,200))
            self.assertEqual(pet.state.gait_clock,clock)
        finally:pet.hide();pet.deleteLater()


if __name__=='__main__':unittest.main()
