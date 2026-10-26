"""Persistent window depth and offscreen-only switches."""
import unittest
from concurrent.futures import Future
from types import SimpleNamespace as NS
from unittest.mock import Mock, patch
from PySide6.QtCore import QRect
from PySide6.QtGui import QRegion
from patrol_depth import PatrolDepth
from pet_mask import WindowMask


class DepthTests(unittest.TestCase):
    def setUp(self):
        self.screen = NS(geometry=lambda:QRect(0,0,1000,800))
        self.position = [100,100]
        self.pet = NS(x=lambda:self.position[0],y=lambda:self.position[1],width=lambda:100,height=lambda:100,
                      screen=lambda:self.screen,preferences=NS(always_on_top=True),
                      setMask=Mock(),clearMask=Mock(),winId=lambda:123)
        self.pet.masker=WindowMask(self.pet)
        self.depth=PatrolDepth(self.pet)
        self.surfaces=[NS(handle=7,rect=(150,80,200,200))]
        def ready(function):
            future=Future();future.set_result(function());return future
        for target,options in (
            ('patrol_depth._surface_scanner.submit',dict(side_effect=ready)),
            ('patrol_depth.QGuiApplication.screens',dict(return_value=[])),
            ('patrol_depth.visible_surfaces',dict(side_effect=lambda **_:self.surfaces)),
            ('patrol_depth.logical_surface',dict(side_effect=lambda s,_:(s.rect,None,self.screen))),
            ('patrol_depth.set_pet_topmost',{}),('patrol_depth.set_pet_behind',{}),
        ):
            item=patch(target,**options);item.start();self.addCleanup(item.stop)

    def switch_back(self):
        self.position[0]=-104
        self.depth.cross_edge(self.screen)
        self.position[0]=100

    def test_switch_refused_while_any_part_is_visible(self):
        for x in (100,-99,999):
            self.position[0]=x
            with self.assertRaises(ValueError):self.depth.cross_edge(self.screen)
        self.assertEqual(self.depth.mode,'front')

    def test_back_clips_overlap_and_never_emerges_on_timer(self):
        self.switch_back();self.depth.update(10)
        self.assertTrue(self.depth.region.contains(QRect(0,0,50,100)))
        self.assertFalse(self.depth.region.contains(QRect(60,0,30,100)))
        self.depth.update(1000)
        self.assertEqual(self.depth.mode,'back')
        self.assertIsNotNone(self.depth.region)

    def test_full_occlusion_uses_minimal_visible_mask(self):
        self.switch_back();self.surfaces[0].rect=(0,0,1000,800)
        self.depth.update(10)
        self.assertTrue(self.depth.region.isEmpty())
        native=self.pet.setMask.call_args.args[0]
        # Full occlusion must not rely on a paint-time clip: one transparent
        # in-window pixel is the smallest mask Qt still honors.
        self.assertEqual(native,QRegion(QRect(0,0,1,1)))

    def test_engaged_tracks_the_back_layer_override(self):
        self.assertFalse(self.depth.engaged)
        self.switch_back()
        self.assertTrue(self.depth.engaged)
        self.depth.release()
        self.assertFalse(self.depth.engaged)

    def test_all_overlapping_windows_clip_back_layer(self):
        self.switch_back()
        self.surfaces.append(NS(handle=8,rect=(80,80,60,200)))
        self.depth.update(10)
        self.assertTrue(self.depth.region.contains(QRect(40,0,10,100)))
        self.assertFalse(self.depth.region.contains(QRect(0,0,30,100)))

    def test_close_window_reveals_desktop_without_changing_depth(self):
        self.switch_back();self.depth.update(10)
        self.surfaces=[];self.depth.update(11)
        self.assertIsNone(self.depth.region)
        self.assertEqual(self.depth.mode,'back')

    def test_second_exit_restores_front_and_stop_restores_preference(self):
        self.pet.preferences.always_on_top=False
        self.switch_back();self.depth.update(10)
        with patch('patrol_depth.set_pet_topmost') as native:
            self.position[0]=1004;self.depth.cross_edge(self.screen)
            self.position[0]=100;self.depth.update(11)
            self.assertEqual(self.depth.mode,'front')
            self.assertIsNone(self.depth.region)
            self.depth.release()
            native.assert_called_with(123,False)

    def test_native_back_uses_lowest_application_as_anchor(self):
        self.switch_back()
        self.surfaces.append(NS(handle=8,rect=(500,80,60,200)))
        with patch('patrol_depth.set_pet_behind') as native:
            self.depth.update(10)
            native.assert_called_once_with(123,8)

    def test_failed_geometry_scan_does_not_toggle_layer(self):
        self.switch_back();self.depth.update(10)
        with patch('patrol_depth.visible_surfaces',side_effect=OSError('unavailable')):
            self.depth.update(11)
        self.assertEqual(self.depth.mode,'back')
        self.assertTrue(self.depth.error)

    def test_unfinished_native_scan_never_blocks_animation_or_queues_more_scans(self):
        pending=Future()
        with patch('patrol_depth._surface_scanner.submit',return_value=pending) as submit:
            self.depth.update(10)
            self.depth.update(11)
            submit.assert_called_once()
            self.assertEqual(self.depth.surfaces,[])
            pending.set_result((self.surfaces,''))
            self.depth.update(11.01)
            self.assertEqual(self.depth.surfaces[0][0],7)

    def test_release_discards_old_scan_result(self):
        pending=Future();pending.set_running_or_notify_cancel()
        with patch('patrol_depth._surface_scanner.submit',return_value=pending):
            self.depth.update(10)
            self.depth.release()
            pending.set_result((self.surfaces,''))
            self.assertIsNone(self.depth.scan)
            self.assertEqual(self.depth.surfaces,[])


if __name__=='__main__':unittest.main()
