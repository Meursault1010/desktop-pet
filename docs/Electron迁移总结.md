# yuki Electron 迁移总结

历史记录：本文记录 2026-10-17 的迁移状态，不代表当前版本。当前前端版本为 1.1.2，已支持应用内更新；未接入正式产品的 PNG 宠物原型已删除。

## 结论

已完成方案规定的 Electron **兼容迁移阶段**，可以从根目录 `start.bat` 启动。Electron 接管 React 工作台、托盘、单实例、受限 IPC 和后端生命周期；正式宠物保留原 Python/PySide6 窗口、动画与 Windows 桌面互动。已构建包含 Electron、冻结 Python/PySide6 和运行素材的 Windows x64 便携目录。

这不是已经移除 PySide6 的全量迁移。独立 Electron 透明 PNG 宠物原型已实现并通过资源、时序与 Canvas alpha 检查；它还没有接管正式宠物的图标遮挡、行走、攀爬、悬挂、鼠标阻挡或即时吸附。方案要求这些能力通过 Windows 专项验收后再替换，当前继续复用经过测试的实现。

## 迁移范围

| 方案阶段 | 本次结果 |
| --- | --- |
| 0：基线与资产保护 | 迁移前测试记录保留；623 个原运行文件 SHA256 全部一致；用户图片、动作源文件与 QA 未改动 |
| 1：宿主解耦 | `src/host/` 提供统一 request/subscribe/reconnect/exit；Tauri API 收敛在 adapter，React 业务组件共享 |
| 2：Electron 控制台 | 已完成：主进程、preload、本地协议、后端桥接、托盘、单实例与退出清理 |
| 3：PNG 原型 | 已实现：透明无边框置顶窗口、64 相位待机、眨眼、manifest 动作、循环起点、倍速、停止、拖动、按 alpha 穿透；原生透明合成专项验收尚未完成 |
| 4：桌面互动 | 正式版本完整复用 Python/Win32 行为，经 Electron 命令调用；没有重写行为系统或删除 PySide6 GUI |
| 5：入口与打包 | 默认入口已切换；保留 Tauri；Windows x64 便携目录已实测，不含安装器、签名或自动更新 |
| 6：未来接口 | 定义 PetRenderer、AI、音频接口；未加入 SDK、模型网络调用、麦克风或音乐采集 |

## 当前架构

```text
start.bat → start-electron.bat → yuki.exe
  Electron 主进程：单实例 / 托盘 / 窗口 / 本地资源 / 生命周期
    ├─ 隔离 preload → React 工作台 → DesktopHost
    └─ JSONL stdin/stdout → 内置 yuki-backend.exe
                               Python / PySide6 正式宠物窗口
                               行为 / 设置 / Win32 图标和窗口集成

独立开发模式 --pet-prototype
  Electron 透明 BrowserWindow → Canvas PngRenderer
  不启动 Python 后端，不与正式模式同时创建两只宠物
```

正式行为源码未修改：连续呼吸眨眼、动作播放、大小与透明度、置顶、安静与暂停、距离驱动走路、最近边缘寻找、侧边攀爬、下边悬挂、上边坐卧、窗口跟随、图标坐趴与裙摆遮罩、拖动阻挡、松手即时吸附均沿用原实现。工作台上的「拖放即时吸附」与「自动寻找边缘」保持原有独立语义。

浏览器依靠对象仍是原生窗口边框，不是网页内部 DOM 元素。历史动作中少帧与单帧姿势的表现不会因为换宿主自动变得更流畅。

## 启动、构建与回退

| 用途 | 入口 |
| --- | --- |
| 日常启动本次迁移版 | 根目录 `start.bat`，优先启动本地便携包 |
| 直接运行便携版 | `releases/electron/yuki-win32-x64/yuki.exe`；必须保留整个目录 |
| 开发环境首次安装 | `install-electron.bat`，需要 Python 3.10+、Node 22.12+ 与 npm；本次构建使用 Python 3.13.14 |
| 开发运行 | 前端目录 `npm run electron`，先安装依赖并运行 `npm run build`；默认使用 `console-v2/.venv`，也可设置 `PET_PYTHON` |
| 独立 PNG 原型 | 前端目录 `npm run electron:prototype`；双击播放 screen 动作，右键停止，Alt+F4 退出 |
| 构建便携目录 | 根目录 `powershell -ExecutionPolicy Bypass -File .\build-electron.ps1`；需要 Python、Node、npm 和下载构建依赖的网络 |
| 使用已安装构建依赖 | `build-electron.ps1 -SkipInstall`，仍重新冻结后端、构建前端与打包 |
| 回退到原 Tauri | 先从工作台保存并退出，再运行 `start-tauri.bat`；首次准备 Python 使用 `install-tauri.bat` |

项目内 `releases/` 与 `.electron-build/` 不纳入 Git。克隆仓库不会自动获得本地便携包；应安装开发依赖或重新构建。`console-v2/start.bat`、原 Tauri EXE、Rust 源码与 legacy 入口保留。桌面目录 `C:\Users\meursault\Desktop\desktop-pet` 没有部署或覆盖。

完整目录便携包无需全局 Python、Node、Rust 或 WebView2。已在移除 `PET_PYTHON` 指定的情况下运行最终包，并确认后端为 `resources/pet/python/yuki-backend.exe`。尚未在干净虚拟机验收，不能将开发机测试等同于所有 Windows 机器兼容。

## 设置与数据

宠物设置继续使用 `%LOCALAPPDATA%\XiaoJu\DesktopPet\settings.ini`，未改变 schema、默认值或历史标识；无需复制设置。Electron 控制台主题使用自己 profile 中的本地存储，旧 Tauri WebView 的主题不会自动迁入。工作台展示名称与窗口标题已改为 yuki。

Electron profile 默认位于 `%APPDATA%\yuki`；主进程与后端 stderr 日志在该目录的 `logs/yuki.log`。`YUKI_USER_DATA` 可指定独立测试 profile；`PET_SETTINGS_FILE` 指定临时宠物设置，测试不会重置个人配置。可从断线提示手动重连；崩溃时不会无限循环自动拉起后端。

当前采用目录替换升级：退出旧版后，把完整新目录放到另一个文件夹再启动。没有自动更新、安装器或卸载程序；删除便携程序目录不会由程序主动删除用户设置。自定义动作仍需通过现有资源维护流程整合，不能将新图片直接当作动作导入。

## 安全与稳定性

- renderer 禁用 Node，启用 contextIsolation、sandbox、webSecurity，preload 仅暴露工作台所需接口。
- 生产内容通过 `yuki://app/` 加载，限定本地资源根；CSP、权限拒绝、导航和新窗口拒绝、外网拦截生效，没有开发调试端口。
- IPC 同时检查发送窗口、主 frame、协议来源、命令白名单、参数类型、数值范围、动作 ID 和请求大小；后端继续独立校验。
- JSONL 使用 UTF-8 解码；协议版本 1，单行上限 2 MB、请求上限约 64 KB、最多 32 个未完成请求；请求超时 6 秒、就绪超时 15 秒，重连最短间隔 500 ms。
- 退出优先请求后端保存关闭，再关闭输入管道；超过等待时间终止子进程。正式测试验证退出没有遗留后端。
- 本次没有添加外部 AI 服务、凭据、素材上传、音频采集或任意 shell / 文件系统 API。

## 验证结果与证据

| 检查 | 结果与实际覆盖 |
| --- | --- |
| 迁移前 Python 基线 | 86 项通过，见 `整理记录/迁移前Python测试.txt` |
| 迁移后 Python | 使用本次构建环境 Python 3.13.14 / PySide6 6.10.2，86 项通过，33.185 秒；涵盖 IPC、拖放、边缘、图标、动画与行为回归 |
| 前端 / Electron / PNG | 22 项通过：原有 11 项、新增宿主 9 项、PNG 2 项 |
| TypeScript / Vite | 生产构建通过，生成工作台与 pet 双入口 |
| 最终便携版 E2E | 10 组通过，见 `整理记录/Electron便携版端到端.json`；React 连接、预览资源、安全拒绝、显示隐藏、设置、动作、边缘命令、崩溃重连恢复、真实托盘关闭隐藏、双开复用、退出清理 |
| 最终便携版 PNG | ready=true，透明像素 40745、实心像素 23219，renderer 中 require=undefined；仅证明 Canvas alpha 与资源加载，见 `整理记录/Electron便携版PNG原型.json` |
| 可见界面 | 本机当前 150% 缩放下实际打开工作台，观察到 yuki 品牌、角色预览、「本地已连接」及「拖放即时吸附」开关；后续点击验收受用户窗口操作干扰，没有据此宣称所有手动操作已通过 |
| 原始运行文件 | 623 个文件与迁移前 SHA256 全部一致；原宠物行为、动作与 Tauri 运行文件保留 |

非法命令 E2E 会主动触发主进程拒绝并打印预期错误，不代表测试失败。原图 ICC profile 的 libpng 警告不影响加载，本次没有为消除警告重写用户图片。

可复现命令：

```powershell
# 在 console-v2/frontend 运行
npm.cmd test
npm.cmd run build

# 在 console-v2 运行，使用已创建的构建环境
$env:QT_QPA_PLATFORM='offscreen'
& '..\.electron-build\venv\Scripts\python.exe' -B -m unittest discover -p 'test_*.py'
```

便携版 E2E 可运行 `yuki.exe --smoke-test`，PNG 原型测试为 `yuki.exe --pet-prototype --smoke-test`。应先退出正常运行版，设置独立 `YUKI_USER_DATA`、`PET_SETTINGS_FILE` 和 `YUKI_SMOKE_REPORT`，并使用能等待 GUI 进程退出的进程启动方式；不应复用个人设置进行自动测试。

## 包体、性能与构建修复

本地未压缩便携目录约 **611 MiB**。一次空闲状态采样中，Electron 和 PySide6 合计 5 个进程，工作集简单相加约 **607 MiB**；包含共享内存重复统计，不是独占占用，也不是严格性能基准。端到端报告的 durationMs 只覆盖应用就绪后的检查，不是冷启动时间。

兼容阶段同时包含 Chromium 与 Qt，包体和内存开销较大。没有做受控的迁移前后 CPU、GPU、耗电、帧率或冷启动对照，因此不能声称迁移提高了性能。后续完全迁移渲染、去除 Qt GUI 后才适合重新评估体积与内存。

构建时发现并修复了两个实际问题：PyInstaller 的相对 assets 路径按 spec 目录解析，现改为绝对源路径；开发机 PATH 中的 Poppler ICU 与 Qt 不兼容，现对冻结步骤隔离 PATH，显式选择 Windows ICU，并统一根目录 VC runtime 与 Qt 附带版本。修复后重新运行了最终目录包 E2E。

## 未完成验收与下一阶段

尚未完成：Electron 透明窗口的原生桌面合成与点击穿透全套验收、正式 PNG 行为接管、100%/150% 混合 DPI、多显示器、任务栏位置变化、睡眠恢复、远程桌面/显卡 fallback、长时间高帧率运行、干净机安装与签名分发。旧 Tauri 入口的文件和适配器保留，迁移后没有重新执行 Rust release 构建及其完整手动验收。

建议下一阶段先对原型做 Windows 专项验证，再把 Python 的行为输出逐步转换为 Electron 窗口姿态和动作消息；逐项迁移并验证裙摆遮罩、拖动阻挡与即时吸附后，才移除 PySide6 GUI。当前正式兼容版用于保留现有功能和回退能力。
