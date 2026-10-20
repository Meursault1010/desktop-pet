# Electron 主进程 EPIPE 弹窗修复

日期：2026-10-19

## 问题与判断

截图的异常是 `Error: EPIPE: broken pipe, write`，调用链经过 Electron 的 `replyWithError` 和 `console.error`。这表明 Electron 在记录一次 IPC 请求错误时，向已经关闭的标准错误输出管道写入，产生了第二次未处理异常并弹窗。截图没有包含原始 IPC 错误，无法据此确定是哪一个请求失败。

排查发现一个当天早间启动的旧 `breathing` 版本 `--smoke-test` 进程仍在运行，另有正常使用的 `hair-consistent` 版本。旧测试进程与失效输出管道的条件相符，但无法仅凭截图证明弹窗属于哪个实例。本次没有结束这两个现有进程。

## 修复

- 在加载应用模块前安装主进程文件日志，替换全局 `console`，覆盖 Electron 自身打印 IPC 错误的路径。
- 正常启动直接写入用户配置目录下的 `logs/yuki.log`，不依赖启动终端。
- 自动测试仍可镜像输出到终端；遇到 `EPIPE` 后停止向该管道写入，保留文件日志。
- 仅处理标准输出、标准错误管道的 `EPIPE`，不全局吞掉其他异常。
- 保留当前角色素材、动画、前端和后台实现，修复包沿用已构建的后台。

入口：根目录 `start.bat` → `start-electron.bat`，优先启动 `releases/electron/yuki-win32-x64-safe-logging/yuki-win32-x64/yuki.exe`。已运行的旧进程不会自动获得此次修复，需要正常保存并退出后重新启动。

## 验证

- 主进程日志与宿主测试：13 项通过，包括真实子进程的父端同时关闭 stdout/stderr 管道后继续运行。
- 修复发布包：第一个检查通过后，父进程主动关闭其 stdout/stderr 接收端；随后执行会被拒绝的 IPC 校验请求，日志出现管道关闭记录及原始请求错误，进程未崩溃。
- 发布包 18 项检查全部通过，渲染器错误列表为空，退出码 0，后台已清理；运行约 39 秒。
- 报告：`验收资料/safe-logging-smoke-20261019.json`、`验收资料/safe-logging-pipes-20261019.json`。

正常使用日志位置为 `%APPDATA%/yuki/logs/yuki.log`；设置 `YUKI_USER_DATA` 的隔离测试会使用对应测试目录。原始 IPC 错误再次发生时可以从该文件进一步定位。
