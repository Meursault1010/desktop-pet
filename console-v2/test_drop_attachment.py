"""Regression of manual pointer input, immediate landing and disabled state."""
import os
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
import math,tempfile,time,unittest
from pathlib import Path
from unittest.mock import patch
from PySide6.QtCore import QPoint,QPointF,Qt
from PySide6.QtGui import QImage,QMouseEvent
from PySide6.QtWidgets import QApplication
from main import PetApplication
from settings_model import SettingsStore,Preferences
from window_edges import WindowSurface
from drag_feedback import DragFeedback
from drop_attachment import settle_drop

class DropTests(unittest.TestCase):
 @classmethod
 def setUpClass(cls):cls.app=QApplication.instance() or QApplication([]);cls.app.setQuitOnLastWindowClosed(False)
 def setUp(self):
  self.temp=tempfile.TemporaryDirectory();self.path=Path(self.temp.name)/'settings.ini'
  self.c=PetApplication(self.app,SettingsStore(self.path),enable_tray=False,create_console=False)
  self.pet=self.c.pet;self.pet.show();self.pet.animator.timer.stop()
  self.icons=self.c.icon_sleep;self.edge=self.c.edge_attachment;self.icons.load_poses()
  self.c.set_preference('paused',True);self.c.set_preference('quiet',True)
  self.surface=WindowSurface(987,654,(200,220,400,300),(0,0,800,800),(0,0,800,800),False,False)
  self.icon=dict(id='drop-icon',name='图标',rect=dict(x=400,y=350,width=40,height=40))
  self.icons.icons=[self.icon];self.icons.scanned_at=time.monotonic()
  self.icons.cache_images={'drop-icon':QImage(40,40,QImage.Format.Format_ARGB32)};self.icons.cache_images['drop-icon'].fill('#ffffff')
  self.icons.refresh=lambda:None
  self.probes=[patch('edge_attachment.inspect_foreground',return_value=None),patch('edge_attachment.logical_surface',return_value=(self.surface.rect,self.surface.work_area,QApplication.primaryScreen()))]
  for p in self.probes:p.start();self.addCleanup(p.stop)
 def tearDown(self):
  self.c.cleanup();self.pet.deleteLater();self.c.deleteLater();self.app.processEvents();self.temp.cleanup()
 def test_drop_top_sides_and_bottom_is_instant_even_paused(self):
  self.edge.options.update(screens=False,enabled=False)
  choices=self.edge.choices([self.surface])
  for kind in ('top','left','right','bottom'):
   self.edge.release();landing=next(item[0] for item in choices if item[0].kind==kind)
   self.pet.move(*(round(v) for v in landing.position));self.edge.until=time.monotonic()+900
   self.assertTrue(self.edge.on_drop([self.surface],QPoint(*(round(v) for v in landing.anchor))),kind)
   self.assertEqual(self.edge.phase,'resting');self.assertEqual(self.edge.kind,kind)
   self.assertEqual(self.pet.state.gait_until,0);self.assertIsNone(self.pet.state.travel_target)
   self.assertTrue(self.edge.timer.isActive());self.assertTrue(self.edge.animation.isActive())
 def test_manually_attached_window_follows_when_autonomous_search_off(self):
  self.edge.options.update(screens=False,enabled=False)
  landing=self.edge.choices([self.surface])[0][0];self.pet.move(*(round(v) for v in landing.position))
  self.edge.on_drop([self.surface],QPoint(*(round(v) for v in landing.anchor)))
  old=self.pet.pos()
  with patch('edge_attachment.visible_surfaces',return_value=[self.surface]),patch('edge_attachment.logical_surface',return_value=((240,260,400,300),self.surface.work_area,QApplication.primaryScreen())):
   self.edge.tick();self.edge.animate()
  self.assertAlmostEqual(self.pet.x()-old.x(),40,delta=1);self.assertAlmostEqual(self.pet.y()-old.y(),40,delta=1)
  with patch('edge_attachment.visible_surfaces',return_value=[]):self.edge.tick()
  self.assertFalse(self.edge.active)
 def test_icon_drop_chooses_natural_pose_immediately_and_has_priority(self):
  self.pet.move(340,240)
  with patch('drop_attachment.visible_surfaces',return_value=[]),patch('icon_sleep.random.choice',return_value='prone-back'),patch.object(self.edge,'on_drop') as edge:
   self.assertTrue(settle_drop(self.pet,QPoint(420,370)));edge.assert_not_called()
  self.assertEqual(self.icons.phase,'sleeping');self.assertEqual(self.icons.side,'prone-back')
  self.assertIsNotNone(self.icons.image);self.assertEqual(self.pet.state.gait_until,0)
  self.assertEqual((self.pet.x(),self.pet.y()),self.icons.destination)
 def test_covered_or_stale_icon_is_not_selected(self):
  self.pet.move(340,240)
  cover=WindowSurface(1,2,(350,300,180,180),(0,0,800,800),(0,0,800,800),False,False)
  with patch('drop_attachment.visible_surfaces',return_value=[cover]),patch.object(self.edge,'on_drop',return_value=False):
   self.assertFalse(settle_drop(self.pet,QPoint(420,370)))
  self.icons.scanned_at-=5
  with patch('drop_attachment.visible_surfaces',return_value=[]),patch.object(self.edge,'on_drop',return_value=False):
   self.assertFalse(settle_drop(self.pet,QPoint(420,370)))
  self.assertIsNone(self.icons.target)
 def test_disabled_persists_and_blocks_all_drop_targets(self):
  self.c.set_preference('auto_snap',False)
  self.assertFalse(SettingsStore(self.path).load().auto_snap)
  with patch('drop_attachment.visible_surfaces') as probe:
   self.assertFalse(settle_drop(self.pet,QPoint(420,370)));probe.assert_not_called()
  self.assertFalse(self.icons.watch.isActive())
 def test_far_from_edges_does_not_teleport(self):
  self.edge.options.update(screens=False)
  self.pet.move(1000,1100)
  self.assertFalse(self.edge.on_drop([self.surface],QPoint(1090,1190)));self.assertFalse(self.edge.active)
 def test_fullscreen_only_snaps_near_corner(self):
  full=WindowSurface(1,2,(0,0,800,800),(0,0,800,800),(0,0,800,800),True,True)
  with patch('edge_attachment.inspect_foreground',return_value=full):
   self.pet.move(310,250);self.assertFalse(self.edge.on_drop([full],QPoint(400,345)))
   landing=self.edge.choices([full])[0][0];self.pet.move(*(round(v) for v in landing.position))
   self.assertTrue(self.edge.on_drop([full],QPoint(*(round(v) for v in landing.anchor))))
   self.assertEqual(self.edge.kind,'corner')
 def test_fullscreen_uses_surface_when_pet_owns_foreground(self):
  full=WindowSurface(1,2,(0,0,800,800),(0,0,800,800),(0,0,800,800),True,True)
  self.assertEqual(self.edge.choices([full])[0][0].kind,'corner')
 def test_real_mouse_drag_tracks_pointer_and_cleans_up(self):
  self.c.set_preference('auto_snap',False);self.pet.move(200,200)
  def event(kind,local,global_pos,button,buttons):
   return QMouseEvent(kind,QPointF(*local),QPointF(*global_pos),button,buttons,Qt.KeyboardModifier.NoModifier)
  self.pet.mousePressEvent(event(QMouseEvent.Type.MouseButtonPress,(45,55),(245,255),Qt.MouseButton.LeftButton,Qt.MouseButton.LeftButton))
  self.pet.mouseMoveEvent(event(QMouseEvent.Type.MouseMove,(65,75),(265,275),Qt.MouseButton.NoButton,Qt.MouseButton.LeftButton))
  self.assertEqual(self.pet.state.drag_feedback.name,'upper-left')
  self.assertEqual(self.pet.pos()+self.pet.drag_origin,QPoint(265,275))
  self.assertEqual(self.pet.width(),420)
  self.pet.mouseReleaseEvent(event(QMouseEvent.Type.MouseButtonRelease,(210,220),(265,275),Qt.MouseButton.LeftButton,Qt.MouseButton.NoButton))
  self.assertIsNone(self.pet.state.drag_feedback);self.assertIsNone(self.pet.drag_origin);self.assertEqual(self.pet.width(),180)
  self.assertIsNone(self.pet.state.jump_started)
 def test_hide_cancels_drag_and_preserves_size(self):
  self.pet.state.drag_feedback=DragFeedback((90,110));self.pet.setFixedSize(420,440);self.pet.drag_origin=QPoint(210,220)
  self.pet.hide();self.assertIsNone(self.pet.state.drag_feedback);self.assertIsNone(self.pet.drag_origin);self.assertEqual(self.pet.width(),180)
 def test_missing_image_can_arrive_without_approach(self):
  self.icons.cache_images={};self.icons.start('drop-icon',instant=True,auto_pose=True)
  self.assertEqual(self.icons.phase,'sleeping')
  image=QImage(40,40,QImage.Format.Format_ARGB32);image.fill('#ffffff')
  self.icons.scanned({'icons':[self.icon],'image':image,'requested_id':'drop-icon','images':{'drop-icon':image}})
  self.assertEqual(self.icons.phase,'sleeping');self.assertIsNotNone(self.icons.image)

class DragArtTests(unittest.TestCase):
 @classmethod
 def setUpClass(cls):cls.app=QApplication.instance() or QApplication([])
 def test_palms_cover_exact_grab_point_and_body_keeps_moving(self):
  for target in ((45,55),(90,40),(135,55),(35,110),(90,160),(145,110),(10,185),(170,185)):
   feedback=DragFeedback(target);hx,hy=feedback.hand
   frames=[]
   for index in (0,4,8):
    point=feedback.vertex(hx,hy,index*math.tau/16)
    self.assertAlmostEqual(point.x(),210);self.assertAlmostEqual(point.y(),220)
    image=feedback.image(index);frames.append(bytes(image.constBits()))
    self.assertGreater(max(image.pixelColor(x,y).alpha() for x in range(206,215) for y in range(216,225)),150)
   self.assertGreater(len(set(frames)),1)

if __name__=='__main__':unittest.main()
