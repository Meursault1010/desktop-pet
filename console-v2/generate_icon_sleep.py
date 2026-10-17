"""Generate prop-free sleep poses from user-approved character references."""
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
OUT = ROOT/'action-work/icon-sleep'
PROMPT = '''Create ONE character sprite sheet with EXACTLY THREE equal SQUARE cells in ONE horizontal row, 1536x512 canvas. One same full-body chibi character per cell. Flat solid chroma green #00ff00 background. No gutters, no text, no shadows. Full body fits with 15 percent empty margin, SAME scale and baseline in all three cells.
Identity: reproduce attached reference and turnaround accurately: long white wavy hair, white cat ears, blue snowflake dress, blue shoes, snowflake hairclip on VIEWER RIGHT. Same original pixel-like anime/chibi sprite art, outline, proportions and clothing details.
All three characters are SITTING ON THE FLOOR, legs gently stretched in front, eyes closed sleeping, arms relaxed in lap, head gently resting against an INVISIBLE small support behind her shoulder. NO folder, file, book, pillow, chair, wall, icon, furniture or any prop whatsoever. Only character on green background. Do not draw the invisible support.
LEFT CELL: seated at the LEFT side of an imaginary support, leaning gently toward VIEWER RIGHT with rightmost shoulder/back touching the imaginary support. Face mostly toward viewer, slight three-quarter view. Her head inclines gently toward viewer right.
CENTER CELL: seated centrally behind imaginary low support, frontal body, head gently bowed, hands resting in lap, legs extend toward viewer, eyes closed peacefully. Full face still visible.
RIGHT CELL: seated at the RIGHT side of an imaginary support, leaning gently toward VIEWER LEFT, leftmost shoulder/back touching imaginary support. Face mostly toward viewer, slight three-quarter view. Her head inclines toward viewer left.
IMPORTANT: do not mirror asymmetric costume elements or move snowflake hairclip to the wrong side. These are three companion angles of SAME character. No glow, no brightness differences. Only one still pose per cell; breathing will be animated in code. Peaceful, naturally supported sleeping poses, NOT standing, NOT lying flat.'''

if __name__ == '__main__':
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT/'prompt.txt').write_text(PROMPT, encoding='utf-8')
    if not (OUT/'raw.png').exists():
        refs=Path('C:/Users/meursault/Desktop/desktop-pet/图片')
        subprocess.run([sys.executable, 'C:/Users/meursault/.codex/skills/shengtu-skill/scripts/generate_image.py', '--provider','gpt','--mode','edit','--quality','medium','--size','1536x512','--prompt',PROMPT,'--image',str(refs/'参考图.png'),'--image',str(refs/'三视图.png'),'--out',str(OUT/'raw.png')],check=True)
