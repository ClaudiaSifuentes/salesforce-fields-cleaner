import argparse
import json
import os
import subprocess
import sys
import tempfile


THIS_DIR = os.path.dirname(os.path.abspath(__file__))
CLEANSCRIPT = os.path.join(THIS_DIR, 'clean_campos.py')
DIFFSCRIPT = os.path.join(THIS_DIR, 'diff_campos.py')


def is_simplified(path):
    try:
        with open(path, 'r', encoding='utf-8') as fh:
            data = json.load(fh)
    except Exception:
        return False
    if not isinstance(data, dict):
        return False
    fields = data.get('fields')
    if not isinstance(fields, list) or not fields:
        return False
    first = fields[0]
    return isinstance(first, dict) and 'name' in first and 'label' in first and 'picklistValues' in first


def run_clean(input_path, output_path):
    cmd = [sys.executable, CLEANSCRIPT, input_path, output_path]
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0:
        print('clean_campos.py failed:')
        print(proc.stdout)
        print(proc.stderr)
        raise SystemExit(2)
    print(proc.stdout.strip())


def run_diff(old_simplified, new_simplified, report_path=None):
    cmd = [sys.executable, DIFFSCRIPT, old_simplified, new_simplified]
    if report_path:
        cmd.append(report_path)
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0:
        print('diff_campos.py failed:')
        print(proc.stdout)
        print(proc.stderr)
        raise SystemExit(3)
    print(proc.stdout)
    if report_path:
        print(f'Report written to {report_path}')


def main():
    parser = argparse.ArgumentParser(description='Pipeline: clean then diff fields JSON')
    parser.add_argument('new_raw', help='New raw JSON file path (not cleaned)')
    parser.add_argument('--report', help='Optional path to write JSON report produced by diff script')
    parser.add_argument('--keep-temp', action='store_true', help='Keep temporary simplified files')
    args = parser.parse_args()

    new_raw = os.path.abspath(args.new_raw)
    if not os.path.isfile(new_raw):
        print('New JSON not found:', new_raw)
        raise SystemExit(1)

    baseline = os.path.join(THIS_DIR, 'campos_account_simplified_v2_copy.json')
    if not os.path.isfile(baseline):
        print('Baseline simplified file not found:', baseline)
        print('Please add `campos_account_simplified_v2.json` to the folder.')
        raise SystemExit(1)

    tmpdir = tempfile.mkdtemp(prefix='clean_campos_')
    new_simpl = os.path.join(tmpdir, os.path.basename(new_raw) + '_simplified.json')
    baseline_simpl = os.path.join(tmpdir, os.path.basename(baseline) + '_simplified.json')

    try:
        print('Cleaning new file...')
        run_clean(new_raw, new_simpl)

        print('Comparing fixed baseline -> new simplified...')
        run_diff(baseline, new_simpl, args.report)

    finally:
        if args.keep_temp:
            print('Temporary files kept at:', tmpdir)
        else:
            try:
                for f in os.listdir(tmpdir):
                    os.remove(os.path.join(tmpdir, f))
                os.rmdir(tmpdir)
            except Exception:
                pass


if __name__ == '__main__':
    main()
