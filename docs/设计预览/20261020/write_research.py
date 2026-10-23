from pathlib import Path
import json,tempfile,shutil
root=Path(__file__).resolve().parents[3]
out=root/'docs/design-research'
out.mkdir(parents=True,exist_ok=True)
cache=Path(tempfile.gettempdir())/'yuki-refero-styles-20261020'
rows=json.loads((cache/'index.json').read_text(encoding='utf-8'))
notes=json.loads((Path(__file__).parent/'refero-notes.json').read_text(encoding='utf-8'))
assert len(rows)==len(notes)==54
deep={5,7,8,14,23,36,37,54}
header='''# Refero Styles：54 份样式研究记录

日期：2026-10-20（Asia/Shanghai）  
研究入口：https://styles.refero.design/

## 范围与阅读方法

54 个不同样式详情 URL 全部读取成功，并均已对照其截图审阅，阅读设计概要、布局与组件目录；其中 8 份另看完整分辨率截图和组件细节。54 个 URL 无重复；同一品牌不同产品页明确标名，并不等于 54 家不同公司。

多数样本为宣传页或其内嵌产品截图。此次未测试原产品交互、未核验动态效果。Refero 的设计说明属于其测量与解释，不是品牌官方设计规范。所示产品名也不代表本次核实了该产品的发布日期。

截图与文字冲突时以可见截图为限，R23 Default 已专门标记。R26 标题是 Home，截图品牌是 fluidtouch。所有借鉴与舍弃均为针对 Yuki 的设计判断；Adobe 式停靠行为来自用户要求，不能声称这批宣传页已经验证了该功能。

## 54 份逐项审阅

| 编号 | 样式与详情链接 | 观察 | Yuki 借鉴位置 | 舍弃或证据边界 | 深度 |
|---|---|---|---|---|---|
'''
parts=[header];index=[]
for r,n in zip(rows,notes):
 obs,take,skip=n; ident='R'+str(r['id']).zfill(2);title=r['name'].replace('|','/')
 depth='重点复核' if r['id'] in deep else '截图＋概要'
 parts.append(f'| {ident} | [{title}]({r["url"]}) | {obs} | {take} | {skip} | {depth} |\n')
 index.append(dict(id=ident,title=r['name'],sourceUrl=r['url'],screenshotUrl=r['image'],reviewedOn='2026-10-20',depth=depth,observation=obs,adopt=take,rejectOrLimit=skip))
parts.append('\n## 截图联系表\n\n六张联系表按编号排列，每张九份。仅作设计研究证据，保留来源；不得作为 Yuki 的生产或宣传资产。完整截图与第三方设计原文留在临时缓存，不收入正式素材目录。\n\n')
for i in range(1,7):
 name=f'Refero-样式联系表-{i:02d}.jpg';shutil.copy2(cache/f'board-{i}.jpg',out/name)
 parts.append(f'- [R{(i-1)*9+1:02d}–R{i*9:02d} 联系表]({name})\n')
parts.append('\n## 归纳\n\n优先参考 Linear 的暗色层级、Perplexity 的输入中心、teenage engineering 的对象优先、Attio 的标签与操作区分工。Dala 只提取低密度空间感。Raycast 与 Paste 以本次可见截图为限，不能推断完整产品行为。\n\nYuki 保持蓝白银、固定五栏、原角色素材和克制星辰。详细方案见 [Yuki Refero UI 设计文档](../Yuki-Refero-UI设计文档.md)。\n')
(out/'Refero-Styles-54份样式研究.md').write_text(''.join(parts),encoding='utf-8')
(out/'refero-styles-index.json').write_text(json.dumps(index,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print('Saved',len(rows),'unique records and 6 contact sheets')
