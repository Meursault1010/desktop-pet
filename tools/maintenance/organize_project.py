"""One-time, local-only yuki project consolidation; no installed app writes."""
from datetime import datetime
import hashlib
import json
from pathlib import Path
import shutil

ROOT = Path(__file__).resolve().parents[2]
STAGE = Path(r'C:\Users\meursault\Documents\Codex\2026-10-17\c-users-meursault-documents-chatgpt-md\work\desktop-pet')
INSTALLED = Path(r'C:\Users\meursault\Desktop\desktop-pet')
DELIVERY = STAGE.parents[1] / 'outputs'
REPORT = ROOT / 'docs/整理记录'
EXCLUDED = {'.git', '.venv', '__pycache__', 'node_modules', 'target', 'dist', 'gen', '.toolchain'}
ONE_OFF = {
    'adapt_motion_tests.py', 'fix_fullscreen_drop.py', 'fix_scan_lifecycle.py',
    'make_motion_package.py', 'package_drag_update.py', 'package_interaction_update.py',
    'package_locomotion_update.py', 'replace_edge.py',
}
records = []


def digest(path):
    h = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def local(path):
    resolved = path.resolve()
    if not resolved.is_relative_to(ROOT):
        raise ValueError(f'Write outside project: {path}')
    return resolved


def files(folder):
    for path in sorted(folder.rglob('*')):
        if path.is_file() and not any(p in EXCLUDED for p in path.relative_to(folder).parts):
            if path.suffix not in {'.pyc', '.pyo', '.tsbuildinfo'}:
                yield path


def record_copy(source, destination, operation='copy'):
    destination = local(destination)
    expected = digest(source)
    if destination.exists():
        if digest(destination) == expected:
            return
        saved = local(ROOT / '归档/整理前源码-20261017' / destination.relative_to(ROOT))
        if saved.exists():
            raise FileExistsError(saved)
        saved.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(destination, saved)
        records.append(dict(operation='backup', source=str(destination),
                            destination=str(saved.relative_to(ROOT)), sha256=digest(saved)))
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, destination)
    assert digest(destination) == expected
    records.append(dict(operation=operation, source=str(source),
                        destination=str(destination.relative_to(ROOT)), sha256=expected))


def record_move(source, destination):
    source, destination = local(source), local(destination)
    if destination.exists():
        raise FileExistsError(destination)
    before = {str(p.relative_to(source)): digest(p) for p in source.rglob('*') if p.is_file()} if source.is_dir() else {'': digest(source)}
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.move(str(source), str(destination))
    for relative, expected in before.items():
        target = destination / relative if relative else destination
        assert digest(target) == expected
        records.append(dict(operation='move', source=str((source / relative).relative_to(ROOT)) if relative else str(source.relative_to(ROOT)),
                            destination=str(target.relative_to(ROOT)), sha256=expected))


def main():
    REPORT.mkdir(parents=True, exist_ok=True)
    if (REPORT / '文件整理清单.json').exists():
        raise RuntimeError('Already organized; review manifest instead of repeating.')
    # Preserve the full older handoff, then categorize loose original files.
    record_copy(ROOT / '项目交接摘要.md', ROOT / 'docs/历史/项目交接摘要-整理前-20261017.md')
    record_move(ROOT / 'console-v1', ROOT / '归档/console-v1')
    for path in sorted((ROOT / 'console-v2').glob('backup-*')):
        record_move(path, ROOT / '归档/备份' / path.name)
    for path in sorted(ROOT.glob('*.png')):
        category = '挥手补帧' if path.name.startswith('wave_frame_') else '早期姿势' if path.name.startswith('pose_') else '早期角色方案'
        record_move(path, ROOT / '素材' / category / path.name)
    record_move(ROOT / 'generate_wave_frames.ps1', ROOT / '归档/生图脚本/generate_wave_frames.ps1')
    # Runtime code is checked against the installed version before consolidation.
    runtime = ['main.py', 'pet.py', 'pet_backend.py', 'settings_model.py', 'console.py',
               'idle_animation.py', 'action_player.py', 'desktop_icons.py', 'icon_sleep.py',
               'icon_pose_geometry.py', 'locomotion.py', 'edge_geometry.py', 'edge_attachment.py',
               'window_edges.py', 'drag_feedback.py', 'drop_attachment.py']
    for name in runtime:
        if digest(STAGE / name) != digest(INSTALLED / name):
            raise ValueError(f'Stage differs from installed runtime: {name}')
    for source in sorted(STAGE.iterdir()):
        if source.is_file():
            if source.name in ONE_OFF:
                record_copy(source, ROOT / '归档/阶段脚本-20261017' / source.name)
            elif source.suffix in {'.py', '.ps1', '.md', '.bat'} or source.name == '.gitignore':
                record_copy(source, ROOT / 'console-v2' / source.name, 'sync')
    for name in ['assets', 'action-work', 'frontend', 'qa', 'app']:
        for source in files(STAGE / name):
            record_copy(source, ROOT / 'console-v2' / name / source.relative_to(STAGE / name), 'sync')
    for name in ['install.bat', 'requirements.txt']:
        record_copy(INSTALLED / name, ROOT / 'console-v2' / name, 'sync')
    for source in files(INSTALLED / '图片'):
        record_copy(source, ROOT / 'console-v2/图片' / source.relative_to(INSTALLED / '图片'), 'reference-copy')
    for source in DELIVERY.iterdir():
        if source.is_file():
            record_copy(source, ROOT / 'docs/验收资料' / source.name, 'delivery-copy')
        elif source.is_dir():
            # Keep release manifests/installers and their rollback backups, not duplicate payloads.
            for item in files(source):
                if 'payload' not in item.relative_to(source).parts:
                    record_copy(item, ROOT / '归档/历史交付' / source.name / item.relative_to(source), 'release-record')
    # Record the immutable current runtime snapshot for future regression checks.
    snapshot = {}
    for name in runtime + ['app/xiaoju-console.exe', 'start.bat', 'install.bat', 'requirements.txt']:
        snapshot[name] = digest(ROOT / 'console-v2' / name)
    for source in files(ROOT / 'console-v2/assets'):
        snapshot[str(source.relative_to(ROOT / 'console-v2')).replace('\\', '/')] = digest(source)
    (REPORT / '运行文件基线.json').write_text(json.dumps(snapshot, ensure_ascii=False, indent=2), encoding='utf-8')
    (REPORT / '文件整理清单.json').write_text(json.dumps(dict(created=datetime.now().isoformat(), root=str(ROOT),
        installed_untouched=str(INSTALLED), operations=records), ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps(dict(operations=len(records), runtime_files=len(snapshot),
                         moved=sum(r['operation']=='move' for r in records),
                         synced=sum(r['operation']=='sync' for r in records)), ensure_ascii=False))


if __name__ == '__main__':
    main()
