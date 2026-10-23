from pathlib import Path
import subprocess
import sys

here = Path(__file__).resolve().parent
console = here.parents[2]
skill = Path.home() / '.codex/skills/shengtu-skill/scripts/generate_image.py'
prompt = (here / 'waltz-gpt-dance-prompt.txt').read_text(encoding='utf-8')
args = [sys.executable, str(skill), '--provider', 'gpt', '--mode', 'edit',
        '--quality', 'high', '--size', '2048x1536', '--prompt', prompt,
        '--image', str(console / '图片/三视图.png'),
        '--image', str(console / 'assets/actions/waltz-preview/waltz-frames.png'),
        '--out', str(here / 'waltz-gpt-dance-preview.png')]
raise SystemExit(subprocess.call(args))
