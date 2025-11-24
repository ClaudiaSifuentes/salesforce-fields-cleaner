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
    parser.add_argument('new_raw', nargs='?', help='New raw JSON file path (not cleaned). If provided, pipeline processes only this file.')
    parser.add_argument('--map', dest='map', help='Path to objects map JSON (defaults to objects_map.json in this folder)')
    parser.add_argument('--report', help='Optional path to write JSON report produced by diff script')
    parser.add_argument('--keep-temp', action='store_true', help='Keep temporary files (not used except for backwards compatibility)')
    args = parser.parse_args()

    incoming_list = []
    use_map = False
    map_path = None
    if args.new_raw:
        single = os.path.abspath(args.new_raw)
        if not os.path.isfile(single):
            print('New JSON not found:', single)
            raise SystemExit(1)
        incoming_list = [single]
    else:
        default_map = os.path.join(THIS_DIR, 'objects_map.json')
        map_path = os.path.abspath(args.map) if args.map else (default_map if os.path.isfile(default_map) else None)
        if map_path and os.path.isfile(map_path):
            use_map = True
        if use_map:
            try:
                with open(map_path, 'r', encoding='utf-8') as mf:
                    map_data = json.load(mf)
            except Exception as e:
                print('Failed to load map file', map_path, 'error:', e)
                raise SystemExit(1)
            objs = map_data.get('objects') or []
            if not objs:
                print('Map file has no objects to process:', map_path)
                raise SystemExit(1)
            incoming_list = []
            for entry in objs:
                incoming_name = entry.get('incoming')
                if not incoming_name:
                    print('Skipping map entry without incoming:', entry)
                    continue
                incoming_path = incoming_name if os.path.isabs(incoming_name) else os.path.join(INCOMING_DIR, incoming_name)
                incoming_list.append(incoming_path)
        else:
            incoming_list = sorted(glob.glob(os.path.join(INCOMING_DIR, 'incoming-*.json')))
            if not incoming_list:
                print('No incoming files found in', INCOMING_DIR)
                raise SystemExit(1)
    for d in (SCRIPTS_DIR, BASELINE_DIR, SIMPLIFIED_DIR, INCOMING_DIR, REPORT_DIR, BACKUP_DIR):
        if not os.path.isdir(d):
            os.makedirs(d, exist_ok=True)

    if not os.path.isfile(CLEANSCRIPT):
        print('Cleaner script not found:', CLEANSCRIPT)
        raise SystemExit(2)
    if not os.path.isfile(DIFFSCRIPT):
        print('Diff script not found:', DIFFSCRIPT)
        raise SystemExit(3)

    simplified_main = os.path.join(SIMPLIFIED_DIR, 'simplified-account.json')
    baseline_main = os.path.join(BASELINE_DIR, 'baseline-account.json')

    def most_recent_json(dirpath):
        files = glob.glob(os.path.join(dirpath, '*.json'))
        if not files:
            return None
        files.sort(key=os.path.getmtime, reverse=True)
        return files[0]

    if os.path.isfile(baseline_main):
        baseline_file = baseline_main
        print('Using baseline file:', baseline_file)
    else:
        baseline_file = most_recent_json(BASELINE_DIR)
        if baseline_file:
            print('Using baseline file (recent):', baseline_file)
        else:
            baseline_file = os.path.join(BASELINE_DIR, 'empty_baseline.json')
            with open(baseline_file, 'w', encoding='utf-8') as fh:
                json.dump({'fields': []}, fh, indent=2, ensure_ascii=False)
            print('No baseline found, created empty baseline at:', baseline_file)

    if use_map:
        objs_iter = objs
    else:
        objs_iter = []
        for incoming_path in incoming_list:
            incoming_basename = os.path.basename(incoming_path)
            obj_basename = os.path.splitext(incoming_basename)[0]
            obj_name = obj_basename.split('incoming-', 1)[1] if obj_basename.startswith('incoming-') else obj_basename
            objs_iter.append({'object': obj_name, 'incoming': incoming_basename, 'simplified': f'simplified-{obj_name}.json', 'baseline': f'baseline-{obj_name}.json', 'report': f'report-{obj_name}.json'})

    for entry in objs_iter:
        incoming_name = entry.get('incoming')
        incoming_path = incoming_name if os.path.isabs(incoming_name) else os.path.join(INCOMING_DIR, incoming_name)
        if not os.path.isfile(incoming_path):
            print('Incoming file not found, skipping:', incoming_path)
            continue
        obj_name = entry.get('object') or os.path.splitext(os.path.basename(incoming_path))[0].split('incoming-', 1)[-1]
        print('\n=== Processing object:', obj_name, '===')

        simplified_name = entry.get('simplified') or f'simplified-{obj_name}.json'
        baseline_name = entry.get('baseline') or f'baseline-{obj_name}.json'
        report_name = entry.get('report') or f'report-{obj_name}.json'

        simplified_main_obj = simplified_name if os.path.isabs(simplified_name) else os.path.join(SIMPLIFIED_DIR, simplified_name)
        baseline_main_obj = baseline_name if os.path.isabs(baseline_name) else os.path.join(BASELINE_DIR, baseline_name)
        temp_simpl_obj = os.path.join(SIMPLIFIED_DIR, f'simplified-{obj_name}.tmp.json')
        report_obj = report_name if os.path.isabs(report_name) else os.path.join(REPORT_DIR, report_name)

        if os.path.isfile(baseline_main_obj):
            baseline_file_obj = baseline_main_obj
            print('Using baseline file:', baseline_file_obj)
        else:
            candidates = sorted(glob.glob(os.path.join(BASELINE_DIR, f'*{obj_name}.json')),
                                key=os.path.getmtime, reverse=True)
            if candidates:
                baseline_file_obj = candidates[0]
                print('Using baseline file (matched):', baseline_file_obj)
            else:
                baseline_file_obj = os.path.join(BASELINE_DIR, f'empty_baseline_{obj_name}.json')
                with open(baseline_file_obj, 'w', encoding='utf-8') as fh:
                    json.dump({'fields': []}, fh, indent=2, ensure_ascii=False)
                print('No baseline found for', obj_name, '- created empty baseline at:', baseline_file_obj)

        print('Cleaning', incoming_path, '->', temp_simpl_obj)
        run_clean(incoming_path, temp_simpl_obj)

        report_path_obj = args.report if args.report else report_obj
        print('Comparing baseline -> new simplified for', obj_name)
        run_diff(baseline_file_obj, temp_simpl_obj, report_path_obj)

        try:
            if os.path.isfile(temp_simpl_obj):
                if os.path.isfile(baseline_main_obj):
                    bak = os.path.join(BACKUP_DIR, time.strftime(f'backup_%Y%m%dT%H%M%S_baseline-{obj_name}.json'))
                    try:
                        shutil.move(baseline_main_obj, bak)
                        print('Backed up existing baseline to', bak)
                    except Exception as e:
                        print('Failed to backup existing baseline:', e)
                if os.path.isfile(simplified_main_obj):
                    try:
                        shutil.move(simplified_main_obj, baseline_main_obj)
                        print('Promoted previous simplified -> baseline for', obj_name)
                    except Exception as e:
                        print('Failed to promote previous simplified to baseline:', e)
                shutil.move(temp_simpl_obj, simplified_main_obj)
                print('Updated simplified file for', obj_name, ':', simplified_main_obj)
        except Exception as e:
            print('Warning: failed to finalize promotion of simplified/baseline files for', obj_name, e)

    if args.keep_temp:
        print('Kept intermediate files in:', SIMPLIFIED_DIR)


if __name__ == '__main__':
    main()
