# 小橘现代控制台（v0.2）

## 使用

双击项目根目录的 `start.bat`。新版由 React + TypeScript 前端、Tauri Windows 窗口和 Python 宠物进程组成。普通使用无需启动开发服务器，也无需安装 Node 或 Rust。保留 `.venv` 和项目 Python 文件；当前 exe 是控制台程序，不是包含 Python 的独立安装包。

关闭窗口会隐藏到系统托盘；从托盘图标或宠物右键菜单打开控制台。彻底退出请在设置页、托盘菜单或宠物右键菜单选择退出。托盘不可用时，关闭窗口改为最小化。

`start_legacy.bat` 启动原版 Qt 控制台，用于兼容与对照。日常请只打开一种控制台，避免两个独立宠物同时运行。

## 页面

| 页面 | 功能 |
|---|---|
| 我的小屋 | 当前状态、角色预览、显示开关、安静模式、活动频率、快捷动作 |
| 外观 | 大小、不透明度、置顶 |
| 行为 | 速度、活动频率、随机移动、暂停、气泡、安静模式 |
| 互动 | 跳跃、回到底部、显示/隐藏 |
| 设置 | 浅色/深色主题、配置路径、恢复默认、退出 |

宠物预览复用真实矢量角色的导出图，展示缩放、透明度与跳跃反馈，不是桌面画面的实时录像。新增的参考图未自动替换当前角色。

## 通信与状态

React 使用 Tauri 命令调用 Rust；Rust 启动 `pet_backend.py` 并通过标准输入输出交换 UTF-8 逐行 JSON。没有本地网络服务或开放端口。Python Qt 主线程执行宠物操作；输入读取线程只投递消息。

- 每个请求有编号，响应带状态快照；状态变化同时推送到前端。
- Python 为状态来源，前端用 revision 过滤旧快照；操作按序发送，滑块立即进入应用级队列，并合并尚未发送的同项更改，切换页面不会取消最后一次修改。
- 参数在 Python 再次校验；无效命令返回可读错误。
- 请求有超时；后端退出时显示断开状态和重新连接按钮。
- 退出时先通知 Python 保存配置；管道关闭时 Python 自动结束。
- Python 日志使用 stderr，stdout 专用于协议。
- 新版托盘由 Tauri 管理，Python 不创建第二个控制台或托盘。

宠物设置沿用 `%LOCALAPPDATA%\XiaoJu\DesktopPet\settings.ini`；控制台主题单独存于 WebView 本地存储。

## 源码结构

```text
desktop-pet/
  app/xiaoju-console.exe          已编译桌面控制台
  start.bat                      新版入口
  start_legacy.bat               原版入口
  pet_backend.py                 Python JSON 消息服务
  main.py / pet.py               共用控制逻辑与宠物
  settings_model.py              原有设置存储
  frontend/
    src/main.tsx                 React 挂载入口
    src/App.tsx                  页面与交互
    src/components/SettingControls.tsx 公共滑块、数字输入与开关
    src/usePetController.ts      连接、保存状态与错误提示
    src/commandQueue.ts          有序命令与待发送偏好合并
    src/bridge.ts                通信与数据类型
    src/styles.css               基础主题、布局、动效
    src/refinements.css          字号、对比度与控件体验优化
    public/pet-preview.png        宠物预览
    package.json / package-lock.json
    src-tauri/
      src/main.rs                子进程、通信、窗口与托盘
      tauri.conf.json            窗口与构建配置
      Cargo.toml / Cargo.lock    Rust 依赖
      capabilities/default.json 最小窗口能力
      icons/                    程序图标
  test_ipc.py                    真实子进程通信验收
  build_frontend.ps1             重建 exe
```

## 开发与重建

需要 Node.js、Rust MSVC 工具链、Visual Studio C++ Build Tools、WebView2 和现有 Python 环境。

```powershell
cd frontend
npm ci
npm run tauri dev
```

仅查看界面可运行 `npm run dev`，打开终端显示的本地地址并加 `?demo=1`。页面明确标记为演示，不能控制真实宠物；不带演示参数时普通浏览器会显示未连接。

重建并更新项目内的控制台 exe：

```powershell
.\build_frontend.ps1
```

本次为编译准备的隔离 Rust 工具链未加入系统 PATH，可显式指定：

```powershell
.\build_frontend.ps1 -ToolchainDirectory 'C:\Users\meursault\Documents\ChatGPT\桌面宠物\console-v2\.toolchain'
```

## 验证

```powershell
.\.venv\Scripts\python.exe -B -m unittest test_console test_ipc -v
cd frontend
npm run build
```

测试使用临时配置，涵盖设置、动作、安静模式、非法参数、跨进程状态、重启保留和父进程断开退出。Qt 离屏测试不代替真实多屏幕与 DPI 验收。

## 现有功能体验优化（2026-10-16）

- 大小、透明度、速度支持数字输入和单项恢复默认；Enter 提交、Escape 取消，失焦提交有效值，非法或越界值恢复当前值并提示。
- 数值更改立即入队，未发送的同项更改合并；重复动作在等待响应时去重，恢复默认和退出按顺序等待之前的命令。
- 控件展示正在应用状态；底部和设置页区分等待连接、应用中、已保存、未完成和保存失败，演示模式不会宣称已保存到桌面。
- 错误提示持续显示，偏好与显示状态操作可手动重试；动作超时不自动重发，避免重复触发。
- 字号、对比度、点击区域和键盘焦点优化；安静模式与隐藏状态明确说明操作不可用原因。
- 公共控件位于 `frontend/src/components/SettingControls.tsx`；通信状态与操作队列拆分为 `usePetController.ts`、`commandQueue.ts`。
- 新增队列与数值校验测试：在 `frontend` 目录运行 `node --test tests/commandQueue.test.mjs`（需要支持原生 TypeScript 的 Node 版本；本机为 Node 24）。

### 分发限制

当前交付可在这台电脑直接使用，尚未制作包含 Python 的独立安装包。将来分发到其他电脑时，需要打包 Python sidecar、制作安装器，并验证签名与 WebView2 依赖。未加入 AI 聊天、语音、皮肤导入或在线功能。
