from pathlib import Path
from PIL import Image,ImageDraw,PngImagePlugin
import random
BASE=Path(__file__).resolve().parent
exec((BASE/'render_silver_concept.py').read_text(encoding='utf-8').split('\nshell()\n')[0])
OUT=BASE/'silver-observatory'
DARK='#10273B';LIGHT='#D1E2EF';DSUB='#B3CADA'

def page(section,title,desc,tablist,active=0):
    global im,d
    im=Image.new('RGBA',(W*S,H*S),C['bg']);d=ImageDraw.Draw(im)
    shell()
    rr(201,85,1555,1040,C['paper'],None,0)
    rr(33,100,141,409,C['nav'],None,0)
    for i,(t,ic) in enumerate([('总览','grid'),('角色','pet'),('AI 助手','spark'),('工具','tool'),('设置','settings')]):
        y=126+i*72;sel=i==section
        if sel:rr(35,y-13,135,48,C['deep'],None,8)
        icon(ic,53,y+1,'#DBEAF4' if sel else C['secondary'],19)
        text(87,y,t,14,'#F1F7FB' if sel else C['secondary'],sel)
    text(218,103,title,27,C['ink'],True);text(218,147,desc,13,C['secondary'])
    x=218
    for i,t in enumerate(tablist):
        text(x,191,t,12,C['ink'] if i==active else C['secondary'],i==active)
        tw=d.textlength(t,font=font(12))/S
        if i==active:rule(x,215,tw,C['blue'])
        x+=tw+38
    rule(216,1074,1528)
    text(218,1095,'冰银工作区',11,C['secondary'])
    right(1744,1095,'静态设计预览 · 所有内容与数据均为示例 · 待确认后开发',11,C['secondary'])

def stars(x,y,w,h,seed=23):
    random.seed(seed)
    for _ in range(26):dot(random.uniform(x,x+w),random.uniform(y,y+h),random.choice([.5,.7,1]),random.choice(['#476B85','#37566F','#6C8CA3']))

def asset(x,y,w,h,name):
    p=Image.open(ROOT/'console-v2/frontend/public/actions'/name/'poster.png').convert('RGBA')
    p=p.crop(p.getbbox());p.thumbnail((round(w*S),round(h*S)),Image.Resampling.LANCZOS)
    im.alpha_composite(p,(round((x+w/2)*S-p.width/2),round((y+h)*S-p.height)))

def field(x,y,w,t):
    rr(x,y,w,37,'#F0F5F8','#BFCFDB',6);text(x+13,y+10,t,12,C['secondary'])

def save(name):
    meta=PngImagePlugin.PngInfo();meta.add_text('Description','Original static Yuki UI concept based on the three local design documents. Existing Yuki art, synthetic example data. No production functionality changed.')
    path=OUT/name;im.convert('RGB').resize((W,H),Image.Resampling.LANCZOS).save(path,pnginfo=meta);print(path)

# Role screen: a slate stage, light catalog and a quiet, open inspector.
page(1,'角色','动作、外观与小小日常，在这里慢慢调整。',['音乐互动','动作','外观','行为逻辑'],1)
button(1597,114,147,'在桌面演示','play',True)
text(219,254,'动作分类',12,C['secondary'])
for i,t in enumerate(['全部动作','站立待机','坐下待机','趴着待机','睡眠','移动与舞蹈','拖拽与物理','附着与互动','情绪与事件','出现与离开']):
    y=301+i*45
    if i==1:rr(216,y-8,174,36,'#E4EEF5',None,6)
    text(233,y,t,13,C['ink'] if i==1 else C['secondary'],i==1)
rule(231,794,146)
text(233,816,'预览仅在此舞台播放，',11,C['secondary']);text(233,841,'不会打断桌面上的雪。',11,C['secondary'])
rr(415,242,840,566,DARK,None,14)
text(445,266,'安静等待',20,'#EDF6FC',True)
right(1224,275,'站立待机',11,DSUB)
stars(449,333,770,378)
pet(689,328,294,361)
rule(622,705,431,'#38556D')
text(445,760,'预览播放',11,DSUB)
icon('prev',742,758,DSUB,18);rr(797,742,42,42,'#D5E6F3',None,21);icon('pause',808,753,'#17384F',20);icon('next',875,758,DSUB,18)
right(1224,760,'00:01 / 00:03',11,DSUB)
text(416,841,'站立待机',16,C['ink'],True);field(1004,831,251,'搜索动作')
for i,(a,t) in enumerate([('wait','等待'),('comb','梳头'),('dress','整理衣服'),('stretch','伸懒腰'),('yawn','打哈欠')]):
    x=415+i*170
    rr(x,886,157,156,'#F0F5F8','#91B2CB' if i==0 else '#D5E0E8',8)
    asset(x+25,895,107,107,a);text(x+14,1017,t,12,C['ink'] if i==0 else C['secondary'],i==0)
ln([(1291,242),(1291,1044)])
text(1325,255,'动作信息',17,C['ink'],True)
text(1325,311,'安静等待',25,C['ink'],True)
text(1325,359,'呼吸轻轻起伏，偶尔放松一下。',13,C['secondary'])
rule(1325,413,419)
for y,t,v in [(442,'姿态归属','站立'),(496,'触发方式','自然待机 / 手动预览'),(550,'表现方式','动作帧与程序呼吸'),(604,'播放策略','短暂活动后自然停留')]:
    text(1325,y,t,12,C['secondary']);right(1744,y,v,12,C['ink'])
rule(1325,660,419)
text(1325,690,'自然衔接',15,C['ink'],True)
text(1325,733,'站立 → 安静等待 → 自然停留',13,C['secondary'])
text(1325,786,'动作不会一直完整重复，',12,C['secondary']);text(1325,814,'保持停留、呼吸和适当的安静。',12,C['secondary'])
rule(1325,922,419)
icon('check',1325,951,C['blue'],18);text(1355,948,'沿用现有角色素材与比例',12,C['secondary'])
text(1325,994,'在桌面演示后，恢复原有行为。',12,C['secondary'])
save('Yuki-冰银工作区-角色动作.png')

# Assistant screen: focus on the conversation; the character is a quiet side presence.
page(2,'AI 助手','说说今天，也一起处理眼前的小事。',['本地模型','云端 API'])
button(1608,114,136,'连接设置','settings')
# Conversation rail uses lines rather than repeated bubbles.
text(219,255,'对话',14,C['ink'],True);icon('plus',428,258,C['blue'],18)
rule(218,293,230)
for i,(title,meta) in enumerate([('截图文字与翻译','今天 14:32'),('今天的工作安排','今天 10:16'),('与雪聊聊天','昨天 20:41')]):
    y=328+i*90
    if i==0:rr(211,y-12,245,76,'#E7EFF5',None,7)
    text(229,y,title,13,C['ink'],i==0);text(229,y+30,meta,11,C['secondary'])
text(229,997,'会话保留在本机。',11,C['secondary'])
ln([(483,242),(483,1044)])
dot(522,264,3,'#3D806F');text(536,254,'Qwen · 本地服务',13,C['ink']);right(1344,256,'连接正常',11,C['secondary'])
rule(517,294,828)
center(927,323,'今天 14:32',11,C['secondary'])
rr(809,376,534,111,'#E7EFF5',None,12)
text(832,394,'雪，帮我识别这张截图里的英文，',15,C['ink']);text(832,423,'再翻译成中文。',15,C['ink'])
rr(832,454,176,22,'#D6E4EF',None,4);text(842,458,'截图.png · 已提取文字',10,C['secondary'])
icon('spark',520,546,C['blue'],24);text(560,544,'雪',15,C['ink'],True)
text(561,590,'我读到了这句话：',14,C['secondary'])
text(560,634,'“Take a moment to rest your eyes.”',24,C['ink'],latin=True)
text(561,693,'中文是：“让眼睛休息一会儿。”',17,C['ink'])
text(561,748,'先看看远处，让眼睛放松一下，再慢慢继续。',14,C['secondary'])
text(561,805,'由本地 OCR 提取文字，再交给模型回答。',11,C['secondary'])
icon('check',561,846,C['blue'],15);text(585,842,'回答完成',11,C['secondary'])
rr(517,914,828,131,'#F1F6F9','#ADC3D4',10)
text(540,935,'继续和雪聊聊…',15,C['secondary'])
icon('plus',539,1002,C['secondary'],19);text(570,1000,'图片或文档',12,C['secondary'])
text(918,1006,'Enter 发送 / Shift + Enter 换行',10,C['secondary']);button(1232,990,91,'发送',primary=True)
# Companion panel: restrained object focus and a short provenance list.
rr(1382,242,362,802,DARK,None,14)
text(1411,272,'雪在听',18,'#EDF6FC',True)
stars(1410,327,300,250,31);pet(1456,350,213,243)
q='“So long as men can breathe”';qw=d.textlength(q,font=font(16,serif=True))/S;text(1563-qw/2,637,q,16,LIGHT,serif=True)
center(1563,675,'Shakespeare · Sonnet 18',10,DSUB,latin=True)
rule(1411,731,303,'#39566C')
for y,t,v in [(763,'当前来源','本地模型'),(812,'图片处理','OCR 文字提取'),(861,'云端发送','未启用')]:
    text(1411,y,t,11,DSUB);right(1715,y,v,11,'#ECF4FA')
rule(1411,920,303,'#39566C')
text(1411,950,'查看人设与长期记忆',12,'#D2E5F3');icon('arrow',1692,951,LIGHT,18)
text(1411,997,'本地会话不会自动转发到云端。',10,DSUB)
save('Yuki-冰银工作区-AI助手.png')

# Clipboard screen: list and full text, with a calm timer shelf as a separate useful object.
page(3,'工具','留住刚刚复制的内容，再继续手边的事。',['时间管理','剪贴板','待办事项'],1)
button(1475,114,129,'暂停记录','pause');button(1618,114,126,'清空历史')
field(216,244,496,'搜索最近 10 条文本')
text(218,304,'本次会话 · 最近 10 条',11,C['secondary'])
clips=[('休息提醒的英文','Take a moment to rest your eyes.','14:32'),('界面设计备忘','蓝白银，信息清楚，角色完整。','14:16'),('项目目录','C:/Projects/Yuki','13:50'),('一段英文诗句','But thy eternal summer shall not fade.','11:42'),('今天的待办','整理界面设计；检查动作衔接。','10:24')]
for i,(title,sub,t) in enumerate(clips):
    y=350+i*121
    if i==0:rr(209,y-13,511,105,'#E5EFF6',None,8)
    text(234,y,title,15,C['ink'],i==0);right(693,y+2,t,11,C['secondary'])
    text(234,y+36,sub,12,C['secondary']);text(234,y+68,'文本',10,C['secondary'])
    if i and i<4:rule(234,y+101,459)
text(234,1013,'仅保留最近 10 条不同文本。',12,C['secondary'])
ln([(751,242),(751,1044)])
text(790,254,'休息提醒的英文',22,C['ink'],True)
text(791,295,'今天 14:32 · 文本',12,C['secondary'])
button(1469,251,128,'复制内容','layout',True);button(1613,251,131,'删除此条')
rule(790,342,954)
text(792,392,'Take a moment to rest your eyes.',29,C['ink'],latin=True)
text(792,455,'完整内容',11,C['secondary'])
rule(790,540,954)
text(792,570,'如何使用',15,C['ink'],True)
text(792,612,'点选左侧条目，在这里查看完整文本；复制后可以直接粘贴。',14,C['secondary'])
text(792,648,'剪贴板内容不会自动发送给模型，也不会自动加入长期记忆。',13,C['secondary'])
# A compact, complementary time-management panel as a usable object.
rr(790,769,954,275,DARK,None,13)
text(819,795,'留一点时间给自己',18,'#F0F6FC',True)
text(819,837,'开始专注后，雪会减少主动打扰。',13,DSUB)
text(819,888,'25:00',62,'#F0F6FC',latin=True)
text(1041,927,'专注 / 5 分钟短休',12,DSUB)
button(1495,894,217,'开始专注','play',True,True)
rule(819,981,893,'#39566C')
text(819,1001,'时间管理',11,DSUB);right(1712,1001,'与总览共享同一个计时会话',11,DSUB)
save('Yuki-冰银工作区-工具剪贴板.png')

# Layout editor: a light canvas, one deep character panel and temporary block library.
page(0,'我的工作区','自由安排你的桌面工作区。',['默认总览','我的工作区'],1)
button(1501,114,105,'取消');button(1621,114,123,'完成布局',primary=True)
text(1300,124,'布局编辑中',12,C['blue'])
def handle(x,y):
    for i in range(2):
        for j in range(3):dot(x+i*4,y+j*4,.8,C['secondary'])
def panel(x,y,w,h,title,selected=False,dark=False):
    rr(x,y,w,h,DARK if dark else '#FFFFFF','#5B8BAE' if selected else '#C9D8E2',12,1.5 if selected else 1)
    handle(x+17,y+17);text(x+36,y+9,title,12,LIGHT if dark else C['ink'])
    rule(x+1,y+37,w-2,'#39566C' if dark else '#D5DFE6')
    if selected:
        for xx,yy in [(x,y),(x+w,y),(x,y+h),(x+w,y+h)]:rr(xx-3,yy-3,6,6,'#4A7D9F',None,1)
        ln([(x+w-21,y+h-7),(x+w-7,y+h-21)],'#5B8BAE');ln([(x+w-13,y+h-7),(x+w-7,y+h-13)],'#5B8BAE')
panel(216,242,619,802,'雪的此刻',True,True)
text(246,311,'雪',26,'#EDF6FC',True);text(246,355,'安静待机',14,LIGHT)
text(246,389,'下一步暂未安排。',12,DSUB)
stars(246,443,550,325,17);pet(367,432,314,356)
q='“But thy eternal summer shall not fade.”';qw=d.textlength(q,font=font(16,serif=True))/S;text(525-qw/2,844,q,16,LIGHT,serif=True)
button(252,947,189,'隐藏宠物','eye',dark=True);button(455,947,336,'移到屏幕右下角','corner',True,True)
panel(855,242,495,316,'时间与天气')
text(881,304,'14:32',64,C['ink'],latin=True);text(883,402,'10 月 20 日 · 星期二',12,C['secondary'])
ln([(1123,308),(1123,439)])
icon('sun',1150,321,C['blue'],29);text(1190,309,'18°',34,C['ink'],latin=True)
text(1152,377,'上海 · 多云',12,C['secondary'])
text(883,496,'本地时间与天气示例',11,C['secondary'])
panel(855,578,495,275,'今日足迹')
for y,t,title in [(644,'14:26','编译成功'),(707,'11:20','完成专注'),(770,'09:10','开始工作')]:
    dot(886,y+10,3,'#467C9F');text(903,y,t,11,C['secondary'],latin=True);text(977,y-2,title,14,C['ink'])
panel(855,873,495,171,'正在播放')
icon('music',882,940,C['blue'],24);text(922,931,'Clair de lune',18,C['ink'],latin=True)
text(923,968,'Claude Debussy',11,C['secondary'],latin=True)
rr(1259,937,42,42,C['deep'],None,21);icon('pause',1270,948,'#ECF5FC',20)
# Temporary block drawer, not another permanent sidebar.
rr(1374,242,370,802,'#EDF3F7','#BFCDDA',13)
text(1400,268,'添加区块',20,C['ink'],True)
text(1400,311,'拖入工作区，或点击添加。',12,C['secondary'])
field(1400,353,318,'搜索区块')
for i,(ic,title,desc,exists) in enumerate([('pet','雪的此刻','当前状态与快捷操作',True),('sun','时间与天气','时钟、地点与天气',True),('music','正在播放','系统媒体与播放控制',True),('play','专注计时','与时间管理共享状态',False),('layout','剪贴板','最近 10 条文本',False),('check','待办事项','计划与到期提醒',False)]):
    y=426+i*82
    icon(ic,1402,y+6,C['blue'],19);text(1436,y,title,14,C['ink']);text(1436,y+31,desc,11,C['secondary'])
    icon('check' if exists else 'plus',1693,y+10,C['secondary'] if exists else C['blue'],17)
    if i<5:rule(1400,y+65,318)
rule(1400,950,318)
text(1400,973,'移除区块只改变布局，',12,C['secondary']);text(1400,1001,'不会删除原有业务数据。',12,C['secondary'])
# footer is for edit affordances, no resting-state handles.
rr(213,1086,1110,36,C['paper'],None,0)
text(216,1095,'拖动标题栏移动 · 拖动选中区块右下角缩放',11,C['secondary'])
save('Yuki-冰银工作区-自定义布局.png')

