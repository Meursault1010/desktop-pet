# Yuki 当前源码

当前正式桌面版由 Electron 工作台与 PySide6 桌宠 sidecar 组成。产品说明、安装步骤、能力边界和发布入口统一维护在[根目录 README](../README.md)。

## 从源码运行

在仓库根目录首次运行 `install-electron.bat`，之后运行 `start-workbench.bat`。开发入口使用 `console-v2/frontend/dist`、`node_modules` 中的 Electron，以及 `console-v2/.venv` Python 环境。日常入口为 `start.bat`：本机有便携版时优先运行便携版，否则使用已安装的源码环境。

在 `frontend/` 目录可运行 `npm test`、`npm run build` 和 `npm run electron`。

## 旧版 Tauri 路径

`src-tauri/` 以及根目录的 `start-tauri.bat` / `install-tauri.bat` 为兼容和恢复用途保留，不属于当前正式工作台。Python 桌宠实现和本机设置仍与 Electron 共用。
