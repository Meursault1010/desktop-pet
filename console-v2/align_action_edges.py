"""Align one action's frame line weight to its own key poses.

For clips that are not rebuilt by build_smoothed_actions (hand-tuned schedules
such as yawn), the warped in-betweens still come out softer than the key poses.
This lifts every frame below 92% of the key poses' median edge strength and
rebuilds the atlas, leaving frame count and timing untouched.
"""
import json
import sys
from pathlib import Path

import numpy as np
from PIL import Image

from build_smoothed_actions import build_atlas, edge_strength, load_frame, match_edge

ROOT = Path(__file__).resolve().parent
ACTIONS = ROOT / 'assets' / 'actions'


def main():
    action = sys.argv[1]
    folder = ACTIONS / action
    source = ROOT / 'action-work' / 'smooth' / action / 'original'
    entry = next(item for item in json.loads((ACTIONS / 'catalog.json').read_text(encoding='utf-8'))
                 if item['id'] == action)
    key_edges = [edge_strength(load_frame(path)) for path in sorted(source.glob('[0-9][0-9].png'))]
    target = float(np.median(key_edges))
    frames = []
    lifted = 0
    for path in sorted(folder.glob('[0-9][0-9].png')):
        frame = load_frame(path)
        if edge_strength(frame) < target * 0.92:
            frame, _ = match_edge(frame, target)
            lifted += 1
        frames.append(frame)
        Image.fromarray(frame).save(path)
    atlas = build_atlas(frames, entry.get('columns', 4))
    atlas.save(folder / 'atlas.png')
    Image.fromarray(frames[0]).save(folder / 'poster.png')
    print(f'{action}: lifted {lifted}/{len(frames)} frames to edge {target:.2f}')


if __name__ == '__main__':
    main()
