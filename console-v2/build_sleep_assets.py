"""Bake approved master breathing at runtime resolution, with premultiplied remap."""
import sys
from pathlib import Path
from PIL import Image

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT/'action-work'/'sleep-v3-preview'))
from prepare_sleep_master import breathing

def main():
    master = Image.open(ROOT/'action-work/sleep-v3-preview/sleep-right-02-master.png').convert('RGBA')
    target = ROOT/'assets/sleep'
    target.mkdir(exist_ok=True)
    for i in range(96):
        breathing(master, i/20).resize((340, 328), Image.Resampling.LANCZOS).save(target/f'{i:02}.png')

if __name__ == '__main__':
    main()
