from pathlib import Path
import runpy
import sys
import time
import urllib.error

skill = Path.home() / '.codex/skills/shengtu-skill/scripts/generate_image.py'
module = runpy.run_path(str(skill))
main = module['main']
original_save = main.__globals__['save_image']

def retry_download(result, out_path):
    print('Generation response received; downloading image.', flush=True)
    for attempt in range(3):
        try:
            original_save(result, out_path)
            return
        except (urllib.error.URLError, TimeoutError) as exc:
            code = getattr(exc, 'code', None)
            print(f'Download attempt {attempt + 1} failed ({code or type(exc).__name__}).', flush=True)
            if attempt == 2:
                raise
            time.sleep(2 * (attempt + 1))

main.__globals__['save_image'] = retry_download
sys.argv = [str(skill), '--provider', 'gpt', '--prompt',
            'One small ice-blue crystal snowflake centered on a plain navy background, soft lighting, no text.',
            '--size', '1024x1024', '--out',
            str(Path(__file__).parent / 'gpt-connectivity-retry-20261020.png')]
raise SystemExit(main())
