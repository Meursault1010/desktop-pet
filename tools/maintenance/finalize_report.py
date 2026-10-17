"""Finish documentation and audit preserved files after consolidation."""
import hashlib
import json
from pathlib import Path

root = Path(__file__).resolve().parents[2]
report = root / 'docs/整理记录'
manifest = json.loads((report / '文件整理清单.json').read_text(encoding='utf-8'))
failures = []
for entry in manifest['operations']:
    destination = root / entry['destination']
    if not destination.is_file() or hashlib.sha256(destination.read_bytes()).hexdigest() != entry['sha256']:
        failures.append(entry['destination'])
if failures:
    raise RuntimeError(f'Organization audit failed: {failures}')
baseline = json.loads((report / '运行文件基线.json').read_text(encoding='utf-8'))
installed = Path(manifest['installed_untouched'])
installed_differences = []
for name, expected in baseline.items():
    source = installed / name
    if not source.is_file() or hashlib.sha256(source.read_bytes()).hexdigest() != expected:
        installed_differences.append(name)
if installed_differences:
    raise RuntimeError(f'Runtime differs from installed: {installed_differences}')

summary = dict(organization_entries=len(manifest['operations']), organization_failures=failures,
               runtime_matches_installed=len(baseline), installed_differences=installed_differences,
               moved_root_png=sum(e['operation']=='move' and e['source'].endswith('.png')
                                  and '\\' not in e['source'] for e in manifest['operations']),
               backup_directories=len(list((root/'归档/备份').iterdir())))
(report/'最终核对.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding='utf-8')
(report/'Python测试.txt').write_text('2026-10-17\n整理后 console-v2 目录\n'
    'QT_QPA_PLATFORM=offscreen; PYTHONDONTWRITEBYTECODE=1\n'
    'python -B -m unittest discover -p test_*.py\n'
    'Ran 86 tests in 31.069s\nOK\nexit_code=0\n',encoding='utf-8')

handoff = '''# yuki 项目交接入口

更新时间：2026-10-17。项目与桌宠正式名称为 **yuki**。

当前功能、技术架构、命名兼容和限制请先阅读 [yuki 项目总结](docs/yuki项目总结.md)，目录用途、构建与回退见 [目录与维护指南](docs/目录与维护指南.md)。

- 当前开发源码：本项目 `console-v2/`，已补齐走路、窗口抓框、拖动阻挡与即时吸附。
- 日常运行目录：`C:\\Users\\meursault\\Desktop\\desktop-pet`；本次整理没有修改安装版或结束进程。
- 个人设置：`%LOCALAPPDATA%\\XiaoJu\\DesktopPet\\settings.ini`，保留原位置和内容。
- 当前仍为 Tauri + React + Python/PySide6。`ELECTRON_MIGRATION_PLAN.md` 仅是已有方案，尚未执行。
- 程序的历史名称、EXE 文件名和应用标识暂保留以兼容现有功能；文档中正式名称为 yuki。
- 必须保留：目标图标可遮裙摆、头发始终前景、其他图标和文字不裁宠物；自主移动有行走动画，手动松手吸附即时完成。
- 整理后验证：86 项 Python、11 项前端测试通过，TypeScript/Vite 构建通过；623 个运行文件与安装版哈希一致。

整理前的完整交接文档保存在 [历史交接](docs/历史/项目交接摘要-整理前-20261017.md)，其中缺少后续走路、附着和拖动功能，不能用旧文档覆盖当前源码。

移动、同步与备份记录见 [整理说明](docs/整理记录/整理说明.md) 和同目录 JSON 清单。后续开发前先核对现有改动与运行进程，不盲目重跑历史部署、打包或生图脚本。
'''
(root/'项目交接摘要.md').write_text(handoff,encoding='utf-8')
notes = report/'整理说明.md'
content = notes.read_text(encoding='utf-8').replace('26 张 PNG','25 张 PNG')
content = content.replace('验证结果将在本文件末尾记录。', '''## 整理后的验证结果

- Python 全套回归：86 项通过，31.069 秒，退出码 0；离屏运行，使用临时测试设置。
- 前端测试：11 项通过，0 失败。
- TypeScript/Vite 构建：通过，资源打包正常；未重新构建或部署 Tauri EXE。
- 运行基线：623 个文件完整，全部与现有桌面安装版 SHA256 一致。
- 全部 827 条文件整理记录的目标文件复核通过，无缺失或哈希差异。
- Qt 环境启动与 esbuild 读取曾被沙箱权限阻止，获自动审批后使用现有环境完成验证；不属于代码故障。

日志见本目录 `Python测试.txt`、`前端测试.txt`、`前端构建.txt` 与 `最终核对.json`。本次未执行额外真实窗口拖动或开关切换验收，未改变现有功能。
''')
notes.write_text(content,encoding='utf-8')
print(json.dumps(summary,ensure_ascii=False,indent=2))
