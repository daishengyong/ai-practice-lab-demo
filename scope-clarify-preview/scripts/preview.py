#!/usr/bin/env python3
"""One-round free preview recorder. No network, model, purchase or reply generation."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import tempfile

def canonical(v):
    return json.dumps(v, ensure_ascii=False, sort_keys=True, separators=(',', ':')).encode()

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--state-dir', required=True)
    ap.add_argument('command', choices=['start', 'resume', 'save', 'feedback'])
    ap.add_argument('--input-file')
    args = ap.parse_args()
    root = Path(args.state_dir).resolve()
    path = root / 'preview.json'
    try:
        if args.command == 'start':
            if path.exists():
                raise ValueError('已有记录，使用resume，不覆盖。')
            root.mkdir(parents=True, exist_ok=True)
            case = json.loads((Path(__file__).resolve().parents[1] / 'case.json').read_text())
            state = {'version': 'preview-1', 'kind': 'one_round_preview', 'opening': case,
                     'reply': None, 'feedback': None, 'next': 'reply'}
        else:
            state = json.loads(path.read_text(encoding='utf-8'))
            claimed = state.pop('sha256')
            if hashlib.sha256(canonical(state)).hexdigest() != claimed:
                raise ValueError('原记录校验失败，保留文件并停止。')
            if args.command != 'resume':
                if not args.input_file:
                    raise ValueError('需要同目录的实际原话文件。')
                inp = (root / args.input_file).resolve()
                if root not in inp.parents or inp == path or inp.name.startswith('.preview-'):
                    raise ValueError('只接受会话目录中的独立文本文件。')
                text = inp.read_text(encoding='utf-8')
                if not text.strip() or len(text) > 20000:
                    raise ValueError('实际原话为空或超长。')
                field = 'reply' if args.command == 'save' else 'feedback'
                if state['next'] != field:
                    if state.get(field) == text:
                        state['sha256'] = claimed
                        print(json.dumps(state, ensure_ascii=False))
                        return
                    raise ValueError('当前轮次不符，未覆盖已有记录。')
                state[field] = text
                state['next'] = 'feedback' if field == 'reply' else 'finished'
        state['sha256'] = hashlib.sha256(canonical(state)).hexdigest()
        if args.command != 'resume':
            fd, tmp = tempfile.mkstemp(prefix='.preview-', dir=root)
            try:
                with os.fdopen(fd, 'w', encoding='utf-8') as f:
                    json.dump(state, f, ensure_ascii=False, indent=2)
                    f.write('\n')
                os.replace(tmp, path)
            finally:
                if os.path.exists(tmp):
                    os.unlink(tmp)
        print(json.dumps(state, ensure_ascii=False))
    except (OSError, ValueError, KeyError) as e:
        print(json.dumps({'status': 'error', 'message': str(e), 'written': False}, ensure_ascii=False))
        raise SystemExit(2)

if __name__ == '__main__':
    main()
