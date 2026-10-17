"""Read-only SHA256 verification of yuki's organized runtime baseline."""
import hashlib
import json
from pathlib import Path

root = Path(__file__).resolve().parents[2]
baseline = json.loads((root / 'docs/整理记录/运行文件基线.json').read_text(encoding='utf-8'))
failures = []
for name, expected in baseline.items():
    path = root / 'console-v2' / name
    if not path.is_file():
        failures.append((name, 'missing'))
    elif hashlib.sha256(path.read_bytes()).hexdigest() != expected:
        failures.append((name, 'changed'))
print(json.dumps({'checked': len(baseline), 'failures': failures}, ensure_ascii=False, indent=2))
raise SystemExit(bool(failures))
