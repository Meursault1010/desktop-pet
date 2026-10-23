from pathlib import Path
from PIL import Image, ImageDraw, ImageFilter
import math

ROOT = Path(__file__).parent
frames_dir = ROOT.parent / "waltz-preview" / "frames"
sprites = [Image.open(frames_dir / f"{i:02}.png").convert("RGBA") for i in range(1, 9)]
W, H = 720, 520
cx, floor = W // 2, 430
frames = []
N = 96

for k in range(N):
    t = k / N
    phase = 2 * math.pi * t
    # Waltz steps carry the character along a shallow oval; pauses land on the beat.
    x = cx + 118 * math.sin(phase) + 18 * math.sin(2 * phase)
    depth = math.cos(phase)
    scale = 0.70 + 0.08 * (depth + 1) / 2
    lift = 9 + 12 * max(0, math.sin(2 * phase + 0.5))
    bob = 2.2 * math.sin(6 * phase)
    idx = int((t * 8) % 8)
    src = sprites[idx]
    sw, sh = src.size
    # Controlled depth cue: tiny perspective scaling and a slight turn, never a flat glide.
    angle = 2.2 * math.sin(phase) + 0.8 * math.sin(2 * phase)
    nw, nh = max(1, round(sw * scale)), max(1, round(sh * scale))
    sprite = src.resize((nw, nh), Image.Resampling.LANCZOS).rotate(angle, resample=Image.Resampling.BICUBIC, expand=True)

    canvas = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    # Contact shadow grows slightly as Yuki comes closer and softens on each lifted step.
    shadow_w = int(94 * scale * (1.0 + 0.10 * depth))
    shadow_h = max(7, int(12 * scale))
    alpha = int(54 * (1 - 0.25 * (lift - 9) / 12))
    shadow = Image.new("RGBA", (shadow_w + 28, shadow_h + 22), (0, 0, 0, 0))
    sd = ImageDraw.Draw(shadow)
    sd.ellipse((14, 7, 14 + shadow_w, 7 + shadow_h), fill=(45, 79, 126, alpha))
    shadow = shadow.filter(ImageFilter.GaussianBlur(7))
    canvas.alpha_composite(shadow, (round(x - shadow.width / 2), floor - 8))

    px = round(x - sprite.width / 2)
    py = round(floor - lift - bob - sprite.height)
    canvas.alpha_composite(sprite, (px, py))
    frames.append(canvas)

frames[0].save(ROOT / "waltz-2p5d-preview.gif", save_all=True, append_images=frames[1:], duration=48, loop=0, disposal=2, optimize=False)
frames[0].save(ROOT / "waltz-2p5d-preview.png")
print(ROOT / "waltz-2p5d-preview.gif")
