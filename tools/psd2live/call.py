"""Local-only PSD2Live MCP client; credentials never appear in command output."""
import argparse
import json
import re
from pathlib import Path

from mcp_proxy import Client, McpError

BASE = Path(__file__).resolve().parent

def client():
    log = (BASE / 'server-local.log').read_text(encoding='utf-8', errors='replace')
    endpoint = re.search(r'^endpoint (\S+)', log, re.M).group(1)
    token = re.search(r'^token (\S+)', log, re.M).group(1)
    return Client(endpoint=endpoint, token=token, timeout=90)

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('operation')
    parser.add_argument('--request')
    parser.add_argument('--edit', action='store_true')
    parser.add_argument('--out')
    args = parser.parse_args()
    request = json.loads(Path(args.request).read_text(encoding='utf-8-sig')) if args.request else {}
    try:
        with client() as api:
            if args.edit:
                request.setdefault('state', api.state())
            data, images = api.call(args.operation, request)
            if args.out:
                output = Path(args.out)
                output.parent.mkdir(parents=True, exist_ok=True)
                output.with_suffix('.json').write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')
                for i, png in enumerate(images):
                    output.with_name(output.stem + f'-{i}.png').write_bytes(png)
                print(json.dumps({'saved': str(output.with_suffix('.json')), 'images': len(images)}))
            else:
                print(json.dumps(data, ensure_ascii=True, indent=2))
    except McpError as error:
        print(json.dumps({'error': str(error), 'detail': error.detail}, ensure_ascii=True))
        raise SystemExit(1)
