import os
import argparse
import subprocess
import json
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime

login_cmd = "sf force:auth:web:login -a pluz--dev -d --instance-url https://pluz--dev.sandbox.my.salesforce.com/"

# default objects list (kept as fallback if no map file provided)
objects = [
    {"label": "Lead", "apiName": "Lead"},
    {"label": "Contact", "apiName": "Contact"},
    {"label": "Account", "apiName": "Account"},
    {"label": "Party_Relationship", "apiName": "vlocity_cmt__PartyRelationship__c"},
    {"label": "Opportunity", "apiName": "Opportunity"},
    {"label": "Action_Plan", "apiName": "ActionPlan"},
    {"label": "Action_Plan_Item", "apiName": "ActionPlanItem"},
    {"label": "Premise", "apiName": "vlocity_cmt__Premises__c"},
    {"label": "Quote", "apiName": "Quote"},
    {"label": "Quote_Line_Item", "apiName": "QuoteLineItem"},
    {"label": "Contract", "apiName": "Contract"},
    {"label": "Order", "apiName": "Order"},
    {"label": "Order_Product", "apiName": "OrderItem"},
    {"label": "Work_Order", "apiName": "WorkOrder"},
    {"label": "Fulfilment_Request", "apiName": "vlocity_cmt__FulfilmentRequest__c"},
    {"label": "Fulfilment_Request_Line", "apiName": "vlocity_cmt__FulfilmentRequestLine__c"},
    {"label": "Task", "apiName": "Task"},
    {"label": "Service_Point", "apiName": "vlocity_cmt__ServicePoint__c"},
    {"label": "Asset", "apiName": "Asset"},
    {"label": "MessagingSession", "apiName": "MessagingSession"},
    {"label": "Messaging_User", "apiName": "MessagingEndUser"},
    {"label": "Approval_Submission", "apiName": "ApprovalSubmission"},
    {"label": "Approval_Submission_Detail", "apiName": "ApprovalSubmissionDetail"},
    {"label": "Case", "apiName": "Case"},
    {"label": "Email_Message", "apiName": "EmailMessage"},
    {"label": "Inventory_Item", "apiName": "vlocity_cmt__InventoryItem__c"},
    {"label": "Ubigeo", "apiName": "pz_AddressStandardLocation__c"},
    {"label": "User", "apiName": "User"},
    {"label": "Party", "apiName": "vlocity_cmt__Party__c"},
    {"label": "Product", "apiName": "Product2"},
    {"label": "Payment_Adjustment", "apiName": "vlocity_cmt__PaymentAdjustment__c"},
    {"label": "Store_Location", "apiName": "vlocity_cmt__BusinessSite__c"}
]


def load_objects_map(map_path):
    """Load a map JSON with structure {"objects": [ {"object": "Account", ...}, ... ]}
    Each entry can contain either `apiName` or `object`. We return a list of dicts with
    keys `label` and `apiName` suitable for the rest of the script.
    """
    if not os.path.exists(map_path):
        print(f'No map file found at {map_path}; using default object list')
        return None
    try:
        with open(map_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
    except Exception as e:
        print(f'Failed to read objects map {map_path}: {e}; using default list')
        return None
    objs = []
    items = data.get('objects') if isinstance(data, dict) else None
    if not items:
        print(f'No "objects" array found in {map_path}; using default list')
        return None
    for it in items:
        label = it.get('label') or it.get('object') or it.get('apiName')
        api = it.get('apiName') or it.get('object') or label
        if label and api:
            objs.append({'label': label, 'apiName': api})
    if not objs:
        print(f'Parsed map but found no valid objects in {map_path}; using default list')
        return None
    print(f'Loaded {len(objs)} objects from {map_path}')
    return objs

def run_cmd(cmd, dry_run=False):
    print(cmd)
    if dry_run:
        return 0
    proc = subprocess.run(cmd, shell=True)
    return proc.returncode


# NOTE: --timeout and --retries are added inside main() after the parser is created.

# Función para ejecutar comandos sin shell y con timeout
def run_cmd_list(cmd_list, timeout=None, dry_run=False):
    print(' '.join(cmd_list))
    if dry_run:
        return 0, b'', b''
    try:
        proc = subprocess.run(cmd_list, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=timeout)
        return proc.returncode, proc.stdout, proc.stderr
    except subprocess.TimeoutExpired as e:
        return -1, b'', f'timeout after {timeout}s'.encode()


# describe_object usando stdout a archivo y reintentos
def describe_object(obj, incoming_dir, target_org=None, dry_run=False, timeout=120, retries=2):
    label = obj.get('label') or obj.get('apiName')
    api = obj.get('apiName') or obj.get('label')
    safe_label = label.replace(' ', '_')
    out_path = os.path.join(incoming_dir, f'incoming-{safe_label}.json')

    cmd = ['sf', 'force:schema:sobject:describe', '--sobjecttype', api, '--json']
    if target_org:
        cmd += ['--target-org', target_org]

    print(f'Downloading {label} ({api}) -> {out_path}')
    attempt = 0
    while attempt <= retries:
        attempt += 1
        if dry_run:
            print('DRY-RUN:', ' '.join(cmd), '>', out_path)
            return (label, 0)
        try:
            # Open file and stream stdout there
            with open(out_path, 'wb') as f:
                try:
                    proc = subprocess.run(cmd, stdout=f, stderr=subprocess.PIPE, timeout=timeout)
                except FileNotFoundError:
                    # On Windows the `sf` entry may be a PowerShell shim (sf.ps1). In that case
                    # launching the literal 'sf' as an executable can raise FileNotFoundError.
                    # Fall back to running the full command line via the shell.
                    target_part = f' --target-org {target_org}' if target_org else ''
                    cmd_line = f'sf force:schema:sobject:describe --sobjecttype "{api}" --json{target_part}'
                    proc = subprocess.run(cmd_line, stdout=f, stderr=subprocess.PIPE, timeout=timeout, shell=True)
            if proc.returncode == 0:
                return (label, 0)
            else:
                err = proc.stderr.decode(errors='ignore') if proc.stderr else ''
                print(f'Attempt {attempt} failed for {api}: rc={proc.returncode} err={err}')
        except subprocess.TimeoutExpired:
            print(f'Attempt {attempt} timed out after {timeout}s for {api}')
        # small backoff before retry
        import time; time.sleep(1 + attempt)
    return (label, 1)


def main():
    parser = argparse.ArgumentParser(description='Download sobject describes to incoming_objects using sf CLI')
    parser.add_argument('--fields-dir', default='.', help='Base folder to write incoming_objects')
    parser.add_argument('--map', default='objects_map.json', help='Path (relative to fields-dir) to objects map JSON')
    parser.add_argument('--login', action='store_true', help='Run sf web login before downloading')
    parser.add_argument('--login-cmd', default=login_cmd, help='Custom login command')
    parser.add_argument('--target-org', help='sf alias or username to pass as --target-org')
    parser.add_argument('--dry-run', action='store_true', help='Print commands without executing')
    parser.add_argument('--parallel', type=int, default=4, help='Number of parallel describe requests')
    parser.add_argument('--timeout', type=int, default=120, help='Timeout (seconds) for each sf call')
    parser.add_argument('--retries', type=int, default=2, help='Number of retries on timeout/failure')
    parser.add_argument('--only', help='Comma-separated list of object labels or apiNames to download (limits to subset)')
    parser.add_argument('--plan-only', action='store_true', help='Print planned commands and exit (no threads, no subprocesses)')
    args = parser.parse_args()

    fields_dir = os.path.abspath(args.fields_dir)
    incoming_dir = os.path.join(fields_dir, 'incoming_objects')

    # Attempt to load objects map (path is relative to fields_dir by default)
    map_path = os.path.join(fields_dir, args.map) if args.map else None
    if map_path:
        loaded = load_objects_map(map_path)
        if loaded:
            objects_to_use = loaded
        else:
            objects_to_use = objects
    else:
        objects_to_use = objects

    if args.login:
        print('Running login command...')
        if args.dry_run:
            print(args.login_cmd)
        else:
            run_cmd(args.login_cmd, dry_run=False)

    # create import fields directory
    if not os.path.exists(fields_dir):
        os.makedirs(fields_dir)
    if not os.path.exists(incoming_dir):
        os.makedirs(incoming_dir)

    # Prepare jobs (include timeout and retries). Optionally filter via --only
    selected = None
    if args.only:
        tokens = [t.strip() for t in args.only.split(',') if t.strip()]
        selected = []
        for o in objects_to_use:
            label = o.get('label') or o.get('apiName')
            safe = label.replace(' ', '_')
            api = o.get('apiName') or label
            if label in tokens or safe in tokens or api in tokens:
                selected.append(o)
        if not selected:
            print('Warning: --only specified but no objects matched. Proceeding with full list.')
            selected = None

    jobs = []
    for obj in (selected if selected is not None else objects_to_use):
        jobs.append((obj, incoming_dir, args.target_org, args.dry_run, args.timeout, args.retries))

    # Plan-only: print the exact commands that would run, but don't spawn threads or subprocesses
    if args.plan_only:
        if args.login:
            print('Planned login command:')
            print(args.login_cmd)
        for obj, incoming_dir, target_org, dry_run, timeout, retries in jobs:
            label = obj.get('label') or obj.get('apiName')
            api = obj.get('apiName') or obj.get('label')
            safe_label = label.replace(' ', '_')
            out_path = os.path.join(incoming_dir, f'incoming-{safe_label}.json')
            cmd = ['sf', 'force:schema:sobject:describe', '--sobjecttype', api, '--json']
            if target_org:
                cmd += ['--target-org', target_org]
            print('DRY-PLAN:', ' '.join(cmd), '>', out_path)
        return

    # Run in parallel
    if args.parallel and args.parallel > 1:
        print(f'Running {len(jobs)} describe requests with {args.parallel} workers...')
        results = []
        with ThreadPoolExecutor(max_workers=args.parallel) as ex:
            futures = [ex.submit(describe_object, *job) for job in jobs]
            for fut in as_completed(futures):
                try:
                    res = fut.result()
                    results.append(res)
                except Exception as e:
                    print('Job failed:', e)
        # summary
        for label, rc in results:
            status = 'OK' if rc == 0 else f'ERR({rc})'
            print(f'{label}: {status}')
    else:
        # sequential
        for job in jobs:
            label, rc = describe_object(job[0], job[1], target_org=job[2], dry_run=job[3], timeout=job[4], retries=job[5])
            status = 'OK' if rc == 0 else f'ERR({rc})'
            print(f'{label}: {status}')

    print('Done.')


if __name__ == '__main__':
    main()
