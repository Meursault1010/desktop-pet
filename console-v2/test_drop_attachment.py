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
 def test_flight_grabs_each_crossed_window_edge_and_stops_physics(self):
  for kind,delta in [('left',(30,0)),('right',(-30,0)),('top',(0,30)),('bottom',(0,-30))]:
   self.edge.release();self.pet.move(300,300)
   targets=self.edge.flight_targets([self.surface])
   item=next(item for item in targets if item[0].kind==kind)
   px,py=item[0].position;dx,dy=delta
   start=(px-dx,py-dy);end=(px+dx,py+dy)
   self.pet.state.physics.launch(start,(dx*30,dy*30))
   self.assertTrue(self.edge.catch_flight(start,end,[item]),kind)
   self.assertTrue(self.edge.active);self.assertEqual(self.edge.kind,kind)
   self.assertFalse(self.pet.state.physics.active)
   self.assertEqual(self.pet.animator.timer.interval(),16)
   self.assertAlmostEqual(self.pet.x(),px,delta=1)
   self.assertAlmostEqual(self.pet.y(),py,delta=1)
 def test_flight_misses_distant_reverse_and_covered_edges(self):
  targets=self.edge.flight_targets([self.surface])
  item=next(item for item in targets if item[0].kind=='left')
  px,py=item[0].position
  self.pet.state.physics.launch((px+20,py),(-900,0))
  self.assertFalse(self.edge.catch_flight((px+20,py),(px-20,py),[item]))
  self.assertFalse(self.edge.catch_flight((px-80,py),(px-40,py),[item]))
  cover=WindowSurface(1,2,(100,100,600,600),(0,0,800,800),(0,0,800,800),False,False)
  self.assertFalse(any(item[1].handle==self.surface.handle for item in self.edge.flight_targets([cover,self.surface])))
  self.c.set_preference('auto_snap',False)
  self.assertEqual(self.edge.flight_targets([self.surface]),[])
  self.assertFalse(self.edge.catch_flight((px-20,py),(px+20,py),[item]))
 def test_physics_substeps_catch_fast_flight_without_window_rescan(self):
  self.pet.move(300,300)
  targets=self.edge.flight_targets([self.surface])
  item=next(item for item in targets if item[0].kind=='left')
  px,py=item[0].position
  py+=(sum(item[0].interval)/2-item[0].parameter)
  self.pet.state.physics.launch((px-20,py),(1600,0))
  with patch('edge_attachment.visible_surfaces',side_effect=AssertionError('synchronous window scan')):
   self.pet.state.physics.step(.05,(-1000,-1000,2000,2000),lambda a,b:self.edge.catch_flight(a,b,[item]))
  self.assertTrue(self.edge.active);self.assertEqual(self.edge.kind,'left')
 def test_runtime_flight_keeps_grip_position_instead_of_cancelled_physics_origin(self):
  from PySide6.QtCore import QRect
  self.pet.move(300,300)
  targets=self.edge.flight_targets([self.surface])
  item=next(item for item in targets if item[0].kind=='left')
  px,py=item[0].position
  py+=(sum(item[0].interval)/2-item[0].parameter)
  self.pet.state.physics.launch((px-20,py),(1600,0))
  self.pet.snap_preview.surfaces=[self.surface];self.pet.snap_preview.surfaces_at=time.monotonic()
  with patch.object(self.pet.snap_preview,'request_surfaces'),patch.object(self.edge,'flight_targets',return_value=[item]),patch.object(self.pet,'screen_area',return_value=QRect(-1000,-1000,4000,4000)):
   self.pet.advance_physics(.05)
  self.assertTrue(self.edge.active)
  self.assertAlmostEqual(self.pet.x(),px,delta=1)
  self.assertGreater(self.pet.y(),100)
 def test_flight_chooses_first_contact_even_when_targets_are_reversed(self):
  from dataclasses import replace
  from edge_geometry import flight_intersection
  self.pet.move(300,300)
  item=next(item for item in self.edge.flight_targets([self.surface]) if item[0].kind=='left')
  l=item[0];px,py=l.position
  later=replace(l,position=(px+40,py),anchor=(l.anchor[0]+40,l.anchor[1]))
  found=flight_intersection((px-30,py),(px+80,py),(self.pet.width(),self.pet.height()),[(later,*item[1:]),item])
  self.assertEqual(found[0].anchor,l.anchor)
 def test_manually_attached_window_follows_when_autonomous_search_off(self):
  self.edge.options.update(screens=False,enabled=False)
  landing=self.edge.choices([self.surface])[0][0];self.pet.move(*(round(v) for v in landing.position))
  self.edge.on_drop([self.surface],QPoint(*(round(v) for v in landing.anchor)))
  old=self.pet.pos()
  self.pet.snap_preview.surfaces=[self.surface];self.pet.snap_preview.surfaces_at=time.monotonic()
  with patch('edge_attachment.visible_surfaces',return_value=[self.surface]),patch('edge_attachment.logical_surface',return_value=((240,260,400,300),self.surface.work_area,QApplication.primaryScreen())):
   self.edge.tick();self.edge.animate()
  self.assertAlmostEqual(self.pet.x()-old.x(),40,delta=1);self.assertAlmostEqual(self.pet.y()-old.y(),40,delta=1)
  self.pet.snap_preview.surfaces=[];self.pet.snap_preview.surfaces_at=time.monotonic()
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
 def test_release_without_surface_cache_never_scans_or_invents_clear_desktop(self):
  self.pet.move(340,240)
  preview=self.pet.snap_preview;preview.surfaces_at=0
  with patch('drop_attachment.visible_surfaces',side_effect=AssertionError('release blocked on native scan')),patch.object(preview,'request_surfaces') as request:
   self.assertFalse(settle_drop(self.pet,QPoint(420,370),cached_only=True))
   request.assert_called_once()
  self.assertIsNone(self.icons.target)
 def test_release_uses_cache_without_any_native_window_reads(self):
  self.pet.move(300,300)
  item=next(item for item in self.edge.choices([self.surface]) if item[0].kind=='left')
  self.pet.move(*(round(v) for v in item[0].position))
  self.pet.snap_preview.surfaces=[self.surface];self.pet.snap_preview.surfaces_at=time.monotonic()
  with patch('drop_attachment.visible_surfaces',side_effect=AssertionError('sync scan')),patch('edge_attachment.inspect_foreground',side_effect=AssertionError('sync foreground')):
   self.assertTrue(settle_drop(self.pet,QPoint(*(round(v) for v in item[0].anchor)),cached_only=True))
  self.assertEqual(self.edge.kind,'left')
 def test_window_follow_waits_for_background_scan_without_blocking(self):
  self.pet.move(300,300)
  item=next(item for item in self.edge.choices([self.surface]) if item[0].kind=='left')
  self.edge.attach(item)
  preview=self.pet.snap_preview;preview.surfaces_at=0
  with patch('edge_attachment.visible_surfaces',side_effect=AssertionError('sync follow scan')),patch.object(preview,'request_surfaces') as request:
   self.edge.tick();self.assertTrue(self.edge.active)
   request.assert_called_once_with(force=True)
   preview.surfaces=[];preview.surfaces_at=time.monotonic()
   self.edge.tick();self.assertFalse(self.edge.active)
 def test_physics_atlases_survive_action_lru_eviction(self):
  from pet import PetRenderer
  pinned=PetRenderer.interaction_atlases()
  PetRenderer.action_atlas.cache_clear()
  for key in ('read','eat','shy','affection','sit-neat','prone-rest','sleep'):
   PetRenderer.action_atlas(key)
  for key,image in pinned.items():
   self.assertFalse(image.isNull());self.assertIs(PetRenderer.action_atlas(key),image)
 def test_real_release_does_not_probe_scan_or_freeze_the_previous_drag_frame(self):
  self.pet.move(200,200)
  preview=self.pet.snap_preview
  def event(kind,x,y,button,buttons):
   return QMouseEvent(kind,QPointF(45,55),QPointF(x,y),button,buttons,Qt.KeyboardModifier.NoModifier)
  with patch.object(preview,'request_surfaces'),patch.object(preview,'probe',side_effect=AssertionError('release recomputed ghost')),patch('drop_attachment.visible_surfaces',side_effect=AssertionError('sync scan')),patch('edge_attachment.inspect_foreground',side_effect=AssertionError('sync foreground')):
   self.pet.mousePressEvent(event(QMouseEvent.Type.MouseButtonPress,245,255,Qt.MouseButton.LeftButton,Qt.MouseButton.LeftButton))
   self.pet.mouseMoveEvent(event(QMouseEvent.Type.MouseMove,285,275,Qt.MouseButton.NoButton,Qt.MouseButton.LeftButton))
   preview.surfaces_at=0
   self.pet.mouseReleaseEvent(event(QMouseEvent.Type.MouseButtonRelease,285,275,Qt.MouseButton.LeftButton,Qt.MouseButton.NoButton))
  self.assertIsNone(self.pet.drag_origin);self.assertIsNone(self.pet.state.drag_feedback)
  self.assertIsNone(self.pet.renderer.pointer_hold_image)
  self.assertTrue(self.pet.state.physics.active)
  self.assertEqual(self.pet.animator.timer.interval(),16)
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
  self.assertEqual(self.pet.width(),180)
  self.pet.mouseReleaseEvent(event(QMouseEvent.Type.MouseButtonRelease,(210,220),(265,275),Qt.MouseButton.LeftButton,Qt.MouseButton.NoButton))
  self.assertIsNone(self.pet.state.drag_feedback);self.assertIsNone(self.pet.drag_origin);self.assertEqual(self.pet.width(),180)
  self.assertIsNone(self.pet.state.jump_started)
 def test_preview_scans_surfaces_off_the_gui_thread_and_reuses_drop_cache(self):
  from PySide6.QtCore import QThread
  preview=self.pet.snap_preview;scan_threads=[]
  deadline=time.monotonic()+2
  while preview.surface_scanner is not None and time.monotonic()<deadline:
   self.app.processEvents();time.sleep(.01)
  preview.surfaces_at=0;preview.surfaces=[]
  def scan(*_):
   scan_threads.append(QThread.currentThread())
   time.sleep(.15)
   return [self.surface]
  from PySide6.QtCore import QTimer
  heartbeat=[];timer=QTimer();timer.setInterval(10)
  timer.timeout.connect(lambda:heartbeat.append(time.monotonic()))
  timer.start()
  with patch('snap_preview.visible_surfaces',side_effect=scan):
   preview.queue(QPoint(420,370))
   deadline=time.monotonic()+2
   while preview.surface_scanner is not None and time.monotonic()<deadline:
    self.app.processEvents();time.sleep(.01)
   self.app.processEvents()
  timer.stop()
  self.assertGreaterEqual(len(heartbeat),5,'GUI froze during the slow native scan')
  self.assertEqual(len(scan_threads),1)
  self.assertIsNot(scan_threads[0],self.app.thread())
  self.assertEqual(preview.surfaces,[self.surface])
  self.assertGreater(preview.surfaces_at,0)
  preview.surfaces=[];preview.surfaces_at=time.monotonic()
  self.pet.state.drag_feedback=DragFeedback((90,110))
  with patch('drop_attachment.visible_surfaces',side_effect=AssertionError('unexpected sync scan')):
   self.assertTrue(settle_drop(self.pet,QPoint(420,370)))
  self.assertEqual(self.icons.phase,'sleeping')
 def test_hide_cancels_drag_and_preserves_size(self):
  self.pet.state.drag_feedback=DragFeedback((90,110));self.pet.setFixedSize(420,440);self.pet.drag_origin=QPoint(210,220)
  self.pet.hide();self.assertIsNone(self.pet.state.drag_feedback);self.assertIsNone(self.pet.drag_origin);self.assertEqual(self.pet.width(),180)
 def test_missing_image_can_arrive_without_approach(self):
  self.icons.cache_images={};self.icons.start('drop-icon',instant=True,auto_pose=True)
  self.assertEqual(self.icons.phase,'sleeping')
  image=QImage(40,40,QImage.Format.Format_ARGB32);image.fill('#ffffff')
  self.icons.scanned({'icons':[self.icon],'image':image,'requested_id':'drop-icon','images':{'drop-icon':image}})
  self.assertEqual(self.icons.phase,'sleeping');self.assertIsNotNone(self.icons.image)

 def test_ghost_matches_icon_pose_and_final_landing(self):
  self.pet.state.drag_feedback=DragFeedback((90,110))
  self.pet.setFixedSize(420,440)
  self.pet.move(210,210)
  preview=self.pet.snap_preview
  preview.surfaces=[];preview.surfaces_at=time.monotonic()
  with patch('snap_preview.visible_surfaces',return_value=[]):
   preview.probe(QPoint(420,370))
  self.assertTrue(preview.isVisible())
  self.assertEqual(preview.candidate['icon'],'drop-icon')
  predicted=preview.pos();pose=preview.candidate['pose']
  preview.last_probe=0
  with patch('snap_preview.visible_surfaces',return_value=[]):
   preview.probe(QPoint(420,370))
  self.assertEqual(preview.candidate['pose'],pose)
  self.pet.end_drag_feedback()
  with patch('drop_attachment.visible_surfaces',return_value=[]):
   self.assertTrue(settle_drop(self.pet,QPoint(420,370)))
  self.assertEqual(self.icons.side,pose)
  self.assertEqual(self.pet.pos(),predicted)
  self.assertFalse(preview.isVisible())

 def test_ghost_matches_edge_and_does_not_intercept_input(self):
  self.edge.options['screens']=False
  self.pet.state.drag_feedback=DragFeedback((90,110))
  landing=min(self.edge.choices([self.surface]),key=lambda item:item[0].distance)[0]
  dx,dy=self.pet.state.drag_feedback.body_origin()
  self.pet.move(round(landing.position[0]-(dx-10)),round(landing.position[1]-(dy-25)))
  self.pet.setFixedSize(420,440)
  point=QPoint(*(round(v) for v in landing.anchor))
  preview=self.pet.snap_preview
  preview.surfaces=[self.surface];preview.surfaces_at=time.monotonic()
  with patch('snap_preview.visible_surfaces',return_value=[self.surface]):preview.probe(point)
  self.assertTrue(preview.isVisible())
  predicted=preview.pos()
  self.assertTrue(preview.windowFlags() & Qt.WindowType.WindowTransparentForInput)
  self.pet.end_drag_feedback()
  self.assertTrue(self.edge.on_drop([self.surface],point))
  self.assertEqual(self.pet.pos(),predicted)
  preview.clear()

class DragArtTests(unittest.TestCase):
 @classmethod
 def setUpClass(cls):cls.app=QApplication.instance() or QApplication([])
 def test_short_reaches_are_bounded_and_keep_trying(self):
  for target in ((45,55),(90,40),(135,55),(35,110),(90,160),(145,110),(10,185),(170,185)):
   feedback=DragFeedback(target);hx,hy=feedback.hand
   frames=[]
   for index in (0,4,8):
    point=feedback.vertex(hx,hy,index*math.tau/16)
    ox,oy=feedback.body_origin()
    rest=(ox+hx*.625,oy+hy*.625)
    self.assertLessEqual(math.hypot(point.x()-rest[0],point.y()-rest[1]),7.01)
    if target==(10,185):self.assertGreater(math.hypot(point.x()-210,point.y()-220),25)
    image=feedback.image(index);frames.append(bytes(image.constBits()))
    self.assertGreater(image.pixelColor(round(point.x()),round(point.y())).alpha(),100)
   self.assertGreater(len(set(frames)),1)

 def test_render_never_stretches_or_shears_the_character(self):
  for target in ((10,185),(90,40),(170,185)):
   feedback=DragFeedback(target)
   for index in range(32):
    transform=feedback.sprite_transform(index)
    # Basis lengths are identical and orthogonal: rotation/translation only.
    x=(transform.m11(),transform.m12());y=(transform.m21(),transform.m22())
    self.assertAlmostEqual(math.hypot(*x),1)
    self.assertAlmostEqual(math.hypot(*y),1)
    self.assertAlmostEqual(x[0]*y[0]+x[1]*y[1],0)

 def test_preview_queue_never_scans_inside_mouse_handler(self):
  from pet import DesktopPet
  pet=DesktopPet()
  try:
   with patch('snap_preview.SurfaceScanner.start'),patch('snap_preview.visible_surfaces') as scan:
    for x in range(100):pet.snap_preview.queue(QPoint(x,100))
    scan.assert_not_called()
   self.assertEqual(pet.snap_preview.point,QPoint(99,100))
  finally:
   pet.snap_preview.clear();pet.close();pet.deleteLater()
   self.app.sendPostedEvents(None,0);self.app.processEvents()

if __name__=='__main__':unittest.main()
