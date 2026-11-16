from pathlib import Path
import subprocess
import time

ROOT = Path(__file__).resolve().parents[1]
GEN = Path(r"C:\Users\meursault\.codex\skills\shengtu-skill\scripts\generate_image.py")
REF = ROOT / "output/yuki-back-walk-idle-reference-single.png"
OUT = ROOT / "output"
poses = {
    "pass": "the leg on the IMAGE RIGHT is passing forward under the skirt while the IMAGE LEFT foot supports, both shoes fully visible",
    "peak": "the leg on the IMAGE RIGHT is lifted forward at medium height with a relaxed bent knee while the IMAGE LEFT foot supports, natural walking pose",
    "lower": "the leg on the IMAGE RIGHT is lowering toward the ground after the forward step while the IMAGE LEFT foot supports, balanced transition",
}
base = ("Re-render ONE complete centered full-body back-facing walking frame using this character reference. "
        "Keep the exact idle anime style, pale icy-blue and white palette, hair, snowflake hair clip on the IMAGE LEFT, "
        "dress, lace hem, white socks, blue shoes, body proportions and scale. The entire character from ears to shoe soles "
        "must fit inside a 1024x1024 transparent checkerboard canvas. Keep the head center at x=512 and shoe baseline fixed. "
        "Do not create a sprite sheet, do not crop, do not add a background, no extra limbs, no broken legs, no blocks. ")
for name, pose in poses.items():
    out = OUT / f"yuki-back-walk-right-{name}-v12.png"
    cmd = ["python", str(GEN), "--provider", "gpt", "--mode", "edit", "--image", str(REF),
           "--size", "1024x1024", "--out", str(out), "--prompt", base + pose + ".", "--quality", "high"]
    for attempt in range(3):
        try:
            subprocess.run(cmd, cwd=ROOT, check=True)
            break
        except subprocess.CalledProcessError:
            if attempt == 2:
                raise
            time.sleep(3)
    print(out.name, flush=True)
