# yuki

yuki 是一只运行在 Windows 桌面上的白发蓝裙桌宠。当前发布候选：**yuki v1.1.1 · Windows x64 便携版**。

## 下载与使用

从[GitHub Releases](https://github.com/Meursault1010/desktop-pet/releases/latest)下载 Windows x64 版本。发布文件共三件：不含模型的应用包，以及可选本地模型的两个分卷。只用轻量版时，解压应用包并运行 `yuki.exe`；要安装内置 Qwen，三件下载到同一目录，解压应用包后运行 `./install-yuki.ps1 -AssetsPath "下载目录" -IncludeModel`。未签名版本可能触发 Windows 未知发布者提示。

桌宠和工作台开箱可用；内置 Qwen 可选安装。也可连接兼容的本地模型或自行配置云端 API。云端聊天内容会发送到所选服务；OCR 与文档解析在本机完成。能力说明见 [PRODUCT.md](PRODUCT.md)。

她可以持续呼吸和眨眼、走动、播放动作，坐靠或趴在桌面图标上，抓住窗口边框爬行，在下沿悬挂，在上沿坐卧；拖动时会看向抓取点并伸手阻挡，松手后可即时吸附。

- [项目总结](docs/yuki项目总结.md)：功能、架构、素材、验证及当前边界。
- [目录与维护指南](docs/目录与维护指南.md)：目录用途、开发验证、构建和回退。
- [本次整理记录](docs/整理记录/整理说明.md)：整理范围、校验结果及保留内容。
- [后续交接入口](项目交接摘要.md)。
- [版本记录](CHANGELOG.md)。
- [工作台改版说明](docs/工作台改版说明.md)：蓝白银九页界面、动态与验收范围。
- [本地模型接入说明](docs/本地模型接入说明.md)：雪的本地中文聊天、LM Studio 配置、模型来源与能力边界。
- [Electron 迁移总结](docs/Electron迁移总结.md)：迁移范围、启动与回退、测试证据、包体与限制。

## 从仓库运行

本机验证过的 Windows x64 候选包位于 `releases/electron/yuki-win32-x64-release-candidate-v2/`，运行目录里的 `yuki.exe` 即可启动；完整目录需一起保留。

便携产物与构建缓存不上传 Git。克隆仓库后，安装 Python 3.10+、Node 22.12+ 与 npm，运行 `install-electron.bat`，再运行 `start.bat`；或使用 `build-electron.ps1` 构建内含 Python/PySide6 的便携版。首次构建需要下载依赖。

正式版本由 Electron 管理工作台、托盘、单实例和 IPC，宠物透明窗口与桌面行为仍由 PySide6 实现。Electron Canvas PNG 窗口是独立开发原型，尚未替代正式宠物。旧 Tauri 路径保留：保存并退出当前版本后运行 `start-tauri.bat`，环境安装使用 `install-tauri.bat`。

源码开发时先运行 `install-electron.bat`，再运行 `start-workbench.bat`。前端命令（`console-v2/frontend/`）：`npm test`、`npm run build`、`npm run electron`；PNG 原型使用 `npm run electron:prototype`。`start-electron.bat` 与 `start.bat` 使用同一正式便携目录规则。

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

工作台与 Qt 用户可见品牌统一为 **yuki**；旧 `xiaoju-console.exe` 和 `XiaoJu` 配置目录保留历史兼容标识。

已通过 86 项 Python、22 项前端/Electron/PNG 测试及最终便携版 10 组端到端检查。原有 623 个运行文件哈希保持一致。多屏、混合 DPI、休眠恢复及 Electron 原生透明窗口全套验收仍待完成；详见迁移总结。
