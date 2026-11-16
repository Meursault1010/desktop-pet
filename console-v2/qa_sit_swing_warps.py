"""Audit the rebuilt sit-swing warps: exact endpoints, and no re-introduced slide."""
import json
import sys
from pathlib import Path

import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
MOTION = ROOT / 'assets/action-motion'
ASSETS = ROOT / 'assets/actions'


def cells(atlas_path, count, columns=4):
    atlas = np.asarray(Image.open(atlas_path).convert('RGBA'))
    return [atlas[i // columns * 256:(i // columns + 1) * 256,
                   i % columns * 256:(i % columns + 1) * 256] for i in range(count)]


def landmarks(cell):
    alpha = cell[:, :, 3]
    ys, xs = np.nonzero(alpha >= 32)
    top, bottom = int(ys.min()), int(ys.max())
    crown = ys < top + int((bottom - top + 1) * .22)
    return float(xs[crown].mean()), bottom, int(xs.min()), int(xs.max())


def main():
    from action_player import catalog

    action = catalog()['sit-swing']
    shipped = cells(ROOT / 'assets' / action['atlas'], action['frames'])
    manifest = json.loads((MOTION / 'manifest.json').read_text(encoding='utf-8'))
    report = json.loads((MOTION / 'quality-report.json').read_text(encoding='utf-8'))
    pairs = {key: value for key, value in manifest['pairs'].items() if key.startswith('sit-swing:')}
    print(f'{len(pairs)} rebuilt pairs')
    worst_head = worst_floor = 0.
    failures = []
    for key, entry in sorted(pairs.items()):
        (left, right) = key.split('>')
        a_id, a_frame = left.rsplit(':', 1)
        b_id, b_frame = right.rsplit(':', 1)
        strip = cells(MOTION / entry['file'], entry['frames'], entry['columns'])
        if not np.array_equal(strip[0], shipped[int(a_frame)]):
            failures.append(f'{key}: first cell is not the shipped pose')
        if not np.array_equal(strip[-1], shipped[int(b_frame)]):
            failures.append(f'{key}: last cell is not the shipped pose')
        marks = [landmarks(cell) for cell in strip]
        head = np.array([mark[0] for mark in marks])
        floor = np.array([mark[1] for mark in marks])
        left_edge = min(mark[2] for mark in marks)
        right_edge = max(mark[3] for mark in marks)
        worst_head = max(worst_head, float(head.max() - head.min()))
        worst_floor = max(worst_floor, float(floor.max() - floor.min()))
        step = report[key]
        print(f'{key:34s} head {head.min():6.1f}..{head.max():6.1f} '
              f'floor {floor.min()}..{floor.max()} box {left_edge}..{right_edge} '
              f'peak={step["playback_peak"]:5.1f} step={step["largest_step"]:5.1f} '
              f'raw={step["original_jump"]:5.1f} switch={step["switch"]}')
        if left_edge < 1 or right_edge > 254:
            failures.append(f'{key}: clipped at the canvas edge')
    print(f'worst head drift inside a strip: {worst_head:.1f}px, floor drift {worst_floor:.1f}px')
    print('accepted', len(pairs), '/', sum(1 for key in report if key.startswith('sit-swing:')))
    for line in failures:
        print('FAIL', line)
    return 1 if failures else 0


if __name__ == '__main__':
    raise SystemExit(main())
