"""Read bounded, offline-built pose warps as display-ready frames.

Decoding and scaling run on one worker thread. The paint path only samples an
already prepared frame: no optical flow, QPixmap conversion or pixel blending
on the GUI thread.
"""
import json
from collections import OrderedDict
from concurrent.futures import ThreadPoolExecutor
from functools import lru_cache
from pathlib import Path

from PySide6.QtCore import QRect, Qt
from PySide6.QtGui import QImage

ROOT = Path(__file__).resolve().parent/'assets/action-motion'
# draw_pose composites actions into a 160x160 box. Prepare the warps above
# that box so the click jelly, which briefly enlarges the sprite, still
# downscales them; a 160px strip would be upscaled and soften the transition.
FRAME_SIZE = 256
# Five 256px pairs take about as much memory as the earlier twelve 160px ones.
MAX_PREPARED_PAIRS = 5
_decoder = ThreadPoolExecutor(max_workers=1, thread_name_prefix='yuki-pose-decode')
_pending = OrderedDict()
_prepared = OrderedDict()


def pair_key(before, after):
    return f'{before[0]}:{before[1]}>{after[0]}:{after[1]}'


@lru_cache(maxsize=1)
def manifest():
    path = ROOT/'manifest.json'
    return json.loads(path.read_text(encoding='utf-8'))['pairs'] if path.exists() else {}


def _decode(entry):
    atlas = QImage(str(ROOT/entry['file'])).convertToFormat(
        QImage.Format.Format_RGBA8888_Premultiplied)
    if atlas.isNull():
        return ()
    frames = entry['frames']
    columns = entry['columns']
    return tuple(
        atlas.copy(index % columns*256, index//columns*256, 256, 256).scaled(
            FRAME_SIZE, FRAME_SIZE, Qt.AspectRatioMode.IgnoreAspectRatio,
            Qt.TransformationMode.SmoothTransformation)
        for index in range(frames))


def prepare(entry):
    name = entry['file']
    if name not in _pending:
        _pending[name] = _decoder.submit(_decode, entry)
    _pending.move_to_end(name)
    while len(_pending) > MAX_PREPARED_PAIRS:
        _, expired = _pending.popitem(last=False)
        expired.cancel()
    return _pending[name]


def frames(entry):
    """Return prepared display frames, or None while the worker is still busy."""
    name = entry['file']
    cached = _prepared.get(name)
    if cached is not None:
        _prepared.move_to_end(name)
        return cached
    future = prepare(entry)
    # Never wait for disk or scaling during a repaint: the authored pose stays
    # on screen for this tick and the warp appears on the next ready frame.
    if not future.done() or future.cancelled():
        return None
    decoded = future.result()
    if not decoded:
        return None
    _prepared[name] = decoded
    _prepared.move_to_end(name)
    while len(_prepared) > MAX_PREPARED_PAIRS:
        _prepared.popitem(last=False)
    return decoded


def sample_pose(before, after, progress):
    """Sample the nearest prepared warp frame instead of blending pixels.

    Twenty-five frames cover at most a 340ms transition, so nearest sampling
    still advances faster than a 60Hz display while removing the per-tick
    numpy blend from the paint path.
    """
    entry = manifest().get(pair_key(before, after))
    if entry is None or before == after or progress <= 0:
        return None
    decoded = frames(entry)
    if decoded is None:
        return None
    index = round(min(1., max(0., progress))*(len(decoded)-1))
    frame = decoded[index]
    return frame, QRect(0, 0, frame.width(), frame.height())


def prefetch(pairs):
    for before, after in pairs:
        entry = manifest().get(pair_key(before, after))
        if entry:
            prepare(entry)
