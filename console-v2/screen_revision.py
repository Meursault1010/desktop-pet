"""Reference-grounded pocket screen still sequence. Never overwrites original art."""
import subprocess
import sys
from pathlib import Path

ROOT=Path(__file__).resolve().parent
OUT=ROOT/'action-work/screen-v2'
REF=Path('C:/Users/meursault/Desktop/desktop-pet/图片')
PROMPT='''Create a production animation KEYFRAME SHEET, EXACTLY 3 columns by 4 rows, 12 equal square cells in row-major chronological order. Each cell contains exactly ONE full-body character. Fixed camera, identical body size, feet ground baseline and lighting except local screen illumination. Plain flat pure green #00ff00 backdrop, NO checkerboard, NO grid, NO captions, NO numbers, NO floor shadows. Generous separation and margins, nothing crosses cell boundaries.

IDENTITY: Precisely preserve the attached main reference and turnaround: chibi pixel-art/anime sprite hybrid, very large head, white long wavy hair, white cat ears, blue eyes, original blue off-shoulder snowflake dress, blue belt/gold buckle, blue shoes, snowflake clip on VIEWER RIGHT, matching earrings. No costume redesign, extra accessories, hats or glasses. The third image shows the OLD WRONG action: use it ONLY for identity and small blue device design. Correct it, do NOT copy its outward-facing screen or prop disappearance.

ACTION: she reaches into a discreet existing side-seam pocket at HER LEFT hip (VIEWER RIGHT), takes out ONE small pocket electronic touch-screen, holds it with HER LEFT hand continuously, then uses HER RIGHT index finger to tap and swipe. Device is a rigid rectangular slim blue handheld screen, landscape orientation, same dimensions and design throughout, not a book, not a folding game console, no keyboard. NO second device. No hologram. Screen must face HER FACE (tilted upward/inward), not displayed squarely toward camera; viewer sees its back/edge and at most an oblique sliver of screen. Use slight three-quarter head tilt only while body stays frontal.

PHYSICS / CONTINUITY: from frame 3 onward LEFT palm and fingers physically grip underside/left end in every frame. Device never floats, disappears, changes hand, duplicates or abruptly changes size. RIGHT index visibly touches the inward-facing glass in operating frames. Her eyes look DOWN at device, not straight at viewer. Cyan light from the device gently but clearly illuminates underside of cheeks, chin, nose and fingers with blue eye reflections. Do NOT tint entire image blue, bleach the face, or change global brightness. In frames 6 through 12 screen brightness and local face-light intensity are steady.

TWELVE POSES:
1 neutral standing, left fingertips approach left skirt side-seam pocket, right arm relaxed; screen still in pocket.
2 left hand inserted into pocket, visible top rim of blue device emerging.
3 device half pulled out, left fingers gripping it firmly; right hand begins to lift.
4 device completely out, held near left waist by left hand, right hand approaching; screen not yet lit.
5 same left hand raises device to lower chest and rotates screen inward/up toward her, faint power-on glow on chin.
6 device stable at lower chest, LEFT hand supporting, face lowered looking at it; stable cyan face and finger illumination.
7 same device location and left grip, right index approaches touchscreen, concentrated gaze.
8 right index makes first tap on screen, same stable device and local face illumination.
9 right index lifted a few millimeters after tap, eyes track the screen, device still held.
10 right index swipes horizontally across inward-facing screen, left grip unchanged.
11 right index makes a second small tap, focused expression, screen remains in same hand.
12 right index relaxes hovering close to screen, she keeps holding and viewing it with soft contentment; same pose, device position and light as frame6. Do NOT put away device. Do NOT return to empty-handed idle.

Consecutive poses should differ only incrementally. Preserve fine pixel-like blue outlines and dress details. All twelve cells must be distinct, readable, consistent animation stills, not twelve unrelated illustrations.'''

if __name__=='__main__':
    OUT.mkdir(parents=True,exist_ok=True)
    (OUT/'prompt.txt').write_text(PROMPT,encoding='utf-8')
    if not (OUT/'raw.png').exists():
        subprocess.run([sys.executable,'C:/Users/meursault/.codex/skills/shengtu-skill/scripts/generate_image.py','--provider','gpt','--mode','edit','--quality','medium','--size','1536x2048','--prompt',PROMPT,'--image',str(REF/'参考图.png'),'--image',str(REF/'三视图.png'),'--image',str(REF/'口袋电子屏幕动作/frame_05.png'),'--out',str(OUT/'raw.png')],check=True)
