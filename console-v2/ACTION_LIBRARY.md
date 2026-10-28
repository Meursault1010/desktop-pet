# 动作库

在控制台左侧点击“动作库”，即可搜索、分类选择动作，播放/暂停、调整 0.25～2 倍速度、循环或拖动时间轴逐帧查看。“在桌面播放”会把当前动作交给真实宠物；“恢复待机”立即停止手动动作。手动播放不会改写安静模式、暂停走动等设置。隐藏宠物会停止动作。

默认呼吸、头发微动和随机眨眼保持原来的连续待机实现，没有被六帧动作取代。动作库里的“眨眼”是已有静帧序列的演示，不是默认待机调度器。点击、拖动会使用各自的反应动作；松开拖动后恢复待机。

## 素材目录

- `assets/actions/catalog.json`：动作名称、来源、帧数、各帧停留时间和检查状态。
- `assets/actions/<动作ID>/01.png...`：透明背景、统一画布的独立静帧。
- 同目录 `atlas.png`：运行时图集；`poster.png`：控制台封面。
- `action-work/<动作ID>/raw.png`：生成服务返回的原始六格图；`prompt.txt`：完整提示词，便于复现和精修。
- `qa/actions/`：各动作的逐帧总览 JPG 与播放 GIF，用于检查动作含义、背景、跳变和角色一致性。
- `frontend/public/actions/`：供控制台预览的镜像。图集为无损 WebP（解码后逐像素一致），封面限制在 512px，不携带编号帧；重建素材后运行 `optimize_frontend_actions.py` 刷新镜像。

原始“图片”目录不覆盖。向前/向右打滚的第一张原图是多角色总览，已排除出播放序列。阅读单图标为“静态姿势”，不冒充完整动作。“靠文件夹睡觉”的原图道具和姿势变化明显，保留转换结果并标记待精修。

## 实现

`action_player.py` 是不依赖 Qt 的确定性帧调度器，支持结束、循环、调速和立即停止。`pet.py` 用 Qt 从透明图集中取出当前帧，不做整幅图片透明度交叉渐变，避免重新引入以前的亮度闪烁。大姿势变化不靠交叉淡化伪装成中间帧。

`pet_backend.py` 接收 `play_action`（action_id、loop、speed）和 `stop_action`，Rust 仅转发白名单命令，不能传任意图片路径。React 的 `ActionLibrary.tsx` 用 Canvas 独立预览同一图集及帧时序，预览不会操作桌面宠物。

新生成素材最初是六关键帧的精灵动画。多数 4～12 帧的低帧率站立/情绪/日常/进食/持屏动作现已用 `build_smoothed_actions.py` 依据相邻关键帧生成单源光流中间帧，以约 70ms 步长并入同一动作，总时长保持不变；关键帧原图与原始停留时间备份在 `action-work/smooth/<动作ID>/original/`，catalog 用 `keyframes`、`keyframe_durations`、`smoothed`、`authored_motion` 记录差异。攀爬、打滚、物理撞击、睡眠、舞蹈和双帧静态姿势不走该流程；攀爬保留原有的首尾逐像素一致与过渡桥接。`screen` 的 `loop_start` 会在插帧后重新映射到对应关键帧。中间帧仍属于插值而非逐帧重绘，细小线稿漂移可能存在；追求电影级连贯性时应重画对应中间帧。

## 重建

离线工具 `build_action_library.py` 需要 Pillow、numpy、OpenCV；宠物运行时不需要这些图像处理依赖。

1. 不带参数：处理已有素材和阅读静态姿势。
2. `build_smoothed_actions.py --actions <动作ID...> [--force] --apply`：为低帧率动作烘焙中间帧；`--force` 允许从原图备份重建已平滑动作。
3. `build_frame_alignment.py --write`：动作帧数变化后重建逐帧对齐。
4. `optimize_frontend_actions.py`：刷新前端无损 WebP 镜像与镜像 catalog。
5. `frontend` 目录执行 `npm run build`，工作台才会带上新动作。
6. `--generate`：通过已安装的 shengtu-skill 生成缺失动作，已有 raw.png 会复用，不重复请求。
7. `--generate --only stretch`：只处理某个动作。
8. 前端资源发生变化后重新编译 Tauri EXE；仅 Python 播放逻辑变化不必重新编译 EXE。
9. 若生成脚本改写了 `frontend/public/actions`，再运行 `optimize_frontend_actions.py` 把它转回 WebP 镜像；测试会拒绝回归的编号 PNG。

生成输出和透明静帧均保留在项目内。API 密钥由技能私有配置解析，不复制到项目。

## 横向走路实现

左右走动当前由 `walk_rig` 在运行时实时绘制（`pet.py` / `pet_presence.py` 的 `paint_walk`）；侧身朝向是用户确认的规则。`assets/motion-v2/walk-atlas` 的 8 帧正面小图集是 2026-10-28 被否决的实验，运行时不再引用，未确认前不要切回；更早的 120 帧侧身序列在 `assets/motion-v2/walk-left|walk-right`。纵向上下走路仍由 `walk-vertical` rig 负责。
