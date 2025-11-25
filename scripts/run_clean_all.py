import os
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
IN_DIR = os.path.join(ROOT, 'incoming_objects')
OUT_DIR = os.path.join(ROOT, 'simplified_objects')

def ensure_out():
    if not os.path.exists(OUT_DIR):
        os.makedirs(OUT_DIR)

def run_clean(in_path, out_path):
    cmd = [sys.executable, os.path.join(os.path.dirname(__file__), 'clean_campos.py'), in_path, out_path]
    proc = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    return proc.returncode, proc.stdout.decode(errors='replace')

def main():
    ensure_out()
    files = sorted([f for f in os.listdir(IN_DIR) if f.startswith('incoming-') and f.endswith('.json')])
    if not files:
        print('No incoming files found in', IN_DIR)
        return 1
    summary = []
    for fname in files:
        in_path = os.path.join(IN_DIR, fname)
        name = fname[len('incoming-'):-5]
        out_name = f'simplified-{name}.json'
        out_path = os.path.join(OUT_DIR, out_name)
        print('--- Processing', fname)
        rc, out = run_clean(in_path, out_path)
        print(out)
        if rc == 0:
            print(f'[OK] Wrote {out_path}')
        else:
            print(f'[ERR] {fname} -> rc={rc}')
        summary.append((fname, rc))
    print('\nSummary:')
    for fname, rc in summary:
        print(f'{fname}:', 'OK' if rc == 0 else f'ERR({rc})')
    return 0

if __name__ == '__main__':
    raise SystemExit(main())
