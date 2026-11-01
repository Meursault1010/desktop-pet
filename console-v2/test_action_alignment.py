"""Per-frame alignment stabilizes artwork placement without changing poses."""
import json
import unittest
from pathlib import Path
import numpy as np
from PIL import Image

from build_frame_alignment import ASSETS, build
from frame_alignment import _data, offset_for, profile


class FrameAlignmentTests(unittest.TestCase):
    def test_profile_covers_generated_action_sequences_and_matches_visible_bounds(self):
        generated = {entry['id']:entry for entry in
                     json.loads((ASSETS/'catalog.json').read_text(encoding='utf-8'))
                     if entry.get('origin') == 'generated' and entry['frames'] > 1
                     and not entry.get('ground_idle') and not entry.get('lazy_roll')
                     and not entry.get('physics_only') and entry['id'] not in {'leap', 'dragged'}
                     and all((ASSETS/entry['id']/f'{index+1:02d}.png').exists()
                             for index in range(entry['frames']))}
        measured = build()['actions']
        shipped = profile()
        self.assertEqual(set(shipped), set(generated))
        self.assertEqual(shipped, measured)
        locked = {action_id for action_id, entry in generated.items()
                  if entry.get('body_locked')}
        for action_id, entry in generated.items():
            offsets = shipped[action_id]['offsets']
            self.assertEqual(len(offsets), entry['frames'])
            boxes = []
            for index in range(entry['frames']):
                image = Image.open(ASSETS/action_id/f'{index+1:02d}.png').convert('RGBA')
                box = image.getchannel('A').point(lambda value:255 if value >= 32 else 0).getbbox()
                boxes.append(box)
                self.assertGreaterEqual(box[0], 0)
                self.assertLessEqual(box[2], 256)
                self.assertGreaterEqual(box[1], 0)
                self.assertLessEqual(box[3], 256)
            if action_id in locked:
                self.assertTrue(shipped[action_id].get('body_locked'))
                if entry.get('body_lock') == 'baked-contact':
                    # The desk climb bakes its own contact but keeps the last
                    # three frames on the shared seated registration, so the
                    # warp bridges into play-climb-down stay pure translations.
                    continue
                self.assertEqual(offsets, [[0., 0.]]*entry['frames'])
                continue
            for index, box in enumerate(boxes):
                dx, dy = offsets[index]
                self.assertAlmostEqual((box[0]+box[2])/2+dx, shipped[action_id]['anchor_x'])
                if shipped[action_id].get('preserve_vertical'):
                    self.assertEqual(dy, 0.)
                else:
                    self.assertAlmostEqual(box[3]+dy, shipped[action_id]['floor_y'])
                self.assertGreaterEqual(box[0]+dx, 0)
                self.assertLessEqual(box[2]+dx, 256)
                self.assertGreaterEqual(box[1]+dy, 0)
                self.assertLessEqual(box[3]+dy, 256)

    def test_body_locked_action_keeps_its_frames_in_place(self):
        entry = next(entry for entry in
                     json.loads((ASSETS/'catalog.json').read_text(encoding='utf-8'))
                     if entry['id'] == 'screen')
        self.assertTrue(entry.get('body_locked'))
        self.assertEqual(profile()['screen']['offsets'], [[0., 0.]]*entry['frames'])

    def test_tea_ships_key_poses_only_with_a_baked_foot_anchor(self):
        # The tea batch drew one stance at three canvas positions, and optical
        # flow turned that drift into a sideways glide, so the clip now ships the
        # authored poses with the stabilisation baked into the pixels.
        entry = next(entry for entry in
                     json.loads((ASSETS/'catalog.json').read_text(encoding='utf-8'))
                     if entry['id'] == 'tea')
        self.assertTrue(entry.get('authored_motion'))
        self.assertTrue(entry.get('body_locked'))
        self.assertEqual(entry['frames'], entry['keyframes'])
        self.assertFalse(any(pair.startswith('tea:')
                             for pair in _data()['transitions']))
        shipped = profile()['tea']
        self.assertEqual(shipped['offsets'], [[0., 0.]]*entry['frames'])
        feet = []
        for index in range(entry['frames']):
            with Image.open(ASSETS/'tea'/f'{index+1:02d}.png') as image:
                frame = np.asarray(image.convert('RGBA'))
            alpha = frame[:, :, 3]
            ys, xs = np.where(alpha >= 32)
            band = ys >= ys.max()-9
            feet.append(float((xs[band]*alpha[ys[band], xs[band]]).sum()
                              / alpha[ys[band], xs[band]].sum()))
            self.assertEqual(int(ys.max()), 250)
        self.assertLess(max(feet)-min(feet), 1.5)
        self.assertAlmostEqual(sum(feet)/len(feet), 126.7, delta=1.0)

    def test_frame_offsets_ease_between_poses_and_ignore_world_motion_clips(self):
        from unittest.mock import patch
        action_id = next(action_id for action_id, entry in profile().items()
                         if len(entry['offsets']) > 1 and not entry.get('body_locked')
                         and entry['offsets'][0] != entry['offsets'][1])
        start = offset_for((action_id,0),(action_id,1),0)
        end = offset_for((action_id,0),(action_id,1),1)
        self.assertNotEqual(start, end)
        with patch('frame_alignment._data', return_value={'actions':profile()}):
            middle = offset_for((action_id,0),(action_id,1),.5)
            self.assertAlmostEqual(middle[0], (start[0]+end[0])/2)
            self.assertAlmostEqual(middle[1], (start[1]+end[1])/2)
        self.assertEqual(offset_for(('leap',0),('leap',1),.5),(0.,0.))
        self.assertEqual(offset_for(('lazy-roll-toward',0),('lazy-roll-toward',1),.5),(0.,0.))

    def test_warp_subframes_keep_the_same_anchor_and_exact_endpoints(self):
        payload = _data()
        self.assertEqual(payload['transitions'], build()['transitions'])
        motion = ASSETS.parent/'action-motion'
        manifest = json.loads((motion/'manifest.json').read_text(encoding='utf-8'))['pairs']
        # Locked clips bake their own registration and get no subframe tracks,
        # so the floor only guards against the table being emptied.
        self.assertGreater(len(payload['transitions']), 10)
        for pair, offsets in payload['transitions'].items():
            before, after = [(name, int(index)) for name, index in
                             (ref.rsplit(':', 1) for ref in pair.split('>'))]
            self.assertEqual(offsets[0], list(offset_for(before)))
            self.assertEqual(offsets[-1], list(offset_for(after)))
            entry = manifest[pair]
            with Image.open(motion/entry['file']) as strip:
                for index in range(len(offsets)):
                    t = index/(len(offsets)-1)
                    dx, dy = offset_for(before, after, t)
                    self.assertAlmostEqual(dx, offsets[index][0])
                    self.assertAlmostEqual(dy, offsets[index][1])
                    if index not in (0, len(offsets)//2, len(offsets)-1):
                        continue
                    x, y = index % entry['columns']*256, index//entry['columns']*256
                    box = strip.crop((x,y,x+256,y+256)).getchannel('A').point(
                        lambda value:255 if value >= 32 else 0).getbbox()
                    start, end = profile()[before[0]], profile()[after[0]]
                    anchor_x = start['anchor_x']+(end['anchor_x']-start['anchor_x'])*t
                    self.assertAlmostEqual((box[0]+box[2])/2+dx, anchor_x, places=2)
                    if not start['preserve_vertical'] and not end['preserve_vertical']:
                        floor_y = start['floor_y']+(end['floor_y']-start['floor_y'])*t
                        self.assertAlmostEqual(box[3]+dy, floor_y, places=2)
            i = len(offsets)//2
            midway = (i+.5)/(len(offsets)-1)
            dx, dy = offset_for(before, after, midway)
            self.assertAlmostEqual(dx, (offsets[i][0]+offsets[i+1][0])/2)
            self.assertAlmostEqual(dy, (offsets[i][1]+offsets[i+1][1])/2)


    def test_sit_swing_warps_are_built_on_the_locked_seated_body(self):
        # The twelve cells were placed by their own bounding box, so the hair
        # pooled at viewer left dragged every seated torso ~16px right of the
        # standing one. That drift is baked into the pixels now, and the flow
        # strips are rebuilt from the locked atlas - if a strip no longer starts
        # and ends on the shipped pose, the slide comes back with it.
        entry = next(entry for entry in
                     json.loads((ASSETS/'catalog.json').read_text(encoding='utf-8'))
                     if entry['id'] == 'sit-swing')
        self.assertTrue(entry.get('body_locked'))
        self.assertFalse(entry.get('authored_motion'))
        manifest = json.loads((ASSETS.parent/'action-motion/manifest.json')
                              .read_text(encoding='utf-8'))
        pairs = {pair: warp for pair, warp in manifest['pairs'].items()
                 if pair.startswith('sit-swing:')}
        self.assertTrue(pairs)
        self.assertIn('sit-swing', manifest['source_sha256'])
        self.assertNotIn('sit-swing', profile())
        with Image.open(ASSETS/'sit-swing'/'atlas.png') as atlas_image:
            atlas = np.asarray(atlas_image.convert('RGBA'))
        for pair, warp in pairs.items():
            with Image.open(ASSETS.parent/'action-motion'/warp['file']) as strip_image:
                strip = np.asarray(strip_image.convert('RGBA'))
            for reference, cell_index in zip(pair.split('>'), (0, warp['frames']-1)):
                frame = int(reference.rsplit(':', 1)[1])
                got = strip[cell_index // warp['columns'] * 256:(cell_index // warp['columns'] + 1) * 256,
                             cell_index % warp['columns'] * 256:(cell_index % warp['columns'] + 1) * 256]
                want = atlas[frame // 4 * 256:(frame // 4 + 1) * 256,
                             frame % 4 * 256:(frame % 4 + 1) * 256]
                self.assertTrue(np.array_equal(got, want), f'{pair}: stale endpoint')
        heads, floors = [], []
        for index in range(entry['frames']):
            with Image.open(ASSETS/'sit-swing'/f'{index+1:02d}.png') as image:
                alpha = np.asarray(image.convert('RGBA'))[:, :, 3]
            ys, xs = np.nonzero(alpha >= 32)
            self.assertGreaterEqual(int(xs.min()), 1)
            self.assertLessEqual(int(xs.max()), 254)
            self.assertGreaterEqual(int(ys.min()), 1)
            self.assertLessEqual(int(ys.max()), 254)
            floors.append(int(ys.max()))
            crown = ys < ys.min() + int((ys.max()-ys.min()+1)*.22)
            heads.append(float(xs[crown].mean()))
        self.assertEqual(len(set(floors)), 1, 'the seated body floats off the floor')
        # Frames 1-2 stand, 4-27 hold the seated cycle, 28-30 rise again. The
        # head may lean a few pixels back while a foot kicks out; it may not
        # change where she is sitting.
        dwell = heads[3:27]
        self.assertLess(max(dwell)-min(dwell), 7.0, 'she slides while swinging')
        self.assertLess(abs(sum(dwell)/len(dwell) - heads[0]), 9.0,
                        'sitting down moved her off her own feet')


if __name__ == '__main__':
    unittest.main()
