"""Planted-foot tracks, depth order and undeformed shoes in the walk rig."""
import os
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
import math,unittest
import numpy as np
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QRectF
from PySide6.QtGui import QImage,QPainter
from walk_rig import HOME,LEG_ORDER,NEAR_LEG,FAR_LEG,SWING_TILT,rig,sample,paint
from locomotion import walk_stride


class WalkPerspectiveTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.app=QApplication.instance() or QApplication([])

    def test_far_leg_is_painted_under_the_near_leg_at_its_authored_depth(self):
        self.assertEqual(LEG_ORDER,(FAR_LEG,NEAR_LEG))
        far,near=rig()[2][FAR_LEG],rig()[2][NEAR_LEG]
        # The authored far shoe sits higher in the master and must never be
        # pulled down to the near floor: that stretched the far sock.
        self.assertLess(far['anchor'][1],near['anchor'][1])
        self.assertGreaterEqual(near['anchor'][1]-far['anchor'][1],6)
        self.assertEqual(HOME,(tuple(far['home']),tuple(near['home'])))
        # The near sole is the one that meets the window baseline.
        self.assertAlmostEqual(HOME[NEAR_LEG][1],249,delta=1)
        self.assertLess(HOME[FAR_LEG][1],244)
        # The pair straddles the body pivot (128) instead of inheriting the
        # average of the wide authored stance anchors, which left both walk
        # feet four pixels to the right of the torso.
        self.assertGreater(HOME[NEAR_LEG][0],HOME[FAR_LEG][0])
        self.assertLess(HOME[NEAR_LEG][0]-HOME[FAR_LEG][0],20.)
        self.assertAlmostEqual((HOME[FAR_LEG][0]+HOME[NEAR_LEG][0])/2,128.,delta=.01)

    def test_feet_cross_behind_each_other_every_step(self):
        stride=walk_stride('walk-right')
        signed=[]
        for i in range(240):
            limbs,_,_=sample(i/240*stride,stride)
            signed.append(limbs[NEAR_LEG][3][0]-limbs[FAR_LEG][3][0])
        # The near foot starts ahead, passes behind the far foot and returns:
        # without the sign flip the shoes only breathe apart, never overlap.
        self.assertGreater(max(signed),20.)
        self.assertLess(min(signed),-4.)
        self.assertLess(min(abs(g) for g in signed),2.)
        # The far shoe is still painted first, so the near leg occludes it at
        # the moment they line up.
        self.assertEqual(LEG_ORDER,(FAR_LEG,NEAR_LEG))

    def test_planted_foot_stays_fixed_in_the_world(self):
        for vector in ((1.,0.),(.6,.8),(.6,-.8),(0.,1.)):
            for half in range(2):
                points=[]
                for i in range(1,59):
                    clock=(half+i/60)*20
                    limbs,support,_=sample(clock,40,vector)
                    sole=limbs[support][3]
                    points.append(tuple(clock*axis+coord*160/256 for axis,coord in zip(vector,sole)))
                for axis in (0,1):
                    self.assertLess(max(p[axis] for p in points)-min(p[axis] for p in points),1e-8)

    def test_stance_and_double_support_windows(self):
        contacts=[0,0];double=0
        for i in range(1000):
            # Bin centres avoid counting the exact lift-off instant twice.
            clock=(i+.5)/1000*40
            limbs,_,_=sample(clock,40)
            planted=[abs(limbs[j][3][1]-HOME[j][1])<1e-7 for j in range(2)]
            self.assertTrue(any(planted),(i,limbs))
            double+=all(planted)
            for j in range(2):contacts[j]+=planted[j]
        self.assertEqual(contacts,[500,500])
        # The stance hands off exactly when the other foot lands: no window
        # with both soles planted, so the walk never pauses into a stance.
        self.assertEqual(double,0)

    def test_lift_off_touchdown_are_position_and_velocity_continuous(self):
        epsilon=1e-5
        for phase in (.1,.5,.6,1.):
            samples=[sample((phase+k*epsilon)*40,40)[0] for k in (-1,0,1)]
            for leg in range(2):
                for axis in range(2):
                    a,b,c=[s[leg][3][axis] for s in samples]
                    self.assertLess(abs(c-a),.01)
                    self.assertLess(abs((c-b)/epsilon-(b-a)/epsilon),.1)

    def test_rendered_legs_keep_their_authored_silhouette_under_rigid_swing(self):
        # Swing legs may rock at the hip, but they must never be scaled or
        # redrawn. Compare each rendered silhouette with the rigidly
        # transformed authored alpha mask in both facings.
        legs=rig()[1];data=rig()[2];refs={}
        for leg in range(2):
            image=legs[leg].toImage().convertToFormat(QImage.Format.Format_RGBA8888)
            pixels=np.frombuffer(image.constBits(),np.uint8).reshape(256,256,4)
            # 40 keeps the sock's soft edge without the one-row skirt fringe
            # that the body covers in the real composite.
            yy,xx=np.where(pixels[:,:,3]>40)
            refs[leg]=(xx.astype(float),yy.astype(float))
        for name in ('walk-right','walk-left'):
            for i in range(120):
                clock=i/120*walk_stride(name)
                limbs,support,_=sample(clock,walk_stride(name))
                for leg in range(2):
                    angle,dx,dy,_=limbs[leg]
                    if leg==support:
                        self.assertEqual(angle,0.,(name,i,leg))
                    px,py=data[leg]['pivot']
                    c,s=math.cos(math.radians(angle)),math.sin(math.radians(angle))
                    xx,yy=refs[leg]
                    ex=dx+px+(xx-px)*c-(yy-py)*s
                    ey=dy+py+(xx-px)*s+(yy-py)*c
                    if name=='walk-left':ex=256-ex
                    expected=(ex.min(),ey.min(),ex.max(),ey.max())
                    image=QImage(256,256,QImage.Format.Format_RGBA8888);image.fill(0)
                    painter=QPainter(image)
                    painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
                    if name=='walk-left':
                        painter.translate(256,0);painter.scale(-1,1)
                    painter.translate(dx,dy)
                    if angle:
                        painter.translate(px,py);painter.rotate(angle);painter.translate(-px,-py)
                    painter.drawPixmap(QRectF(0,0,256,256),legs[leg],QRectF(legs[leg].rect()))
                    painter.end()
                    pixels=np.frombuffer(image.constBits(),np.uint8).reshape(256,256,4)
                    yy,xx=np.where(pixels[:,:,3]>40)
                    measured=(xx.min(),yy.min(),xx.max(),yy.max())
                    for a,b in zip(expected,measured):
                        # Rotation resampling may move the soft outline by a
                        # pixel; a scaled or redrawn leg would miss by much more.
                        self.assertLessEqual(abs(a-b),2.,(name,i,leg,expected,measured))

    def test_swing_leg_rocks_from_the_hip_and_lands_flat(self):
        stride=walk_stride('walk-right');swing=[]
        for i in range(240):
            limbs,support,_=sample(i/240*stride,stride)
            swing.append(limbs[1-support][0])
            self.assertEqual(limbs[support][0],0.)
        self.assertAlmostEqual(max(swing),SWING_TILT,delta=.05)
        self.assertAlmostEqual(min(swing),-SWING_TILT,delta=.05)
        for phase in (0.,.5):
            limbs,_,_=sample(phase*stride,stride)
            for leg in range(2):
                # Lift-off and touchdown frames stay flat, so the whole sole
                # meets the floor instead of landing on a toe or heel.
                if abs(limbs[leg][3][1]-HOME[leg][1])<1e-7:
                    self.assertEqual(limbs[leg][0],0.)

    def test_rendered_soles_follow_their_depth_without_clipping(self):
        for name in ('walk-right','walk-left'):
            for i in range(120):
                image=QImage(256,256,QImage.Format.Format_RGBA8888);image.fill(0)
                painter=QPainter(image)
                paint(painter,QRectF(0,0,256,256),name,i/120*40,shadows=False)
                painter.end()
                pixels=np.frombuffer(image.constBits(),np.uint8).reshape(256,256,4)
                self.assertEqual(int(pixels[255,:,3].max()),0,(name,i))
                # Include the softly antialiased sole fringe when measuring
                # the visible bottom; the authored depth is a subpixel value.
                yy,xx=np.where(pixels[:,:,3]>8)
                # The lowest visible point is the lower of the two foot
                # sprites; the far shoe may stay well above the near floor.
                lowest=max(limb[3][1] for limb in
                           sample(i/120*40,walk_stride(name))[0])
                self.assertLess(abs(int(yy.max())-lowest),2.,(name,i))
                self.assertLessEqual(int(yy.max()),249,(name,i))
                self.assertGreaterEqual(int(yy.max()),239,(name,i))

    def test_walk_blink_swaps_only_the_idle_eyelids(self):
        def frame(eye_frame):
            image=QImage(256,256,QImage.Format.Format_RGBA8888);image.fill(0)
            painter=QPainter(image)
            paint(painter,QRectF(0,0,256,256),'walk-right',0,shadows=False,
                  eye_frame=eye_frame)
            painter.end()
            return np.frombuffer(image.constBits(),np.uint8).reshape(256,256,4).copy()
        opened=frame(1)
        # Every idle frame other than half/closed keeps the open eyes.
        self.assertTrue(np.array_equal(frame(6),opened))
        self.assertTrue(np.array_equal(frame(11),opened))
        face=(slice(64,108),slice(110,194))
        outside=np.ones((256,256),bool);outside[face]=False
        for eye_frame,limit in ((4,.85),(10,.1)):
            lid=frame(eye_frame)
            self.assertTrue(np.array_equal(lid[outside],opened[outside]))
            self.assertGreater(np.abs(lid[face].astype(int)-opened[face].astype(int)).max(),20)
            sub=opened[face]
            open_iris=((sub[:,:,0]<100)&(sub[:,:,2]>140)
                       &(sub[:,:,2]-sub[:,:,1]>50)&(sub[:,:,1]<160)&(sub[:,:,3]>200)).sum()
            sub=lid[face]
            lid_iris=((sub[:,:,0]<100)&(sub[:,:,2]>140)
                      &(sub[:,:,2]-sub[:,:,1]>50)&(sub[:,:,1]<160)&(sub[:,:,3]>200)).sum()
            self.assertLess(lid_iris,open_iris*limit,(eye_frame,open_iris,lid_iris))

    def test_contact_shadows_stay_on_the_floor_and_clear_the_bottom_row(self):
        # The shadow is painted before the shoes, so a diff against a
        # shadow-free render isolates exactly the part not covered by a foot.
        def frame(name,clock,shadows):
            image=QImage(256,256,QImage.Format.Format_RGBA8888);image.fill(0)
            painter=QPainter(image)
            paint(painter,QRectF(0,0,256,256),name,clock,shadows=shadows)
            painter.end()
            return np.frombuffer(image.constBits(),np.uint8).reshape(256,256,4).copy()
        for name in ('walk-right','walk-left'):
            stride=walk_stride(name)
            for i in range(120):
                clock=i/120*stride
                before=frame(name,clock,False)
                after=frame(name,clock,True)
                diff=after[:,:,3].astype(int)-before[:,:,3].astype(int)
                # The wider ellipse always peeks out from under a shoe.
                self.assertGreater(int((diff>0).sum()),100,(name,i))
                # Shadows never paint into the clipped bottom row or above the
                # floor strip, and never darken more than their own alpha.
                self.assertEqual(int(diff[255].max()),0,(name,i))
                visible=np.where(diff>0)
                self.assertGreaterEqual(int(visible[0].min()),230,(name,i))
                self.assertLessEqual(int(visible[0].max()),249,(name,i))
                self.assertLessEqual(int(diff.max()),46,(name,i))


if __name__=='__main__':unittest.main()
