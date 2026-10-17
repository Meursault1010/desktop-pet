"""Physical support, nearest visible edge, and distance-driven movement."""
import os
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
import math,time,unittest
from unittest.mock import patch
from PySide6.QtWidgets import QApplication
from PySide6.QtGui import QImage,QPainter
from pet import DesktopPet
from settings_model import Preferences
from icon_sleep import GEOMETRIES
from locomotion import step_towards,metadata,frame
from edge_geometry import nearest,candidates,envelope,contact_offset,corner_landing,screen_landings
import test_edge_attachment as edge_tests


class MotionGeometryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.app=QApplication.instance() or QApplication([])

    def bounds(self):
        from icon_sleep import ASSET_ROOT,pose_bounds
        return {p:pose_bounds(QImage(str(ASSET_ROOT/p/'base.png'))) for p in GEOMETRIES}

    def test_projection_selects_each_nearest_edge(self):
        rect=(400,300,600,400);area=(0,0,1600,1100);size=(180,190);bounds=self.bounds()
        for origin,kind in [((610,100),'top'),((230,370),'left'),((1010,370),'right'),((610,730),'bottom')]:
            landing=nearest(rect,area,size,bounds,origin)
            self.assertEqual(landing.kind,kind,(origin,landing))
            ox,oy=contact_offset(size,landing.pose)
            self.assertAlmostEqual(landing.position[0]+ox,landing.anchor[0])
            self.assertAlmostEqual(landing.position[1]+oy,landing.anchor[1])
            l,t,r,b=envelope(size,bounds,landing.pose)
            self.assertGreaterEqual(landing.position[0]+l,area[0])
            self.assertGreaterEqual(landing.position[1]+t,area[1])
            self.assertLessEqual(landing.position[0]+r,area[0]+area[2])
            self.assertLessEqual(landing.position[1]+b,area[1]+area[3])

    def test_covered_edge_is_excluded_and_exposed_segment_remains(self):
        args=((400,300,600,400),(0,0,1600,1100),(180,190),self.bounds(),(600,100))
        choices=candidates(*args,blocked=((500,250,300,150),))
        self.assertTrue(choices)
        for _,l in choices:
            if l.kind=='top':self.assertFalse(497<l.anchor[0]<803)
        self.assertFalse(candidates(*args,blocked=((0,0,1600,1100),)))

    def test_negative_monitor_and_fullscreen_choose_nearest_corner(self):
        bounds=self.bounds();area=(-1600,-200,1600,1000);size=(180,190)
        for x,expected in [(-1580,'perch-back'),(-180,'perch-front')]:
            landing=corner_landing(area,size,bounds,(x,500),'right' if expected=='perch-back' else 'left')
            self.assertEqual(landing.pose,expected)
        for l in screen_landings(area,size,bounds,(-900,300)):
            a,t,r,b=envelope(size,bounds,l.pose)
            self.assertGreaterEqual(l.position[0]+a,area[0]);self.assertGreaterEqual(l.position[1]+t,area[1])
            self.assertLessEqual(l.position[0]+r,0);self.assertLessEqual(l.position[1]+b,800)

    def test_dt_limit_no_overshoot_and_gait_uses_actual_distance(self):
        p,d,done=step_towards((0,0),(30,40),100,99)
        self.assertAlmostEqual(d,10);self.assertAlmostEqual(math.hypot(*p),10);self.assertFalse(done)
        p,d,done=step_towards((29,40),(30,40),100,.1)
        self.assertTrue(done);self.assertEqual(p,(30,40))
        pet=DesktopPet(Preferences(random_movement=False));pet.animator.timer.stop();pet.move(0,0)
        try:
            for _ in range(10):pet.advance_to((30,40),.1,100)
            self.assertEqual((pet.x(),pet.y()),(30,40));self.assertAlmostEqual(pet.state.gait_distance,50)
            a=frame('walk-right',12).toImage();b=frame('walk-right',48).toImage()
            self.assertNotEqual(a,b)
            pet.go_home();self.assertIsNotNone(pet.state.travel_target)
            pet.wake_icon_sleep();self.assertIsNone(pet.state.travel_target)
        finally:pet.hide();pet.deleteLater()

    def test_grip_assets_have_safe_alpha_and_fixed_hanging_hands(self):
        from locomotion import ROOT
        for name,spec in metadata().items():
            images=[QImage(str(ROOT/name/f'{i:02}.png')) for i in range(spec['frames'])]
            self.assertTrue(all(not im.isNull() for im in images))
            for im in images:
                self.assertEqual(im.pixelColor(0,0).alpha(),0)
            self.assertNotEqual(images[0],images[len(images)//4])
        # Entire band containing both palms is identical over the sway cycle.
        images=[frame('hang',elapsed=e).toImage().copy(0,0,256,38) for e in (0,.6,1.2,1.8)]
        self.assertTrue(all(im==images[0] for im in images))


class GripLifecycleTests(unittest.TestCase):
    manual_attach=edge_tests.EdgeTests.manual_attach
    setUpClass=classmethod(edge_tests.EdgeTests.setUpClass.__func__)
    setUp=edge_tests.EdgeTests.setUp
    tearDown=edge_tests.EdgeTests.tearDown
    def test_side_crawls_with_motion_and_pause_keeps_grip(self):
        self.pet.move(80,280);self.edge.options.update(enabled=True,delay=2,screens=False);self.edge.until=0
        with patch('edge_attachment.inspect_foreground',return_value=self.surface),patch('edge_attachment.logical_surface',return_value=(self.surface.rect,self.surface.work_area,QApplication.primaryScreen())):
            self.manual_attach()
            self.assertTrue(self.edge.active);self.assertEqual(self.edge.kind,'left')
            for _ in range(300):
                self.edge.last_tick-=.1;self.edge.animate()
                if self.edge.phase=='resting':break
            self.assertEqual(self.edge.phase,'resting')
            self.edge.next_move=0;before=self.edge.distance
            for _ in range(20):self.edge.last_tick-=.1;self.edge.animate()
            self.assertGreater(self.edge.distance,before)
            self.assertEqual(self.pet.state.gait_until,0)
            self.controller.set_preference('paused',True);point=self.pet.pos();distance=self.edge.distance
            self.edge.last_tick-=.1;self.edge.animate();self.assertEqual(point,self.pet.pos());self.assertEqual(distance,self.edge.distance)
            image=QImage(self.pet.size(),QImage.Format.Format_ARGB32_Premultiplied);image.fill(0)
            painter=QPainter(image);self.assertTrue(self.edge.paint(painter));painter.end()
            self.pet.hide();self.assertFalse(self.edge.active)

    def test_passive_window_movement_does_not_walk_or_advance_climb(self):
        self.pet.move(80,280);self.edge.options.update(enabled=True,delay=2);self.edge.until=0
        with patch('edge_attachment.inspect_foreground',return_value=self.surface),patch('edge_attachment.logical_surface',return_value=(self.surface.rect,self.surface.work_area,QApplication.primaryScreen())):
            self.manual_attach()
            for _ in range(300):
                self.edge.last_tick-=.1;self.edge.animate()
                if self.edge.phase=='resting':break
            self.edge.next_move=float('inf');old=self.pet.pos();distance=self.edge.distance
            moved=(330,290,600,400)
            with patch('edge_attachment.logical_surface',return_value=(moved,self.surface.work_area,QApplication.primaryScreen())):
                self.edge.tick();self.edge.animate()
            self.assertEqual(self.pet.x()-old.x(),80);self.assertEqual(self.pet.y()-old.y(),50)
            self.assertEqual(distance,self.edge.distance);self.assertEqual(self.pet.state.gait_until,0)

if __name__=='__main__':unittest.main()
