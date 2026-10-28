"""Stage dense in-betweens for low-keyframe action clips.

The original key pose frames are preserved under action-work/smooth/<id>/original.
`--stage` writes the expanded sequence into action-work/smooth/<id>/new without
touching runtime assets; `--apply` publishes it and updates the catalog.
"""

from __future__ import annotations

import argparse
import json
import math
import shutil
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw

from action_player import catalog
from build_action_inbetweens import interpolate

ROOT = Path(__file__).resolve().parent
ACTIONS = ROOT / 'assets' / 'actions'
WORK = ROOT / 'action-work' / 'smooth'
STEP_MS = 70
MIN_K = 2
MAX_K = 6
HOLD_MIN = 120


def load_frame(path):
    return np.asarray(Image.open(path).convert('RGBA')).astype(np.uint8)


def sample_indices(k):
    return [round((index + 1) * 24 / (k + 1)) for index in range(k)]


def fit_frame(frame):
    """Keep warped in-betweens inside the 256 canvas with a 1px margin."""
    alpha = frame[:, :, 3]
    ys, xs = np.where(alpha >= 16)
    if not len(xs):
        return frame
    dx = dy = 0
    if xs.min() < 1:
        dx = 1 - int(xs.min())
    elif xs.max() > 254:
        dx = 254 - int(xs.max())
    if ys.min() < 1:
        dy = 1 - int(ys.min())
    elif ys.max() > 254:
        dy = 254 - int(ys.max())
    if dx == 0 and dy == 0:
        return frame
    shifted = np.zeros_like(frame)
    src_x0, src_x1 = max(0, -dx), min(256, 256 - dx)
    src_y0, src_y1 = max(0, -dy), min(256, 256 - dy)
    dst_x0, dst_x1 = src_x0 + dx, src_x1 + dx
    dst_y0, dst_y1 = src_y0 + dy, src_y1 + dy
    shifted[dst_y0:dst_y1, dst_x0:dst_x1] = frame[src_y0:src_y1, src_x0:src_x1]
    return shifted


def choose_k(duration_ms):
    if duration_ms - 60 < STEP_MS:
        return 0
    k = max(MIN_K, min(MAX_K, round((duration_ms - HOLD_MIN) / STEP_MS)))
    while k > 1 and k * STEP_MS > duration_ms - 60:
        k -= 1
    return k


def expanded(action_id, stage_dir, frame_images, base_entry):
    frames = base_entry['frames']
    durations = base_entry['durations']
    loop_source = base_entry.get('loop_start')
    result = []
    schedule = []
    reports = []
    key_index = {}
    for index in range(frames):
        source = frame_images[index]
        duration = durations[index]
        target = index + 1 if index + 1 < frames else loop_source
        k = choose_k(duration) if target is not None else 0
        key_index[index] = len(result)
        if target is None or k == 0:
            result.append(source)
            schedule.append(duration)
            continue
        step = STEP_MS
        hold = max(60, duration - k * step)
        result.append(source)
        schedule.append(hold)
        frames_inbetween, quality = interpolate(
            source, frame_images[target], (action_id, index), (action_id, target))
        picks = sample_indices(k)
        for pick in picks:
            result.append(fit_frame(frames_inbetween[pick]))
            schedule.append(step)
        reports.append({'segment': [index, target], 'k': k, 'hold': hold,
                        'step': step, **quality})
    assert abs(sum(schedule) - sum(durations)) < 1e-6, (action_id, sum(schedule), sum(durations))
    stage_dir.mkdir(parents=True, exist_ok=True)
    for i, frame in enumerate(result):
        Image.fromarray(frame).save(stage_dir / f'{i + 1:02d}.png')
    return result, schedule, reports, key_index


def build_atlas(frames, columns=4):
    rows = math.ceil(len(frames) / columns)
    atlas = Image.new('RGBA', (columns * 256, rows * 256))
    for index, frame in enumerate(frames):
        atlas.alpha_composite(Image.fromarray(frame), ((index % columns) * 256, (index // columns) * 256))
    return atlas


def preview_gif(frames, durations, path):
    images = []
    for frame in frames:
        bg = Image.new('RGB', (256, 256), '#48505e')
        bg.paste(Image.fromarray(frame), (0, 0), Image.fromarray(frame))
        images.append(bg)
    path.parent.mkdir(parents=True, exist_ok=True)
    images[0].save(path, save_all=True, append_images=images[1:], duration=durations, loop=0)


def prune_motion(action_id):
    """Authored frames replace the flow bridges between their own poses."""
    motion = ACTIONS.parent / 'action-motion'
    manifest_path = motion / 'manifest.json'
    if not manifest_path.exists():
        return
    payload = json.loads(manifest_path.read_text(encoding='utf-8'))
    pairs = payload.get('pairs', {})
    for pair, entry in list(pairs.items()):
        refs = [ref.rsplit(':', 1)[0] for ref in pair.split('>')]
        if action_id in refs:
            (motion / entry['file']).unlink(missing_ok=True)
            pairs.pop(pair)
    payload.get('source_sha256', {}).pop(action_id, None)
    manifest_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding='utf-8')
    quality_path = motion / 'quality-report.json'
    if quality_path.exists():
        quality = json.loads(quality_path.read_text(encoding='utf-8'))
        for pair in list(quality):
            if action_id in [ref.rsplit(':', 1)[0] for ref in pair.split('>')]:
                quality.pop(pair)
        quality_path.write_text(json.dumps(quality, ensure_ascii=False, indent=2), encoding='utf-8')


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--actions', nargs='+', required=True)
    parser.add_argument('--apply', action='store_true')
    parser.add_argument('--force', action='store_true')
    args = parser.parse_args()
    WORK.mkdir(parents=True, exist_ok=True)
    manifest = {}
    manifest_path = WORK / 'report.json'
    if manifest_path.exists():
        manifest = json.loads(manifest_path.read_text(encoding='utf-8'))
    catalog_path = ACTIONS / 'catalog.json'
    entries = json.loads(catalog_path.read_text(encoding='utf-8'))
    by_id = {entry['id']: entry for entry in entries}
    for action_id in args.actions:
        entry = by_id[action_id]
        if ((entry.get('authored_motion') and not args.force)
                or entry.get('ground_idle') or entry.get('lazy_roll')
                or entry.get('dance_rest') or entry.get('physics_only')):
            print(f'skip special action {action_id}')
            continue
        folder = ACTIONS / action_id
        backup = WORK / action_id / 'original'
        if not backup.exists():
            backup.mkdir(parents=True)
            for path in sorted(folder.glob('[0-9][0-9].png')):
                shutil.copy2(path, backup / path.name)
            for name in ('atlas.png', 'poster.png'):
                if (folder / name).exists():
                    shutil.copy2(folder / name, backup / name)
        entry_file = backup / 'catalog-entry.json'
        if not entry_file.exists():
            entry_file.write_text(json.dumps(entry, ensure_ascii=False, indent=2), encoding='utf-8')
        base_entry = json.loads(entry_file.read_text(encoding='utf-8'))
        original = [load_frame(backup / f'{i + 1:02d}.png') for i in range(base_entry['frames'])]
        stage = WORK / action_id / 'new'
        frames, durations, reports, key_index = expanded(action_id, stage, original, base_entry)
        loop_start = key_index[base_entry['loop_start']] if base_entry.get('loop_start') is not None else None
        preview_gif(frames, durations, WORK / action_id / 'preview.gif')
        atlas = build_atlas(frames)
        atlas.save(WORK / action_id / 'atlas.png')
        manifest[action_id] = {
            'keyframes': base_entry['frames'],
            'frames': len(frames),
            'durations': durations,
            'loop_start': loop_start,
            'segments': reports,
        }
        print(f'{action_id}: {base_entry["frames"]} -> {len(frames)} frames, '
              f'{sum(durations) / 1000:.2f}s, report {WORK / action_id / "preview.gif"}')
        if args.apply:
            keyframes = base_entry['frames']
            for path in folder.glob('[0-9][0-9].png'):
                path.unlink()
            for i, frame in enumerate(frames):
                Image.fromarray(frame).save(folder / f'{i + 1:02d}.png')
            atlas.save(folder / 'atlas.png')
            Image.fromarray(frames[0]).save(folder / 'poster.png')
            entry.update(frames=len(frames), durations=durations, authored_motion=True,
                         smoothed=True, keyframes=keyframes,
                         keyframe_durations=base_entry['durations'])
            if loop_start is None:
                entry.pop('loop_start', None)
            else:
                entry['loop_start'] = loop_start
            catalog_path.write_text(json.dumps(entries, ensure_ascii=False, indent=2), encoding='utf-8')
            preview_gif(frames, durations, ROOT / 'qa' / 'actions' / f'{action_id}.gif')
            prune_motion(action_id)
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding='utf-8')


if __name__ == '__main__':
    main()
