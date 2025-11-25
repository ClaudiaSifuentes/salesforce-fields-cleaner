import os
import json
import argparse
import subprocess
import time

THIS_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT_DIR = os.path.dirname(THIS_DIR)
INCOMING_DIR = os.path.join(ROOT_DIR, 'incoming_objects')
SCRIPTS_DIR = os.path.join(ROOT_DIR, 'scripts')

# Try to import the canonical objects list from the download script so we can
# resolve friendly names in the map (like "Party_Relationship") to real
# Salesforce API names (like "vlocity_cmt__PartyRelationship__c").
try:
    from scripts.download_campos import objects as DOWNLOAD_OBJECTS
except Exception:
    DOWNLOAD_OBJECTS = []


def resolve_api_name(obj_name):
    if not obj_name:
        return obj_name
    if not DOWNLOAD_OBJECTS:
        return obj_name
    for o in DOWNLOAD_OBJECTS:
        if o.get('apiName') == obj_name:
            return obj_name
    for o in DOWNLOAD_OBJECTS:
        label = o.get('label') or o.get('apiName')
        safe = label.replace(' ', '_')
        if obj_name == label or obj_name == safe:
            return o.get('apiName') or label
    return obj_name


def read_json_flexible(path):
    try:
        with open(path, 'rb') as fh:
            data = fh.read()
    except Exception:
        return None

    if not data:
        return None

    candidates = []
    if data.startswith(b"\xef\xbb\xbf"):
        candidates.append('utf-8-sig')
    if data.startswith(b'\xff\xfe') or data.startswith(b'\xfe\xff'):
        candidates.append('utf-16')
    candidates += ['utf-8', 'utf-16', 'latin-1']

    for enc in candidates:
        try:
            text = data.decode(enc)
            return json.loads(text)
        except Exception:
            continue
    return None


def describe_object(api, out_path, target_org=None, timeout=120, retries=2, dry_run=False):
    cmd = ['sf', 'force:schema:sobject:describe', '--sobjecttype', api, '--json']
    if target_org:
        cmd += ['--target-org', target_org]

    attempt = 0
    while attempt <= retries:
        attempt += 1
        if dry_run:
            print('DRY-RUN:', ' '.join(cmd), '>', out_path)
            return 0
        try:
            with open(out_path, 'wb') as f:
                proc = subprocess.run(cmd, stdout=f, stderr=subprocess.PIPE, timeout=timeout)
            if proc.returncode == 0:
                return 0
            else:
                err = proc.stderr.decode(errors='ignore') if proc.stderr else ''
                print(f'Attempt {attempt} failed for {api}: rc={proc.returncode} err={err}')
        except FileNotFoundError:
            target_part = f' --target-org {target_org}' if target_org else ''
            cmd_line = f'sf force:schema:sobject:describe --sobjecttype "{api}" --json{target_part}'
            try:
                with open(out_path, 'wb') as f:
                    proc = subprocess.run(cmd_line, stdout=f, stderr=subprocess.PIPE, timeout=timeout, shell=True)
                if proc.returncode == 0:
                    return 0
                else:
                    err = proc.stderr.decode(errors='ignore') if proc.stderr else ''
                    print(f'Attempt {attempt} failed for {api} (shell): rc={proc.returncode} err={err}')
            except subprocess.TimeoutExpired:
                print(f'Attempt {attempt} timed out after {timeout}s for {api} (shell)')
        except subprocess.TimeoutExpired:
            print(f'Attempt {attempt} timed out after {timeout}s for {api}')
        time.sleep(1 + attempt)
    return 1


def load_map(map_path):
    try:
        with open(map_path, 'r', encoding='utf-8') as fh:
            return json.load(fh)
    except Exception:
        return None


def main():
    parser = argparse.ArgumentParser(description='Validate and re-download incoming object JSON files')
    parser.add_argument('--map', help='Path to objects_map.json (defaults to objects_map.json in repo)')
    parser.add_argument('--target-org', help='sf target org alias')
    parser.add_argument('--timeout', type=int, default=120, help='Timeout seconds per describe')
    parser.add_argument('--retries', type=int, default=2, help='Retries per describe')
    parser.add_argument('--dry-run', action='store_true', help='Print actions without executing')
    args = parser.parse_args()

    map_path = os.path.abspath(args.map) if args.map else os.path.join(ROOT_DIR, 'objects_map.json')
    entries = []
    if os.path.isfile(map_path):
        data = load_map(map_path)
        if not data:
            print('Failed to load map:', map_path)
            return 1
        entries = data.get('objects', [])
    else:
        for fname in sorted(os.listdir(INCOMING_DIR)):
            if fname.startswith('incoming-') and fname.endswith('.json'):
                obj = fname[len('incoming-'):-5]
                entries.append({'object': obj, 'incoming': fname})

    to_fix = []
    for entry in entries:
        incoming = entry.get('incoming')
        raw_obj = entry.get('object') or entry.get('api') or entry.get('apiName')
        api = resolve_api_name(raw_obj)
        incoming_path = incoming if os.path.isabs(incoming) else os.path.join(INCOMING_DIR, incoming)
        if not os.path.isfile(incoming_path) or os.path.getsize(incoming_path) == 0:
            print('Will (re)download missing/empty:', incoming_path)
            to_fix.append((api, incoming_path))
            continue
        parsed = read_json_flexible(incoming_path)
        if parsed is None:
            print('Will (re)download invalid JSON:', incoming_path)
            to_fix.append((api, incoming_path))
        else:
            print('OK:', incoming_path)

    if not to_fix:
        print('All incoming files look valid.')
        return 0

    for api, path in to_fix:
        print('Downloading', api, '->', path)
        rc = describe_object(api, path, target_org=args.target_org, timeout=args.timeout, retries=args.retries, dry_run=args.dry_run)
        if rc == 0:
            print('Downloaded:', path)
        else:
            print('Failed to download after retries:', path)

    return 0


if __name__ == '__main__':
    raise SystemExit(main())
