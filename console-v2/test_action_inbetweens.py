"""Validate shipped warps, worker preparation, and the real renderer."""
import hashlib
import json
import os
from pathlib import Path
import time
import unittest
from concurrent.futures import Future
from unittest.mock import patch

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
from PySide6.QtGui import QColor, QImage, QPainter
from PySide6.QtWidgets import QApplication

import action_inbetweens as inbetweens
from action_inbetweens import (FRAME_SIZE, MAX_PREPARED_PAIRS, ROOT, _pending,
                               _prepared, frames, manifest, pair_key, prepare,
                               sample_pose)
from action_player import catalog, pose_ref
from pet import PetRenderer, PetState


class InbetweenTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        _prepared.clear()
        _pending.clear()

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

    def test_new_idle_vignettes_ship_every_transition(self):
        data = json.loads((ROOT/'manifest.json').read_text(encoding='utf-8'))
        assets = ROOT.parent
        for key in ('snow-catch', 'hum', 'hair-tuck', 'sneeze', 'gaze-far', 'listen',
                    'warm-hands', 'curtsy', 'wave', 'star-wish'):
            for index in range(5):
                self.assertIn(pair_key((key, index), (key, index+1)), data['pairs'])
            self.assertIn(pair_key((key, 5), (key, 0)), data['pairs'])
            self.assertEqual(data['source_sha256'][key],
                             hashlib.sha256((assets/catalog()[key]['atlas']).read_bytes()).hexdigest())

    def test_safe_fallback_and_bounded_cache(self):
        self.assertIsNone(sample_pose(('missing',0),('missing',1),.5))
        self.assertIsNone(sample_pose(('read',0),('read',0),.5))
        for key in list(manifest())[:MAX_PREPARED_PAIRS+2]:
            entry = manifest()[key]
            prepare(entry).result()
            decoded = frames(entry)
            self.assertIsNotNone(decoded)
            self.assertEqual(len(decoded), entry['frames'])
            self.assertEqual((decoded[0].width(), decoded[0].height()),
                             (FRAME_SIZE, FRAME_SIZE))
        self.assertLessEqual(len(_prepared), MAX_PREPARED_PAIRS)

    def test_pending_decode_never_blocks_render_and_holds_are_cheap(self):
        before, after = ('sit-neat',0), ('sit-neat',1)
        future = Future()
        with patch('action_inbetweens.prepare',return_value=future) as prepare:
            self.assertIsNone(sample_pose(before,after,0))
            prepare.assert_not_called()
            self.assertIsNone(sample_pose(before,after,.5))
            prepare.assert_called_once()
            self.assertFalse(future.done())

    def test_nearest_sampling_returns_display_ready_frames(self):
        before, after = ('sit-neat',0), ('sit-neat',1)
        for _ in range(40):
            sample = sample_pose(before, after, .51)
            if sample is not None:
                break
            time.sleep(.02)
        self.assertIsNotNone(sample)
        image, source = sample
        self.assertIsInstance(image, QImage)
        self.assertEqual((image.width(), image.height()),(FRAME_SIZE,FRAME_SIZE))
        self.assertEqual((source.width(), source.height()),(FRAME_SIZE,FRAME_SIZE))
        first = sample_pose(before, after, .02)[0]
        last = sample_pose(before, after, .98)[0]
        self.assertNotEqual(bytes(first.constBits()), bytes(last.constBits()))

    def test_nearest_sampling_preserves_constant_alpha_and_colour(self):
        colour = QImage(FRAME_SIZE, FRAME_SIZE,
                        QImage.Format.Format_RGBA8888_Premultiplied)
        colour.fill(0)
        painter = QPainter(colour)
        painter.fillRect(colour.rect(), QColor(100,180,240,128))
        painter.end()
        future = Future()
        future.set_result((colour,)*25)
        entry = {'file':'constant-test.png','frames':25,'columns':5}
        key = 'sit-neat:0>sit-neat:1'
        with patch('action_inbetweens.manifest',return_value={key:entry}),\
             patch('action_inbetweens.prepare',return_value=future):
            samples = [sample_pose(('sit-neat',0),('sit-neat',1),p)[0]
                       for p in (.5,.51,.52,.53,.54)]
        pixels = [(image.pixelColor(80,80).red(), image.pixelColor(80,80).green(),
                   image.pixelColor(80,80).blue(), image.pixelColor(80,80).alpha())
                  for image in samples]
        self.assertEqual(len(set(pixels)),1)
        self.assertEqual(pixels[0][3],128)

    def test_physical_and_music_clips_never_decode_or_sample_optical_flow(self):
        for key in ('throw-flight','impact-left','impact-right','impact-ceiling',
                    'impact-floor','music-waltz','dragged'):
            pair=((key,0),(key,1))
            with patch('action_inbetweens.prepare') as decode:
                self.assertIsNone(sample_pose(*pair,.5),key)
                inbetweens.prefetch([pair])
                decode.assert_not_called()

    def test_expressive_actions_use_their_shipped_inbetweens(self):
        for key in ('curious','play-peek','celebrate','affection','play-climb-up'):
            pair=((key,0),(key,1))
            self.assertIn(inbetweens.pair_key(*pair), inbetweens.manifest(), key)
            with patch('action_inbetweens.prepare') as decode:
                inbetweens.prefetch([pair])
                decode.assert_called_once()

    def test_idle_families_keep_their_optical_flow_permission(self):
        for key in ('comb','sit-neat','prone-rest','sleep','lazy-roll-toward','lazy-roll-away'):
            self.assertTrue(inbetweens.flow_allowed((key,0),(key,1)),key)
        self.assertTrue(inbetweens.flow_allowed(('sit-neat',0),('affection',0)))
        self.assertFalse(inbetweens.flow_allowed(('sit-neat',0),('throw-flight',0)))
        self.assertFalse(inbetweens.flow_allowed(('sit-neat',0),('music-waltz',0)))

    def test_real_render_advances_between_authored_poses_and_stops_immediately(self):
        state, renderer = PetState(), PetRenderer()
        state.action_player.play('sit-neat', now=100)
        first_pair = (('sit-neat',0), ('sit-neat',1))
        prepare(manifest()[pair_key(*first_pair)]).result()
        frames(manifest()[pair_key(*first_pair)])
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
