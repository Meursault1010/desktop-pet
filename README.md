# yuki

yuki 是一只运行在 Windows 桌面上的白发蓝裙桌宠，也是本项目的正式名称。当前版本：**yuki v1.1.0 · Electron 兼容迁移版**。

她可以持续呼吸和眨眼、走动、播放动作，坐靠或趴在桌面图标上，抓住窗口边框爬行，在下沿悬挂，在上沿坐卧；拖动时会看向抓取点并伸手阻挡，松手后可即时吸附。

- [项目总结](docs/yuki项目总结.md)：功能、架构、素材、验证及当前边界。
- [目录与维护指南](docs/目录与维护指南.md)：目录用途、开发验证、构建和回退。
- [本次整理记录](docs/整理记录/整理说明.md)：整理范围、校验结果及保留内容。
- [后续交接入口](项目交接摘要.md)。
- [版本记录](CHANGELOG.md)。
- [Electron 迁移总结](docs/Electron迁移总结.md)：迁移范围、启动与回退、测试证据、包体与限制。

## 从仓库运行

本地已生成 Windows x64 便携目录 `releases/electron/yuki-win32-x64/`。运行根目录 `start.bat` 或其中的 `yuki.exe`；整个便携目录一起保留，无需全局 Python、Node、Rust 或 WebView2。不要同时运行旧桌面安装版。

便携产物与构建缓存不上传 Git。克隆仓库后，安装 Python 3.10+、Node 22.12+ 与 npm，运行 `install-electron.bat`，再运行 `start.bat`；或使用 `build-electron.ps1` 构建内含 Python/PySide6 的便携版。首次构建需要下载依赖。

正式版本由 Electron 管理工作台、托盘、单实例和 IPC，宠物透明窗口与桌面行为仍由 PySide6 实现。Electron Canvas PNG 窗口是独立开发原型，尚未替代正式宠物。旧 Tauri 路径保留：保存并退出当前版本后运行 `start-tauri.bat`，环境安装使用 `install-tauri.bat`。

开发命令（`console-v2/frontend/`）：`npm test`、`npm run build`、`npm run electron`；PNG 原型使用 `npm run electron:prototype`。

## 目录

```text
console-v2/       当前完整开发源码、运行素材、控制台及本机构建缓存
releases/electron/ 本地 Electron 便携目录包，不纳入 Git
.electron-build/  隔离构建环境、冻结 Python 与打包暂存，不纳入 Git
图片/             原有素材，原样保留
素材/             从根目录分类收纳的早期角色方案、姿势和挥手补帧
docs/             当前总结、历史文档、验收资料和整理清单
tools/maintenance/ 本次整理脚本，仅供审计，不要重复执行
归档/             本地第一版、旧备份、整理前源码和阶段脚本（不上传 Git）
```

本项目根目录 `start.bat` 已切换为 Electron。桌面旧安装目录 `C:\Users\meursault\Desktop\desktop-pet` 未部署更新，那里仍是旧版。宠物设置继续使用 `%LOCALAPPDATA%\XiaoJu\DesktopPet\settings.ini`。

工作台展示名称统一为 **yuki**；Qt 窗口标题、旧 `xiaoju-console.exe`、`XiaoJu` 配置目录等保留历史兼容标识。

已通过 86 项 Python、22 项前端/Electron/PNG 测试及最终便携版 10 组端到端检查。原有 623 个运行文件哈希保持一致。多屏、混合 DPI、休眠恢复及 Electron 原生透明窗口全套验收仍待完成；详见迁移总结。
