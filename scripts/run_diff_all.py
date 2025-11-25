import os
import sys
import json
import subprocess

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MAP_PATH = os.path.join(ROOT, 'objects_map.json')
SIMPLIFIED_DIR = os.path.join(ROOT, 'simplified_objects')
BASELINE_DIR = os.path.join(ROOT, 'baseline_objects')
REPORT_DIR = os.path.join(ROOT, 'report_objects')

def ensure_dirs():
    for d in (SIMPLIFIED_DIR, BASELINE_DIR, REPORT_DIR):
        if not os.path.exists(d):
            os.makedirs(d)

def run_diff(old_path, new_path, report_path):
    cmd = [sys.executable, os.path.join(os.path.dirname(__file__), 'diff_campos.py'), old_path, new_path, report_path]
    proc = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    return proc.returncode, proc.stdout.decode(errors='replace')

def main():
    ensure_dirs()
    try:
        with open(MAP_PATH, 'r', encoding='utf-8') as fh:
            data = json.load(fh)
    except Exception as e:
        print('Failed to load map:', MAP_PATH, e)
        return 2

    entries = data.get('objects', [])
    summary = []
    for entry in entries:
        obj = entry.get('object')
        incoming = entry.get('incoming')
        simplified = entry.get('simplified')
        baseline = entry.get('baseline')
        report = entry.get('report')

        # derive paths
        simp_path = os.path.join(SIMPLIFIED_DIR, simplified) if simplified else os.path.join(SIMPLIFIED_DIR, f'simplified-{obj}.json')
        base_path = os.path.join(BASELINE_DIR, baseline) if baseline else os.path.join(BASELINE_DIR, f'baseline-{obj}.json')
        report_path = os.path.join(REPORT_DIR, report) if report else os.path.join(REPORT_DIR, f'report-{obj}.json')

        print('--- Diffing', obj)
        if not os.path.isfile(simp_path):
            print('[SKIP] simplified missing:', simp_path)
            summary.append((obj, 'SKIP(simplified_missing)'))
            continue
        if not os.path.isfile(base_path):
            print('[WARN] baseline missing, using empty baseline:', base_path)
            # create an empty baseline file
            with open(base_path, 'w', encoding='utf-8') as fh:
                json.dump({'fields': []}, fh)

        rc, out = run_diff(base_path, simp_path, report_path)
        print(out)
        if rc == 0:
            print('[OK] report ->', report_path)
        else:
            print('[ERR] diff rc=', rc)
        summary.append((obj, 'OK' if rc == 0 else f'ERR({rc})'))

    print('\nSummary:')
    for obj, status in summary:
        print(f'{obj}: {status}')
    return 0

if __name__ == '__main__':
    raise SystemExit(main())
