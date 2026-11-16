"""Generate eight complete back-walk frames through shengtu-skill."""
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[1]
GEN = Path(r"C:\Users\meursault\.codex\skills\shengtu-skill\scripts\generate_image.py")
REF = ROOT / "output/yuki-back-walk-idle-reference-single.png"
OUT = ROOT / "output"

poses = [
    "neutral contact pose, both feet flat and parallel under the skirt",
    "left foot stepping forward, left knee slightly bent and lifted, right foot planted",
    "left foot at the highest point of the step, clearly lifted forward, right foot planted",
    "left foot lowering toward the ground, right foot still supporting, balanced transition",
    "neutral contact pose, both feet flat and parallel under the skirt",
    "right foot stepping forward, right knee slightly bent and lifted, left foot planted",
    "right foot at the highest point of the step, clearly lifted forward, left foot planted",
    "right foot lowering toward the ground, left foot still supporting, balanced transition",
]

base = (
    "Create ONE complete full-body back-facing walking frame of this exact character. "
    "Use the reference as the fixed design: same idle anime illustration style, pale icy-blue and white palette, "
    "same head size, long hair silhouette, dress width, lace hem, sock color, shoe color, and body proportions. "
    "The entire character from cat ears to both shoe soles must fit inside the image with generous transparent margin. "
    "Transparent background only. No checkerboard, white background, black background, text, extra limbs, cut-off legs, "
    "blocky artifacts, or merged frames. Keep head, skirt, and camera position fixed; only the walking pose changes. "
)

for i, pose in enumerate(poses, 1):
    out = OUT / f"yuki-back-walk-full-frame-v5-{i:02d}.png"
    prompt = base + pose + "."
    cmd = ["python", str(GEN), "--provider", "gemini", "--mode", "edit",
           "--image", str(REF), "--size", "1024x1024", "--out", str(out),
           "--prompt", prompt, "--quality", "high"]
    subprocess.run(cmd, cwd=ROOT, check=True)
    print(out.name, flush=True)
