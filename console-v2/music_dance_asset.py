"""Decode bounded dance pages on a worker; keep at most four cached pages."""
from collections import OrderedDict
from concurrent.futures import ThreadPoolExecutor
import json
from pathlib import Path
from PySide6.QtCore import QRect
from PySide6.QtGui import QImage

ACTION_ID='music-waltz'
ROOT=Path(__file__).resolve().parent/'assets/actions'/ACTION_ID
_decoder=ThreadPoolExecutor(max_workers=1,thread_name_prefix='yuki-music-atlas')
_tasks=OrderedDict()
_manifest=None
_last=None
_last_index=None


def displayed_frame():
    return _last_index


def metadata():
    global _manifest
    if _manifest is None:
        _manifest=json.loads((ROOT/'pages.json').read_text(encoding='utf-8'))
    return _manifest


def preload(page=0):
    meta=metadata()
    page=max(0,min(len(meta['pages'])-1,page))
    if page not in _tasks:
        _tasks[page]=_decoder.submit(QImage,str(ROOT/meta['pages'][page]['file']))
    _tasks.move_to_end(page)
    # The first page remains warm for a new dance session.
    for old in list(_tasks):
        if len(_tasks)<=4:break
        if old not in (0,page):
            task=_tasks.pop(old)
            if not task.done():task.cancel()
    return _tasks[page]


def ready():
    task=preload()
    return task.done() and not task.cancelled() and task.exception() is None and not task.result().isNull()


def image():
    return preload().result() if ready() else None


def frame(index):
    """Return a decoded page and local cell, holding the last pose during IO."""
    global _last,_last_index
    meta=metadata();per_page=meta['per_page'];columns=meta['columns']
    page=max(0,min(len(meta['pages'])-1,index//per_page))
    task=preload(page)
    preload((page+1)%len(meta['pages']))
    if task.done() and not task.cancelled() and task.exception() is None:
        atlas=task.result()
        if not atlas.isNull():
            local=index-meta['pages'][page]['first']
            _last=(atlas,QRect(local%columns*256,local//columns*256,256,256))
            _last_index=index
    return _last
