"""One targeted gateway edit: keep all artwork, replace baked checkerboard."""
import subprocess
import sys
from pathlib import Path
root=Path(__file__).parent/'action-work/icon-sleep-v2'
prompt='''Change ONLY the BACKGROUND of this exact 2 by 2 character sprite sheet. Replace every grey/white checkerboard background square with ONE perfectly flat solid chroma green RGB(0,255,0), hex #00FF00, including all gaps between hair strands and between limbs. The input has a BAKED-IN checkerboard, it is not transparent. Remove that checkerboard completely. Keep all FOUR characters absolutely unchanged: same exact poses, same exact pixel positions and size, same white hair, same faces, clothes, snowflakes, blue outlines and colors, same layout and same 1536x1536 canvas. Do NOT redraw characters or add details. Do NOT add shadow or green reflections to white hair. No transparency simulation or checkerboard anywhere. Only replace background with flat pure green for subsequent deterministic color keying.'''
if __name__=='__main__':
    subprocess.run([sys.executable,'C:/Users/meursault/.codex/skills/shengtu-skill/scripts/generate_image.py',
                    '--provider','gpt','--mode','edit','--quality','high','--size','1536x1536',
                    '--prompt',prompt,'--image',str(root/'raw.png'),'--out',str(root/'raw-chroma.png')],check=True)
