# 小橘桌面宠物：迁移到 Electron 的实施方案

> 本文是交给 Codex 分阶段实施的技术方案。目标是迁移桌面运行时到 Electron，同时尽量复用现有 React 控制台、Python 行为逻辑和 PNG 动画资产；迁移过程中不得破坏当前可运行版本。

## 1. 目标与决策

目标平台为 Windows。采用 Electron + React + TypeScript 作为桌面应用和渲染基础，PNG 静帧/精灵图集作为当前角色动画格式；为后续 Live2D、音乐响应、语音聊天、AI 服务和受控工具调用建立边界，但本次迁移不实现这些未来功能。

推荐目标架构：

```text
Electron 主进程（窗口、托盘、生命周期、安全边界）
  ├── 控制台窗口：复用 frontend React UI
  ├── 宠物透明窗口：React/Canvas PNG 动画渲染
  ├── IPC：严格白名单、类型化消息
  └── Python sidecar：复用现有设置、移动、吸附、桌面图标等逻辑
```

先采用“Electron 接管窗口与系统集成，Python/PySide6 暂时继续负责宠物行为和真实宠物窗口”的兼容阶段；确认所有控制台能力稳定后，再迁移宠物渲染窗口到 Electron。这样可将高风险窗口重写拆开，并保留随时回退路径。不得在一次提交中同时重写 PySide6 宠物窗口、控制台、行为系统和打包流程。

最终推荐状态是 Electron 管理控制台与透明宠物窗口，Python 保留为无 UI 的行为/桌面集成 sidecar，React 负责 PNG/Live2D 显示；但只有当 Windows 透明窗口、穿透、托盘、DPI、多屏幕和拖拽验收通过后，才移除 PySide6 GUI 层。

## 2. 当前项目事实（迁移基线）

- 宠物本体：Python 3.10+、PySide6。`main.py`、`pet.py`、`pet_backend.py` 管理宠物窗口、托盘、设置、移动、动画与 IPC。
- 宠物窗口目前由 `pet.py` 的 `QWidget/QPainter/QPixmap/QTimer` 绘制；连续待机和动作序列已经实现。
- `action_player.py` 从 `assets/actions/catalog.json` 读取动作定义和帧时长；`pet.py` 使用动作 atlas 绘制当前帧。
- 桌面边缘吸附、桌面图标交互、拖动反馈、多屏幕几何等逻辑分布在 `edge_attachment.py`、`desktop_icons.py`、`window_edges.py`、`icon_sleep.py` 等文件中，属于高风险 Windows 集成逻辑，应先保留。
- 控制台：`frontend/`，React 19、TypeScript、Vite；包含动作库、设置、预览和交互页面。
- 当前桌面宿主：Tauri 2 + Rust，位于 `frontend/src-tauri/`。Rust 启动 Python `pet_backend.py`，经标准输入输出交换逐行 JSON，并实现命令白名单、请求 ID、超时、事件推送和托盘。
- 入口：`start.bat` 启动 `app/xiaoju-console.exe`，设置 `PET_PROJECT_DIR/PET_PYTHON`；旧 Qt 入口 `start_legacy.bat`。
- 配置：沿用 `%LOCALAPPDATA%\XiaoJu\DesktopPet\settings.ini`，控制台主题为前端本地存储。
- 测试：Python `unittest`、前端 Node 测试和 IPC 测试；已有测试不可因迁移被删除或无理由降级。
- 现有目录含用户图片、原始生图、QA 与动作素材。迁移不得移动、覆盖或清理 `图片/`、`action-work/`、`qa/` 中用户资产；只将经整理的运行资源纳入应用资源。

迁移开始前 Codex 必须重新检查实际仓库状态、未提交改动和当前启动方式，以仓库实情为准。上列内容是基线，不是覆盖当前实现的许可。

## 3. 技术选型原则

### Electron

- 主进程只管理 BrowserWindow、tray、生命周期、应用目录、sidecar 生命周期和授权 IPC。
- renderer 不开启 Node integration；使用 `contextIsolation: true`、`sandbox: true`（若兼容）和窄范围 preload API。
- 不允许 renderer 任意调用 shell、文件系统、子进程、任意 URL 或任意本地路径。
- 开发服务器仅绑定 loopback；生产环境加载打包资源，不开放调试端口。
- 权限策略和 CSP 限制远程内容；默认不加载远程页面。

### 前端与动画

- 复用 `frontend/src` React 页面和组件，抽象宿主 API，避免业务组件直接依赖 Tauri 或 Electron。
- 用统一 `PetRenderer` 接口承载 PNG 和未来 Live2D：`loadCharacter`、`playAction`、`stopAction`、`setParameter`、`dispose`。当前只实现 PNG renderer，Live2D adapter 仅预留接口，不加 SDK 依赖。
- PNG 必须保持透明通道；渲染 pixel-art 时默认 `image-rendering: pixelated`，Canvas 关闭 image smoothing。针对现有 atlas 的 alpha、帧格、缩放和资源路径建立测试。
- 动作清单继续采用版本化 JSON manifest，动作 ID 稳定、帧顺序显式、时长可配置、可指定 loopStart/loopEnd。不要仅依赖文件名排序或硬编码路径。
- 用户新增的图片默认属于素材库，不自动等同于可播放动作；播放前检查透明度、尺寸、帧数和角色一致性。

### Python sidecar

- 迁移早期继续复用 Python `pet_backend.py` 与现有行为代码；将进程通信从 Rust 移到 Electron 主进程，协议仍使用 UTF-8、逐行 JSON、请求 ID、响应、事件、协议版本和命令白名单。
- stdout 专用于协议，日志走 stderr；限制单条消息长度、队列积压和请求超时；sidecar 退出要通知 UI，并支持受控重连。
- 生产阶段需规划打包 sidecar（如 PyInstaller），开发阶段仍可用 `.venv` Python。不得假定目标用户机器安装 Python。
- 保留 Python 端对每条命令的独立校验；前端校验不能替代后端校验。
- 不把 API 密钥经 renderer 或日志传递。后续 AI 凭据由主进程/安全存储或本地服务读取。

## 4. 目标模块边界

```text
electron/main/          窗口、托盘、应用生命周期、单实例、sidecar manager
electron/preload/       contextBridge 暴露的有限、类型化 API
frontend/src/host/      宿主抽象；Electron/Tauri adapter 分离
frontend/src/pet/       PetRenderer、PngRenderer、动作时序和状态机
frontend/src/ai/        未来 AI 客户端接口（本次仅定义边界，不接入服务）
frontend/src/audio/     未来音频输入/分析接口（本次仅定义边界）
shared/protocol/        IPC schema、版本、命令/事件类型
python sidecar          设置、行为、Windows 桌面集成（渐进拆分）
```

目录可按当前 repo 风格调整，但职责边界必须保持。避免过度抽象：本次只落地已需要的宿主接口、动画接口和协议类型，不搭建空的插件平台。

## 5. 分阶段实施

### 阶段 0：迁移前审计与保护

1. 检查 `git status`、当前分支、启动/构建/测试流程、所有 Tauri 命令和 Python JSON 命令。
2. 记录当前功能与测试基线；运行现有 Python、前端、IPC 测试并保存结果。
3. 找出用户素材、运行 atlas、预览资源和打包资产的来源关系。
4. 不修改现有 Tauri 路径之前，确保 `start.bat` 当前版本仍可运行或明确记录已有故障。
5. 在实施文档或 PR 描述中列出不在本次范围内的功能。

验收：有可复现的基线清单；无资产丢失、无配置覆盖。

### 阶段 1：前端宿主解耦

1. 将 React 中直接使用 `@tauri-apps/api` 的代码收敛到 host adapter，例如当前 `bridge.ts`、`usePetController.ts`。
2. 定义统一、类型化的 `DesktopHost`：请求、事件订阅、平台能力查询、退出/托盘状态等；不要向组件暴露任意 invoke。
3. 保持 Tauri adapter 作为当前默认适配器，确保功能与测试不回退。
4. 定义并校验共享 IPC schema（建议 Zod 或轻量运行时校验，但避免为少量消息引入过重依赖）。

验收：Tauri 仍通过现有测试；React 业务组件不再直接调用 Tauri API。

### 阶段 2：引入 Electron 控制台宿主（兼容运行）

1. 添加 Electron 主进程和 preload，复用现有 Vite/React 控制台。
2. Electron 主进程启动 Python backend，并实现与现有 Rust 类似的 JSON-lines bridge。
3. 托盘、单实例、控制台隐藏/恢复、退出确认由 Electron 实现。
4. 第一版可以继续让 Python/PySide6 管理真实宠物窗口，Electron 仅负责控制台；避免同时运行两个宠物实例。
5. 增加 `start-electron` 开发入口；原 `start.bat` 和 Tauri 构建保留，直到 Electron 验收后再明确切换。

验收：Electron 控制台能连接同一 Python 后端；显示/隐藏、偏好、状态、动作库、重连和退出通过端到端测试；旧 Tauri 路径仍可运行。

### 阶段 3：Electron PNG 宠物窗口原型

1. 新建独立透明、无边框、置顶的宠物 BrowserWindow，启用严格安全设置。
2. 初期以 PNG atlas 播放器验证渲染、alpha、pixelated scaling、动作时序和窗口透明。
3. 按已有 action manifest 播放动作；支持 loop、speed、stop、恢复 idle。
4. 加入窗口拖动、DPI 缩放和多屏幕边界逻辑的最小原型，但不立即移除 PySide6 窗口。
5. 通过 feature flag/开发配置选择 PySide6 或 Electron pet renderer，确保同一时刻仅一个真实宠物窗口活动。

验收：Electron 窗口在 Windows 透明桌面上没有黑底/白底；PNG 边缘清晰；坐标、缩放和点击行为通过手动 smoke test。

### 阶段 4：迁移桌面交互与行为

分批迁移并逐项验收：拖动、点击/右键、置顶、显示隐藏、窗口位置持久化、屏幕变化、DPI、多显示器、托盘菜单、暂停、巡逻、跳跃/动作触发、图标吸附和边缘停靠。

高风险项（桌面图标自动化、窗口边界吸附、图标睡眠）可暂时保留 Python/Win32 实现，由 Electron 通过明确命令调用；不要为了统一语言而重写稳定的 Windows 专用代码。

验收：对照当前 README 与需求文档逐条验证；至少单显示器/多显示器、缩放 100%/150%、任务栏位置变化和休眠恢复进行人工验收。

### 阶段 5：默认入口与打包

1. Electron 完成核心验收后，切换默认启动入口；保留 Tauri/legacy 启动脚本一个过渡版本并标注用途。
2. 打包 Python sidecar 与资源，路径使用 Electron `app.getPath()`/resources，而非依赖项目 checkout。
3. 配置安装包、升级策略、日志目录、崩溃恢复和卸载行为；用户素材/设置不随卸载误删。
4. 若暂不分发独立安装包，明确标示开发运行依赖和启动方式。

验收：干净 Windows 用户环境无需全局 Python/Node/Rust 即可运行发行版；更新不覆盖用户动作素材和设置。

### 阶段 6：未来能力接口（本次只预留）

- Live2D：`PetRenderer` adapter；未来实现 Cubism Web SDK renderer。Live2D 用于呼吸、眨眼、视线、嘴型等连续动作；PNG 继续用于打滚、吃东西等复杂/像素动作。
- 音乐互动：`AudioFeatureSource` 输出归一化音量、低/中/高频能量、节拍事件；动画层只消费抽象参数，不直接绑定某个音频服务。默认仅监听用户明确选择的输入/播放源，提供暂停与隐私指示。
- AI：`ConversationProvider` 与 UI/角色状态机解耦；模型网络调用从 renderer 移到受控主进程或本地服务。密钥不进源码、renderer、日志或素材包。
- 语音：STT/TTS adapter；统一取消、超时、设备选择、权限状态和数据保留设置。实时音频不阻塞动画线程。
- 工具调用：工具注册表采用白名单、JSON schema、权限等级和审计日志。只读工具可按设置授权；写入、删除、执行命令、外网访问等高影响动作必须逐次明确确认。模型不能直接调用 Node、shell、任意文件系统或任意 URL。
- 自主巡逻：独立 `BehaviorController`/状态机，使用可取消任务、边界感知、冷却时间和用户暂停；AI 不能绕过行为约束直接移动桌宠或控制系统。

本次不添加 AI SDK、音频采集、麦克风权限、Live2D 商业素材或远程 API 配置。

## 6. 安全与稳定性要求

- Electron renderer：`nodeIntegration: false`、`contextIsolation: true`、生产 CSP；导航和新窗口策略默认拒绝，外链由主进程显式处理。
- IPC 方法逐条暴露并做主进程校验；禁止 `ipcRenderer` 原样透传、任意命令执行、任意路径访问。
- sidecar 协议设置最大行长、请求超时、并发/队列限制、退出清理、重连退避和版本协商。
- 用户设置迁移采用备份/原子写入；不删除旧配置。数据 schema 升级可回滚。
- 密钥使用 Windows Credential Manager 或系统安全存储方案，不能明文写入普通配置；迁移前需明确用户同意。
- 语音与音乐分析默认最小采集，提供可见状态、停止按钮和隐私说明。
- 桌面工具执行保持权限最小化，危险操作需要确认与审计。

## 7. 测试与质量门槛

自动化：

- 保留并运行现有 Python unittest、前端测试和动作资源测试。
- 为 Electron main/preload/IPC 添加单元测试：白名单、schema 错误、请求超时、sidecar 崩溃/重连、单实例、退出清理。
- 为 PNG renderer 添加帧时序、loopStart、透明 alpha、无效资源和缺帧测试。
- 增加端到端 smoke：启动、连接、显示/隐藏、偏好保存/重启恢复、播放/停止动作、关闭控制台仍驻留托盘、退出。
- 对生成素材和用户图片不做自动破坏式转换；测试转换工具使用临时目录。

人工 Windows 验收：透明窗口合成、任务栏/桌面图标点击穿透、拖拽、DPI、多显示器、远程桌面/显卡 fallback、睡眠唤醒、托盘重启和高帧率长期运行。

任何阶段不得以“构建通过”代替透明窗口和桌面交互实机验收。

## 8. 非目标与避免事项

- 不一次性重写所有 Python 行为为 TypeScript/Rust。
- 不在本轮实现 Live2D、音乐监听、AI、语音聊天或任意工具调用；只设计边界。
- 不为展示技术栈而引入微服务、数据库、消息队列或复杂插件市场。
- 不删除 Tauri/PySide6 旧实现，直到 Electron 对应功能验证且用户明确接受默认入口切换。
- 不覆盖或重命名用户图片、API 配置、动作源文件和既有设置。
- 不把桌面素材文件夹作为唯一运行时资源目录；经过验证的运行资产需 manifest 化并可随应用打包。

## 9. 建议实施顺序与提交拆分

1. `refactor(frontend): isolate desktop host bridge`
2. `feat(electron): add secure shell and console adapter`
3. `feat(electron): launch python sidecar over versioned ipc`
4. `feat(pet): add electron transparent png renderer prototype`
5. `feat(electron): migrate pet window interactions incrementally`
6. `build(electron): package windows app and python sidecar`
7. `docs: document migration, development, privacy and release flows`

每个阶段单独可构建、可测试、可回退。Codex 实施时先完成阶段 0 与 1，再报告发现和风险；后续阶段按仓库状态继续，不应未经用户请求直接发布、上传或删除旧入口。

## 10. 最终验收清单

- [ ] React UI 可被 Electron 复用，UI 组件不耦合特定桌面 API。
- [ ] Electron preload 暴露最小 API，安全选项和 CSP 生效。
- [ ] Python sidecar 协议兼容、类型校验、可恢复、无 stdout 日志污染。
- [ ] PNG 动作可按 manifest 稳定播放，透明与像素边缘正确。
- [ ] 托盘、单实例、关闭隐藏、显式退出正常。
- [ ] 桌面宠物拖动、置顶、DPI、多屏幕和边缘行为经过 Windows 实测。
- [ ] 原设置和用户素材安全迁移，无静默丢失。
- [ ] 安装包不依赖用户全局 Node/Python/Rust，或明确标注开发版限制。
- [ ] 现有测试通过，新增 IPC/renderer/端到端测试通过。
- [ ] Live2D、音频、AI、语音、工具调用有模块边界，但尚未越权采集数据或执行操作。
