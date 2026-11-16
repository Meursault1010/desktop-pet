"""Rebuild the shy clip in place with clean eyelid states.

The six authored poses drift 32px sideways and 16px vertically, and the optical
flow turns the closed-eye -> wink transition into a double eye. This rebuilds
the in-betweens at 40ms spacing, registers every frame to the idle foot anchor,
and holds a clean face from the nearest key until the authored wink.

`--stage` writes only action-work/shy-stabilize; `--apply` publishes the clip.
"""
from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

import cv2
import numpy as np
from PIL import Image

from build_action_inbetweens import interpolate
from build_frame_alignment import image_bounds
from build_smoothed_actions import edge_strength, fit_frame, match_edge

ROOT = Path(__file__).resolve().parent
ACTIONS = ROOT / 'assets/actions'
WORK = ROOT / 'action-work/shy-stabilize'
ORIGINAL = ROOT / 'action-work/smooth/shy/original'
ID = 'shy'
STEP_MS = 30
HOLD_MIN = 60
MIN_K, MAX_K = 2, 16
# The reviewed 1.66s clip reads as a startle; the user wants a slower, softer
# bashful beat, so every authored slot is stretched together.
TEMPO_SCALE = 1.45
# Idle (blink) registration: feet on the same ground line, body on the same axis.
ANCHOR_X = 126.3
ANCHOR_Y = 251
EYE_ZONE = (slice(60, 135), slice(85, 175))
FACE_RADII = (26, 18)
FACE_FEATHER = 4
# Pose phase where the authored eyelid state flips. Closed eyes stay closed
# while the hand rises; the wink opens again on the lowering half.
EYE_SWITCH = 0.55


def load(path):
    return np.asarray(Image.open(path).convert('RGBA')).astype(np.uint8)


def foot_anchor(frame):
    alpha = frame[:, :, 3]
    ys, _ = np.nonzero(alpha > 8)
    foot = int(ys.max())
    _, xs = np.nonzero(alpha[max(0, foot-9):foot+1] > 8)
    return float(xs.mean()), foot


def translate(frame, dx, dy):
    dx, dy = int(round(dx)), int(round(dy))
    if dx == 0 and dy == 0:
        return frame
    out = np.zeros_like(frame)
    height, width = frame.shape[:2]
    sx0, sx1 = max(0, -dx), min(width, width-dx)
    sy0, sy1 = max(0, -dy), min(height, height-dy)
    out[sy0+dy:sy1+dy, sx0+dx:sx1+dx] = frame[sy0:sy1, sx0:sx1]
    return out


def anchored(frame):
    # Integer pixels only: subpixel resampling drags edge strength and the
    # semi-transparent edge ratio out of the style anchor range.
    x, y = foot_anchor(frame)
    return translate(frame, ANCHOR_X-x, ANCHOR_Y-y)


def head_anchor(frame):
    ys, xs = np.nonzero(frame[:70, :, 3] > 40)
    return np.array([xs.mean(), ys.min()], dtype=np.float64)


def eyes(frame):
    rgb = frame[:, :, :3].astype(np.float32)
    alpha = frame[:, :, 3]
    lum = rgb.mean(2)
    zone = np.zeros(lum.shape, bool)
    zone[EYE_ZONE] = True
    mask = ((alpha > 235) & (lum < 100) & (rgb[:, :, 2] > rgb[:, :, 0]+10)
            & zone).astype(np.uint8)
    mask = cv2.dilate(mask, np.ones((3, 3), np.uint8))
    count, _, stats, centres = cv2.connectedComponentsWithStats(mask, 8)
    found = [centres[i] for i in range(1, count) if stats[i, 4] > 20]
    if len(found) < 2:
        raise ValueError('eye landmarks missing')
    found = sorted(found, key=lambda point: point[0])
    points = np.array([found[0], found[-1]], dtype=np.float64)
    return dict(points=points, eyes=points.mean(0), head=head_anchor(frame))


def eased_indices(k):
    picks = []
    for step in range(1, k+1):
        u = step/(k+1)
        smooth = u*u*(3-2*u)
        pick = min(23, max(1, int(round((.35*u+.65*smooth)*24))))
        if picks and pick <= picks[-1]:
            pick = min(23, picks[-1]+1)
        picks.append(pick)
    return picks


def segment_k(duration):
    k = max(MIN_K, min(MAX_K, int(round((duration-70)/STEP_MS))))
    while k > MIN_K and k*STEP_MS > duration-HOLD_MIN:
        k -= 1
    return k


def paste_face(target, source, source_state, target_eye, feather=FACE_FEATHER):
    move = target_eye-source_state['eyes']
    matrix = np.float32([[1, 0, move[0]], [0, 1, move[1]]])
    shifted = cv2.warpAffine(source, matrix, (256, 256), flags=cv2.INTER_LINEAR,
                             borderMode=cv2.BORDER_CONSTANT)
    yy, xx = np.mgrid[:256, :256]
    mask = np.zeros((256, 256), np.float32)
    for eye_x, eye_y in source_state['points']:
        cx, cy = eye_x+move[0], eye_y+move[1]
        inside = (((xx-cx)/FACE_RADII[0])**2+((yy-cy)/FACE_RADII[1])**2 <= 1)
        mask = np.maximum(mask, inside.astype(np.float32))
    mask = cv2.GaussianBlur(mask, (0, 0), feather)[..., None]
    blended = shifted*mask+target*(1-mask)
    blended[:, :, 3] = shifted[:, :, 3]*mask[:, :, 0]+target[:, :, 3]*(1-mask[:, :, 0])
    return np.clip(np.rint(blended), 0, 255).astype(np.uint8)


def build():
    base = json.loads((ORIGINAL/'catalog-entry.json').read_text(encoding='utf-8'))
    base = dict(base, durations=[round(d*TEMPO_SCALE/10)*10 for d in base['durations']])
    keys = [anchored(load(ORIGINAL/f'{i+1:02d}.png')) for i in range(base['frames'])]
    states = [eyes(key) for key in keys]
    frames, schedule, owners = [], [], []
    for index in range(len(keys)-1):
        duration = base['durations'][index]
        k = segment_k(duration)
        hold = duration-k*STEP_MS
        frames.append(keys[index])
        schedule.append(hold)
        owners.append(dict(segment=index, t=0., key=index))
        if k == 0:
            continue
        picks = eased_indices(k)
        inbetweens, _ = interpolate(keys[index], keys[index+1],
                                    (ID, index), (ID, index+1))
        for pick in picks:
            t = pick/24
            frame = anchored(fit_frame(inbetweens[pick]))
            frames.append(frame)
            schedule.append(STEP_MS)
            owners.append(dict(segment=index, t=t, key=None))
    frames.append(keys[-1])
    schedule.append(base['durations'][-1])
    owners.append(dict(segment=len(keys)-1, t=1., key=len(keys)-1))
    # Warped in-betweens come out softer than the key poses; lift their line
    # weight back to the authored median before the face patch goes on.
    key_at = [i for i, owner in enumerate(owners) if owner['key'] is not None]
    target_edge = float(np.median([edge_strength(frames[i]) for i in key_at]))
    for i, frame in enumerate(frames):
        if i in key_at:
            continue
        if edge_strength(frame) < target_edge*0.92:
            # Unsharp touches the alpha fringe, so re-register afterwards.
            frames[i] = anchored(match_edge(frame, target_edge)[0])
    # The optical flow smears eyelids. Keep the authored eye state until the
    # next key pose, then let the key change it in one frame.
    for i, owner in enumerate(owners):
        if owner['key'] is not None or owner['segment'] not in (2, 3, 4):
            continue
        a, b = owner['segment'], owner['segment']+1
        t = owner['t']
        if owner['segment'] == 2:
            source = a if t < EYE_SWITCH else b
        elif owner['segment'] == 3:
            source = a
        else:
            source = a if t < EYE_SWITCH else b
        rel_a = states[a]['eyes']-states[a]['head']
        rel_b = states[b]['eyes']-states[b]['head']
        target_eye = head_anchor(frames[i])+rel_a+(rel_b-rel_a)*t
        frames[i] = paste_face(frames[i], keys[source], states[source], target_eye)
    for frame in frames:
        x, y = foot_anchor(frame)
        assert abs(x-ANCHOR_X) < 1.2 and abs(y-ANCHOR_Y) < 1.2, (x, y)
    return frames, schedule, owners, states


def atlas(frames, columns=4):
    rows = math.ceil(len(frames)/columns)
    sheet = Image.new('RGBA', (columns*256, rows*256))
    for i, frame in enumerate(frames):
        sheet.alpha_composite(Image.fromarray(frame), (i % columns*256, i//columns*256))
    return sheet


def gif(frames, durations, path):
    images = []
    for frame in frames:
        bg = Image.new('RGB', (256, 256), '#48505e')
        bg.paste(Image.fromarray(frame), (0, 0), Image.fromarray(frame))
        images.append(bg)
    path.parent.mkdir(parents=True, exist_ok=True)
    images[0].save(path, save_all=True, append_images=images[1:], duration=durations, loop=0)


def alignment_entry(frames):
    boxes = [image_bounds(Image.fromarray(frame)) for frame in frames]
    centres = sorted((box[0]+box[2])/2 for box in boxes)
    anchor_x = (centres[(len(centres)-1)//2]+centres[len(centres)//2])/2
    floor_y = max(box[3] for box in boxes)
    offsets = [[round(anchor_x-(box[0]+box[2])/2, 3), round(floor_y-box[3], 3)]
               for box in boxes]
    return dict(anchor_x=round(anchor_x, 3), floor_y=floor_y,
                preserve_vertical=False, offsets=offsets)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--apply', action='store_true')
    args = parser.parse_args()
    frames, schedule, owners, states = build()
    authored = json.loads((ORIGINAL/'catalog-entry.json').read_text(encoding='utf-8'))['durations']
    expected = sum(round(d*TEMPO_SCALE/10)*10 for d in authored)
    assert abs(sum(schedule)-expected) < 1e-6, (sum(schedule), expected)
    staged = WORK/'new'
    staged.mkdir(parents=True, exist_ok=True)
    for i, frame in enumerate(frames):
        Image.fromarray(frame).save(staged/f'{i+1:02d}.png')
    sheet = atlas(frames)
    sheet.save(WORK/'atlas.png')
    gif(frames, schedule, WORK/'preview.gif')
    key_at = [i for i, owner in enumerate(owners) if owner['key'] is not None]
    report = dict(frames=len(frames), durations=schedule, owners=owners,
                  key_frames=key_at, click_frame=key_at[1],
                  anchors=[foot_anchor(frame) for frame in frames],
                  alignment=alignment_entry(frames))
    (WORK/'report.json').write_text(json.dumps(report, ensure_ascii=False, indent=1),
                                    encoding='utf-8')
    print(f'{ID}: 6 -> {len(frames)} frames, {sum(schedule)/1000:.2f}s, {WORK/"preview.gif"}')
    if not args.apply:
        return
    folder = ACTIONS/ID
    for path in folder.glob('[0-9][0-9].png'):
        path.unlink()
    for i, frame in enumerate(frames):
        Image.fromarray(frame).save(folder/f'{i+1:02d}.png')
    sheet.save(folder/'atlas.png')
    Image.fromarray(frames[0]).save(folder/'poster.png')
    catalog_path = ACTIONS/'catalog.json'
    entries = json.loads(catalog_path.read_text(encoding='utf-8'))
    for entry in entries:
        if entry['id'] != ID:
            continue
        entry.update(frames=len(frames), durations=schedule, authored_motion=True,
                     smoothed=True, keyframes=6, click_frame=key_at[1],
                     keyframe_durations=json.loads(
                         (ORIGINAL/'catalog-entry.json').read_text(encoding='utf-8'))['durations'],
                     review=f'已修复：脚底锚定 + 眼睑状态；{len(frames)} 帧 / '
                            f'{sum(schedule)/1000:.2f}s 原地害羞')
    catalog_path.write_text(json.dumps(entries, ensure_ascii=False, indent=2), encoding='utf-8')
    alignment_path = ACTIONS/'frame-alignment.json'
    payload = json.loads(alignment_path.read_text(encoding='utf-8'))
    payload['actions'][ID] = alignment_entry(frames)
    alignment_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2)+'\n',
                              encoding='utf-8')
    gif(frames, schedule, ROOT/'qa/actions'/f'{ID}.gif')
    print('applied')


if __name__ == '__main__':
    main()
