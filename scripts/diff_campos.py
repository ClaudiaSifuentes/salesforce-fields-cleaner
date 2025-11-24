import json
import sys
import os
import argparse
from collections import defaultdict


def load_fields(path):
    with open(path, 'r', encoding='utf-8') as fh:
        data = json.load(fh)
    fields = data.get('fields', []) if isinstance(data, dict) else []
    by_name = {f.get('name'): f for f in fields if f.get('name')}
    return by_name


def picklist_map(picklist_values):
    m = {}
    for pv in picklist_values or []:
        if not isinstance(pv, dict):
            continue
        value = pv.get('value')
        if value is None:
            value = pv.get('label')
        m[value] = {'label': pv.get('label'), 'active': pv.get('active')}
    return m


def compare_picklists(old_list, new_list):
    old_map = picklist_map(old_list)
    new_map = picklist_map(new_list)
    old_vals = set(old_map.keys())
    new_vals = set(new_map.keys())
    added = sorted(list(new_vals - old_vals))
    removed = sorted(list(old_vals - new_vals))
    changed = []
    for v in old_vals & new_vals:
        o = old_map[v]
        n = new_map[v]
        if o.get('label') != n.get('label') or bool(o.get('active')) != bool(n.get('active')):
            changed.append({'value': v, 'old': o, 'new': n})
    return {'added': added, 'removed': removed, 'changed': changed}


def compare_references(old_ref, new_ref):
    old_set = set(old_ref or [])
    new_set = set(new_ref or [])
    return {'added': sorted(list(new_set - old_set)), 'removed': sorted(list(old_set - new_set))}


def compare_field(old, new):
    diffs = []
    keys_to_check = ['label', 'custom', 'type', 'precision', 'scale', 'length']
    for k in keys_to_check:
        o = old.get(k) if old else None
        n = new.get(k) if new else None
        if o != n:
            diffs.append({'attribute': k, 'old': o, 'new': n})

    pick_diff = compare_picklists(old.get('picklistValues') if old else [], new.get('picklistValues') if new else [])
    if pick_diff['added'] or pick_diff['removed'] or pick_diff['changed']:
        diffs.append({'attribute': 'picklistValues', 'detail': pick_diff})

    ref_diff = compare_references(old.get('referenceTo') if old else [], new.get('referenceTo') if new else [])
    if ref_diff['added'] or ref_diff['removed']:
        diffs.append({'attribute': 'referenceTo', 'detail': ref_diff})

    return diffs


def make_report(old_by_name, new_by_name):
    old_names = set(old_by_name.keys())
    new_names = set(new_by_name.keys())
    added = sorted(list(new_names - old_names))
    removed = sorted(list(old_names - new_names))
    common = sorted(list(old_names & new_names))

    modified = {}
    for name in common:
        diffs = compare_field(old_by_name.get(name, {}), new_by_name.get(name, {}))
        if diffs:
            modified[name] = {'old': old_by_name.get(name), 'new': new_by_name.get(name), 'diffs': diffs}

    report = {
        'summary': {
            'fields_old': len(old_names),
            'fields_new': len(new_names),
            'added': len(added),
            'removed': len(removed),
            'modified': len(modified),
        },
        'added_fields': added,
        'removed_fields': removed,
        'modified_fields': modified,
    }
    return report


def print_summary(report):
    s = report.get('summary', {})
    print('Old fields:', s.get('fields_old'))
    print('New fields:', s.get('fields_new'))
    print('Added fields:', s.get('added'))
    print('Removed fields:', s.get('removed'))
    print('Modified fields:', s.get('modified'))
    print('')

    if report.get('added_fields'):
        print('Added:')
        for n in report['added_fields']:
            print('  +', n)
    if report.get('removed_fields'):
        print('Removed:')
        for n in report['removed_fields']:
            print('  -', n)
    if report.get('modified_fields'):
        print('\nModified:')
        for name, info in report['modified_fields'].items():
            print(' *', name)
            for d in info['diffs']:
                if 'detail' in d:
                    print('    -', d['attribute'], json.dumps(d['detail'], ensure_ascii=False))
                else:
                    print('    -', d['attribute'], '->', 'old:', d.get('old'), 'new:', d.get('new'))


def format_summary(report):
    """Return a human-readable string similar to the terminal output produced by print_summary."""
    out_lines = []
    s = report.get('summary', {})
    out_lines.append(f"Old fields: {s.get('fields_old')}")
    out_lines.append(f"New fields: {s.get('fields_new')}")
    out_lines.append(f"Added fields: {s.get('added')}")
    out_lines.append(f"Removed fields: {s.get('removed')}")
    out_lines.append(f"Modified fields: {s.get('modified')}")
    out_lines.append('')

    if report.get('added_fields'):
        out_lines.append('Added:')
        for n in report['added_fields']:
            out_lines.append(f"  + {n}")
    if report.get('removed_fields'):
        out_lines.append('Removed:')
        for n in report['removed_fields']:
            out_lines.append(f"  - {n}")
    if report.get('modified_fields'):
        out_lines.append('')
        out_lines.append('Modified:')
        for name, info in report['modified_fields'].items():
            out_lines.append(f"* {name}")
            for d in info['diffs']:
                if 'detail' in d:
                    # pretty-print JSON detail inline
                    detail = json.dumps(d['detail'], ensure_ascii=False)
                    out_lines.append(f"    - {d['attribute']} {detail}")
                else:
                    out_lines.append(f"    - {d['attribute']} -> old: {d.get('old')} new: {d.get('new')}")

    return '\n'.join(out_lines)


def main():
    parser = argparse.ArgumentParser(description='Compare two simplified Salesforce fields JSON files')
    parser.add_argument('old', help='Old JSON file path')
    parser.add_argument('new', help='New JSON file path')
    parser.add_argument('report', nargs='?', help='Optional output report JSON path')
    args = parser.parse_args()

    old_by_name = load_fields(args.old)
    new_by_name = load_fields(args.new)

    report = make_report(old_by_name, new_by_name)

    print_summary(report)

    if args.report:
        # embed a human-readable text version into the JSON report
        try:
            report['text_report'] = format_summary(report)
        except Exception:
            report['text_report'] = ''
        with open(args.report, 'w', encoding='utf-8') as fh:
            json.dump(report, fh, ensure_ascii=False, indent=2)
        print('\nWrote report to', args.report)


if __name__ == '__main__':
    main()
