"""Spatial dance must move the live window continuously and yield to interaction."""
import os
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
import json
import time
import unittest
from pathlib import Path
from dataclasses import replace
from PySide6.QtWidgets import QApplication
from action_player import catalog
from dance_stage import footwork,stage_position,route_fits
from music_timing import follow_tempo


class RouteTests(unittest.TestCase):
    def test_every_dance_frame_has_the_same_visible_height_and_baseline(self):
        from PIL import Image
        folder=Path(__file__).resolve().parent/'assets/actions/music-waltz'
        report=json.loads((folder/'choreography.json').read_text())
        with Image.open(folder/'atlas.png') as atlas:
            for index in range(report['frames']):
                x=index%report['columns']*256;y=index//report['columns']*256
                cell=atlas.crop((x,y,x+256,y+256))
                bbox=cell.getchannel('A').point(lambda a:255 if a>24 else 0).getbbox()
                self.assertEqual((bbox[1],bbox[3]),(20,233),f'frame {index}')
        # Both directions use the repaired skin; a dark desktop must not show
        # through the palm or forearm again.
        with Image.open(folder/'atlas.png') as atlas:
            for row in footwork()['rows']:
                source=report['frame_checks'][row['source_frame']]['source']
                points={'mixed-pose-19.png':[(59,86)],
                        'keyed-turn-03.png':[(72,94),(76,104),(80,111)]}.get(source,[])
                for px,py in points:
                    index=row['frame']
                    rgba=atlas.getpixel((index%report['columns']*256+px,index//report['columns']*256+py))
                    self.assertGreater(rgba[3],240,(index,px,py,rgba))
                    self.assertGreater(min(rgba[:3]),180,(index,px,py,rgba))

    def test_every_frame_is_an_unwarped_source_drawing(self):
        import hashlib
        from PIL import Image
        from build_dance_25d import ROOT,BRIDGES,SOURCE,clean_cell
        from dance_artwork_repair import repair_cell
        import numpy as np
        folder=ROOT/'assets/actions/music-waltz'
        report=json.loads((folder/'choreography.json').read_text())
        track=footwork()
        self.assertIs(report['optical_flow'],False)
        self.assertEqual(report['interpolation'],'none')
        self.assertIs(report['silhouette_morph'],False)
        expected=[]
        for check in report['frame_checks']:
            source=SOURCE/'consistent-keys'/check['source']
            if not source.exists():source=BRIDGES/check['source']
            with Image.open(source) as image:
                expected.append(repair_cell(clean_cell(np.array(image.convert('RGBA'))), check['source']).tobytes())
            self.assertEqual(hashlib.sha256(expected[-1]).hexdigest(),check['cell_sha256'])
        with Image.open(folder/'atlas.png') as atlas:
            for row in track['rows']:
                index=row['frame'];x=index%report['columns']*256;y=index//report['columns']*256
                self.assertEqual(atlas.crop((x,y,x+256,y+256)).tobytes(),expected[row['source_frame']])

    def test_planted_foot_locks_x_while_the_window_bobs(self):
        data=footwork();rows=data['rows'];scale=data['cell_scale']
        for a,b in zip(rows,rows[1:]):
            if a['support']==b['support']:
                # The sole may not slide sideways. Height is carried by the
                # window instead, so the vertical lock is deliberately released.
                self.assertAlmostEqual(a['root'][0]+a['contact'][0]*scale,
                                       b['root'][0]+b['contact'][0]*scale)
                self.assertLess(abs(a['root'][1]-b['root'][1]),3.)
            else:
                self.assertEqual(a['root'][0],b['root'][0])
        ys=[r['root'][1] for r in rows]
        self.assertLessEqual(max(abs(v) for v in ys),3.5)
        self.assertTrue(3.<=max(ys)-min(ys)<=5.,max(ys)-min(ys))
        self.assertEqual((data['bounds'][0][1],data['bounds'][1][1]),(min(ys),max(ys)))
        self.assertEqual(stage_position((200,300),(180,190),0),
                         (200.+rows[0]['root'][0],300.+rows[0]['root'][1],1.))

    def test_bounds_admit_whole_route_or_decline_without_clamping(self):
        self.assertTrue(route_fits((200,300),(0,0,1000,800),(180,190)))
        self.assertFalse(route_fits((0,300),(0,0,1000,800),(180,190)))
        for row in footwork()['rows']:
            self.assertEqual(stage_position((200,300),(180,190),row['frame'])[2],1.)

    def test_contact_is_on_visible_sole_and_page_matches_track(self):
        from PIL import Image
        root=Path(__file__).resolve().parent/'assets/actions/music-waltz'
        manifest=json.loads((root/'pages.json').read_text())
        action=catalog()['music-waltz'];rows=footwork()['rows']
        self.assertEqual(len(rows),action['frames'])
        self.assertEqual(sum(p['count'] for p in manifest['pages']),len(rows))
        # Independently inspect rendered source pixels around support transfers,
        # page boundaries and both loop seams, rather than only testing algebra.
        selected={0,len(rows)-1,footwork()['source_frames']-1}
        selected.update(p['first'] for p in manifest['pages'])
        selected.update(i for i in range(1,len(rows)) if rows[i]['support']!=rows[i-1]['support'])
        for index in sorted(selected):
            page=manifest['pages'][index//manifest['per_page']]
            with Image.open(root/page['file']) as image:
                local=index-page['first'];col=manifest['columns']
                cell=image.crop((local%col*256,local//col*256,local%col*256+256,local//col*256+256))
                x,y=rows[index]['contact'];x=round(x);y=round(y)
                self.assertGreater(max(cell.getpixel((xx,yy))[3]
                    for xx in range(max(0,x-2),min(256,x+3))
                    for yy in range(max(0,y-2),y+1)),128)
                opaque=cell.getchannel('A').point(lambda a:255 if a>128 else 0).getbbox()
                self.assertLessEqual(abs(opaque[3]-1-y),2)

    def test_all_original_poses_used_and_loop_asset_matches_metadata(self):
        root=Path(__file__).resolve().parent/'assets/actions/music-waltz'
        report=json.loads((root/'choreography.json').read_text())
        self.assertEqual(report['originals_used'],52)
        self.assertEqual(len(report['order']),len(set(report['order'])))
        self.assertEqual(report['used_count'],footwork()['source_frames'])
        self.assertLess(report['after']['maximum'],report['before']['maximum']*.7)
        self.assertTrue(report['loop_closed'])
        action=catalog()['music-waltz']
        self.assertEqual(action['frames'],report['frames'])
        self.assertEqual(sum(action['durations']),round(report['duration_seconds']*1000))


class LiveStageTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app=QApplication.instance() or QApplication([])
        cls.app.setQuitOnLastWindowClosed(False)

    def setUp(self):
        from pet import DesktopPet
        from settings_model import Preferences
        self.pet=DesktopPet(replace(Preferences(),random_movement=False,auto_snap=False))
        from PySide6.QtCore import QRect
        self.pet.screen_area=lambda:QRect(0,0,1000,800)
        self.pet.move(200,300);self.pet.show();self.pet.animator.timer.stop()
        self.now=time.monotonic()
        self.pet.state.action_player.play('music-waltz',now=self.now,loop=True)

    def tearDown(self):
        self.pet.close();self.pet.deleteLater();self.app.processEvents()

    def test_manual_dance_moves_real_window_and_cancel_keeps_position(self):
        stage=self.pet.dance_stage
        home=self.pet.pos()
        stage.advance(self.now)
        self.assertEqual(self.pet.pos(),home)
        from music_dance_asset import preload,metadata
        idx=self.pet.state.action_player.frame(self.now+3)
        preload(idx//metadata()['per_page']).result(timeout=20)
        stage.advance(self.now+3)
        self.assertNotEqual(self.pet.pos(),home)
        current=self.pet.pos()
        self.pet.state.action_player.stop()
        self.assertFalse(stage.advance(self.now+3.1))
        self.assertEqual(self.pet.pos(),current)
        self.assertEqual(self.pet.state.dance_depth_scale,1)

    def test_no_space_declines_dance_without_teleport_or_clamp(self):
        self.pet.move(0,300);before=self.pet.pos()
        self.assertFalse(self.pet.dance_stage.advance(self.now))
        self.assertEqual(self.pet.pos(),before)
        self.assertIsNone(self.pet.state.action_player.action)

    def test_tempo_changes_preserve_route_and_drag_interrupts(self):
        stage=self.pet.dance_stage;player=self.pet.state.action_player
        stage.advance(self.now)
        from music_dance_asset import preload,metadata
        idx=player.frame(self.now+3)
        preload(idx//metadata()['per_page']).result(timeout=20)
        stage.advance(self.now+3)
        before=self.pet.pos()
        follow_tempo(player,144,self.now+3,.1)
        stage.advance(self.now+3)
        self.assertEqual(self.pet.pos(),before)
        self.pet.drag_origin=object()
        self.assertFalse(stage.advance(self.now+3.1))
        self.assertEqual(self.pet.pos(),before)
        self.pet.drag_origin=None

    def test_depth_scales_about_feet_and_render_does_not_clip(self):
        from PySide6.QtGui import QImage,QPainter
        from unittest.mock import patch
        stage=self.pet.dance_stage
        stage.advance(self.now)
        duration=sum(self.pet.state.action_player.action['durations'])/1000
        now=self.now+duration/2;stage.advance(now)
        from music_dance_asset import preload,metadata
        index=self.pet.state.action_player.frame(now)
        preload(index//metadata()['per_page']).result(timeout=20)
        self.assertEqual(self.pet.state.dance_depth_scale,1.)
        image=QImage(180,190,QImage.Format.Format_RGBA8888);image.fill(0)
        painter=QPainter(image)
        with patch('pet.time.monotonic',return_value=now):
            self.pet.renderer.draw_pose(painter,self.pet.state)
        painter.end()
        self.assertTrue(any(image.pixelColor(x,y).alpha()>128 for y in range(30,182,8) for x in range(10,171,8)))
        self.assertFalse(any(image.pixelColor(x,y).alpha()>16 for x in range(180) for y in (0,189)))

    def test_tempo_following_does_not_restart_renderer_handoff(self):
        from PySide6.QtGui import QImage,QPainter
        from unittest.mock import patch
        from music_dance_asset import preload
        preload().result(timeout=20)
        player=self.pet.state.action_player
        def render(now):
            image=QImage(180,190,QImage.Format.Format_RGBA8888);image.fill(0)
            painter=QPainter(image)
            with patch('pet.time.monotonic',return_value=now):self.pet.renderer.draw(painter,self.pet.state)
            painter.end()
        render(self.now+.1)
        # Native-resolution buffer keeps detail without changing logical size.
        buffer=self.pet.renderer.last_display_image
        self.assertEqual((buffer.width(),buffer.height()),(360,380))
        self.assertEqual((buffer.deviceIndependentSize().width(),
                          buffer.deviceIndependentSize().height()),(180.,190.))
        before=self.pet.renderer.last_pose
        follow_tempo(player,144,self.now+.2,.1)
        render(self.now+.2)
        self.assertEqual(self.pet.renderer.last_pose,before)
        self.assertIsNone(self.pet.renderer.transition_image)
