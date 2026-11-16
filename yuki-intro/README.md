# Yuki · 桌面上的一天

30 秒，1920×1080，30 fps，H.264 / AAC。画面包含简体中文标题，配乐和音效使用同一条时间轴。

- `out/Yuki-桌面上的一天.mp4` 是交付影片，`out/poster.png` 是封面。
- `brief.md` 是分镜，`scene.js` 控制画面，`timeline.js` 控制时点，`score.mjs` 控制声音。
- `assets/` 中是从 Yuki 项目素材打包的透明帧图。影片中的交互是标注过的情境示意。字体 DM Sans 与 Noto Sans SC 的 SIL OFL 授权文本位于 `fonts/`。

在本目录执行以下命令可打开剪辑工作区。依赖 Node.js、FFmpeg 和 motion-showreel 技能。

```powershell
$skill = 'C:/Users/meursault/.agents/skills/motion-showreel'
node "$skill/scripts/editor.mjs" . --size 1920x1080 --fps 30 --audio audio/final.wav
```

保留原混音重建成片可执行 `sh build.sh --workers 4 --crf 17`。改动乐谱后使用 `AUDIO=synth sh build.sh --workers 4 --crf 17`。如果 Windows 上 FFmpeg 的 `drawtext` 无法生成验收缩略图，已渲染的 MP4 仍位于 `out/final.mp4`，可用普通 `scale,tile` 滤镜抽帧。
