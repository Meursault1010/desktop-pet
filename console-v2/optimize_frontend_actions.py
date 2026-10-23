"""Rebuild the console action mirror as lossless WebP without losing a pixel.

The desktop backend keeps using assets/actions/*.png; only the read-only
frontend copy is converted. Posters are downscaled to 512px because the action
grid never renders them larger than ~130 CSS pixels.
"""
import argparse
import io
import json
import shutil
import time
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parent
SOURCE = ROOT / 'assets' / 'actions'
PUBLIC = ROOT / 'frontend' / 'public' / 'actions'
POSTER_EDGE = 512


def lossless_webp(image, method=6):
    buffer = io.BytesIO()
    # exact keeps the RGB values of fully transparent pixels, which libwebp
    # otherwise normalizes; without it the decode is not byte-identical.
    image.save(buffer, 'WEBP', lossless=True, quality=100, method=method, exact=True)
    return buffer.getvalue()


def verify(original, payload, label):
    decoded = Image.open(io.BytesIO(payload)).convert('RGBA')
    if decoded.size != original.size:
        raise RuntimeError(f'{label}: size changed {original.size} -> {decoded.size}')
    if decoded.tobytes() != original.tobytes():
        raise RuntimeError(f'{label}: lossless WebP is not pixel-identical')


def convert_atlas(action, force):
    source = SOURCE / action['id'] / 'atlas.png'
    target = PUBLIC / action['id'] / 'atlas.webp'
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.exists() and not force and target.stat().st_mtime >= source.stat().st_mtime:
        target.with_suffix('.png').unlink(missing_ok=True)
        return target.stat().st_size, 0
    with Image.open(source) as image:
        image = image.convert('RGBA')
        payload = lossless_webp(image)
        verify(image, payload, action['id'] + '/atlas')
    target.write_bytes(payload)
    for stale in (target.with_suffix('.png'),):
        if stale.exists():
            stale.unlink()
    return len(payload), source.stat().st_size


def convert_poster(action, force):
    source = SOURCE / action['id'] / 'poster.png'
    target = PUBLIC / action['id'] / 'poster.webp'
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.exists() and not force and target.stat().st_mtime >= source.stat().st_mtime:
        target.with_suffix('.png').unlink(missing_ok=True)
        return target.stat().st_size, 0
    with Image.open(source) as image:
        image = image.convert('RGBA')
        image.thumbnail((POSTER_EDGE, POSTER_EDGE), Image.Resampling.LANCZOS)
        payload = lossless_webp(image, method=6)
        verify(image, payload, action['id'] + '/poster')
    target.write_bytes(payload)
    stale = target.with_suffix('.png')
    if stale.exists():
        stale.unlink()
    return len(payload), source.stat().st_size


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--force', action='store_true', help='re-encode even when the WebP is newer')
    args = parser.parse_args()
    catalog = json.loads((SOURCE / 'catalog.json').read_text(encoding='utf-8'))
    started = time.time()
    before = after = 0
    for action in catalog:
        for kind, converter in (('atlas', convert_atlas), ('poster', convert_poster)):
            new, old = converter(action, args.force)
            after += new
            before += old
            action[kind] = action[kind][:-4] + '.webp'
            print(f"{action['id']:22s} {kind:6s} {old/1048576:7.2f} -> {new/1048576:6.2f} MB", flush=True)
        folder = PUBLIC / action['id']
        for frame in folder.glob('[0-9][0-9].png'):
            frame.unlink()
    known = {action['id'] for action in catalog}
    for folder in PUBLIC.iterdir():
        if folder.is_dir() and folder.name not in known:
            shutil.rmtree(folder)
            print(f'removed uncatalogued mirror {folder.name}')
    (PUBLIC / 'catalog.json').write_text(json.dumps(catalog, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    if before:
        print(f'\n{len(catalog)} actions, {before/1048576:.1f} MB of source raster -> {after/1048576:.1f} MB WebP '
              f'({(1-after/before)*100:.1f}% smaller) in {time.time()-started:.1f}s')
    else:
        print(f'\n{len(catalog)} actions already mirrored at {after/1048576:.1f} MB in {time.time()-started:.1f}s')


if __name__ == '__main__':
    main()
