from pathlib import Path
from PIL import Image,ImageDraw,ImageFont,PngImagePlugin
import json,math,re
BASE=Path(__file__).resolve().parent
source=(BASE/'render_window_sizes.py').read_text(encoding='utf-8')
primitives=(BASE/'render_integrated_silver.py').read_text(encoding='utf-8').split('# Overview:')[0]
exec(primitives)
OUT=BASE/'theme-motion';OUT.mkdir(exist_ok=True)
compact='W,H=1120,800'+source.split('W,H=1120,800',1)[1].split("save_new('Yuki-融洽版-小窗口.png')",1)[0]
def button(x,y,w,t,ic=None,primary=False,dark=False):
    fill=C['deep'] if primary else PAPER
    ink=('#10283C' if C['bg']=='#0A111B' else '#FFFFFF') if primary else INK
    rr(x,y,w,38,fill,None if primary else EDGE,6)
    if ic:icon(ic,x+13,y+10,ink,17)
    text(x+(40 if ic else 17),y+9,t,13,ink,primary)
# Translate semantic UI inks only, never recolor character pixels.
palettes={
'雪白':{'C':dict(C),'INK':'#243C50','SUB':'#53697A','BLUE':'#276E94','PAPER':'#FCFDFE','SOFT':'#F1F6F9','EDGE':'#D2DFE8','map':{}},
'银雾':{'C':{'bg':'#CED8E1','paper':'#E8EEF3','ink':'#263D50','secondary':'#4C6477','muted':'#576C7D','line':'#BECDD9','nav':'#DAE4ED','blue':'#245F86','deep':'#234861'},'INK':'#263D50','SUB':'#4C6477','BLUE':'#245F86','PAPER':'#E8EEF3','SOFT':'#DDE8F0','EDGE':'#B8CBDA','map':{'#E6ECF1':'#CED8E1','#B7C7D4':'#A1B5C5','#EAF0F4':'#DAE4ED','#CCD9E3':'#BBCDDA','#EEF2F5':'#DAE4ED','#E0EDF6':'#E8F4FC','#F0F7FC':'#F1F7FC','#6C91AA':'#557C99','#E9F1F6':'#CFDFEB','#FFFFFF':'#F0F6FA','#C7D8E5':'#ACBFCE','#DFEBF4':'#CBDDEB','#D3DFE8':'#B9CBD9','#5D87A3':'#3D7196','#3D806F':'#2E6E5E'}},
'星夜':{'C':{'bg':'#0A111B','paper':'#121C29','ink':'#E1EAF3','secondary':'#A6B8C9','muted':'#99ADBF','line':'#34485D','nav':'#101925','blue':'#A7CCE8','deep':'#C4DDEF'},'INK':'#E1EAF3','SUB':'#A6B8C9','BLUE':'#A7CCE8','PAPER':'#121C29','SOFT':'#192838','EDGE':'#34485D','map':{'#E6ECF1':'#0A111B','#B7C7D4':'#3B5167','#EAF0F4':'#172331','#CCD9E3':'#34485D','#EEF2F5':'#101925','#E0EDF6':'#17344A','#F0F7FC':'#17344A','#6C91AA':'#8DAEC8','#E9F1F6':'#203347','#FFFFFF':'#344F68','#C7D8E5':'#53728C','#DFEBF4':'#2A4259','#D3DFE8':'#34485D','#5D87A3':'#91B8D5','#3D806F':'#95CABB'}}
}
for name,p in palettes.items():
    C=p['C'];INK=p['INK'];SUB=p['SUB'];BLUE=p['BLUE'];PAPER=p['PAPER'];SOFT=p['SOFT'];EDGE=p['EDGE']
    code=compact
    for a,b in p['map'].items():code=code.replace(a,b)
    exec(code)
    # Theme indicator lives in an existing quiet footer; no extra pane around the pet.
    rr(24,746,105,29,C['nav'],None,0)
    text(32,754,name+'主题',10,SUB)
    rr(405,18,307,25,C['nav'],None,0)
    center(558,25,name+' · 动态视觉预览',11,SUB)
    meta=PngImagePlugin.PngInfo();meta.add_text('Description','Yuki original theme preview, semantic surface colors only; original character pixels retained. Example data, not a live application screenshot.')
    path=OUT/('Yuki-'+name+'-小窗口.png')
    im.convert('RGB').resize((W,H),Image.Resampling.LANCZOS).save(path,pnginfo=meta)
    print(path)
# An editorial contact sheet compares exactly the same screen and states.
CW,CH=1860,568
board=Image.new('RGB',(CW,CH),'#DCE5ED');bd=ImageDraw.Draw(board)
headfont=ImageFont.truetype('C:/Windows/Fonts/msyhbd.ttc',20)
smallfont=ImageFont.truetype('C:/Windows/Fonts/msyh.ttc',13)
for i,(name,caption) in enumerate([('雪白','明亮清晰，适合白天与长时间阅读'),('银雾','更柔和的银蓝层次，减少纯白面积'),('星夜','低亮度深灰蓝，角色与页面共用背景')]):
    x=20+i*614
    bd.text((x,17),name,font=headfont,fill='#243C50')
    bd.text((x,51),caption,font=smallfont,fill='#53697A')
    pic=Image.open(OUT/('Yuki-'+name+'-小窗口.png')).convert('RGB');pic.thumbnail((594,425),Image.Resampling.LANCZOS)
    board.paste(pic,(x,84))
bd.text((20,535),'同一布局、同一角色素材；主题改变表面与文字层级。静态设计预览，数据均为示例。',font=smallfont,fill='#53697A')
board.save(OUT/'Yuki-三主题对照.png')
# Motion study: show theme crossfade and a gently moving sparse environment; no pet deformation.
images=[Image.open(OUT/('Yuki-'+name+'-小窗口.png')).convert('RGB') for name in ['雪白','银雾','星夜']]
frames=[];duration=9200;fps=16;count=round(duration/1000*fps)
for k in range(count):
    t=k/fps
    # hold 2.2 s per theme, 0.35 s transition between them.
    if t<2.4:idx=0;mix=0
    elif t<2.75:idx=0;mix=(t-2.4)/.35
    elif t<5.15:idx=1;mix=0
    elif t<5.5:idx=1;mix=(t-5.15)/.35
    elif t<8.6:idx=2;mix=0
    else:idx=2;mix=min(1,(t-8.6)/.35)
    mix=mix*mix*(3-2*mix)
    base=Image.blend(images[idx],images[(idx+1)%3],mix) if mix else images[idx].copy()
    draw=ImageDraw.Draw(base)
    # Star movement is 0.7 px/s in blank margin only, never over data or text.
    coords=[(383,83),(423,109),(504,77),(581,99),(659,82),(717,123),(776,98)]
    for j,(x,y) in enumerate(coords):
        shift=math.sin(t*.3+j*.8)*1.6
        lum=(math.sin(t*.55+j)+1)/2
        dark=(idx==2 and mix<.5) or (idx==1 and mix>.5)
        cc=(79+int(lum*15),104+int(lum*14),124+int(lum*15)) if dark else (181+int(lum*10),199+int(lum*8),213+int(lum*6))
        r=.5 if j%3 else .8
        draw.ellipse((x+shift-r,y-r,x+shift+r,y+r),fill=cc)
    # Small clearly labeled animation-study strip outside the window content.
    small=base.resize((896,640),Image.Resampling.LANCZOS)
    f=Image.new('RGB',(936,704),'#CEDAE4');f.paste(small,(20,12));fd=ImageDraw.Draw(f)
    tf=ImageFont.truetype('C:/Windows/Fonts/msyh.ttc',13)
    label='主题过渡与微弱星点演示 · 动效幅度刻意克制 · 预览数据'
    fd.text((22,673),label,font=tf,fill='#36566F')
    frames.append(f)
frames[0].save(OUT/'Yuki-主题与星辰-动态预览.gif',save_all=True,append_images=frames[1:],duration=round(1000/fps),loop=0,optimize=False,disposal=2)
print(OUT/'Yuki-三主题对照.png');print(OUT/'Yuki-主题与星辰-动态预览.gif')
(OUT/'themes.json').write_text(json.dumps(palettes,ensure_ascii=False,indent=2),encoding='utf-8')

