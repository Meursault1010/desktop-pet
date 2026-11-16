"""Planted-foot tracks, depth order and undeformed shoes in the walk rig."""
import os
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
import math,unittest
import numpy as np
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QRectF
from PySide6.QtGui import QImage,QPainter
import walk_rig
from walk_rig import (HOME,LEG_ORDER,NEAR_LEG,FAR_LEG,SWING_TILT,STANCE_ROLL,BODY_LOWER,
                      NEAR_SWING_LEAN,parts,_poses,_swing_lean,rig,sample,paint)
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
        # The pair sits on the body axis measured from the torso and skirt hem
        # (x≈140), not on the canvas centre: at 128 both walk feet hung off the
        # left of her skirt.
        self.assertGreater(HOME[NEAR_LEG][0],HOME[FAR_LEG][0])
        self.assertLess(HOME[NEAR_LEG][0]-HOME[FAR_LEG][0],20.)
        self.assertAlmostEqual((HOME[FAR_LEG][0]+HOME[NEAR_LEG][0])/2,140.,delta=.01)

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

    def test_sock_stays_vertical_while_the_shoe_rolls(self):
        # 支撑相袜筒只平移、不旋转。把渲染结果和"只在 (dx,dy) 平移画一次袜筒"
        # 的参考图逐像素比对；旧做法整腿绕髋旋转，倾斜相位下边缘会差出几十级。
        socks,shoes=parts();stride=walk_stride('walk-right');checked=0
        for i in range(96):
            phase=i/96
            if _swing_lean(phase):continue
            image=QImage(256,256,QImage.Format.Format_RGBA8888);image.fill(0)
            painter=QPainter(image)
            paint(painter,QRectF(0,0,256,256),'walk-right',phase*stride,shadows=False)
            painter.end()
            drawn=np.frombuffer(image.constBits(),np.uint8).reshape(256,256,4)
            angle,dx,dy,_=_poses(phase*stride,stride)[0][NEAR_LEG]
            if abs(angle)<1.:continue
            ref=QImage(256,256,QImage.Format.Format_RGBA8888);ref.fill(0)
            painter=QPainter(ref)
            painter.setRenderHint(QPainter.RenderHint.Antialiasing,True)
            painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
            painter.translate(dx,dy)
            painter.drawPixmap(QRectF(0,0,256,256),socks[NEAR_LEG],
                               QRectF(socks[NEAR_LEG].rect()))
            painter.end()
            want=np.frombuffer(ref.constBits(),np.uint8).reshape(256,256,4)
            mask=(want[:,:,3]==255)&(drawn[:,:,3]==255)
            # 只比裙摆以下、鞋口以上的那几行；抬脚时整条腿会上移，窗口跟着 dy 走
            lo=max(221,int(math.ceil(223+dy)));hi=int(math.floor(229+dy))
            mask[:lo]=False
            mask[hi+1:]=False
            if hi-lo<2:continue
            checked+=1
            diff=np.abs(drawn[mask].astype(int)-want[mask].astype(int)).max()
            self.assertLessEqual(diff,2,(i,diff))
        self.assertGreater(checked,4)

    def test_swing_lean_trails_then_leads_and_returns_to_plumb(self):
        # near 腿：u=0 刚离地（脚在后）→ 后倾；u=0.5 脚在最前 → 前倾；两端 0°。
        # Qt 正角是顺时针，髋点在脚踝正上方，所以正角让袜筒下端向左（向后）走。
        self.assertEqual(_swing_lean(0.),0.)
        self.assertEqual(_swing_lean(.5),0.)
        self.assertAlmostEqual(_swing_lean(.75),0.)        # u=0.5，脚在髋下
        self.assertGreater(_swing_lean(.625),NEAR_SWING_LEAN*.9)    # u=0.25 后倾
        self.assertLess(_swing_lean(.875),-NEAR_SWING_LEAN*.9)      # u=0.75 前倾
        peak=max(abs(_swing_lean(i/960)) for i in range(960))
        self.assertAlmostEqual(peak,NEAR_SWING_LEAN,delta=.01)
        for phase in (.2,.3,.4):
            self.assertEqual(_swing_lean(phase),0.)

    def test_the_swing_lean_moves_only_the_near_leg(self):
        # 摆动相加了髋部摆动后，只有近腿那一片像素可以变；远腿、裙摆、上身
        # 必须逐字节不变（后腿按要求不动）。支撑相则完全不受影响。
        def frame(phase,lean):
            old=walk_rig.NEAR_SWING_LEAN;walk_rig.NEAR_SWING_LEAN=lean
            try:
                image=QImage(256,256,QImage.Format.Format_RGBA8888);image.fill(0)
                painter=QPainter(image)
                paint(painter,QRectF(0,0,256,256),'walk-right',phase*40)
                painter.end()
                return np.frombuffer(image.constBits(),np.uint8).reshape(
                    256,256,4).copy()
            finally:walk_rig.NEAR_SWING_LEAN=old
        for phase in (.625,.6875,.875):
            a=frame(phase,NEAR_SWING_LEAN);b=frame(phase,0.)
            moved=np.abs(a.astype(int)-b.astype(int)).max(axis=2)>0
            self.assertGreater(int(moved.sum()),40,(phase,))
            ys,xs=np.where(moved)
            self.assertGreaterEqual(int(xs.min()),105,(phase,int(xs.min())))
            self.assertLessEqual(int(xs.max()),200,(phase,int(xs.max())))
            self.assertGreaterEqual(int(ys.min()),195,(phase,int(ys.min())))
        for phase in (.1,.2,.3,.4):
            self.assertTrue(np.array_equal(frame(phase,NEAR_SWING_LEAN),frame(phase,0.)),
                            phase)

    def test_left_walk_mirrors_the_same_near_leg_swing(self):
        # 左右走共用同一套摆动，方向靠画布镜像。近腿区域的像素镜像后必须
        # 几乎重合；残余只来自 Qt 的镜像采样（远小于"没镜像"时的差异）。
        def render(name,clock):
            image=QImage(256,256,QImage.Format.Format_RGBA8888);image.fill(0)
            painter=QPainter(image)
            paint(painter,QRectF(0,0,256,256),name,clock,shadows=False)
            painter.end()
            a=np.frombuffer(image.constBits(),np.uint8).reshape(256,256,4)
            a=a.astype(float)
            a[:,:,:3]*=a[:,:,3:4]/255.
            return a
        right=(125,215,205,252)
        left=(256-right[2],right[1],256-right[0],right[3])
        for i in range(24):
            phase=i/24
            a=render('walk-right',phase*40)[right[1]:right[3],right[0]:right[2]]
            b=render('walk-left',phase*40)[left[1]:left[3],left[0]:left[2]][:,::-1]
            mean=np.abs(a-b).mean()
            self.assertLess(mean,8.,(i,mean))
            # 同一张图不镜像时差异要大一个数量级，说明这条断言真的在测镜像
            self.assertGreater(np.abs(a-b[:,::-1]).mean(),20.)

    def test_planted_foot_rolls_heel_to_toe_and_stays_flat_mid_stance(self):
        # 支撑脚只在落地/蹬离两端滚动，中段整只脚掌踩平；摆动脚从蹬地角度
        # 连续接回落地角度，所以交接处不会出现角度跳变。
        stride=walk_stride('walk-right');planted=[];each=[[],[]]
        for i in range(480):
            phase=i/480
            limbs,support,_=sample(phase*stride,stride)
            for leg in range(2):
                each[leg].append(limbs[leg][0])
            p=(phase+(.5 if support==0 else 0.))%1.
            planted.append((p/.5,limbs[support][0]))
        for leg in range(2):
            a=each[leg]
            self.assertLess(max(abs(y-x) for x,y in zip(a,a[1:])),.6,(leg,))
        self.assertLessEqual(max(abs(x) for a in each for x in a),STANCE_ROLL+SWING_TILT+.05)
        flat=[a for q,a in planted if .22<q<.78]
        self.assertTrue(flat and max(abs(a) for a in flat)==0.)
        self.assertGreater(max(a for q,a in planted if q<.01),STANCE_ROLL*.99)   # q=0 精确取到
        self.assertLess(min(a for q,a in planted if q>.99),-STANCE_ROLL*.95)

    def test_swing_leg_rocks_from_the_hip_and_lands_flat(self):
        stride=walk_stride('walk-right');swing=[]
        for i in range(240):
            limbs,support,_=sample(i/240*stride,stride)
            swing.append(limbs[1-support][0])
        # 摆动相两端分别接上蹬离与着地角度，中段再挑一次脚跟
        self.assertAlmostEqual(min(swing),-STANCE_ROLL,delta=.05)
        self.assertGreater(max(swing),STANCE_ROLL)
        self.assertLess(max(swing),STANCE_ROLL+SWING_TILT)

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
        def frame(name, eye_frame):
            image=QImage(256,256,QImage.Format.Format_RGBA8888);image.fill(0)
            painter=QPainter(image)
            paint(painter,QRectF(0,0,256,256),name,0,shadows=False,
                  eye_frame=eye_frame)
            painter.end()
            return np.frombuffer(image.constBits(),np.uint8).reshape(256,256,4).copy()
        for name in ('walk-right','walk-left'):
            opened=frame(name,1)
            # Every idle frame other than half/closed keeps the open eyes.
            self.assertTrue(np.array_equal(frame(name,6),opened))
            self.assertTrue(np.array_equal(frame(name,11),opened))
            face=(slice(64+int(BODY_LOWER),108+int(BODY_LOWER)),slice(58,198))
            outside=np.ones((256,256),bool);outside[face]=False
            for eye_frame,limit in ((4,.85),(10,.1)):
                lid=frame(name,eye_frame)
                # The torso now sways on a sub-pixel offset, so re-sampling leaves
                # up to two levels of anti-aliasing noise outside the face.
                self.assertLessEqual(np.abs(lid[outside].astype(int)-opened[outside].astype(int)).max(),2)
                self.assertGreater(np.abs(lid[face].astype(int)-opened[face].astype(int)).max(),20)
                sub=opened[face]
                open_iris=((sub[:,:,0]<100)&(sub[:,:,2]>140)
                           &(sub[:,:,2]-sub[:,:,1]>50)&(sub[:,:,1]<160)&(sub[:,:,3]>200)).sum()
                sub=lid[face]
                lid_iris=((sub[:,:,0]<100)&(sub[:,:,2]>140)
                          &(sub[:,:,2]-sub[:,:,1]>50)&(sub[:,:,1]<160)&(sub[:,:,3]>200)).sum()
                self.assertLess(lid_iris,open_iris*limit,(name,eye_frame,open_iris,lid_iris))

    def test_walk_blink_keeps_eye_line_anchored(self):
        """Blink variants must not inherit a translated idle eye position."""
        from build_walk_blink import IDLE_EYES, PATCH_DROP, WALK_EYES
        self.assertEqual(PATCH_DROP, 0.0)
        self.assertAlmostEqual(IDLE_EYES[0][0], 107.5)
        self.assertAlmostEqual(IDLE_EYES[1][0], 147.5)
        self.assertAlmostEqual(WALK_EYES[0][0], 135.0)
        self.assertAlmostEqual(WALK_EYES[1][0], 167.5)

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
