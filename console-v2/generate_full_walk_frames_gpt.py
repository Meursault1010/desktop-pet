"""Generate eight complete back-walk frames with GPT image editing."""
from pathlib import Path
import subprocess
import time

ROOT = Path(__file__).resolve().parents[1]
GEN = Path(r"C:\Users\meursault\.codex\skills\shengtu-skill\scripts\generate_image.py")
REF = ROOT / "output/yuki-back-walk-idle-reference-single.png"
OUT = ROOT / "output"

poses = [
    "neutral contact pose, both feet flat and parallel under the skirt",
    "left foot stepping forward and lifted, right foot planted, natural counterbalance",
    "left foot at the highest point of the step, clearly lifted forward, right foot planted",
    "left foot lowering toward the ground, right foot supporting, balanced transition",
    "neutral contact pose, both feet flat and parallel under the skirt",
    "right foot stepping forward and lifted, left foot planted, natural counterbalance",
    "right foot at the highest point of the step, clearly lifted forward, left foot planted",
    "right foot lowering toward the ground, left foot supporting, balanced transition",
]

base = (
    "Re-render ONE complete full-body back-facing walking frame using this exact character as the reference. "
    "Keep the same idle anime illustration style, pale icy-blue and white palette, head size, long hair silhouette, "
    "dress width, lace hem, sock pattern and blue shoe design. Keep the entire character centered and fully visible "
    "from cat ears to both shoe soles, with generous margin. Transparent background only, shown as the editor's "
    "checkerboard transparency. Keep the camera, scale, body proportions, skirt hem and hair length fixed; only the "
    "walking pose changes. Do not create a sprite sheet, do not crop, do not add a background, no text, no extra limbs, "
    "no broken legs, no blocks, no missing skirt edge. "
)

for i, pose in enumerate(poses, 1):
    out = OUT / f"yuki-back-walk-full-frame-v6-{i:02d}.png"
    prompt = base + pose + "."
    cmd = ["python", str(GEN), "--provider", "gpt", "--mode", "edit",
           "--image", str(REF), "--size", "1024x1024", "--out", str(out),
           "--prompt", prompt, "--quality", "high"]
    for attempt in range(3):
        try:
            subprocess.run(cmd, cwd=ROOT, check=True)
            break
        except subprocess.CalledProcessError:
            if attempt == 2:
                raise
            time.sleep(3)
    print(out.name, flush=True)
