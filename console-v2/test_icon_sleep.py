"""Isolated interaction tests: never move a real desktop icon or use user settings."""
import os
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch
from PySide6.QtCore import QRect, QPoint
from PySide6.QtGui import QImage, QPainter, QRegion
from PySide6.QtWidgets import QApplication
from main import PetApplication
from settings_model import SettingsStore
from icon_sleep import DEFAULTS, validated, placement, body_bounds, pose_bounds, alpha_region, skirt_region


class PlacementTests(unittest.TestCase):
    def test_validation_rejects_unknown_nonfinite_bool_and_bad_direction(self):
        for value in ({'offset_x':True},{'breath':float('nan')},{'duration':121},{'direction':'elsewhere'},{'auto_snap':'true'},{'injected':True}):
            with self.assertRaises(ValueError): validated(value)
        self.assertEqual(validated({}),DEFAULTS)

    def test_placement_directions_and_offsets(self):
        positions={}
        for side in ('left','back','right'):
            direction,position=placement((400,300,50,50),(180,190),side,DEFAULTS,(0,0,1000,800))
            self.assertEqual(side,direction);positions[side]=position
        self.assertLess(positions['back'][0],positions['right'][0])
        self.assertLess(positions['left'][0],positions['right'][0])
        self.assertLess(positions['back'][0],positions['right'][0])
        _,shifted=placement((400,300,50,50),(180,190),'left',{**DEFAULTS,'offset_x':12,'offset_y':-9},(0,0,1000,800))
        self.assertEqual(shifted,(positions['left'][0]+12,positions['left'][1]-9))

    def test_edges_switch_pose_and_minimally_adjust_instead_of_rejecting(self):
        side,position=placement((0,0,50,50),(180,190),'left',DEFAULTS,(0,0,1000,800))
        self.assertEqual(side,'right')
        self.assertGreaterEqual(position[1]+body_bounds((180,190),(0,0,1,1))[1],0)
        side,_=placement((50,300,50,50),(180,190),'auto',DEFAULTS,(0,0,1000,800))
        self.assertEqual(side,'right')

    def test_all_corners_manual_directions_and_negative_monitor_origin(self):
        size=(196,207); area=(-1280,-200,1280,900)
        bounds={s:(.15,.05,.85,.94) for s in ('left','back','right')}
        for x,y in ((-1280,-200),(-30,-200),(-1280,650),(-30,650)):
            for preferred in ('auto','left','back','right'):
                side,(px,py)=placement((x,y,30,30),size,preferred,DEFAULTS,area,bounds)
                l,t,r,b=body_bounds(size,bounds[side])
                self.assertGreaterEqual(px+l,area[0]); self.assertGreaterEqual(py+t,area[1])
                self.assertLessEqual(px+r,area[0]+area[2]); self.assertLessEqual(py+b,area[1]+area[3])

    def test_transparent_margins_are_allowed_outside_screen(self):
        bounds={s:(.3,.3,.7,.7) for s in ('left','back','right')}
        _,(x,y)=placement((0,0,30,30),(180,190),'auto',DEFAULTS,(0,0,1000,800),bounds)
        self.assertLess(x,0); self.assertLess(y,0)
        with self.assertRaises(ValueError):
            placement((0,0,30,30),(180,190),'auto',DEFAULTS,(0,0,20,20),bounds)

    def test_faint_icon_edges_remain_protected(self):
        image=QImage(4,4,QImage.Format.Format_ARGB32);image.fill(0)
        image.setPixel(1,1,0x01000000)
        self.assertTrue(alpha_region(image).contains(QPoint(1,1)))
        self.assertFalse(alpha_region(image).contains(QPoint(0,0)))

    def test_front_pose_is_explicit_only(self):
        side,_=placement((400,300,50,50),(180,190),'front',DEFAULTS,(0,0,1000,800))
        self.assertEqual(side,'front')
        side,_=placement((400,300,50,50),(180,190),'auto',DEFAULTS,(0,0,1000,800))
        self.assertNotEqual(side,'front')


class SleepInteractionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app=QApplication.instance() or QApplication([])
        cls.app.setQuitOnLastWindowClosed(False)

    def setUp(self):
        self.directory=tempfile.TemporaryDirectory(prefix='xiaoju-sleep-')
        self.controller=PetApplication(self.app,SettingsStore(Path(self.directory.name)/'settings.ini'),enable_tray=False,create_console=False)
        self.controller.pet.show(); self.app.processEvents(); self.controller.pet.animator.timer.stop()
        self.sleep=self.controller.icon_sleep
        self.screen=QApplication.primaryScreen()
        self.icon=dict(id='test-icon',name='测试文件夹',folder=True,rect=dict(x=400,y=300,width=50,height=50))
        self.sleep.icons=[self.icon]
        self.scan=patch.object(self.sleep,'refresh');self.scan.start();self.addCleanup(self.scan.stop)
        self.coords=patch('icon_sleep.logical_rect',return_value=((400,300,50,50),self.screen));self.coords.start();self.addCleanup(self.coords.stop)

    def tearDown(self):
        self.controller.cleanup();self.controller.pet.deleteLater();self.controller.deleteLater();self.app.processEvents();self.directory.cleanup()

    def start(self):
        self.sleep.start('test-icon')
        for _ in range(400):
            self.sleep.last_tick-=.1;self.sleep.tick()
            if self.sleep.phase=='sleeping':break
        self.assertEqual(self.sleep.phase,'sleeping')
        self.sleep.image=QImage(50,50,QImage.Format.Format_ARGB32_Premultiplied);self.sleep.image.fill(0)
        self.sleep.image.setPixelColor(25,25,'#ffffff')
        self.sleep.exposed=True

    def test_start_sleep_wake_and_original_preferences_unchanged(self):
        preferences=self.controller.preferences
        self.start()
        self.assertFalse(self.controller.pet.movement_allowed())
        self.assertIn('测试文件夹',self.controller.pet.status_text())
        self.sleep.wake()
        self.assertEqual(self.sleep.phase,'idle'); self.assertTrue(self.controller.pet.mask().isEmpty())
        self.assertEqual(self.controller.preferences,preferences)

    def test_target_deleted_or_moved_wakes(self):
        self.start();self.sleep.scanned({'icons':[],'image':None,'exposed':True})
        self.assertIsNone(self.sleep.target)
        self.sleep.icons=[self.icon]
        self.start();moved={**self.icon,'rect':{**self.icon['rect'],'x':420}}
        self.sleep.scanned({'icons':[moved],'image':None,'exposed':True})
        self.assertIsNone(self.sleep.target)

    def test_config_persists_and_invalid_values_do_not_mutate(self):
        self.sleep.configure({'breath':72,'offset_x':10,'direction':'right'})
        self.assertEqual(self.controller.store.settings.value('icon_sleep/breath'),72)
        with self.assertRaises(ValueError): self.sleep.configure({'breath':999})
        self.assertEqual(self.sleep.options['breath'],72)

    def test_sleep_has_continuous_breath_and_never_blanket_hides(self):
        self.start()
        def render():
            image=QImage(self.controller.pet.size(),QImage.Format.Format_ARGB32_Premultiplied);image.fill(0)
            painter=QPainter(image);self.sleep.paint(painter);painter.end();return image
        with patch('icon_sleep.time.monotonic',return_value=self.sleep.started+1): first=render()
        with patch('icon_sleep.time.monotonic',return_value=self.sleep.started+3): second=render()
        self.assertNotEqual(bytes(first.constBits()),bytes(second.constBits()))
        self.sleep.exposed=False
        self.assertTrue(any(bytes(render().constBits())[3::4]))
        self.sleep.image=None
        self.assertTrue(any(bytes(render().constBits())[3::4]))

    def test_approach_is_visible_before_icon_scan_finishes(self):
        self.sleep.start('test-icon')
        image=QImage(self.controller.pet.size(),QImage.Format.Format_ARGB32_Premultiplied);image.fill(0)
        painter=QPainter(image)
        self.assertFalse(self.sleep.paint(painter))
        painter.end()

    def render_sleep(self):
        image=QImage(self.controller.pet.size(),QImage.Format.Format_ARGB32_Premultiplied);image.fill(0)
        painter=QPainter(image)
        painted=self.sleep.paint(painter)
        painter.end()
        return painted,image

    @staticmethod
    def opaque_pixels(image):
        return sum(1 for alpha in bytes(image.constBits())[3::4] if alpha)

    def test_paint_ignores_the_shared_window_mask(self):
        self.start()
        with patch('icon_sleep.time.monotonic',return_value=self.sleep.started+1):
            painted,owned=self.render_sleep()
            self.assertTrue(painted)
            expected=self.opaque_pixels(owned)
            self.assertGreater(expected,1000)
            # Another feature may release or replace the shared native mask
            # between two animation ticks. Painting must never depend on it.
            self.controller.pet.masker.clear_all()
            painted,released=self.render_sleep()
            self.assertTrue(painted)
            self.assertEqual(self.opaque_pixels(released),expected)
            self.controller.pet.masker.set('depth',QRegion(0,0,10,10))
            painted,foreign=self.render_sleep()
            self.assertTrue(painted)
            self.assertEqual(self.opaque_pixels(foreign),expected)

    def test_foreign_mask_does_not_crop_the_sleep_pose(self):
        self.start()
        self.sleep.update_mask()
        own=self.controller.pet.mask()
        self.controller.pet.masker.set('peek',QRegion(0,0,12,12))
        combined=self.controller.pet.mask()
        self.assertEqual(combined,own.intersected(QRegion(0,0,12,12)))
        self.controller.pet.masker.clear('peek')
        self.assertEqual(self.controller.pet.mask(),own)

    def test_scanned_window_overlap_does_not_enable_invisible_passthrough(self):
        self.start()
        with patch('icon_sleep.set_input_passthrough') as passthrough:
            self.sleep.scanned({'icons':[self.icon], 'image':self.sleep.image,
                                'exposed':False, 'requested_id':'test-icon'})
            passthrough.assert_not_called()
        self.assertIsNotNone(self.sleep.target)

    def test_dense_icon_group_is_available(self):
        self.sleep.icons=[{**self.icon,'id':str(i)} for i in range(20)]
        self.sleep.mark_available()
        self.assertTrue(all(i['available'] for i in self.sleep.icons))

    def test_only_target_intersecting_skirt_is_cut_in_every_pose(self):
        self.start()
        self.sleep.image.fill('#ffffff')
        for side in ('left','right','back','front'):
            self.sleep.configure({'direction':side})
            self.sleep.skirts[side]=QRegion(0,0,256,256)
            self.sleep.update_mask()
            x,y=round(400-self.controller.pet.x()),round(300-self.controller.pet.y())
            self.assertFalse(self.controller.pet.mask().contains(QPoint(x+20,y+20)))
            self.sleep.skirts[side]=QRegion()
            self.sleep.update_mask()
            self.assertTrue(self.controller.pet.mask().contains(QPoint(x+20,y+20)))

    def test_nearby_icon_and_all_labels_do_not_cut_pet(self):
        self.start()
        neighbor={**self.icon,'id':'neighbor',
                  'rect':dict(x=self.controller.pet.x()+25,y=self.controller.pet.y()+90,width=20,height=20),
                  'label_rect':dict(x=self.controller.pet.x()+20,y=self.controller.pet.y()+110,width=35,height=15)}
        self.sleep.icons.append(neighbor)
        def coords(rect):
            return (rect['x'],rect['y'],rect['width'],rect['height']),self.screen
        with patch('icon_sleep.logical_rect',side_effect=coords):
            self.sleep.update_mask()
        self.assertTrue(self.controller.pet.mask().contains(QPoint(30,95)))
        self.assertTrue(self.controller.pet.mask().contains(QPoint(30,115)))

    def test_blue_skirt_matte_does_not_include_white_hair(self):
        image=QImage(256,256,QImage.Format.Format_ARGB32);image.fill(0)
        image.setPixelColor(40,180,'#eef4ff')  # long hair below the waist
        image.setPixelColor(80,180,'#238cdb')  # skirt
        image.setPixelColor(80,60,'#238cdb')   # blue hairclip above waist
        matte=skirt_region(image)
        self.assertFalse(matte.contains(QPoint(40,180)))
        self.assertTrue(matte.contains(QPoint(80,180)))
        self.assertFalse(matte.contains(QPoint(80,60)))

    def test_real_pose_mattes_have_skirt_but_no_bright_hair(self):
        self.sleep.load_poses()
        for side,pixmap in self.sleep.pixmaps.items():
            matte=self.sleep.skirts[side]
            self.assertFalse(matte.isEmpty())
            image=pixmap.toImage()
            for y in range(0,256,3):
                for x in range(0,256,3):
                    color=image.pixelColor(x,y)
                    if color.alpha()>200 and color.red()>210 and color.green()>210:
                        self.assertFalse(matte.contains(QPoint(x,y)),(side,x,y))

    def test_contact_is_at_shoulder_height_not_feet(self):
        self.sleep.configure({'direction':'left'})
        self.start()
        contact_y=325-self.sleep.destination[1]
        self.assertLess(contact_y,self.controller.pet.height()*.65)
        self.assertGreater(contact_y,self.controller.pet.height()*.4)

    def test_real_pose_envelopes_fit_at_screen_edges(self):
        self.sleep.load_poses()
        for side,pixmap in self.sleep.pixmaps.items():
            self.assertEqual(self.sleep.bounds[side],pose_bounds(pixmap.toImage()))
        area=(0,0,800,600); size=(196,207)
        for x,y in ((0,0),(770,0),(0,570),(770,570),(400,300)):
            side,(px,py)=placement((x,y,30,30),size,'left',DEFAULTS,area,self.sleep.bounds)
            l,t,r,b=body_bounds(size,self.sleep.bounds[side])
            self.assertGreaterEqual(px+l,0);self.assertGreaterEqual(py+t,0)
            self.assertLessEqual(px+r,800);self.assertLessEqual(py+b,600)

    def test_manual_jump_and_hide_cancel_sleep(self):
        self.start();self.controller.pet.animator.jump();self.assertIsNone(self.sleep.target)
        self.start();self.controller.pet.hide();self.assertIsNone(self.sleep.target)

    def test_duration_and_reject_unknown_or_hidden_target(self):
        with self.assertRaises(ValueError):self.sleep.start('../bad')
        self.start();self.sleep.configure({'duration':1});self.sleep.started-=61;self.sleep.tick();self.assertIsNone(self.sleep.target)
        self.controller.pet.hide()
        with self.assertRaises(ValueError):self.sleep.start('test-icon')


if __name__=='__main__': unittest.main()
