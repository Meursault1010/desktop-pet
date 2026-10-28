"""Geometry and lifecycle without inspecting or moving another application."""
import os
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QPoint
from PySide6.QtGui import QImage
from main import PetApplication
from settings_model import SettingsStore
from window_edges import WindowSurface
from edge_attachment import validated,edge_placement,logical_surface
from icon_sleep import GEOMETRIES,pose_envelope,placement,DEFAULTS as ICON_DEFAULTS


class EdgeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.app=QApplication.instance() or QApplication([])

    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.controller=PetApplication(self.app,SettingsStore(Path(self.temp.name)/'settings.ini'),enable_tray=False,create_console=False)
        self.pet=self.controller.pet;self.pet.show();self.pet.animator.timer.stop()
        self.edge=self.controller.edge_attachment;self.poses=self.controller.icon_sleep;self.poses.load_poses()
        self.surface=WindowSurface(1234,999,(250,240,600,400),(0,0,1280,900),(0,0,1280,860),False,False)
        self.pet.move(460,50)
        self.edge.options['screens']=False
        probe=patch('edge_attachment.visible_surfaces',return_value=[self.surface]);probe.start();self.addCleanup(probe.stop)
        self.pet.snap_preview.surfaces=[self.surface];self.pet.snap_preview.surfaces_at=time.monotonic()
        probe=patch.object(self.pet.snap_preview,'request_surfaces');probe.start();self.addCleanup(probe.stop)

    def tearDown(self):
        self.controller.cleanup();self.pet.deleteLater();self.controller.deleteLater();self.app.processEvents();self.temp.cleanup()

    def test_validation_and_persistence(self):
        for bad in ({'enabled':1},{'corner':'top'},{'delay':True},{'delay':61},{'injected':False}):
            with self.assertRaises(ValueError):validated(bad)
        self.edge.configure({'enabled':True,'delay':2,'corner':'left'})
        self.assertEqual(self.controller.store.settings.value('edge_attachment/corner'),'left')
        self.assertFalse(self.edge.timer.isActive())
        self.edge.configure({'enabled':False});self.assertFalse(self.edge.timer.isActive())

    def test_timer_never_attaches_even_with_legacy_enabled(self):
        self.edge.options['enabled']=True
        self.edge.until=0
        for _ in range(5):
            self.edge.pending_since=0
            self.edge.tick()
        self.assertFalse(self.edge.active)
        self.pet.state.ambient.next_at=0
        self.pet.animator.update_ambient(time.monotonic()+2)
        self.assertIsNotNone(self.pet.state.action_player.action)

    def test_manual_docking_does_not_expire(self):
        self.edge.active=True
        with patch.object(self.edge,'follow',return_value=True):
            self.edge.tick()
        self.assertTrue(self.edge.active)

    def manual_attach(self):
        landing=min(self.edge.choices([self.surface]),key=lambda item:item[0].distance)[0]
        self.pet.move(*(round(v) for v in landing.position))
        self.assertTrue(self.edge.on_drop([self.surface],QPoint(*(round(v) for v in landing.anchor))))

    def test_exact_top_contact_and_fullscreen_corners(self):
        size=(180,190);area=(0,0,1280,860)
        side,(x,y),kind=edge_placement(self.surface.rect,area,size,self.poses.bounds)
        self.assertEqual(kind,'top')
        cy=size[1]*(.10+.88*GEOMETRIES[side].contact[1])
        self.assertAlmostEqual(y+cy,240,delta=.51)
        for corner in ('left','right'):
            side,(x,y),kind=edge_placement(area,area,size,self.poses.bounds,corner,True)
            self.assertEqual(kind,'corner')
            l,t,r,b=pose_envelope(size,self.poses.bounds[side],side)
            self.assertGreaterEqual(x+l,0);self.assertGreaterEqual(y+t,0)
            self.assertLessEqual(x+r,1280);self.assertLessEqual(y+b,860)
            self.assertAlmostEqual(y+b,854,delta=.51)

    def test_dwell_follow_resize_manual_release_and_icon_priority(self):
        self.edge.configure({'enabled':True,'delay':2})
        with patch('edge_attachment.inspect_foreground',return_value=self.surface),patch('edge_attachment.logical_surface',return_value=(self.surface.rect,self.surface.work_area,QApplication.primaryScreen())):
            self.edge.tick();self.assertFalse(self.edge.active)
            self.manual_attach();self.assertTrue(self.edge.active)
            for _ in range(200):
                self.edge.last_tick-=.1;self.edge.animate()
                if self.edge.phase=='resting':break
            self.assertEqual(self.edge.phase,'resting');original=self.pet.pos()
            moved=(330,290,620,400)
            with patch('edge_attachment.logical_surface',return_value=(moved,self.surface.work_area,QApplication.primaryScreen())):
                self.edge.tick();self.edge.animate()
            self.assertNotEqual(original,self.pet.pos())
            self.assertFalse(self.pet.movement_allowed())
            self.pet.wake_icon_sleep();self.assertFalse(self.edge.active)
            self.edge.tick();self.assertFalse(self.edge.active)
            self.edge.until=0;self.poses.target={'id':'icon'}
            self.edge.tick();self.assertFalse(self.edge.active)
            self.poses.target=None

    def test_closed_minimized_window_releases_then_screen_fallback(self):
        self.edge.options.update(enabled=True,delay=2,screens=False)
        self.edge.until=0
        with patch('edge_attachment.inspect_foreground',return_value=self.surface),patch('edge_attachment.logical_surface',return_value=(self.surface.rect,self.surface.work_area,QApplication.primaryScreen())):
            self.manual_attach();self.assertTrue(self.edge.active)
        with patch('edge_attachment.visible_surfaces',return_value=[]),patch('edge_attachment.inspect_foreground',return_value=None):
            self.pet.snap_preview.surfaces=[];self.pet.snap_preview.surfaces_at=time.monotonic()
            self.edge.tick();self.assertFalse(self.edge.active)
            self.edge.options['screens']=True;self.edge.until=0
            self.edge.tick();self.edge.pending_since-=2.1;self.edge.tick()
            self.assertFalse(self.edge.active);self.assertIsNone(self.edge.handle)

    def attach_left(self):
        self.edge.options.update(enabled=False,screens=False)
        item=next(item for item in self.edge.choices([self.surface]) if item[0].kind=='left')
        self.pet.move(*(round(v) for v in item[0].position))
        self.edge.on_drop([self.surface],QPoint(*(round(v) for v in item[0].anchor)))
        self.pet.snap_preview.surfaces=[self.surface];self.pet.snap_preview.surfaces_at=time.monotonic()
        with patch('edge_attachment.inspect_foreground',return_value=self.surface),patch('edge_attachment.logical_surface',return_value=(self.surface.rect,self.surface.work_area,QApplication.primaryScreen())):
            self.edge.tick()
        self.assertTrue(self.edge.confirmed)
        return item[0]

    def test_vanished_window_drops_pet_from_current_position(self):
        self.attach_left()
        before=self.pet.pos()
        self.pet.snap_preview.surfaces=[];self.pet.snap_preview.surfaces_at=time.monotonic()
        with patch('edge_attachment.inspect_foreground',return_value=None):
            self.edge.tick()
        self.assertFalse(self.edge.active)
        physics=self.pet.state.physics
        self.assertTrue(physics.active)
        self.assertEqual((physics.x,physics.y),(float(before.x()),float(before.y())))
        self.assertEqual((physics.vx,physics.vy),(0.,0.))
        self.assertIsNone(self.pet.state.action_player.action)

    def test_live_window_missing_from_top_list_keeps_following_without_dropping(self):
        self.attach_left()
        self.pet.snap_preview.surfaces=[];self.pet.snap_preview.surfaces_at=time.monotonic()
        with patch('edge_attachment.inspect_foreground',return_value=self.surface),patch('edge_attachment.logical_surface',return_value=(self.surface.rect,self.surface.work_area,QApplication.primaryScreen())):
            self.edge.tick()
        self.assertTrue(self.edge.active)
        self.assertFalse(self.pet.state.physics.active)

    def test_generated_pose_top_contact_stays_at_icon_surface(self):
        options={**ICON_DEFAULTS,'direction':'sit-front'}
        side,(x,y)=placement((400,300,50,50),(180,190),'sit-front',options,(0,0,1280,900),self.poses.bounds)
        self.assertEqual(side,'sit-front')
        self.assertAlmostEqual(y+190*(.10+.88*GEOMETRIES[side].contact[1]),300,delta=.51)

    def test_generated_animation_changes_locally_and_blinks(self):
        for side in GEOMETRIES:
            first=self.poses.pose_pixmap(side,0).toImage()
            second=self.poses.pose_pixmap(side,1.8).toImage()
            blink=self.poses.pose_pixmap(side,3.25).toImage()
            self.assertFalse(first.isNull());self.assertNotEqual(first,second);self.assertNotEqual(second,blink)
            # All reference contact points stay fixed in the geometry layer.
            self.assertEqual(first.size(),second.size())

    def test_auto_window_variants_include_sitting_and_prone(self):
        sides=set()
        for variant in range(4):
            side,_,kind=edge_placement(self.surface.rect,self.surface.work_area,(180,190),self.poses.bounds,variant=variant)
            self.assertEqual(kind,'top');sides.add(side)
        self.assertEqual(sides,{'sit-front','sit-back','prone-front','prone-back'})

    def test_monitor_specific_dpi_conversion(self):
        class Geo:
            def x(self):return -1920
            def y(self):return 0
        class Screen:
            def geometry(self):return Geo()
            def devicePixelRatio(self):return 1.5
        surface=WindowSurface(1,2,(-1800,150,900,600),(-1920,0,1920,1080),(-1920,0,1920,1020),False,False)
        rect,area,_=logical_surface(surface,[Screen()])
        self.assertEqual(rect,(-1840,100,600,400));self.assertEqual(area,(-1920,0,1280,680))

if __name__=='__main__':unittest.main()
