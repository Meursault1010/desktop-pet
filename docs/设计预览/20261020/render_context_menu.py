from pathlib import Path
from PIL import Image,ImageDraw,ImageFilter,PngImagePlugin
BASE=Path(__file__).resolve().parent
exec((BASE/'render_silver_concept.py').read_text(encoding='utf-8').split('def shell():')[0])
OUT=BASE/'context-menu';OUT.mkdir(exist_ok=True)
THEMES={
'雪白':dict(bg='#E6ECF1',paper='#FCFDFE',ink='#243C50',secondary='#53697A',line='#D2DFE8',nav='#EEF2F5',blue='#276E94',deep='#163D57',input='#F0F5F8',good='#347564'),
'银雾':dict(bg='#CED8E1',paper='#E8EEF3',ink='#263D50',secondary='#4C6477',line='#B8CBDA',nav='#DAE4ED',blue='#245F86',deep='#234861',input='#DCE7EF',good='#2E6E5E'),
'星夜':dict(bg='#0A111B',paper='#152130',ink='#E1EAF3',secondary='#A6B8C9',line='#34485D',nav='#101925',blue='#A7CCE8',deep='#C4DDEF',input='#1D3043',good='#95CABB')}
def shadow(x,y,w,h):
 global im,d
 layer=Image.new('RGBA',im.size);ld=ImageDraw.Draw(layer)
 ld.rounded_rectangle((x*S,(y+9)*S,(x+w)*S,(y+h+9)*S),radius=14*S,fill=(6,22,37,32))
 im.alpha_composite(layer.filter(ImageFilter.GaussianBlur(12*S)));d=ImageDraw.Draw(im)
def send(x,y):
 rr(x,y,28,28,C['deep'],None,6)
 ink=C['bg'] if C['bg']=='#0A111B' else '#FFFFFF'
 ln([(x+8,y+14),(x+20,y+14)],ink,1.4);ln([(x+15,y+9),(x+20,y+14),(x+15,y+19)],ink,1.4)
def menu(x,y,expanded=False):
 h=495 if expanded else 366
 shadow(x,y,328,h);rr(x,y,328,h,C['paper'],None,14)
 text(x+20,y+12,'yuki',25,C['deep'],serif=True)
 ln([(x+295,y+22),(x+303,y+30)],C['secondary'],1);ln([(x+303,y+22),(x+295,y+30)],C['secondary'],1)
 dot(x+23,y+62,2.7,C['good']);text(x+33,y+52,'安静待机',12,C['ink'])
 right(x+307,y+53,'本地模型已连接',11,C['secondary']);rule(x+20,y+83,288)
 text(x+20,y+101,'对话',12,C['ink'],True)
 if expanded:
  text(x+20,y+130,'你',10,C['secondary']);text(x+20,y+151,'陪我安静地待一会儿吧。',13,C['ink'])
  text(x+20,y+187,'雪',10,C['secondary']);text(x+20,y+209,'好呀，我就在这里。',13,C['ink']);iy=y+260
 else:iy=y+131
 rr(x+20,iy,288,44,C['input'],None,7);text(x+32,iy+12,'想和雪说些什么？',12,C['secondary']);send(x+272,iy+8)
 yy=iy+60
 icon('chat',x+23,yy+11,C['blue'],18);text(x+54,yy+8,'划词翻译',13,C['ink'])
 rr(x+272,yy+10,34,20,C['line'],None,10);dot(x+282,yy+20,7,C['paper'])
 yy+=46
 icon('layout',x+23,yy+11,C['secondary'],18);text(x+54,yy+8,'打开工作台',13,C['ink']);icon('arrow',x+287,yy+13,C['secondary'],15)
 rule(x+20,yy+54,288)
 icon('exit',x+23,yy+72,C['secondary'],18);text(x+54,yy+69,'退出 Yuki',13,C['secondary'])
def save(name):
 meta=PngImagePlugin.PngInfo();meta.add_text('Description','Yuki context menu visual study. Illustrative state and conversation, not a running application screenshot. Original character artwork retained.')
 im.convert('RGB').resize((W,H),Image.Resampling.LANCZOS).save(OUT/name,pnginfo=meta)
W,H=1560,742;im=Image.new('RGBA',(W*S,H*S),'#DDE6ED');d=ImageDraw.Draw(im);C=THEMES['雪白']
text(34,23,'Yuki · 右键快捷面板',25,C['ink'],True);text(35,65,'对话、翻译与常用入口，留在手边。',13,C['secondary'])
for i,(name,p) in enumerate(THEMES.items()):
 C=p;x=20+i*514
 rr(x,110,492,575,C['bg'],None,12);text(x+24,128,name,16,C['ink'],True);right(x+468,132,'右键展开',11,C['secondary'])
 menu(x+41,176);pet(x+364,505,103,150);text(x+25,655,'示例状态 · 不连接正式程序',10,C['secondary'])
C=THEMES['雪白'];text(34,706,'菜单约 328 × 366 px；跟随工作台主题，靠近屏幕边缘时向内展开。',12,C['secondary']);save('Yuki-右键菜单-三主题.png')
W,H=1110,780;C=THEMES['银雾'];im=Image.new('RGBA',(W*S,H*S),C['bg']);d=ImageDraw.Draw(im)
text(38,28,'右键，轻轻聊两句。',27,C['ink'],True);text(40,76,'默认保持紧凑；发送消息后，原位展开最近一轮对话。',13,C['secondary'])
menu(70,167);menu(602,136,True);text(72,568,'默认展开',14,C['ink'],True);text(72,598,'输入框直接可用，减少一次点击。',12,C['secondary']);pet(427,463,117,161)
text(604,664,'对话展开态',14,C['ink'],True);text(604,694,'仅展示最近一轮，长对话进入工作台继续。',12,C['secondary'])
text(40,740,'视觉预览 · 对话内容与连接状态均为示例 · 尚未替换正式界面',11,C['secondary']);save('Yuki-右键菜单-对话展开.png')
print('Saved 2 context menu previews.')
