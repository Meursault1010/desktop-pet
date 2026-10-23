from PIL import Image, ImageDraw, ImageFont
from pathlib import Path
import math, random

ROOT = Path(__file__).resolve().parents[3]
OUT = Path(__file__).resolve().parent
S = 2
W,H = 1800,1120
im = Image.new('RGBA',(W*S,H*S),'#070d17')
d = ImageDraw.Draw(im)
FONT = Path('C:/Windows/Fonts')
WHITE='#e8eff8'; TEXT='#c1cedd'; MUTED='#8495ac'; FAINT='#56677e'; BLUE='#9dcbee'; LINE='#28364b'

def font(n,bold=False,latin=False,italic=False):
    f = 'georgiai.ttf' if italic else ('seguisb.ttf' if bold else 'segoeui.ttf') if latin else ('msyhbd.ttc' if bold else 'msyh.ttc')
    return ImageFont.truetype(str(FONT/f),round(n*S))
def box(x,y,w,h,fill,outline=None,r=10,width=1):
    d.rounded_rectangle((x*S,y*S,(x+w)*S,(y+h)*S),radius=r*S,fill=fill,outline=outline,width=round(width*S))
def line(points,fill=LINE,width=1):
    d.line([(round(x*S),round(y*S)) for x,y in points],fill=fill,width=max(1,round(width*S)),joint='curve')
def text(x,y,t,n=16,fill=TEXT,bold=False,latin=False,italic=False):
    d.text((round(x*S),round(y*S)),t,font=font(n,bold,latin,italic),fill=fill)
def dot(x,y,r=2,fill=BLUE):
    d.ellipse(((x-r)*S,(y-r)*S,(x+r)*S,(y+r)*S),fill=fill)
def label_right(right,y,t,n=14,fill=MUTED):
    f=font(n); b=d.textbbox((0,0),t,font=f); text(right-(b[2]-b[0])/S,y,t,n,fill)
def icon(name,x,y,c=MUTED,s=20):
    u=s/20
    def l(p): line([(x+a*u,y+b*u) for a,b in p],c,1.4)
    if name=='grid':
        for a,b in [(2,2),(11,2),(2,11),(11,11)]:box(x+a*u,y+b*u,6*u,6*u,None,c,1.2)
    elif name=='person':
        d.ellipse(((x+6*u)*S,(y+1*u)*S,(x+14*u)*S,(y+9*u)*S),outline=c,width=2*S)
        l([(2,19),(3,14),(7,12),(13,12),(17,14),(18,19)])
    elif name=='spark':
        l([(10,1),(12,7),(19,10),(12,12),(10,19),(8,12),(1,10),(8,7),(10,1)])
    elif name=='tools':
        l([(3,2),(8,7),(6,10),(2,6),(2,11),(7,14),(11,11),(17,18),(19,16),(12,9),(14,5),(10,1)])
    elif name=='settings':
        for a in range(0,360,45):
            q=math.radians(a);l([(10+7*math.cos(q),10+7*math.sin(q)),(10+9*math.cos(q),10+9*math.sin(q))])
        d.ellipse(((x+4*u)*S,(y+4*u)*S,(x+16*u)*S,(y+16*u)*S),outline=c,width=S)
        d.ellipse(((x+8*u)*S,(y+8*u)*S,(x+12*u)*S,(y+12*u)*S),outline=c,width=S)
    elif name=='chevron':l([(7,5),(12,10),(7,15)])
    elif name=='corner':l([(3,3),(17,3),(17,17),(3,17),(3,3)]);l([(10,10),(14,14)]);l([(10,14),(14,14),(14,10)])
    elif name=='eye':
        l([(1,10),(5,5),(10,3),(15,5),(19,10),(15,15),(10,17),(5,15),(1,10)])
        d.ellipse(((x+7*u)*S,(y+7*u)*S,(x+13*u)*S,(y+13*u)*S),outline=c,width=S)
    elif name=='moon':l([(14,2),(8,3),(4,7),(3,12),(6,17),(11,18),(17,15),(11,14),(8,10),(9,5),(14,2)])
    elif name=='sun':
        d.ellipse(((x+5*u)*S,(y+5*u)*S,(x+15*u)*S,(y+15*u)*S),outline=c,width=S)
        for a in range(0,360,45):
            q=math.radians(a);l([(10+7*math.cos(q),10+7*math.sin(q)),(10+9*math.cos(q),10+9*math.sin(q))])
    elif name=='play':l([(6,3),(16,10),(6,17),(6,3)])
    elif name=='pause':l([(7,4),(7,16)]);l([(13,4),(13,16)])
    elif name=='prev':l([(5,4),(5,16)]);l([(15,4),(7,10),(15,16),(15,4)])
    elif name=='next':l([(15,4),(15,16)]);l([(5,4),(13,10),(5,16),(5,4)])
    elif name=='check':l([(3,10),(8,15),(17,5)])
    elif name=='plus':l([(10,3),(10,17)]);l([(3,10),(17,10)])
    elif name=='chat':l([(2,3),(18,3),(18,14),(8,14),(3,18),(3,14),(2,14),(2,3)])
    elif name=='exit':l([(9,3),(3,3),(3,17),(9,17)]);l([(8,10),(19,10)]);l([(15,6),(19,10),(15,14)])
    elif name=='layout':l([(2,3),(18,3),(18,17),(2,17),(2,3)]);l([(7,3),(7,17)]);l([(7,9),(18,9)])
def handle(x,y):
    for a in range(2):
        for b in range(3):dot(x+a*4,y+b*4,.8,FAINT)
def panel(x,y,w,h,title,selected=False):
    box(x,y,w,h,'#111c2c', '#6b98b8' if selected else LINE,10,1)
    handle(x+18,y+22); text(x+36,y+13,title,15,WHITE)
    text(x+w-34,y+9,'···',20,MUTED,latin=True)
    line([(x+1,y+47),(x+w-1,y+47)],'#243246')
    if selected:
        line([(x+w-15,y+h-6),(x+w-6,y+h-15)],'#9dcbee')
        line([(x+w-21,y+h-6),(x+w-6,y+h-21)],'#6b98b8')
def toggle(x,y,on=True):
    box(x,y,34,19,'#7ca8ca' if on else '#304055',None,10)
    dot(x+(24 if on else 10),y+9.5,6.5,'#edf4fc' if on else '#8c9bb0')
def button(x,y,w,title,primary=False,ico=None):
    box(x,y,w,38,'#b9d7ee' if primary else '#1b293c',None if primary else '#34465e',6)
    if ico:icon(ico,x+12,y+9,'#162a3d' if primary else TEXT,18)
    text(x+(39 if ico else 16),y+8,title,14,'#142638' if primary else TEXT,bold=primary)

# A restrained desktop shell: silver details, navy surfaces, and sparse stars.
box(20,20,1760,1080,'#0c1523','#344157',15)
box(20,20,1760,58,'#101b2a',None,15)
box(20,65,1760,13,'#101b2a',None,0)
line([(20,78),(1780,78)],'#28364a')
text(48,34,'yuki',25,WHITE,True,True)
text(112,40,'/ 工作台',14,MUTED)
box(812,36,176,26,'#182638','#2b3b50',13)
dot(826,49,2,'#b2cce1');text(837,40,'样式预览 · 示例数据',11,TEXT)
line([(1647,49),(1659,49)],MUTED)
box(1692,43,11,10,None,MUTED,0)
line([(1740,43),(1751,54)],MUTED);line([(1751,43),(1740,54)],MUTED)
line([(212,79),(212,1100)],'#253247')
text(48,113,'属于你的桌面伙伴',12,FAINT)
for i,(t,ic) in enumerate([('总览','grid'),('角色','person'),('AI 助手','spark'),('工具','tools'),('设置','settings')]):
    y=166+i*61
    if i==0:
        box(35,y-9,162,46,'#203249',None,7);box(35,y+3,3,22,'#acd6f6',None,1)
    icon(ic,55,y+3,BLUE if i==0 else MUTED,20);text(91,y,t,16,WHITE if i==0 else MUTED,bold=i==0)
line([(47,925),(183,925)],LINE)
dot(55,953,3,'#a8c6dd');text(67,943,'本地模型已连接',12,TEXT)
text(48,978,'星夜主题',12,MUTED)
for i,c in enumerate(['#d9e2ec','#a1b4ca','#6786a5','#192a42']):
    dot(57+i*28,1015,7,c)
    if i==3:d.ellipse(((48+i*28)*S,1006*S,(66+i*28)*S,1024*S),outline=BLUE,width=S)
text(48,1060,'yuki / workspace',11,FAINT,latin=True)

random.seed(81)
for _ in range(51):
    x=random.uniform(240,1750);y=random.uniform(90,1090)
    dot(x,y,random.choice([.6,.7,.9,1.2]),random.choice(['#283c53','#344b65','#547087']))
for x,y in [(1161,114),(1682,210),(1032,1045)]:
    line([(x-3,y),(x+3,y)],'#7694ae');line([(x,y-3),(x,y+3)],'#7694ae')

text(248,109,'总览',32,WHITE,True)
text(249,157,'留一点安静，给桌面上的生活。',15,MUTED)
icon('layout',1502,122,TEXT,18);text(1528,119,'布局编辑中',13,TEXT)
button(1644,111,100,'完成',True)
text(248,199,'默认总览',14,WHITE,True);line([(248,226),(309,226)],BLUE,2)
text(345,199,'我的工作区',14,MUTED);icon('plus',458,202,MUTED,16)
label_right(1744,199,'拖动标题栏调整位置，拖动右下角缩放',12,FAINT)

panel(248,246,724,405,'Yuki',True)
text(278,318,'雪，在身边。',30,WHITE,True)
dot(284,381,3,BLUE);text(297,369,'安静待机',16,BLUE)
text(278,412,'她正在安静地陪着你。',15,TEXT)
text(278,441,'下一步  /  片刻后伸个懒腰',12,MUTED)
button(278,491,135,'隐藏宠物',False,'eye');button(425,491,140,'移到右下角',False,'corner')
text(278,588,'“Shall I compare thee to a summer’s day?”',15,'#8c9fb7',italic=True)
text(278,614,'William Shakespeare · Sonnet 18',11,FAINT,latin=True)
pet=Image.open(ROOT/'console-v2/frontend/public/pet-preview.png').convert('RGBA')
pet=pet.crop(pet.getbbox());pet.thumbnail((round(262*S),round(320*S)),Image.Resampling.LANCZOS)
px=806*S-pet.width//2;py=309*S
im.alpha_composite(pet,(px,py))
line([(696,633),(915,633)],'#2e435b')

panel(992,246,342,405,'时间与天气')
text(1020,316,'14:32',60,WHITE,False,True)
text(1021,396,'10 月 20 日  星期二',14,MUTED)
line([(1020,442),(1306,442)],LINE)
icon('sun',1022,473,BLUE,35)
text(1077,458,'18°',39,WHITE,latin=True)
text(1078,508,'多云  /  体感 17°',13,TEXT)
text(1020,560,'天气地点',12,FAINT);label_right(1306,560,'未设置 · 此处为示例',12,MUTED)
text(1020,601,'为今天留一点慢下来的时间。',12,MUTED)

panel(1354,246,390,405,'陪伴模式')
box(1380,315,338,40,'#0b1523',None,6)
for x,t,sel in [(1384,'日常',True),(1496,'健康',False),(1608,'专注',False)]:
    if sel:box(x,319,106,32,'#2b4059',None,5)
    text(x+37,325,t,13,WHITE if sel else MUTED)
text(1382,383,'安静地陪伴，偶尔有小惊喜。',14,TEXT)
text(1382,429,'健康提醒',14,WHITE);toggle(1683,432,True)
text(1382,458,'每 50 分钟提醒休息与眺望',12,MUTED)
line([(1382,496),(1716,496)],LINE)
text(1382,520,'开始一段专注',15,WHITE)
text(1382,550,'减少闲聊，保留重要提醒。',12,MUTED)
button(1382,589,188,'开始 25 分钟',False,'play')

panel(248,671,724,343,'今日足迹')
text(278,742,'从今天开始，到此刻。',19,WHITE,True)
text(278,777,'桌面活动与任务结果，会在这里汇成一天。',13,MUTED)
text(278,821,'3 小时 42 分',29,WHITE,latin=False)
text(278,866,'使用时长',12,MUTED)
text(493,821,'2 次',29,WHITE);text(493,866,'完成专注',12,MUTED)
text(660,821,'6 项',29,WHITE);text(660,866,'已完成任务',12,MUTED)
for i in range(61):
    h=6+int((math.sin(i*.29)+1)*10)+random.randint(0,24)
    box(279+i*10.7,944-h,5,h,'#567896' if i<43 else '#2d435a',None,2)
text(278,958,'08:00',11,FAINT,latin=True);text(593,958,'11:00',11,FAINT,latin=True);label_right(939,958,'14:32',11,MUTED)
text(831,746,'查看总结',12,BLUE);icon('chevron',922,750,BLUE,15)

panel(992,671,342,343,'系统状态')
for y,t,v,p in [(740,'CPU','12%',.12),(801,'内存','14.6 / 32 GB',.456)]:
    text(1020,y,t,13,MUTED);label_right(1306,y,v,14,WHITE)
    box(1020,y+31,286,3,'#26374d',None,1);box(1020,y+31,286*p,3,'#92badb',None,1)
line([(1020,868),(1306,868)],LINE)
for y,t,v in [(885,'电源','已接通 · 86%'),(919,'U 盘','未连接'),(953,'开机自启','已开启')]:
    text(1020,y,t,12,MUTED);label_right(1306,y,v,12,TEXT)

panel(1354,671,390,343,'正在播放')
box(1382,741,65,65,'#21344b','#354f69',6)
for rr in [20,12,4]:
    d.ellipse(((1414-rr)*S,(773-rr)*S,(1414+rr)*S,(773+rr)*S),outline='#6988a3',width=S)
text(1466,741,'Clair de lune',19,WHITE,latin=True)
text(1467,774,'Claude Debussy',13,MUTED,latin=True)
box(1382,832,334,3,'#293a50',None,1);box(1382,832,128,3,'#98bddc',None,1);dot(1510,833,3,WHITE)
text(1382,845,'01:48',11,MUTED,latin=True);label_right(1716,845,'04:57',11,MUTED)
icon('prev',1476,887,MUTED,21);box(1520,877,44,42,'#283e57',None,21);icon('pause',1531,887,WHITE,22);icon('next',1588,887,MUTED,21)
line([(1382,939),(1716,939)],LINE)
text(1382,960,'音乐互动',12,MUTED);toggle(1683,962,True)

icon('check',250,1043,'#a2c2d8',16);text(275,1039,'编译成功',12,TEXT);text(358,1039,'14:26',11,FAINT,latin=True)
dot(421,1050,1.5,FAINT);text(437,1039,'下载完成  ·  项目素材.zip',12,MUTED)
label_right(1744,1039,'添加区块     /     恢复默认布局',12,TEXT)
line([(248,1076),(1744,1076)],'#1d2c40')
text(248,1081,'设计方向  /  蓝白银 · 星夜',10,FAINT)
label_right(1744,1081,'静态样式预览 · 功能与数据仅作视觉示意',10,FAINT)
im.convert('RGB').resize((W,H),Image.Resampling.LANCZOS).save(OUT/'Yuki-工作台总览-样式预览.png')

# Companion context menu, drawn at its intended compact scale.
im=Image.new('RGBA',(1000*S,800*S),'#0a1220');d=ImageDraw.Draw(im)
random.seed(16)
for _ in range(35):dot(random.randrange(40,960),random.randrange(40,760),random.choice([.7,1]),'#344b64')
text(58,48,'Yuki · 右键菜单',24,WHITE,True);text(59,88,'同一视觉语言，更少的操作入口。',13,MUTED)
pet.thumbnail((235*S,360*S),Image.Resampling.LANCZOS);im.alpha_composite(pet,(100*S,275*S))
box(405,174,370,518,'#111d2e','#394b63',13)
dot(433,207,3,BLUE);text(446,194,'雪正在安静待机',14,WHITE)
text(433,229,'“陪你把今天慢慢过完。”',12,MUTED)
line([(429,268),(751,268)],LINE)
icon('chat',432,291,BLUE,19);text(461,287,'和 Yuki 聊聊',14,WHITE)
box(431,330,318,90,'#0c1625','#354a63',7)
text(446,344,'想对雪说些什么？',13,FAINT)
text(446,390,'Enter 发送',11,FAINT,latin=False);box(709,382,26,24,'#a9cce7',None,5);line([(716,394),(728,394),(723,389)],'#23394d')
for yy,ic,tt,meta in [(448,'spark','划线翻译','关闭'),(510,'layout','打开工作台',''),(585,'exit','保存并退出','')]:
    if yy==585:line([(429,565),(751,565)],LINE)
    icon(ic,433,yy+1,MUTED,20);text(466,yy-3,tt,14,TEXT)
    if meta:
        text(684,yy-1,meta,12,MUTED);toggle(714,yy,False)
text(433,650,'按 Esc 关闭',11,FAINT)
text(58,741,'静态样式预览 · 待确认后实现',12,MUTED)
im.convert('RGB').resize((1000,800),Image.Resampling.LANCZOS).save(OUT/'Yuki-右键菜单-样式预览.png')
print(OUT/'Yuki-工作台总览-样式预览.png')
print(OUT/'Yuki-右键菜单-样式预览.png')
