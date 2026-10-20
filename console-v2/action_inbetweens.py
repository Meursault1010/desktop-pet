"""Read bounded, offline-built pose warps. No optical flow on the UI thread."""
import json
from collections import OrderedDict
from concurrent.futures import ThreadPoolExecutor
from functools import lru_cache
from pathlib import Path

import numpy as np
from PySide6.QtCore import QRect
from PySide6.QtGui import QImage, QPixmap

ROOT = Path(__file__).resolve().parent/'assets/action-motion'
_decoder = ThreadPoolExecutor(max_workers=1, thread_name_prefix='yuki-pose-decode')
_pending = OrderedDict()


def pair_key(before, after):
    return f'{before[0]}:{before[1]}>{after[0]}:{after[1]}'


@lru_cache(maxsize=1)
def manifest():
    path = ROOT/'manifest.json'
    return json.loads(path.read_text(encoding='utf-8'))['pairs'] if path.exists() else {}


@lru_cache(maxsize=6)
def strip(name):
    # QImage decoding is safe on a worker; QPixmap construction stays on Qt's
    # GUI thread. The renderer calls this only after the future is ready.
    return QPixmap.fromImage(prepare(name).result())


def prepare(name):
    if name not in _pending:
        _pending[name] = _decoder.submit(QImage, str(ROOT/name))
    _pending.move_to_end(name)
    while len(_pending) > 8:
        _, expired = _pending.popitem(last=False)
        expired.cancel()
    return _pending[name]


def sample_pose(before, after, progress):
    """Subframe sampling between neighbouring, already warped poses."""
    entry = manifest().get(pair_key(before, after))
    if entry is None or before == after:
        return None
    decoded = prepare(entry['file'])
    # Start prefetch during the authored hold, never wait for disk on input or
    # paint. If decoding is late, keep the approved original frame this tick.
    if progress <= 0 or not decoded.done() or decoded.cancelled():
        return None
    atlas = strip(entry['file'])
    if atlas.isNull():
        return None
    frame_position = min(entry['frames']-1, max(0., progress)*(entry['frames']-1))
    index = int(frame_position)
    columns = entry['columns']
    source = QRect(index % columns*256, index//columns*256, 256, 256)
    fraction = frame_position-index
    if fraction < 1e-4 or index+1 >= entry['frames']:
        return atlas, source
    next_index = index+1
    next_source = QRect(next_index % columns*256, next_index//columns*256, 256, 256)
    source_image = atlas.toImage()
    first = source_image.copy(source).convertToFormat(QImage.Format.Format_RGBA8888_Premultiplied)
    second = source_image.copy(next_source).convertToFormat(QImage.Format.Format_RGBA8888_Premultiplied)
    first_pixels = np.frombuffer(first.constBits(), dtype=np.uint8).reshape(256, 256, 4)
    second_pixels = np.frombuffer(second.constBits(), dtype=np.uint8).reshape(256, 256, 4)
    # Blend premultiplied colour and alpha directly; painter opacity with Plus
    # also attenuates the destination and causes brightness/alpha pumping.
    mixed = np.rint(first_pixels.astype(np.float32)*(1-fraction)
                    + second_pixels.astype(np.float32)*fraction).astype(np.uint8)
    image = QImage(mixed.data, 256, 256, 256*4,
                   QImage.Format.Format_RGBA8888_Premultiplied).copy()
    return image, QRect(0, 0, 256, 256)


def prefetch(pairs):
    for before, after in pairs:
        entry = manifest().get(pair_key(before, after))
        if entry:
            prepare(entry['file'])
