"""Subframe translations that correct sprite-sheet composition drift."""
import json
from functools import lru_cache
from pathlib import Path


@lru_cache(maxsize=1)
def _data():
    path = Path(__file__).resolve().parent/'assets/actions/frame-alignment.json'
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding='utf-8'))


def profile():
    return _data().get('actions', {})


def offset_for(before, after=None, progress=0.):
    """Return the canvas correction, interpolated with the pose transition."""
    if not before:
        return 0., 0.
    after = before if after is None else after

    def frame_offset(reference):
        action_id, frame = reference
        action = profile().get(action_id)
        if action is None or not isinstance(frame, int) or not 0 <= frame < len(action['offsets']):
            return 0., 0.
        return action['offsets'][frame]

    amount = max(0., min(1., float(progress)))
    pair = f'{before[0]}:{before[1]}>{after[0]}:{after[1]}'
    samples = _data().get('transitions', {}).get(pair)
    if samples:
        position = amount*(len(samples)-1)
        index = int(position)
        start, end = samples[index], samples[min(index+1, len(samples)-1)]
        amount = position-index
    else:
        start = frame_offset(before)
        end = frame_offset(after)
    return (start[0]+(end[0]-start[0])*amount,
            start[1]+(end[1]-start[1])*amount)
