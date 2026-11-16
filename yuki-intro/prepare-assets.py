"""Package the existing Yuki animations as deterministic sprite sheets."""

from pathlib import Path
import json
from PIL import Image

HERE = Path(__file__).resolve().parent
SOURCE = HERE.parent / "console-v2" / "assets" / "actions"
OUT = HERE / "assets"
CELL = 256
COLUMNS = 8
OUT.mkdir(exist_ok=True)


def load_image(path):
    with Image.open(path) as image:
        return image.convert("RGBA")


def pack(name, frames):
    rows = (len(frames) + COLUMNS - 1) // COLUMNS
    sheet = Image.new("RGBA", (COLUMNS * CELL, rows * CELL))
    for i, frame in enumerate(frames):
        if frame.size != (CELL, CELL):
            raise ValueError(f"{name}: unexpected frame size {frame.size}")
        sheet.paste(frame, (i % COLUMNS * CELL, i // COLUMNS * CELL))
    sheet.save(OUT / f"{name}.webp", lossless=True, method=4)
    return len(frames)


clips = {}
for name in ["wave", "play-peek", "smile", "reading-pose-1", "sit-swing"]:
    paths = sorted(p for p in (SOURCE / name).glob("*.png") if p.stem.isdecimal())
    clips[name] = pack(name, [load_image(p) for p in paths])

atlas = load_image(SOURCE / "music-waltz" / "atlas.png")
dance = []
for i in range(104):
    x, y = i % 10 * CELL, i // 10 * CELL
    dance.append(atlas.crop((x, y, x + CELL, y + CELL)))
clips["music-waltz"] = pack("music-waltz", dance)
(OUT / "clips.json").write_text(json.dumps(clips, indent=2) + "\n", encoding="utf-8")
