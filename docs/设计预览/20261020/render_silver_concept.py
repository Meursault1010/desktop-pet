from PIL import Image, ImageDraw, ImageFont, PngImagePlugin
from pathlib import Path
import random, math
BASE=Path(__file__).resolve().parent
ROOT=BASE.parents[2]
OUT=BASE/'silver-observatory'
OUT.mkdir(exist_ok=True)
S=2;W=1800;H=1160
FONTS=Path('C:/Windows/Fonts')
C={'bg':'#E6ECF1','paper':'#FCFDFE','ink':'#243C50','secondary':'#53697A','muted':'#607587','line':'#D5DFE6','nav':'#EEF2F5','blue':'#276E94','deep':'#10283C'}
im=Image.new('RGBA',(W*S,H*S),C['bg']);d=ImageDraw.Draw(im)
def font(n,b=False,latin=False,serif=False):
    name='georgiai.ttf' if serif else ('seguisb.ttf' if b else 'segoeui.ttf') if latin else ('msyhbd.ttc' if b else 'msyh.ttc')
    return ImageFont.truetype(str(FONTS/name),round(n*S))
def text(x,y,t,n=14,c=None,b=False,latin=False,serif=False):
    d.text((round(x*S),round(y*S)),t,font=font(n,b,latin,serif),fill=c or C['ink'])
def rr(x,y,w,h,c,stroke=None,r=8,lw=1):
    d.rounded_rectangle((round(x*S),round(y*S),round((x+w)*S),round((y+h)*S)),radius=round(r*S),fill=c,outline=stroke,width=round(lw*S))
def ln(points,c=None,w=1):
    d.line([(round(x*S),round(y*S)) for x,y in points],fill=c or C['line'],width=max(1,round(w*S)),joint='curve')
def rule(x,y,w,c=None):ln([(x,y),(x+w,y)],c)
def dot(x,y,r,c):d.ellipse(((x-r)*S,(y-r)*S,(x+r)*S,(y+r)*S),fill=c)
def right(x,y,t,n=13,c=None,b=False,latin=False):
    tw=d.textlength(t,font=font(n,b,latin))/S;text(x-tw,y,t,n,c,b,latin)
def center(x,y,t,n=14,c=None,b=False,latin=False):
    tw=d.textlength(t,font=font(n,b,latin))/S;text(x-tw/2,y,t,n,c,b,latin)
def icon(name,x,y,c=None,s=20):
    c=c or C['secondary'];u=s/20
    def l(p,w=1.4):ln([(x+a*u,y+b*u) for a,b in p],c,w)
    if name=='grid':
        for a,b in [(2,2),(12,2),(2,12),(12,12)]:rr(x+a*u,y+b*u,6*u,6*u,None,c,1)
    elif name=='pet':
        l([(2,9),(2,2),(7,5),(13,5),(18,2),(18,9),(17,15),(13,18),(7,18),(3,15),(2,9)])
        dot(x+7*u,y+11*u,.7*u,c);dot(x+13*u,y+11*u,.7*u,c)
    elif name=='spark':l([(10,1),(12,7),(19,10),(12,12),(10,19),(8,12),(1,10),(8,7),(10,1)])
    elif name=='tool':
        l([(2,3),(8,3),(8,9),(2,9),(2,3)]);l([(12,3),(18,3),(18,9),(12,9),(12,3)]);l([(2,13),(8,13),(8,19),(2,19),(2,13)]);l([(15,13),(15,19)]);l([(12,16),(18,16)])
    elif name=='settings':
        for yy,a in [(4,7),(10,13),(16,9)]:l([(2,yy),(18,yy)]);rr(x+(a-2)*u,y+(yy-2)*u,4*u,4*u,C['nav'],c,1)
    elif name=='eye':
        l([(1,10),(5,5),(10,3),(15,5),(19,10),(15,15),(10,17),(5,15),(1,10)])
        d.ellipse(((x+7*u)*S,(y+7*u)*S,(x+13*u)*S,(y+13*u)*S),outline=c,width=S)
    elif name=='corner':l([(2,2),(18,2),(18,18),(2,18),(2,2)]);l([(10,10),(15,15),(15,10)]);l([(10,15),(15,15)])
    elif name=='plus':l([(10,3),(10,17)]);l([(3,10),(17,10)])
    elif name=='arrow':l([(3,10),(17,10)]);l([(11,4),(17,10),(11,16)])
    elif name=='down':l([(5,8),(10,13),(15,8)])
    elif name=='play':l([(6,3),(16,10),(6,17),(6,3)])
    elif name=='pause':l([(7,4),(7,16)],1.8);l([(13,4),(13,16)],1.8)
    elif name=='prev':l([(5,4),(5,16)]);l([(15,4),(7,10),(15,16),(15,4)])
    elif name=='next':l([(15,4),(15,16)]);l([(5,4),(13,10),(5,16),(5,4)])
    elif name=='sun':
        d.ellipse(((x+6*u)*S,(y+6*u)*S,(x+14*u)*S,(y+14*u)*S),outline=c,width=S)
        for a in range(0,360,45):
            q=math.radians(a);l([(10+7*math.cos(q),10+7*math.sin(q)),(10+9.5*math.cos(q),10+9.5*math.sin(q))])
    elif name=='layout':l([(2,3),(18,3),(18,17),(2,17),(2,3)]);l([(8,3),(8,17)]);l([(8,9),(18,9)])
    elif name=='check':l([(3,10),(8,15),(17,5)])
    elif name=='chat':l([(2,3),(18,3),(18,14),(8,14),(3,18),(3,14),(2,14),(2,3)])
    elif name=='exit':l([(9,3),(3,3),(3,17),(9,17)]);l([(8,10),(19,10)]);l([(15,6),(19,10),(15,14)])
    elif name=='music':
        l([(7,15),(7,4),(17,2),(17,13)]);l([(7,7),(17,5)])
        d.ellipse(((x+2*u)*S,(y+13*u)*S,(x+7*u)*S,(y+17*u)*S),outline=c,width=S)
        d.ellipse(((x+12*u)*S,(y+11*u)*S,(x+17*u)*S,(y+15*u)*S),outline=c,width=S)
def toggle(x,y,on=True,dark=False):
    rr(x,y,36,21,('#AECFE6' if dark else '#326F91') if on else '#C8D3DC',None,11)
    dot(x+(25 if on else 11),y+10.5,7,'#F8FCFF')
def button(x,y,w,t,ic=None,primary=False,dark=False):
    fill=('#DBEAF5' if dark else '#163D57') if primary else ('#1C364C' if dark else '#FFFFFF')
    stroke=None if primary else ('#4F687D' if dark else '#C5D3DD')
    ink=('#18394F' if dark else '#FFFFFF') if primary else ('#DAE6F1' if dark else C['ink'])
    rr(x,y,w,38,fill,stroke,6)
    if ic:icon(ic,x+13,y+10,ink,17)
    text(x+(40 if ic else 17),y+9,t,13,ink,primary)
PET=Image.open(ROOT/'console-v2/frontend/public/pet-preview.png').convert('RGBA');PET=PET.crop(PET.getbbox())
def pet(x,y,w,h):
    p=PET.copy();p.thumbnail((round(w*S),round(h*S)),Image.Resampling.LANCZOS)
    im.alpha_composite(p,(round((x+w/2)*S-p.width/2),round((y+h)*S-p.height)))
def shell():
    rr(20,20,1760,1120,C['paper'],'#B7C7D4',16)
    # Silver title bar, no decorative header banner.
    rr(21,21,1758,48,'#EAF0F4',None,15);rr(21,52,1758,17,'#EAF0F4',None,0)
    text(45,26,'yuki',28,C['deep'],False,False,True);text(115,38,'工作台',11,C['secondary'])
    center(900,37,'静态设计预览 · 示例数据',11,C['secondary'])
    ln([(1653,45),(1664,45)],C['secondary']);rr(1695,39,10,10,None,C['secondary'],0)
    ln([(1740,39),(1751,50)],C['secondary']);ln([(1751,39),(1740,50)],C['secondary'])
    rule(21,69,1758,'#CAD6DF')
    # A narrow, neutral navigation column. Most of the window belongs to content.
    rr(21,70,163,1069,C['nav'],None,0);rr(21,1120,163,19,C['nav'],None,14)
    for i,(title,ic) in enumerate([('总览','grid'),('角色','pet'),('AI 助手','spark'),('工具','tool'),('设置','settings')]):
        y=126+i*72;sel=i==0
        if sel:rr(35,y-13,135,48,C['deep'],None,8)
        icon(ic,53,y+1,'#DBEAF4' if sel else C['secondary'],19)
        text(87,y,title,14,'#F1F7FB' if sel else C['secondary'],sel)
    rule(45,827,114,'#CEDAE3')
    icon('pet',49,855,C['secondary'],18);text(79,853,'雪在桌面',12,C['secondary'])
    dot(53,914,3,'#3D806F');text(65,903,'本地模型',12,C['ink']);text(65,928,'已连接',10,C['secondary'])
    text(48,1001,'主题',11,C['secondary'])
    for i,c in enumerate(['#FAFCFD','#A4B9CC','#16364F']):
        dot(57+i*37,1040,7,c)
        if i==0:d.ellipse(((47+i*37)*S,1030*S,(67+i*37)*S,1050*S),outline='#3E6B88',width=S)
    text(48,1097,'vNext · 设计稿',10,C['secondary'])
    # Small stable page heading and local page tabs.
    text(218,103,'总览',27,C['ink'],True)
    text(218,147,'此刻在身边，今天有迹可循。',13,C['secondary'])
    button(1580,116,164,'自定义工作区','layout')
    text(218,191,'默认总览',12,C['ink'],True);rule(218,215,55,'#285F80')
    text(316,191,'我的工作区',12,C['secondary']);icon('plus',414,194,C['secondary'],14)
    right(1744,190,'10 月 20 日 · 星期二',12,C['secondary'])

shell()
# A single deep stage, a physical visual anchor within a bright working surface.
rr(216,242,638,802,'#10273B',None,15)
text(250,270,'雪',27,'#EDF6FC',True)
dot(793,290,3,'#B0D4E8');right(781,279,'桌面可见',11,'#BCD0E0')
text(250,318,'安静待机',16,'#BAD9EF')
text(250,350,'正在轻轻呼吸。下一步暂未安排。',12,'#B2C7D9')
random.seed(101)
for _ in range(36):
    x=random.uniform(245,828);y=random.uniform(396,822)
    dot(x,y,random.choice([.5,.7,.9]),random.choice(['#36586F','#54728A','#6A8CA5']))
for x,y in [(302,489),(770,423),(705,784)]:
    ln([(x-3,y),(x+3,y)],'#6F91AA');ln([(x,y-3),(x,y+3)],'#6F91AA')
# Characters retain their actual source details and aspect ratio.
pet(361,405,350,392)
center(535,842,'“But thy eternal summer shall not fade.”',18,'#D5E2ED',False,False)
# Redraw the quotation with a deliberate editorial serif.
rr(239,839,590,36,'#10273B',None,0)
q='“But thy eternal summer shall not fade.”'
qw=d.textlength(q,font=font(18,serif=True))/S;text(535-qw/2,842,q,18,'#D2E0EA',serif=True)
center(535,877,'William Shakespeare · Sonnet 18',10,'#A3BDCF',latin=True)
button(294,946,198,'隐藏宠物','eye',dark=True)
button(508,946,266,'移到屏幕右下角','corner',primary=True,dark=True)
# The reading surface: open, with a clear information hierarchy, not a card grid.
text(900,247,'今天',17,C['ink'],True)
right(1744,251,'本地时间与天气',11,C['secondary'])
text(894,284,'14:32',83,C['ink'],latin=True)
text(901,389,'2026 年 10 月 20 日，星期二',13,C['secondary'])
ln([(1335,297),(1335,407)],C['line'])
icon('sun',1371,300,C['blue'],38)
text(1427,287,'18°',49,C['ink'],latin=True)
text(1371,356,'上海 · 多云 · 体感 17°',13,C['secondary'])
text(1371,389,'天气示例，更新于 14:25',11,C['muted'])
rule(900,443,844)
# Adjustable modes are one compact horizontal instrument, independent health reminder below.
text(900,472,'陪伴节奏',17,C['ink'],True)
rr(1176,464,568,43,'#EDF2F6',None,7)
for i,(t,sel) in enumerate([('日常',False),('安静',True),('专注',False)]):
    x=1181+i*187
    if sel:rr(x,468,181,35,'#FFFFFF','#CCD8E2',5)
    center(x+90,477,t,13,C['ink'] if sel else C['secondary'],sel)
text(900,523,'安静陪伴，保留重要提醒。',12,C['secondary'])
button(1558,523,186,'开始 25 分钟','play',primary=True)
text(900,582,'健康提醒',13,C['ink'])
text(1005,583,'每 50 分钟，休息与眺望',12,C['secondary']);toggle(1708,583,True)
rule(900,632,844)
# Activity journal with useful authored records and traceable summary wording.
text(900,661,'今日足迹',18,C['ink'],True)
text(900,695,'活跃 3 小时 42 分钟  /  完成 2 次专注',12,C['secondary'])
text(1584,668,'生成今日总结',12,C['blue']);icon('arrow',1719,669,C['blue'],17)
ln([(917,758),(917,914)],'#C6D4DF')
for y,when,title,desc in [(748,'14:26','编译成功','Yuki 项目 · 任务结果'),(816,'11:20','完成一段专注','25 分钟 · 时间管理'),(884,'09:10','开始今天的工作','编辑器 · 活动记录')]:
    dot(917,y+10,4,'#FCFDFE');d.ellipse((913*S,(y+6)*S,921*S,(y+14)*S),outline='#5E88A4',width=S)
    text(942,y,when,12,C['secondary'],latin=True);text(1028,y-2,title,14,C['ink'])
    right(1742,y+1,desc,11,C['secondary'])
rule(900,959,844)
for i,(title,value) in enumerate([('CPU','12%'),('内存','14.6 / 32 GB'),('电源','86% · 已接通'),('U 盘','未连接')]):
    x=901+i*216
    text(x,986,title,11,C['secondary']);text(x,1013,value,15,C['ink'],latin=i<2)
# A media shelf, distinct from a dashboard panel. One continuous baseline.
rule(216,1068,1528,'#C9D6E0')
icon('music',220,1094,C['blue'],21)
text(255,1085,'Clair de lune',14,C['ink'],latin=True);text(255,1109,'Claude Debussy',10,C['secondary'],latin=True)
icon('prev',500,1098,C['secondary'],18)
rr(542,1085,37,37,C['deep'],None,19);icon('pause',551,1094,'#F2F7FC',19);icon('next',604,1098,C['secondary'],18)
rr(665,1104,190,2,'#D2DDE5',None,1);rr(665,1104,70,2,'#467C9F',None,1);dot(735,1105,3,'#467C9F')
text(876,1096,'01:48 / 04:57',10,C['secondary'],latin=True)
text(1109,1094,'开机自启',11,C['secondary']);text(1180,1094,'已开启',11,C['ink'])
right(1742,1094,'设计预览 · 全部数据为示例',11,C['secondary'])
meta=PngImagePlugin.PngInfo();meta.add_text('Description','Original Yuki UI concept based on the three local design documents. Existing pet-preview.png artwork, original proportions; synthetic demonstration data; no functional changes.')
im.convert('RGB').resize((W,H),Image.Resampling.LANCZOS).save(OUT/'Yuki-冰银工作区-全新总览.png',pnginfo=meta)
print(OUT/'Yuki-冰银工作区-全新总览.png')

# A matching light menu to check whether the new language survives a small surface.
W,H=1060,740
im=Image.new('RGBA',(W*S,H*S),'#E6ECF1');d=ImageDraw.Draw(im)
text(51,35,'yuki',33,C['deep'],serif=True);text(128,54,'桌面快捷面板',13,C['secondary'])
text(52,98,'新方向 / 冰银工作区',12,C['secondary'])
pet(135,249,253,345)
rr(492,188,396,383,'#FCFDFE','#BFCFDB',14)
icon('pet',516,212,C['blue'],21);text(548,210,'雪',16,C['ink'],True)
right(861,215,'安静待机',11,C['secondary'])
text(517,251,'正在轻轻呼吸，陪你做自己的事。',12,C['secondary'])
rr(514,290,352,94,'#F0F5F8','#BCCEDC',8)
text(531,307,'想对雪说些什么？',14,C['secondary'])
text(532,356,'Enter 发送',10,C['muted'])
rr(822,344,29,26,C['deep'],None,5);icon('arrow',828,350,'#FFFFFF',17)
icon('spark',519,410,C['secondary'],19);text(549,407,'划线翻译',13,C['ink']);toggle(829,409,False)
icon('layout',519,454,C['secondary'],19);text(549,451,'打开工作台',13,C['ink'])
rule(515,494,350)
icon('exit',519,521,C['secondary'],18);text(549,517,'保存并退出',13,C['ink'])
text(52,679,'静态设计预览 · 原有角色素材 · 所有文字与状态为示例',11,C['secondary'])
im.convert('RGB').resize((W,H),Image.Resampling.LANCZOS).save(OUT/'Yuki-冰银工作区-快捷面板.png',pnginfo=meta)
print(OUT/'Yuki-冰银工作区-快捷面板.png')

