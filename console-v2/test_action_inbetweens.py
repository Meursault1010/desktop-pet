"""Validate the shipped warps and the real renderer, including interruption."""
import hashlib
import json
import os
from pathlib import Path
import time
import unittest
from concurrent.futures import Future
from unittest.mock import patch

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
from PySide6.QtGui import QImage, QPainter
from PySide6.QtWidgets import QApplication

from action_inbetweens import ROOT, manifest, sample_pose, strip
from action_player import catalog, pose_ref
from pet import PetRenderer, PetState


class InbetweenTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def test_shipped_sources_match_and_accepted_strips_have_exact_endpoints(self):
        data = json.loads((ROOT/'manifest.json').read_text(encoding='utf-8'))
        report = json.loads((ROOT/'quality-report.json').read_text(encoding='utf-8'))
        self.assertGreater(len(data['pairs']), 100)
        assets = ROOT.parent
        for key, digest in data['source_sha256'].items():
            self.assertEqual(hashlib.sha256((assets/catalog()[key]['atlas']).read_bytes()).hexdigest(),digest)
        originals = {}
        for key, entry in data['pairs'].items():
            self.assertTrue(report[key]['accepted'])
            self.assertLess(report[key]['largest_step'], report[key]['original_jump']*.841)
            atlas = QImage(str(ROOT/entry['file']))
            self.assertFalse(atlas.isNull(), key)
            self.assertEqual(atlas.width(), entry['columns']*256)
            for ref, index in zip(key.split('>'), (0, entry['frames']-1)):
                action_id, frame = ref.split(':')
                frame = int(frame)
                original = originals.setdefault(action_id,QImage(str(assets/catalog()[action_id]['atlas'])))
                cell = original.copy(frame%catalog()[action_id]['columns']*256,
                                     frame//catalog()[action_id]['columns']*256,256,256)
                actual = atlas.copy(index%entry['columns']*256,index//entry['columns']*256,256,256)
                fmt = QImage.Format.Format_RGBA8888_Premultiplied
                original_pixels = cell.convertToFormat(fmt)
                actual_pixels = actual.convertToFormat(fmt)
                self.assertEqual(bytes(original_pixels.constBits()),
                                 bytes(actual_pixels.constBits()), key)

    def test_safe_fallback_and_bounded_cache(self):
        self.assertIsNone(sample_pose(('missing',0),('missing',1),.5))
        self.assertIsNone(sample_pose(('read',0),('read',0),.5))
        for key in list(manifest())[:12]:
            strip(manifest()[key]['file'])
            refs = [ref.rsplit(':',1) for ref in key.split('>')]
            a,b = [(name,int(frame)) for name,frame in refs]
            self.assertIsNotNone(sample_pose(a,b,.5))
        self.assertLessEqual(strip.cache_info().currsize, 6)

    def test_pending_decode_never_blocks_render_and_hold_prefetches(self):
        before, after = ('sit-neat',0), ('sit-neat',1)
        future = Future()
        with patch('action_inbetweens.prepare',return_value=future) as prepare:
            self.assertIsNone(sample_pose(before,after,0))
            prepare.assert_called_once()
            self.assertIsNone(sample_pose(before,after,.5))
            self.assertFalse(future.done())

    def test_fractional_sampling_blends_adjacent_subframes(self):
        before, after = ('sit-neat',0), ('sit-neat',1)
        for _ in range(40):
            sample = sample_pose(before, after, .51)
            if sample is not None:
                break
            time.sleep(.02)
        self.assertIsNotNone(sample)
        image, source = sample
        self.assertIsInstance(image, QImage)
        self.assertEqual((source.width(), source.height()),(256,256))
        first, _ = sample_pose(before, after, .5)
        self.assertNotEqual(bytes(image.constBits()), bytes(first.copy(source).toImage().constBits()))

    def test_fractional_sampling_preserves_constant_alpha_and_colour(self):
        from PySide6.QtGui import QColor,QPainter,QPixmap
        atlas_image=QImage(1280,1280,QImage.Format.Format_RGBA8888_Premultiplied)
        atlas_image.fill(0)
        colour=QImage(256,256,QImage.Format.Format_RGBA8888_Premultiplied)
        colour.fill(0)
        painter=QPainter(colour)
        painter.fillRect(colour.rect(),QColor(100,180,240,128))
        painter.end()
        painter=QPainter(atlas_image)
        for index in range(25):
            painter.drawImage(index%5*256,index//5*256,colour)
        painter.end()
        future=Future();future.set_result(atlas_image)
        pixmap=QPixmap.fromImage(atlas_image)
        entry={'file':'constant-test.png','frames':25,'columns':5}
        with patch('action_inbetweens.manifest',return_value={'constant:0>constant:1':entry}),\
             patch('action_inbetweens.prepare',return_value=future),\
             patch('action_inbetweens.strip',return_value=pixmap):
            samples=[sample_pose(('constant',0),('constant',1),p)[0]
                     for p in (.5,.51,.52,.53,.54)]
        samples=[image.toImage() if isinstance(image,QPixmap) else image for image in samples]
        pixels=[(image.pixelColor(128,128).red(),image.pixelColor(128,128).green(),
                 image.pixelColor(128,128).blue(),image.pixelColor(128,128).alpha())
                for image in samples]
        self.assertEqual(len(set(pixels)),1)
        self.assertEqual(pixels[0][3],128)

    def test_real_render_advances_between_authored_poses_and_stops_immediately(self):
        state, renderer = PetState(), PetRenderer()
        state.action_player.play('sit-neat', now=100)
        duration = state.action_player.action['durations'][0]/1000
        images = []
        for t in (100+duration*.4,100+duration*.6,100+duration*.8):
            target = QImage(180,190,QImage.Format.Format_ARGB32_Premultiplied)
            target.fill(0)
            with patch('pet.time.monotonic',return_value=t):
                painter = QPainter(target)
                renderer.draw(painter,state)
                painter.end()
            images.append(bytes(target.constBits()))
        self.assertEqual(len(set(images)),3)
        state.action_player.stop()
        self.assertIsNone(state.action_player.motion_sample(100.1))
        state.physics.launch((0,0),(100,-100))
        self.assertIsNotNone(state.physics.animation_frame())
        self.assertEqual(pose_ref('lazy-roll-toward',14),('prone-rest',2))


if __name__ == '__main__':
    unittest.main()
