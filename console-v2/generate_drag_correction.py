from pathlib import Path
import subprocess,sys
root=Path(__file__).resolve().parent
folder=root/'action-work/drag-resist'
prompt='''One full body illustration of the exact reference white-haired cat-eared girl in blue dress, for transparent desktop pet animation. Both connected arms reach diagonally to the IMAGE RIGHT, UP RIGHT. Her two palms close together at x380,y95 on a 512 square canvas. Head x256,y140, eyes looking UP RIGHT toward hands, determined cute pout, torso counterleans to IMAGE LEFT, feet dangling around y450. Viewer sees her front, original snowflake on viewer right, do not mirror accessories. Anatomically clear two arms, two hands gathered at one point. Pure flat green background. Delicate anime chibi illustration matching reference, no cursor, no text. The hands MUST be on the RIGHT side of her head, never left. Entire figure with clear margin.'''
(folder/'prompt-upper-right.txt').write_text(prompt,encoding='utf-8')
refs=Path('C:/Users/meursault/Desktop/desktop-pet/图片')
subprocess.run([sys.executable,'C:/Users/meursault/.codex/skills/shengtu-skill/scripts/generate_image.py','--provider','gpt','--mode','edit','--quality','high','--size','1024x1024','--prompt',prompt,'--image',str(refs/'参考图.png'),'--image',str(refs/'三视图.png'),'--out',str(folder/'upper-right.png')],check=True)
