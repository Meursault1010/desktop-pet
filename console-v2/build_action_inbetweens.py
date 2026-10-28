"""Deterministic local interpolation, with rejection diagnostics and originals intact.

No external service, image generation or runtime flow calculation. Each output
pixel comes from ONE warped endpoint; silhouettes are never double-exposed.
Run again whenever original action atlases change (hashes are recorded).
"""
import argparse
import hashlib
import io
import json
import os
from pathlib import Path
import random
import time

import cv2
import numpy as np
from PIL import Image

from action_player import catalog, ground_idle_timeline, lazy_roll_timeline, pose_ref

ROOT = Path(__file__).resolve().parent
OUTPUT = ROOT/'assets/action-motion'
ALIGNMENT = ROOT/'assets/actions/frame-alignment.json'
# Preserve the density of the reviewed preview in the shipping assets.
# At most 340ms per transition: 25 samples comfortably cover 60Hz drawing.
FRAMES, COLUMNS = 25, 5


def alignment_profile():
    if not ALIGNMENT.exists():
        return {}
    return json.loads(ALIGNMENT.read_text(encoding='utf-8'))['actions']


def endpoint_offset(profile, reference):
    entry = profile.get(reference[0])
    if entry is None or not 0 <= reference[1] < len(entry['offsets']):
        return (0., 0.)
    return entry['offsets'][reference[1]]


def graph():
    pairs = set()
    for key, action in catalog().items():
        if (action.get('physics_only') or action.get('authored_motion')
                or action['frames'] < 2 or key == 'dragged'):
            continue
        orders = [list(range(action['frames']))]
        if action.get('ground_idle'):
            orders = [ground_idle_timeline(action, random.Random(seed))[0] for seed in range(40)]
        if action.get('lazy_roll'):
            orders = [lazy_roll_timeline(action, random.Random(0))[0]]
        for order in orders:
            for left, right in zip(order, order[1:]):
                a, b = pose_ref(key, left), pose_ref(key, right)
                if a != b:
                    pairs.add((a, b))
        if action.get('lazy_roll'):
            pairs.add(((key, 11), ('prone-rest', 3)))
        elif not action.get('ground_idle'):
            pairs.add(((key, action['frames']-1), (key, action.get('loop_start', 0))))
    return sorted(pairs)


def premultiply(image):
    image = image.astype(np.float32)
    image[:, :, :3] *= image[:, :, 3:4]/255
    return image


def unpremultiply(image):
    image = image.copy()
    image[:, :, :3] = np.divide(image[:, :, :3]*255, image[:, :, 3:4],
                               out=np.zeros_like(image[:, :, :3]), where=image[:, :, 3:4] > 0)
    return np.clip(np.rint(image), 0, 255).astype(np.uint8)


def gray(image):
    a = image[:, :, 3:4]/255
    return cv2.cvtColor((image[:, :, :3]*a+240*(1-a)).astype(np.uint8), cv2.COLOR_RGB2GRAY)


def difference(a, b):
    mask = np.maximum(a[:, :, 3], b[:, :, 3]) > 16
    return float(np.abs(a-b)[mask].mean()) if mask.any() else 0.


SWITCHES = (.3, .35, .375, .417, .458, .5, .542, .583, .625, .65, .7)


def shift(image, offset):
    """Move an RGBA drawing in premultiplied space so edges never darken."""
    return unpremultiply(shift_premultiplied(premultiply(image), offset))


def shift_premultiplied(image, offset):
    dx, dy = float(offset[0]), float(offset[1])
    if abs(dx) < 1e-3 and abs(dy) < 1e-3:
        return image
    matrix = np.float32([[1, 0, dx], [0, 1, dy]])
    return cv2.warpAffine(image, matrix, (image.shape[1], image.shape[0]),
                          flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_CONSTANT)


def flow_fields(a, b):
    flow = cv2.DISOpticalFlow_create(cv2.DISOPTICAL_FLOW_PRESET_MEDIUM)
    flow.setFinestScale(0)
    flow.setGradientDescentIterations(64)
    flow.setVariationalRefinementIterations(30)
    forward = flow.calc(gray(a), gray(b), None)
    backward = flow.calc(gray(b), gray(a), None)
    return forward, backward, premultiply(a), premultiply(b)


def sequence(pa, pb, forward, backward, switch):
    """Single-source samples; each pixel comes from one endpoint, never two."""
    yy, xx = np.mgrid[:256, :256].astype(np.float32)

    def warp(source, field, weight):
        return cv2.remap(source, xx+weight*field[:, :, 0], yy+weight*field[:, :, 1],
                         cv2.INTER_LINEAR, borderMode=cv2.BORDER_CONSTANT)

    frames = [pa]
    for index in range(1, FRAMES-1):
        t = index/(FRAMES-1)
        frames.append(warp(pa, backward, t) if t < switch else warp(pb, forward, 1-t))
    frames.append(pb)
    return frames


def placed_peak(frames, before, after, profile):
    """Worst jump after the renderer's per-frame canvas corrections."""
    start, end = profile.get(before[0], {}), profile.get(after[0], {})
    anchor_start, anchor_end = start.get('anchor_x', 128), end.get('anchor_x', 128)
    floor_start, floor_end = start.get('floor_y', 256), end.get('floor_y', 256)
    preserve = start.get('preserve_vertical') or end.get('preserve_vertical')
    placed = []
    last = len(frames)-1
    for index, frame in enumerate(frames):
        t = index/last if last else 0.
        anchor = anchor_start+(anchor_end-anchor_start)*t
        floor = floor_start+(floor_end-floor_start)*t
        alpha = frame[:, :, 3]
        ys, xs = np.where(alpha > 32)
        dx = dy = 0.
        if len(xs):
            dx = anchor-(xs.min()+xs.max())/2
            if not preserve:
                dy = floor-ys.max()
        placed.append(shift_premultiplied(frame, (dx, dy)))
    return max(difference(x, y) for x, y in zip(placed, placed[1:]))


def field_plan(a, b, before, after, profile):
    """Pick the ownership switch that looks smoothest after canvas alignment."""
    forward, backward, pa, pb = flow_fields(a, b)
    baseline = difference(pa, pb)
    best = None
    for switch in SWITCHES:
        frames = sequence(pa, pb, forward, backward, switch)
        score = placed_peak(frames, before, after, profile)
        if best is None or score < best[0]:
            best = (score, frames, switch)
    return best[0], best[1], best[2], baseline


def raw_quality(frames, baseline):
    premultiplied = [premultiply(frame) for frame in frames]
    jump = max(difference(x, y) for x, y in zip(premultiplied, premultiplied[1:]))
    areas = [np.count_nonzero(f[:, :, 3] > 32) for f in frames]
    area_ok = max(areas) <= max(areas[0], areas[-1])*1.10
    return jump, area_ok, baseline > .5 and jump < baseline*.84 and area_ok


def interpolate(a, b, before, after, profile=None):
    profile = alignment_profile() if profile is None else profile
    raw_score, raw, raw_switch, baseline = field_plan(a, b, before, after, profile)
    raw_jump, raw_area_ok, raw_accepted = raw_quality(
        [unpremultiply(frame) for frame in raw], baseline)

    # A drifting canvas makes raw-space flow model translation instead of the
    # pose change, which can leave a large ownership pop. Rebuild the same
    # interpolation in aligned space and move the samples back, so the strip
    # keeps its authored endpoints while its motion is anchored.
    start = endpoint_offset(profile, before)
    end = endpoint_offset(profile, after)
    aligned = None
    if max(abs(start[0]-end[0]), abs(start[1]-end[1])) > 2:
        aligned_score, aligned_raw, aligned_switch, _ = field_plan(
            shift(a, start), shift(b, end), before, after, profile)
        back = [a]
        for index, frame in enumerate(aligned_raw[1:-1], start=1):
            t = index/(len(aligned_raw)-1)
            back.append(shift(unpremultiply(frame), (
                -(start[0]+(end[0]-start[0])*t),
                -(start[1]+(end[1]-start[1])*t))))
        back.append(b)
        aligned_jump, aligned_area_ok, aligned_accepted = raw_quality(back, baseline)
        if aligned_score < raw_score and aligned_accepted:
            aligned = (back, aligned_switch, aligned_jump, aligned_area_ok, aligned_score)

    if aligned is not None:
        frames, switch, jump, area_ok, score = aligned
        building = 'aligned'
        accepted = True
    else:
        frames = [a, *map(unpremultiply, raw[1:-1]), b]
        switch, jump, area_ok, score = raw_switch, raw_jump, raw_area_ok, raw_score
        building = 'raw'
        accepted = raw_accepted
    return frames, {
        'accepted': bool(accepted), 'original_jump': round(baseline, 3),
        'largest_step': round(jump, 3), 'switch': switch, 'area_ok': bool(area_ok),
        'construction': building, 'playback_peak': round(score, 3)}


def save_sheet(sheet, path):
    # Encode first, then publish through a unique temp name. The running pet
    # reads this directory, so it must never observe a half-written sheet; a
    # fresh name also sidesteps Windows filter drivers that intermittently
    # reject reopening a just-created file with EINVAL.
    buffer = io.BytesIO()
    sheet.save(buffer, format='PNG', optimize=True)
    payload = buffer.getvalue()
    for attempt in range(4):
        temporary = path.with_name(f'{path.name}.{os.getpid()}.{attempt}.tmp')
        try:
            temporary.write_bytes(payload)
            os.replace(temporary, path)
            return
        except OSError:
            temporary.unlink(missing_ok=True)
            if attempt == 3:
                raise
            time.sleep(.35*(attempt+1))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--actions', nargs='*')
    args = parser.parse_args()
    cv2.setNumThreads(1)
    OUTPUT.mkdir(parents=True, exist_ok=True)
    manifest_path, report_path = OUTPUT/'manifest.json', OUTPUT/'quality-report.json'
    selected = set(args.actions or ())
    previous = json.loads(manifest_path.read_text(encoding='utf-8')) if selected and manifest_path.exists() else {}
    report = json.loads(report_path.read_text(encoding='utf-8')) if selected and report_path.exists() else {}
    # A partial rebuild must keep every untouched warp: `--actions` is how new
    # atlases are added without discarding the reviewed manifest.
    pairs = {key: value for key, value in previous.get('pairs', {}).items()
             if key.split(':', 1)[0] not in selected}
    for key in set(previous.get('pairs', {})) - set(pairs):
        (OUTPUT/previous['pairs'][key]['file']).unlink(missing_ok=True)
    hashes = {key: value for key, value in previous.get('source_sha256', {}).items()
              if key not in selected}
    report = {key: value for key, value in report.items() if key.split(':', 1)[0] not in selected}
    atlases = {}
    def frame(ref):
        key, index = ref
        if key not in atlases:
            path = ROOT/'assets'/catalog()[key]['atlas']
            atlases[key] = np.array(Image.open(path).convert('RGBA'))
            hashes[key] = hashlib.sha256(path.read_bytes()).hexdigest()
        cols = catalog()[key]['columns']
        return atlases[key][index//cols*256:index//cols*256+256,
                            index%cols*256:index%cols*256+256].copy()
    profile = alignment_profile()
    for n, (a, b) in enumerate(graph()):
        if selected and a[0] not in selected:
            continue
        key = f'{a[0]}:{a[1]}>{b[0]}:{b[1]}'
        frames, review = interpolate(frame(a), frame(b), a, b, profile)
        report[key] = review
        if not review['accepted']:
            continue
        name = f'{a[0]}_{a[1]}--{b[0]}_{b[1]}.png'
        sheet = Image.new('RGBA', (256*COLUMNS, 256*((FRAMES+COLUMNS-1)//COLUMNS)))
        for i, image in enumerate(frames):
            sheet.paste(Image.fromarray(image), (i%COLUMNS*256, i//COLUMNS*256))
        save_sheet(sheet, OUTPUT/name)
        pairs[key] = {'file': name, 'frames': FRAMES, 'columns': COLUMNS}
        if n % 20 == 0:
            print(f'{n}: {key}', flush=True)
    payload = {'version': 1, 'method': 'single-source-bidirectional-warp',
               'source_sha256': hashes, 'pairs': pairs}
    # Readers may hold the live manifest during a build on Windows. Publish a
    # complete replacement instead of truncating a file used by the desktop.
    temporary = manifest_path.with_suffix('.pending.json')
    temporary.write_text(json.dumps(payload, indent=2), encoding='utf-8')
    temporary.replace(manifest_path)
    temporary = report_path.with_suffix('.pending.json')
    temporary.write_text(json.dumps(report, indent=2), encoding='utf-8')
    temporary.replace(report_path)
    print(f'Accepted {len(pairs)}/{len(report)} transitions', flush=True)


if __name__ == '__main__':
    main()
