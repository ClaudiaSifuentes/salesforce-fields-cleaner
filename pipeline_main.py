import argparse
import json
import os
import subprocess
import sys
import shutil
import glob
import time


THIS_DIR = os.path.dirname(os.path.abspath(__file__))
# Folder layout (all relative to THIS_DIR)
SCRIPTS_DIR = os.path.join(THIS_DIR, 'scripts')
# New project layout (folders containing the single files described by the user)
BASELINE_DIR = os.path.join(THIS_DIR, 'baseline_objects')
SIMPLIFIED_DIR = os.path.join(THIS_DIR, 'simplified_objects')
INCOMING_DIR = os.path.join(THIS_DIR, 'incoming_objects')
REPORT_DIR = os.path.join(THIS_DIR, 'report_objects')
BACKUP_DIR = os.path.join(THIS_DIR, 'backup_objects')

CLEANSCRIPT = os.path.join(SCRIPTS_DIR, 'clean_campos.py')
DIFFSCRIPT = os.path.join(SCRIPTS_DIR, 'diff_campos.py')


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
    parser.add_argument('new_raw', nargs='?', help='New raw JSON file path (not cleaned). If omitted, uses incoming_objects/incoming-account.json')
    parser.add_argument('--report', help='Optional path to write JSON report produced by diff script')
    parser.add_argument('--keep-temp', action='store_true', help='Keep temporary files (not used except for backwards compatibility)')
    args = parser.parse_args()

    # Resolve new_raw: use provided path or default incoming_objects/incoming-account.json
    if args.new_raw:
        new_raw = os.path.abspath(args.new_raw)
    else:
        new_raw = os.path.abspath(os.path.join(INCOMING_DIR, 'incoming-account.json'))
    if not os.path.isfile(new_raw):
        print('New JSON not found:', new_raw)
        raise SystemExit(1)
    # Ensure directory layout exists
    for d in (SCRIPTS_DIR, BASELINE_DIR, SIMPLIFIED_DIR, INCOMING_DIR, REPORT_DIR, BACKUP_DIR):
        if not os.path.isdir(d):
            os.makedirs(d, exist_ok=True)

    # Verify scripts are available
    if not os.path.isfile(CLEANSCRIPT):
        print('Cleaner script not found:', CLEANSCRIPT)
        raise SystemExit(2)
    if not os.path.isfile(DIFFSCRIPT):
        print('Diff script not found:', DIFFSCRIPT)
        raise SystemExit(3)

    # Paths for main files
    simplified_main = os.path.join(SIMPLIFIED_DIR, 'simplified-account.json')
    baseline_main = os.path.join(BASELINE_DIR, 'baseline-account.json')

    # Determine baseline file to compare against: use the most recent JSON in BASELINE_DIR
    def most_recent_json(dirpath):
        files = glob.glob(os.path.join(dirpath, '*.json'))
        if not files:
            return None
        files.sort(key=os.path.getmtime, reverse=True)
        return files[0]

    # Determine baseline file to compare against: prefer the main baseline file
    if os.path.isfile(baseline_main):
        baseline_file = baseline_main
        print('Using baseline file:', baseline_file)
    else:
        # fallback: use most recent JSON in BASELINE_DIR (if any)
        baseline_file = most_recent_json(BASELINE_DIR)
        if baseline_file:
            print('Using baseline file (recent):', baseline_file)
        else:
            # If no baseline exists, create an empty baseline so diff can run
            baseline_file = os.path.join(BASELINE_DIR, 'empty_baseline.json')
            with open(baseline_file, 'w', encoding='utf-8') as fh:
                json.dump({'fields': []}, fh, indent=2, ensure_ascii=False)
            print('No baseline found, created empty baseline at:', baseline_file)

    # Clean the incoming file into a temporary simplified file (so we don't overwrite existing simplified yet)
    temp_simpl = os.path.join(SIMPLIFIED_DIR, 'simplified-account.tmp.json')
    print('Cleaning new file to temporary:', temp_simpl)
    run_clean(new_raw, temp_simpl)

    # Run diff: baseline_file vs temp_simpl; write JSON report into report_objects/report-account.json
    report_path = args.report if args.report else os.path.join(REPORT_DIR, 'report-account.json')
    print('Comparing baseline -> new simplified...')
    run_diff(baseline_file, temp_simpl, report_path)

    # After successful diff, promote files: move current simplified to baseline (backup existing baseline), then move temp to simplified
    try:
        if os.path.isfile(temp_simpl):
            # backup existing baseline if present
            if os.path.isfile(baseline_main):
                bak = os.path.join(BACKUP_DIR, time.strftime('backup_%Y%m%dT%H%M%S_baseline-account.json'))
                try:
                    shutil.move(baseline_main, bak)
                    print('Backed up existing baseline to', bak)
                except Exception as e:
                    print('Failed to backup existing baseline:', e)
            # if there's an existing simplified, promote it to baseline (rename)
            if os.path.isfile(simplified_main):
                try:
                    shutil.move(simplified_main, baseline_main)
                    print('Promoted previous simplified -> baseline:', os.path.basename(baseline_main))
                except Exception as e:
                    print('Failed to promote previous simplified to baseline:', e)
            # finally move temp into simplified_main
            shutil.move(temp_simpl, simplified_main)
            print('Updated simplified file:', simplified_main)
    except Exception as e:
        print('Warning: failed to finalize promotion of simplified/baseline files:', e)

    if args.keep_temp:
        print('Kept intermediate files in:', SIMPLIFIED_DIR)


if __name__ == '__main__':
    main()
