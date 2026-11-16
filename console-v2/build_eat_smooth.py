"""Rebuild the eat clip with motion-proportional spacing.

The 12 authored key poses differ wildly in how much they move (1.7 to 41 mean
delta). Sampling them with a constant number of in-betweens produced a frozen
middle and a fast, popping tissue section. Here each segment gets time and
in-between density from its own pose distance, so consecutive frames advance by
a nearly constant amount and the runtime cross-fade never has to carry a jump.

Usage: python build_eat_smooth.py [--apply]
"""
from __future__ import annotations

import argparse
import json
import shutil
from pathlib import Path

import numpy as np
from PIL import Image

from scipy import ndimage
from skimage.color import lab2rgb, rgb2lab

from build_action_inbetweens import interpolate
from build_smoothed_actions import (build_atlas, edge_strength, fit_frame, load_frame,
                                     match_edge, preview_gif)

ROOT = Path(__file__).resolve().parent
ACTIONS = ROOT / 'assets' / 'actions'
ACTION = 'eat'
SOURCE = ROOT / 'action-work' / 'smooth' / ACTION / 'original'
STAGE = ROOT / 'action-work' / 'eat-retime'
COLUMNS = 4
STEP_MS = 48          # displayed length of one in-between
KEY_BEAT_MS = 70      # settle on an authored pose before it starts moving
TARGET_STEP = 3.0     # mean pose change carried by one displayed frame
MAX_JUMP = 4.0        # a larger warp discontinuity becomes a short dissolve
TAIL_MS = 300


def pose_distance(a, b):
    mask = (a[:, :, 3] > 32) | (b[:, :, 3] > 32)
    if not mask.any():
        return 0.0
    delta = a.astype(np.int16) - b.astype(np.int16)
    return float(np.abs(delta)[mask].mean())


def dissolve(a, b, weight):
    """Short cross-fade used only where the single-source warp tears.

    The warp keeps silhouettes single-sourced everywhere else; at a residual
    jump the two warped endpoints disagree on appearance (a prop appears), so a
    two-frame dissolve reads as the prop fading in instead of popping."""
    mixed = a.astype(np.float32)*(1-weight) + b.astype(np.float32)*weight
    return np.clip(np.rint(mixed), 0, 255).astype(np.uint8)


def smooth_samples(samples):
    path = [samples[0]]
    for a, b in zip(samples, samples[1:]):
        jump = pose_distance(a, b)
        if jump > MAX_JUMP:
            pieces = int(np.ceil(jump / TARGET_STEP))
            for step in range(1, pieces):
                path.append(dissolve(a, b, step / pieces))
        path.append(b)
    return path


def cumulative(samples):
    path = [0.0]
    for previous, current in zip(samples, samples[1:]):
        path.append(path[-1] + pose_distance(previous, current))
    return path


def plan(keys):
    segments = []
    for index in range(len(keys) - 1):
        samples, quality = interpolate(keys[index], keys[index + 1],
                                       (ACTION, index), (ACTION, index + 1))
        samples = smooth_samples(samples)
        path = cumulative(samples)
        distance = path[-1]
        inbetweens = max(0, round(distance / TARGET_STEP) - 1)
        picks = []
        for count in range(1, inbetweens + 1):
            target = distance * count / (inbetweens + 1)
            pick = min(range(len(path) - 1), key=lambda i: abs(path[i] - target)) + 1
            if pick <= picks[-1] if picks else False:
                pick = picks[-1] + 1
            if pick >= len(samples) - 1:
                break
            picks.append(pick)
        segments.append({'index': index, 'distance': round(distance, 2),
                         'inbetweens': len(picks), 'picks': picks,
                         'quality': quality, 'samples': samples})
    return segments


def color_match(frames):
    """Hold one palette across the clip.

    The twelve key poses were generated separately and differ by up to ~2.3 L
    and ~12% local contrast, so assembled frames drifted in tone. Every frame
    is matched to the clip's own average Lab mean/std, which keeps the authored
    colours of this action instead of borrowing another sprite's."""
    labs, masks = [], []
    for frame in frames:
        labs.append(rgb2lab(frame[:, :, :3].astype(np.float32) / 255))
        masks.append(frame[:, :, 3] > 199)
    means = np.array([lab[mask].mean(0) for lab, mask in zip(labs, masks)])
    stds = np.array([lab[mask].std(0) for lab, mask in zip(labs, masks)])
    target_mean, target_std = means.mean(0), stds.mean(0)
    matched = []
    for frame, lab, mask, mean, std in zip(frames, labs, masks, means, stds):
        scale = target_std / np.maximum(std, 1e-4)
        rgb = np.clip(lab2rgb((lab - mean) * scale + target_mean), 0, 1) * 255
        matched.append(np.dstack([np.rint(rgb), frame[:, :, 3]]).astype(np.uint8))
    return matched


def prop_mask(reference):
    """Pixels of the static dessert plate, kept clear of the hair above it."""
    yy, xx = np.mgrid[0:256, 0:256]
    geometry = (((xx >= 176) & (yy >= 196)) | ((xx >= 158) & (yy >= 206))
                | ((xx >= 150) & (yy >= 218)))
    solid = (reference[:, :, 3] > 40) & geometry
    return ndimage.gaussian_filter(solid.astype(np.float32), 0.7)


def lock_prop(frames, reference):
    """Hold the plate on one reference so warped in-betweens cannot ghost it."""
    weight = prop_mask(reference)[..., None]
    base = reference.astype(np.float32)
    locked = []
    for frame in frames:
        mixed = frame.astype(np.float32) * (1 - weight) + base * weight
        locked.append(np.clip(np.rint(mixed), 0, 255).astype(np.uint8))
    return locked


def build(keys, segments):
    frames, durations = [], []
    for segment in segments:
        frames.append(keys[segment['index']])
        durations.append(KEY_BEAT_MS)
        for pick in segment['picks']:
            frames.append(fit_frame(segment['samples'][pick]))
            durations.append(STEP_MS)
    frames.append(keys[-1])
    durations.append(TAIL_MS)
    frames = color_match(frames)
    frames = lock_prop(frames, frames[-1])
    key_edges = [edge_strength(key) for key in keys]
    target_edge = float(np.median(key_edges))
    lifted = 0
    for index, frame in enumerate(frames):
        if edge_strength(frame) < target_edge * 0.92:
            frames[index], _ = match_edge(frame, target_edge)
            lifted += 1
    print(f'  edge-aligned {lifted} frames to {target_edge:.2f}')
    steps = [round(pose_distance(frames[i], frames[i + 1]), 2) for i in range(len(frames) - 1)]
    return frames, durations, steps


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--apply', action='store_true')
    args = parser.parse_args()

    backup = STAGE / 'previous'
    if not backup.exists():
        backup.mkdir(parents=True)
        for path in sorted((ACTIONS / ACTION).glob('[0-9][0-9].png')):
            shutil.copy2(path, backup / path.name)
        for name in ('atlas.png', 'poster.png'):
            shutil.copy2(ACTIONS / ACTION / name, backup / name)
        shutil.copy2(ACTIONS / 'catalog.json', backup / 'catalog.json')

    keys = [load_frame(SOURCE / f'{i + 1:02d}.png') for i in range(12)]
    segments = plan(keys)
    frames, durations, steps = build(keys, segments)
    total = sum(durations)

    atlas = build_atlas(frames, COLUMNS)
    STAGE.mkdir(parents=True, exist_ok=True)
    for index, frame in enumerate(frames):
        Image.fromarray(frame).save(STAGE / f'{index + 1:02d}.png')
    atlas.save(STAGE / 'atlas.png')
    preview_gif(frames, durations, STAGE / 'preview.gif')
    summary = {'frames': len(frames), 'total_ms': total, 'steps': steps,
               'segments': [{k: v for k, v in segment.items() if k not in ('samples',)}
                            for segment in segments]}
    (STAGE / 'plan.json').write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding='utf-8')

    print(f'{len(frames)} frames, {total/1000:.2f}s')
    for segment in segments:
        print(f"  kf{segment['index']+1}->{segment['index']+2}: d {segment['distance']:>6} "
              f"inbetweens {segment['inbetweens']:>2}")
    print('  max step', max(steps), 'mean step', round(sum(steps)/len(steps), 2))

    if args.apply:
        folder = ACTIONS / ACTION
        for path in folder.glob('[0-9][0-9].png'):
            path.unlink()
        for index, frame in enumerate(frames):
            Image.fromarray(frame).save(folder / f'{index + 1:02d}.png')
        atlas.save(folder / 'atlas.png')
        Image.fromarray(frames[0]).save(folder / 'poster.png')
        catalog_path = ACTIONS / 'catalog.json'
        entries = json.loads(catalog_path.read_text(encoding='utf-8'))
        for entry in entries:
            if entry['id'] != ACTION:
                continue
            entry['keyframe_durations'] = entry.pop('durations')
            entry['keyframes'] = 12
            entry['frames'] = len(frames)
            entry['durations'] = durations
            entry['authored_motion'] = True
            entry['smoothed'] = True
        catalog_path.write_text(json.dumps(entries, ensure_ascii=False, indent=2), encoding='utf-8')
        preview_gif(frames, durations, ROOT / 'qa' / 'actions' / f'{ACTION}.gif')
        print('applied')


if __name__ == '__main__':
    main()
