# Yuki 梳头动作 · 重做提示词（详细版）

用途：重做 `comb`（梳头）的 6 个关键姿势。目标是让动作**一眼看出是在梳头**：手里有清晰的梳子、梳齿贴着画面左侧仍连在头皮上的侧发、最外层 2–3 根发丝压过梳背，身体不位移。画风、抗锯齿强度、颜色和质感必须与真实待机帧一致。

> **贴发硬规则（先看这一条）**：所有发丝必须连在头皮上。梳齿只能压住最外层几根发丝，不能把一束头发挑起、分离、拉离头部，不能出现一条独立发束，不能把头发拉到胸前，左手不能抓发尾或扶头发。凡是出现“双手把一缕头发拉到胸前”的构图，直接判废重做。

> **画风硬规则（2026-10-29 返工补）**：动作对了但画风不对的版本已废弃。重新生成时不要以 `unified-final`、`attached-hair-final` 或旧 comb 帧作画风参考；唯一画风/身份母版是 `assets/living-idle/open.png` 第一格。姿势参考只负责“手臂在哪”，不能把它的脸、发量、裙装、线稿和比例带进来。生成后先在 256 下验比例：宽约 154–155px、高约 227px、脚底 y≈250、头顶 y≈24；偏窄/偏宽、脸变了、刘海变了，直接判废。

> 这次要修正的旧问题：梳子看不见或与白发糊在一起；手停在脸和胸前，动作像摸脸/抬手；头发对梳子没有反应；头、肩、脚在不同帧里漂移；帧与帧之间像换了一个人；**双手把发束拉到胸前，看起来像把头发梳下来/梳掉**；**动作对了但脸、发量、比例和线稿不是待机那一套**。

---

## 快速使用：通用提示词 + 每张图的详细提示词

使用方法：每张图按 **通用提示词 → 本图提示词 → 通用负向提示词** 的顺序拼成一条完整提示词。六张图共用同一段通用提示词和负向词，只替换“本图提示词”。

### A. 通用提示词（每张图共用，放在最前面）

```text
Master style and character lock for every frame: single full-body 2D chibi anime sprite of Yuki, front three-quarter view, fixed camera, same scale and framing as the reference idle sprite, centered at x≈128 in a 256×256 cell, nothing cropped, clean flat white background for later cutout. Yuki has long straight white hair (#F4F6FB highlights, #D9DDEF midtones, #C9D3EA shadows, #BFD6F2 cool tips), large round deep-blue eyes (#2E4F86 / #1E3A6E with #8CC8F0 highlights and dark navy upper lash lines, never pure black), white cat ears with pale pink inner ears, a light-blue off-shoulder dress (#9BD1F0 base, #7FB9DE shadows, #EAF7FF lace and highlights), a thin blue waist belt, a fine pale-blue pattern on the skirt, white socks, small light-blue round-toe shoes (#9BC5E8), a translucent pale-blue snowflake hairclip on the viewer's RIGHT side of her bangs, and a pair of snowflake earrings. Proportions: total height about 222 px, hair top y≈26, feet baseline y≈248, head-with-hair about 93 px (42%), chin y≈119, skirt hem y≈221 (88%), about 26 px of socks and shoes below the hem, hair width about 150 px, face width about 46 px, skirt width about 86 px, one shoe about 12 px wide. Soft Japanese cel-shaded anime style matching the idle sprite exactly: very thin blue-gray line art (#8FA9C6 at about 35–55% opacity, never thick black outlines), cool lavender-blue two-tone shadows (no gray or black shadows), low-saturation pastel ice-blue palette, flat cel fills with only very light gradients in the hair, dress folds and under the chin, clean digital illustration texture with no grain, no noise, no paper texture, no 3D specular, no plastic gloss, no airbrush blur, no bloom and no chromatic aberration. Anti-aliasing: medium-soft, with about 0.6–1.2 px semi-transparent edge transition at 256, hair tips fading over 1–2 px and 2–5 alpha levels; generate at 1024 or 2048 and downscale with premultiplied-alpha Lanczos; no jagged edges, no white fringe or halo, no black rim, no over-sharpened contour and no blurry edge. BODY LOCK: feet, skirt hem, torso center and head center stay anchored across all frames; only the right arm/hand/comb, a small 5–8° head tilt and a very small compression of the outermost side hair move. No walking, no stepping, no foot lift, no root translation, no body drift, no zoom, no camera rotation and no perspective change. Her LEFT hand stays relaxed at her side or rests lightly on the skirt, never crossing the body or covering the face or the hairclip. ATTACHED-HAIR RULE: every strand stays rooted in her scalp; the comb may slip under the outermost strand layer so a few thin strands lie over the comb spine, but it must never lift, pull, separate, twirl or carry a lock away from the head; no detached hair lock, no hair bundle in front of her chest, no hand holding the hair ends.
```

### B. 通用负向提示词（每张图共用，放在最后）

```text
walking, stepping, foot lift, root translation, lateral slide, body drift, zoom, camera rotation, perspective change, cropped head, cropped feet, floating, background scene, floor, cast shadow, text, watermark, logo, UI, multiple characters; missing comb, invisible comb, comb merged with hair, comb blending into white hair, brush, phone, stick, knife, oversized comb, deformed comb, wrong number of teeth; hand covering face, hand covering eyes, hand on cheek, hand in front of chest, stiff straight arm, elbow above shoulder, extra fingers, missing fingers, broken wrist, distorted hand; detached hair lock, separated lock, loose hair bundle, hair bundle in front of chest, hair pulled in front of the chest, hand holding hair ends, hand holding a hair lock, hand gripping the hair, hair lifted away from the scalp, hair floating, hair falling off the head, combing the hair off, long lock pulled down to the waist, clumps lifted away from the head, hair extension, wig piece; static hair, global hair swing, wind-blown hair, thick ribbon hair, solid hair mass, moved hairclip, hidden hairclip, hairclip on viewer left, missing earrings, extra accessories, outfit change, different character, different face, 3-head or 4-head proportion, short skirt, long legs, large feet; thick black outlines, hard 1px black rim, white halo, white fringe, jagged edges, pixel art, over-sharpened edges, blurry edges, airbrush, soft painting, 3D render, glossy plastic, metallic shine, strong specular, realistic shading, harsh cast shadow, grain, noise, paper texture, jpeg artifacts, bloom, lens flare, chromatic aberration.
```

### C. 每张图的详细提示词

#### 第 1 张 · 准备（梳子藏在身侧）

```text
Pose: neutral standing three-quarter pose, exactly like the idle reference, feet planted on the y≈248 baseline, body locked and centered at x≈128. Her RIGHT hand (viewer's LEFT) is lowered beside the skirt and holds a small pale ice-blue paddle comb with a short handle and 7–9 teeth, teeth turned toward her body, mostly hidden behind the hand and the skirt so the first frame blends with idle. Her LEFT hand rests naturally at her side. Head upright with a tiny 0–3° tilt, eyes calm and looking slightly toward the viewer's left, soft neutral mouth. No raised arm, no combing motion, no shoulder lift, no skirt sway, no foot movement. The snowflake hairclip on the viewer's RIGHT bangs and both earrings are fully visible. This is the calm starting frame, not a pose.
```

中文重点：身体和待机几乎一样；梳子只露一点，手在裙侧；不要提前抬手到脸前。

#### 第 2 张 · 举梳到侧发

```text
Pose: same locked standing body, same feet baseline and head center. Her RIGHT hand (viewer's LEFT) lifts the small pale ice-blue paddle comb to the long hair on the viewer's LEFT side, just below the cat ear and completely outside the face silhouette. The comb is fully visible in profile: short handle, about 26–32 px long at 256, cool-gray edge, a readable spine and 7–9 teeth, a small cool highlight; the teeth point toward the hair. Her LEFT hand stays relaxed at her side or rests lightly on the skirt; she does not reach across her body. Head tilts about 5–8° toward the comb, eyes follow the comb, shoulders stay low, the comb elbow stays below shoulder height. Skirt, feet, torso center and head center do not translate; only the right arm, hand and comb move. Hairclip and both earrings stay fully visible.
```

中文重点：这是“举起梳子”的关键帧；梳子必须清楚，不能像发夹或手指；头只轻轻歪，身体不动。

#### 第 3 张 · 梳齿入发（贴发，不挑起发束）

```text
Pose: same locked standing body and fixed camera. The comb is now touching the hair at the temple on the viewer's LEFT; the teeth slip under the outermost strand layer so two or three thin strands lie over the comb spine and the comb clearly sits inside the attached side hair, not floating in front of it. Every strand stays rooted in her scalp; do NOT lift, separate, twirl or carry any lock away from the head, and do not bring hair in front of her chest. The comb stays outside the face silhouette; the hairclip on the viewer's RIGHT bangs and both earrings stay fixed. Her LEFT hand remains relaxed at her side or lightly on the skirt, not hiding the face or the hairclip. Head tilts a little more toward the comb (about 6–8°), eyes look down along the comb, lips softly closed, calm and gentle. Feet, skirt hem, torso center and head center stay anchored; only the right arm, hand, comb and the outermost hair layer move. No root drift, no step, no zoom. The comb must read as a small paddle comb, not as a stick, a brush or a phone.
```

中文重点：梳齿真正进入头发，但发根仍连在头皮上；只让最外层几根发丝压过梳背，不要再“挑起/分离一束头发”；发夹、耳坠、裙摆和脚都不动。

#### 第 4 张 · 主梳向下拉

```text
Pose: same locked standing body, the main short stroke. The comb is drawn down along the viewer's LEFT attached side hair from the temple to jaw/cheek height, following the hair's outer contour. The outermost strand layer compresses slightly and a few thin strands slide over the comb spine, but every root stays attached to the scalp; no lock separates, no clump is carried away, and no hair comes in front of her chest. Her LEFT hand stays relaxed at her side or lightly on the skirt. Head tilts about 8° toward the comb, eyes track the comb downward, a faint gentle smile, lips closed. Shoulders lift no more than 1–2 px, body lean stays within 0–2°, skirt hem sways no more than 1 px. Feet, skirt hem, torso center and head center stay anchored; no root translation, no step, no zoom. The comb remains clearly visible against the white hair and never crosses the face or eyes.
```

中文重点：这是最像“梳头”的一帧；梳子沿外侧贴发向下，发丝压过梳背但不脱离头皮；身体锁住，只有手臂、梳子和最外层发丝动。

#### 第 5 张 · 梳尾离发，最外层发丝回落

```text
Pose: same locked standing body. The comb has reached jaw/cheek height and leaves the attached side hair; the outermost strands relax back with a soft 1–2 px settle and return toward their original silhouette; no lock was separated at any point. Her RIGHT hand lowers the comb naturally from the end of the stroke toward her side; her LEFT hand stays relaxed at her side. Head returns slightly toward center, eyes follow the comb down and then soften, a calm breath, one natural blink. The hairclip, both earrings, skirt hem, feet and torso center stay fixed. The comb stays visible and outside the face silhouette. Only the right arm, hand, comb and settling hair move; no root drift, no step, no zoom, no camera change.
```

中文重点：梳子离开下颌处的贴发、最外层发丝回落；发根仍连在头皮；手臂自然放下；只眨一次眼，不要重新抬手做第二次完整梳理。

#### 第 6 张 · 收梳，回到待机

```text
Pose: same locked standing body, the end of the action. The comb stroke has finished; the comb is lowered beside the skirt and held mostly hidden behind her RIGHT hand again, the teeth turned toward the body. Her LEFT hand remains relaxed at her side. The hair settles back into the exact idle silhouette; the snowflake hairclip on the viewer's RIGHT bangs and both earrings are unchanged. Head returns upright, a small satisfied smile, eyes soft and relaxed, maybe one final slow blink. The final pose should match the first frame and the idle stance closely enough to blend back without a pop. Feet stay on the y≈248 baseline; no walking, no lateral shift, no zoom. The body remains locked; only the lowering arm, comb and settling hair move.
```

中文重点：梳子收回裙侧，头发回到待机轮廓，表情放松；最后一帧要能无缝回到待机。

---

## 0. 参考图使用顺序（很重要）

1. **画风 / 身份 / 比例 / 配色唯一母版**：`console-v2/assets/living-idle/open.png` 左上第一格 256×256，放大到 1024 作 style + identity reference。成功的做法是只用这一张母版生成入发帧，再以入发帧为基准派生准备/举梳/抬梳，下梳帧最多再用一张旧姿势图，并且只把它当“手臂在哪”的参考。
2. **三视图**：`console-v2/assets/reference/yuki-turnaround.png` 只用于生成后的身份/比例核对，不作为画风参考，也不要和待机帧混成一个“画风基准”。
3. **姿势参考**：旧 comb 帧、`unified-final`、`attached-hair-final` 只能提供手臂/梳子的位置，不能继承它们的脸、发量、裙装、线稿、比例和配色。画面里出现“另一个人的脸”或角色明显变窄/变宽，直接判废。

生成时把参考分清：第 1 张负责画风、脸、发量、比例和配色；姿势图只负责这次的右臂位置。不要用一张“姿势图”同时充当画风参考。

---

## 1. 共用角色与画风（每帧都放在最前面）

### 1.1 中文版

```text
2D 日系 Q 版全身立绘，Yuki：白色长直发猫耳少女，发丝带极淡的蓝紫灰阴影和半透明发梢；大而圆的深蓝眼睛，深蓝近黑（不是纯黑）的上睫线；白色猫耳，耳内侧淡粉；浅蓝色露肩连衣裙，白色蕾丝领口与裙边，腰间细蓝腰带，裙摆有极细的浅蓝花纹；白色短袜，浅蓝色小圆头鞋；左侧刘海（观众视角右侧）别一枚半透明淡蓝雪花发夹，两侧各有一枚雪花耳坠。正面偏 3/4 站姿，镜头固定，角色完整入画，从耳尖到鞋底都不裁切。

画风：与待机原画完全一致的柔和日系 cel 上色，低饱和、高明度、冷色系；线条是极细的蓝灰色线稿，不是黑色粗线；头发、裙子和皮肤的阴影都是冷调淡蓝紫，不用灰黑阴影。平涂为主，只在发丝内部、裙褶和颈下保留非常轻的两段式渐变。干净的数码手绘质感，没有颗粒、纸张纹理、噪点、3D 高光、塑料反光、喷枪糊边或镜头光晕。

构图与比例：256×256 单格；角色总高约 222px，头发顶端 y≈26，鞋底基线 y≈248；含发头部高度约 93px（占 42%），下巴约在 y≈119；裙摆线约在 y≈221（总高 88%），裙下只露出约 26px（12%）的袜子和鞋；头发宽约 150px，脸宽约 46px，裙摆宽约 86px，单只鞋宽约 12px。角色水平居中在 x≈128，所有帧的头顶、下巴、裙摆、鞋底和头宽保持同一尺度与同一基线；不缩放、不俯视、不仰视、不旋转镜头。背景用干净纯白（或纯色键），不画任何场景元素，方便后期抠图。

抗锯齿：轮廓是平滑的矢量感边缘，256 尺寸下约 0.6–1.2px 的半透明过渡；发梢和裙边可以有 1–2px 的柔和淡出，保留 2–5 级 alpha 过渡；不能有锯齿台阶、白色硬边、黑边、过锐的描边或糊成一团的边缘。生成时用 1024/2048 出图，再用预乘 alpha 的 Lanczos 缩到 256，不要把图锐化。

颜色：发色 #F4F6FB（亮）、#D9DDEF（中间调）、#C9D3EA（阴影）、#BFD6F2（冷色发梢）；裙子 #9BD1F0（主色）、#7FB9DE（阴影）、#EAF7FF（蕾丝与高光）；皮肤 #FBE9E4、阴影 #F3D6D0、腮红 #F3C9C9；虹膜 #2E4F86 / #1E3A6E、高光 #8CC8F0；鞋 #9BC5E8，袜子 #F7FAFD；线稿 #8FA9C6 左右、35–55% 不透明度，绝不能用纯黑。
```

### 1.2 English prompt block（可直接粘到模型前）

```text
Single full-body 2D chibi anime sprite of Yuki, front three-quarter view, fixed camera, centered, nothing cropped, clean flat white background for later cutout. Yuki is a cute cat-eared girl with long straight white hair with very pale blue-lavender shadows and semi-transparent tips, large round deep-blue eyes with dark navy upper lash lines (not pure black), white cat ears with pale pink inner ears, a light-blue off-shoulder dress with white lace trim, a thin blue waist belt, a fine pale-blue pattern on the skirt, white socks and small light-blue round-toe shoes, a small translucent pale-blue snowflake hairclip on the viewer's RIGHT side of her bangs, and a pair of snowflake earrings. Soft Japanese cel-shaded anime style matching the reference idle sprite exactly: low-saturation pastel ice-blue palette, thin blue-gray line art (never thick black outlines), cool lavender-blue shadows (no gray/black shadows), flat cel fills with only very light two-step gradients in the hair, dress folds and under the chin. Clean digital illustration texture: no grain, no paper texture, no noise, no 3D specular, no plastic gloss, no airbrush blur, no bloom, no chromatic aberration. Same head-to-body ratio, same head width, same foot baseline and same silhouette as the reference idle frame: total height about 222 px in a 256 px cell, head-with-hair about 93 px (42%), chin at about y=119, skirt hem at about 88% of height, feet baseline y≈248, hair width about 150 px, face width about 46 px, skirt width about 86 px, one shoe about 12 px wide. Smooth vector-like anti-aliased edges: 0.6–1.2 px soft alpha transition at 256, hair tips fading over 1–2 px with 2–5 alpha levels; no jaggies, no white fringe, no black rim, no over-sharpened contour, no blurry edge. Palette: hair #F4F6FB / #D9DDEF / #C9D3EA with #BFD6F2 cool tips; dress #9BD1F0 / #7FB9DE / #EAF7FF; skin #FBE9E4 / #F3D6D0 / #F3C9C9 blush; iris #2E4F86 / #1E3A6E with #8CC8F0 highlight; shoes #9BC5E8; line art #8FA9C6 at about 35–55% opacity, never pure black.
```

---

## 2. 动作核心关键词

```text
in-place hair combing, standing still, no walking, no root movement, no lateral drift; she holds a small pale ice-blue paddle comb with a short handle in her RIGHT hand (viewer's LEFT side); the comb is about 26–32 px long at 256, clearly visible with a cool-gray edge, a readable spine and 7–9 teeth, never merging into the white hair; she lifts the comb to the long hair on the viewer's LEFT side, just below the cat ear; the comb slips under the outermost strand layer at the temple and is drawn slowly down along the attached side hair only to jaw/cheek height; two or three thin strands compress over the comb spine while every root stays attached to the scalp; no lock separates, no clump is lifted away, no hair is carried in front of her chest, and her left hand never holds the hair; the rest of the hair silhouette stays; the snowflake hairclip on the viewer's RIGHT bangs and both snowflake earrings remain visible and fixed; her LEFT hand stays relaxed at her side or rests lightly on the skirt, never crossing the body or covering the face or the hairclip; head tilts 5–8° toward the comb; eyes follow the comb downward; calm gentle expression, one small blink during the return; shoulders lift 1–2 px, body leans 2–3°, weight stays on both planted feet, skirt hem sways no more than 1 px; soft slow everyday tempo, one short attached-hair stroke with a small release, then the comb lowers and the hair settles; the first and last pose return to the neutral standing pose so the action blends back to idle.
```

---

## 3. 负向提示词

```text
walking, stepping, foot lifting, root translation, sliding sideways, body drifting, zoom, camera rotation, different camera angle, perspective change, cropped head, cropped feet, floating, jumping; comb missing, comb invisible, comb merged with hair, comb blending into white hair, brush, phone, stick, knife, oversized comb, extra teeth, deformed comb; hand covering face, hand covering eyes, hand on cheek, hand in front of chest, stiff straight arm, elbow above shoulder, extra fingers, missing fingers, broken wrist, distorted hand; detached hair lock, separated lock, loose hair bundle, hair bundle in front of chest, hair pulled in front of the chest, hand holding hair ends, hand holding a hair lock, hand gripping the hair, hair lifted away from the scalp, hair floating, hair falling off the head, combing the hair off, long lock pulled down to the waist, clumps lifted away from the head, hair extension, wig piece; hair not moving, global hair swing, wind-blown hair, thick ribbon hair, solid hair mass, hairclip moved, hairclip hidden, hairclip on viewer left, missing earrings, extra accessories, outfit change, different character, different face, different eye color, 3-head or 4-head proportion, short skirt, long legs, large feet; thick black outlines, hard 1px black rim, white halo, white fringe, jagged edges, pixel art, over-sharpened edges, blurry edges, airbrush, soft painting, 3D render, glossy plastic, metallic shine, strong specular, realistic shading, harsh cast shadow, grain, noise, paper texture, jpeg artifacts, bloom, lens flare, chromatic aberration, text, watermark, logo, UI, frame border, grid, multiple characters, background, floor, ground shadow.
```

---

## 4. 六个关键姿势（逐帧关键词）

每帧先放“共用角色与画风”，再放本帧描述。六个关键姿势建议对应现有 `comb` 的 6 个 keyframe，时长可沿用约 260 / 400 / 600 / 720 / 450 / 300 ms，再做平滑补帧。

### K1 · 准备（梳子藏在身侧，像待机）

```text
Neutral standing three-quarter pose, feet planted on the same baseline as the idle, arms relaxed. Her RIGHT hand (viewer's LEFT) is lowered beside the skirt and holds the small pale ice-blue comb with the teeth turned toward her body, mostly hidden behind the hand and skirt so the first frame blends with the idle pose. Her LEFT hand rests naturally at her side. Head upright, eyes calm, looking slightly toward the viewer's left. No combing yet, no raised arm, no walking. Keep the same head size, skirt hem and foot baseline as the idle reference.
```

### K2 · 举梳到侧发

```text
Same standing pose, fixed camera and foot baseline. Her RIGHT hand (viewer's LEFT) lifts the small pale ice-blue paddle comb to the side of her long hair on the viewer's LEFT, just below the cat ear and outside the face silhouette. The comb is fully visible in profile: a short handle, about 26–32 px long at 256, cool-gray edge, a readable spine and 7–9 teeth, a small cool highlight; the teeth point toward the hair. Her LEFT hand (viewer's RIGHT) stays relaxed at her side or rests lightly on the skirt; she does not reach across her body. Head tilts about 5–8° toward the comb, eyes follow the comb, shoulders relax, elbow stays below shoulder height. The snowflake hairclip on the viewer's RIGHT bangs and both earrings stay fully visible. No body translation, no stepping.
```

### K3 · 梳齿入发（贴发，不挑起发束）

```text
Same fixed standing pose. The comb is now touching the hair at the temple on the viewer's LEFT; the teeth slip under the outermost strand layer so two or three thin strands lie over the comb spine and the comb sits inside the attached side hair. Every strand stays rooted in her scalp; do NOT lift, separate, twirl or carry any lock away from the head, and do not bring hair in front of her chest. Her LEFT hand stays relaxed at her side or rests lightly on the skirt, without hiding the face or the hairclip. Head tilts a little more toward the comb, eyes look down along the comb, lips softly closed, calm and gentle. The rest of the hair silhouette, the hairclip and the earrings stay fixed. The body weight stays on both feet; only a 2–3° lean, no root drift. The comb must read as a comb, not as a stick or a brush.
```

### K4 · 短距离下梳（发根仍然连着）

```text
Same fixed standing pose, one short main stroke. The comb is drawn slowly down along the viewer's LEFT attached side hair from the temple to jaw/cheek height, following the hair's outer contour; the outermost strand layer compresses slightly and a few thin strands slide over the comb spine, but every root stays attached to the scalp. No lock separates, no clump is carried away, and no hair comes in front of her chest. Her LEFT hand stays relaxed at her side or lightly on the skirt; the comb elbow stays soft and below the shoulder. Head tilts 8° toward the comb, eyes track the comb downward, a faint gentle smile. Shoulders rise about 1–2 px, body leans 2–3°, skirt hem sways no more than 1 px. No step, no lateral movement, no zoom; the comb remains clearly visible against the white hair.
```

### K5 · 梳尾离发，最外层发丝回落

```text
Same fixed standing pose. The comb has reached jaw/cheek height and leaves the attached side hair; the outermost strands relax back with a soft 1–2 px settle and return toward their original silhouette; no lock was separated. Her RIGHT hand lowers the comb naturally from the end of the stroke toward her side; her LEFT hand stays relaxed at her side. Head returns slightly toward center, eyes follow the comb down and then soften, a calm breath, one blink. Hairclip, earrings, skirt hem and feet stay fixed; the comb stays visible and outside the face silhouette. No root drift, no step.
```

### K6 · 收梳，回到待机

```text
Same fixed standing pose, the end of the action. The comb stroke has finished; the comb is lowered beside the skirt and once again held mostly hidden behind her RIGHT hand, the teeth turned toward the body. Her LEFT hand remains relaxed at her side. The hair settles back into the exact idle silhouette; the snowflake hairclip and earrings are unchanged. Head returns upright, a small satisfied smile, eyes soft and relaxed. The final pose should match the first frame and the idle stance closely enough to blend back without a pop. Feet stay on the same baseline; no walking, no lateral shift, no zoom.
```

---

## 5. 画面风格、抗锯齿、颜色与质感（硬指标）

### 5.1 风格

- 与 `assets/living-idle/open.png` 第一格相同的柔和日系 cel 上色；不是厚涂、不是水彩糊边、不是 3D、不是像素画。
- 线稿：极细的蓝灰线（#8FA9C6 左右，35–55% 不透明度）；外轮廓在 256 下约 0.6–1.2px；内部发丝线更淡；禁止纯黑、禁止 2px 以上粗黑边。
- 阴影：冷调淡蓝紫，两段式为主；不要灰黑阴影、不要高对比硬阴影、不要地面投影。
- 高光：只在眼睛、发丝和裙面有很轻的冷白高光；不要金属反光、塑料高光、强镜面。

### 5.2 抗锯齿（与待机帧对齐）

- AA 强度：中等偏软，接近待机帧，不要硬边也不要糊边。
- 256 成品：轮廓边缘有约 0.6–1.2px 的半透明过渡；发梢/裙边可以 1–2px 渐隐；边缘保留 2–5 级 alpha，不要一刀切的硬边。
- 色彩管理：sRGB；导出 PNG-24/32；不要加对比度、饱和度、锐化或滤镜；不要色彩偏移。
- 生成分辨率建议 1024 或 2048，再按预乘 alpha + Lanczos 缩到 256；不要锐化、不要加描边、不要用最近邻缩放。
- 禁止：锯齿台阶、白色硬边/白边、黑边、过锐描边、整圈均匀的粗轮廓；也不能糊成没有边缘。
- 参考待机格的边缘透明度比例：256 下非透明像素约 2.4–2.5 万，其中约 2,900 个是半透明边缘像素（约 11–12%）。新帧应接近这个“有柔和过渡但不脏”的程度。

### 5.3 颜色（以实际待机观感为准，下面是锚点）

| 区域 | 主色 | 阴影 | 高光/其他 |
| --- | --- | --- | --- |
| 头发 | #F4F6FB | #D9DDEF / #C9D3EA | 发梢 #BFD6F2 |
| 裙子 | #9BD1F0 | #7FB9DE | 蕾丝/高光 #EAF7FF |
| 皮肤 | #FBE9E4 | #F3D6D0 | 腮红 #F3C9C9 |
| 眼睛 | #2E4F86 / #1E3A6E | 上睫线 #3A4E7A | 高光 #8CC8F0 |
| 鞋/袜 | #9BC5E8 | — | 袜子 #F7FAFD |
| 发夹/耳坠 | #CFE4F7 | #A9CBE8 | 高光 #FFFFFF |
| 梳子 | #B9D9EE | 边缘/齿 #8FB8D8 | 高光 #EAF7FF |

- 整体低饱和、高明度、冷色；不要偏黄、偏灰、偏紫过头。
- 白发不能变成纯白死白：用 #F4F6FB 的亮面和 #C9D3EA 的冷阴影撑出体积。
- 裙子的蕾丝和浅蓝花纹要清晰但细，不要变成厚白边或大面积深蓝。

### 5.4 质感

- 平涂 + 极轻的两段式渐变；发丝内部有细线分层，发梢半透明。
- 干净数码绘：无颗粒、无纸张纹理、无噪点、无 jpeg 脏边、无镜头光晕、无色差。
- 蕾丝、腰带、雪花发夹的细节在 256 下仍然可辨认，但不能靠加粗线条来“保细节”。

---

### 5.5 梳子道具单独生成（可选，但推荐）

如果模型总是画不好手里的梳子，可以单独出道具，再绑定到手部：

```text
A small pale ice-blue paddle comb prop with a short handle, side three-quarter view, about 26–32 px long at 256 scale, a readable spine and 7–9 clearly separated teeth, cool blue-gray edge #8FB8D8, body #B9D9EE, small cool white highlight #EAF7FF, same soft Japanese cel-shaded style and same anti-aliased edges as the Yuki idle sprite; no hand, no arm, no text, no logo, no background objects, clean flat white background, centered, nothing cropped, no black outline, no 3D gloss, no metallic shine.
```

道具单独生成时保持与角色同一线宽和 AA；合成到手部时要让手指包住梳柄、梳齿朝向头发，并保留至少 1px 的冷灰边缘，避免和白发糊在一起。

---

## 6. 生成与后期流程

1. 先用 1024 或 2048 出图，保持 1:1，角色位于画面中央，背景用纯白或纯色键；不要依赖模型直接输出透明 alpha。
2. 一次只生成一个关键姿势。若模型能稳定出相位，可尝试**单排 4 格**（同一相机、同一比例、同一基线），每格只讲一个相位；不要一次生成 4×2 或整张分镜表。
3. 抠图用项目现有的 `rembg isnet-anime` 流程；白发对浅灰背景不可靠，不要用颜色键硬抠。
4. 按“头宽 + 脚底基线”归一化到 256：同时满足头顶 y≈24–26、脚底 y≈250、宽约 154–155px、高约 227px；不要按身高缩放坐/跪姿势。
5. 缩放到 256 时用预乘 alpha + Lanczos；不要锐化、不要加白边。缩完检查发梢、裙边和梳齿的半透明边缘。
6. 先在 160px 大小、深色壁纸上看一眼：如果梳子、贴发发丝和发夹看不清，这张就不能用。
7. 6 个关键姿势通过后再做平滑补帧；不要把独立静帧直接交叉溶解当动画。
8. 每帧叠在待机帧上做 50% 透明对位，检查头顶、下巴、裙摆、鞋底和头宽；再放大 4 倍对比线宽、AA 和颜色，不要只看缩略图。

### 6.1 画风锁定流程（2026-10-29 成功做法）

1. 取 `assets/living-idle/open.png` 第一格 256，合成到白底，Lanczos 放大到 1024，作为**唯一** style + identity 参考。
2. 生成入发帧：只给待机母版 + 动作文字，要求“只改右臂，脸/刘海/发量/裙装/比例不变”。生成后立刻对照待机检查脸、刘海、发量和 256 宽度；不合格直接重生成。
3. 生成下梳帧：参考图 1 = 待机母版（画风/身份），参考图 2 = 旧姿势图（只取手臂位置）。提示词明确“第一张负责画风/身份，第二张只负责手臂位置，不要复制第二张的脸、发量、裙装和线稿”。
4. 生成准备/举梳/抬梳：以入发帧为基准做局部编辑（只改右臂和梳子），不要每帧重新从待机生成，避免换脸。
5. 抠图、去白边后，六帧共用同一缩放和偏移：脚底 y≈250、高约 227、宽约 154–155。
6. 叠待机做 50% 对位，检查头顶、下巴、裙摆、鞋底、头宽；不合格的帧不能用横向拉伸或后期滤镜掩盖。

### 6.2 帧间锁定 + 补帧流程（2026-10-29 第二次返工）

1. 取入发帧（contact）作为身体母版；把被抬起手臂挡住的头/发区域用准备帧（ready）的同一位置补回，得到一张没有抬起手臂的干净母版。
2. 每一帧只抠“手臂 + 梳子”层，贴回同一张母版；准备、举梳、入发、下梳、下梳中段共用同一张脸、刘海、猫耳、发夹、耳坠、裙面、裙摆和鞋底。
3. 检查静态区域 diff：脸、裙摆、脚等不含手臂的区域，逐帧对母版的平均差异应接近 0（本版 256 下 <0.5）；大于 1 说明还在换脸/换发。
4. 举梳/落梳不要用光流硬补大跨度手臂，会把手臂和梳子拉成双影。用同一手臂层绕袖口 pivot 做 5° 步进旋转补帧（0° → -115°），再贴回母版。
5. 入发和抬梳用 2 帧交叉淡化；下梳段用实际 contact / stroke-mid / stroke 手臂层衔接。40ms/帧，目标 55–70 帧、2.8–3.2s，关键姿势 12–15 张。
6. 检查完整 GIF：暂停单帧看到轻微叠影可以接受，但正常播放不能有双手、双梳子或整帧闪动。

### 6.3 本次采用的 15 个关键姿势

准备（+130°）→ 举梳 +115° → +100° → +70° → +40° → 举梳到位 +15° → 入发 0° → 下梳中段 +18° → 下梳到下颌 +30° → 抬梳 +15° → 落臂 +40° → +70° → +100° → +115° → 准备。全部是同一手臂层绕袖口旋转；入发和抬梳共用同一张“梳子到发际线”的姿势。

### 6.4 单手臂 + 单梳子 rig（2026-10-29 第三次返工）

1. 不要再从多张生成图各抠一条手臂。以入发帧的“手臂 + 梳子”为唯一运动层，所有姿势都靠这层绕袖口 pivot 旋转：
   - 准备：+130°（手在裙侧，梳子清楚）。
   - 举梳：+120° → +15°，5° 步进。
   - 入发：0°。
   - 下梳中段：+18°；下梳到下颌：+30°。
   - 抬梳：+15°；落臂：+20° → +130°，5° 步进。
2. 所有帧使用同一把梳子、同一条前臂，不再出现“准备小梳子 / 入发大梳子 / 下梳淡梳子”，也不需要入发/抬梳的整层交叉淡化。
3. 头/发在入发和下梳时向梳子一侧倾 2°：角度 60° 以上为 0，20° 以下为 -2°，中间线性过渡。头组绕脖子旋转，身体、裙面、脚底保持锁定；中央裙面/脚底对母版的最大平均差异约 1.5（主要是随头移动的发梢）。
4. 40ms/帧，66 张源帧 / 51 帧 GIF，总时长 2.64s；关键姿势 15 张。
5. 这个方案的一致性最好，但前臂是刚性旋转，肘/腕不会自然弯曲；袖口仍是固定的泡泡袖。要更软需要单独补屈肘手臂或可动袖口层。

---

## 7. 验收清单

- [ ] 梳子清晰可见：有短手柄、有 7–9 根梳齿、有冷灰边缘，在 160px 下不和白发糊在一起。
- [ ] 梳子只出现在侧发外侧，不穿过脸、不挡眼睛、不消失在手里。
- [ ] 梳齿贴着最外层侧发进入；只有 2–3 根发丝压过梳背，发根始终连在头皮上；没有被挑起、分离、拉到胸前的独立发束。
- [ ] 左手全程在身侧，不抓发尾、不扶头发、不在胸前；胸前没有一条与头部断开的发束。
- [ ] 下梳只从太阳穴到下颌/脸颊，不出现“从头到腰”的长距离拉发；发束不离开头皮。
- [ ] 雪花发夹始终在观众视角右侧的刘海上；两侧耳坠都在；没有镜像翻转。
- [ ] 头身比 2.4，头含发约 93px，裙摆约 88%，裙下约 12%，鞋很小；没有变成 3–4 头身或短裙长腿。
- [ ] 256 下角色宽约 154–155px、高约 227px、脚底 y≈250，和待机同一宽度；不是窄一圈或大一圈的“另一个人”。
- [ ] 脸、眼睛、刘海、猫耳、发夹、耳坠、线稿和配色与待机同一套；不是生成模型自己的脸；裙面花纹可以不同，但画法、颜色、线宽一致。
- [ ] 六帧的头顶、下巴、裙摆、鞋底和头宽在同一尺度；没有整体平移、缩放、镜头旋转。
- [ ] 帧间静态细节一致：脸、刘海、猫耳、发夹、耳坠、裙面、裙摆、鞋底来自同一身体母版；除头部 2–3° 倾斜区域外，非手臂区域对母版的平均差异 <0.5。
- [ ] 所有帧使用同一只手臂、同一把梳子：准备、举梳、入发、下梳的梳子大小/蓝色对比一致；没有准备小梳子、下梳淡梳子或双梳。
- [ ] 举梳/落梳的中间帧是同一手臂层绕袖口旋转，没有双手、双梳子或整帧闪动；完整 GIF 55–70 帧、2.8–3.2s，关键姿势 ≥12 张。
- [ ] 入发/下梳有 2–3° 歪头，身体、裙面、脚底锁定；中央裙面/脚底对母版的平均差异 <2。眼睛不必独立跟随，但头不能完全静止。
- [ ] 脚不抬、不走路、不侧移；身体只有 2–3° 倾斜、头 5–8° 倾斜、肩 1–2px 起伏。
- [ ] 眼睛跟随梳子，K5 附近自然眨眼一次，结尾有很轻的微笑；没有夸张腮红、汗滴或生气表情。
- [ ] 线稿是细蓝灰线，不是黑边；阴影是冷蓝紫，不是灰黑；没有 3D 高光、塑料感、颗粒或糊边。
- [ ] 256 边缘有 0.6–1.2px 柔和 AA，发梢 1–2px 渐隐；无锯齿、无白边、无黑边、无过锐描边。
- [ ] 首帧和末帧都接近待机站姿，动作结束能平滑回到待机。
- [ ] 160px + 深色壁纸下，梳头动作仍然一眼可读。

---

## 8. 与现有运行时的对应关系

- 动作 id：`comb`；分类：站立日常；6 个关键姿势，目标总时长约 2.7–3.2s，节奏舒缓。
- 建议沿用现有 6 keyframe → 平滑补帧的流程；补帧后保持头/肩/裙摆锚点，不产生横向根位移。
- 画风验收以 `assets/living-idle/open.png` 第一格为准；身份/比例以 `assets/reference/yuki-turnaround.png` 为准；旧 comb 帧只作姿势参考，不作画风参考。
- 2026-10-29 单手臂 rig 版在 `output/comb-generated/idle-style-rig/`：15 个关键姿势、51 帧 GIF / 2.64s；入发手臂+同一把梳子绕袖口旋转，准备 +130°、下梳 +18/+30°，加 2° 歪头。运行时尚未替换。`idle-style-smooth/` 帧间锁定但运动层用了两套手臂/梳子、有双梳交叉淡化，已被本版取代。
