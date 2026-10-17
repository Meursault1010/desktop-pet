"""Edit the existing directional poses without changing their palm anchors."""
from pathlib import Path
import subprocess, sys
from PIL import Image

root=Path(__file__).resolve().parent
short_arms='--short-arms' in sys.argv
out=root/('action-work/short-arm-drag' if short_arms else 'action-work/shy-drag')
out.mkdir(parents=True,exist_ok=True)
names=['upper-left','up','upper-right','left','down','right']
sheet=Image.new('RGBA',(1536,1024),(0,255,0,255))
for i,name in enumerate(names):
    image=Image.open(root/f'assets/drag-resist/{name}.png').convert('RGBA').resize((512,512))
    sheet.alpha_composite(image,((i%3)*512,(i//3)*512))
sheet.save(out/'reference.png')
prompt='''Edit this exact 3 by 2 sprite contact sheet. Preserve all six original full-body characters, the exact silhouettes, every limb, both hand cluster positions, camera, outfit, white hair, blue eyes, blue silver dress and scale. Change ONLY the facial expressions: adorable bashful surprise while gently picked up by a cursor, rosy pink cheeks, slightly raised worried inner eyebrows, shiny blue eyes glancing toward each existing hand cluster, tiny embarrassed surprised mouth, sweet shy flustered expression. Not sad, no crying, no pain, no anger. Both hands already cover the invisible mouse grab location; preserve their exact positions. Modest fully clothed innocent playful desktop companion. Elegant detailed anime illustration, no text, no marks, no cursor. Keep the exact uniform bright green background and identical 3 columns by 2 rows layout. No changes outside the face areas.'''
if short_arms:
    # Reuse the exact sheet whose upload was explicitly authorized in this task.
    source=root/'action-work/shy-drag/reference.png'
    (out/'reference.png').write_bytes(source.read_bytes())
    prompt='''Revise this exact 3 by 2 sprite sheet of the same fully clothed desktop companion. Important requested correction: BOTH ARMS MUST BE SHORTER, petite normal chibi anatomy. Each upper arm and forearm is about 30 percent shorter than the reference, compact soft bent elbows, tiny hands. The shoulders stay connected naturally to the torso. Both small hands cluster together and TRY to reach the same direction as in each reference cell but CANNOT QUITE REACH; adorable earnest reaching and softly flailing, no stretched rubber arms. Raised shoulders, cute flustered surprised blue eyes following the hands, rosy blushing cheeks, shy tiny open mouth. Keep exact original head, torso, dress, legs, hair, character scale and body position. Change arms and face only. Directions in reading order: upper left, up, upper right, left, down, right. Upper reaches have bent elbows and the hands stop near the upper forehead or side of head; sideways reaches stop near the cheek/chest instead of far outside the body; downward hands stop near waist. Gentle innocent bashful surprise, no anger or distress. Clear two connected arms, two hands close together, correct fingers. Same delicate detailed anime style and white hair blue silver dress. Full bodies fully within identical 3 columns 2 rows with empty margins, pure bright green background. No text, no frames, no cursor.'''
(out/'prompt.txt').write_text(prompt,encoding='utf-8')
subprocess.run([sys.executable,'C:/Users/meursault/.codex/skills/shengtu-skill/scripts/generate_image.py',
 '--provider','gpt','--mode','edit','--quality','high','--size','1536x1024',
 '--prompt',prompt,'--image',str(out/'reference.png'),'--out',str(out/'generated.png')],check=True)
