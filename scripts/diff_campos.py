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
    # helper to extract requested metadata keys from a field dict
    def _meta_from_field(f):
        if not isinstance(f, dict):
            return None
        return {
            'label': f.get('label'),
            'name': f.get('name'),
            'custom': f.get('custom'),
            'picklistValues': f.get('picklistValues'),
            'referenceTo': f.get('referenceTo'),
            'type': f.get('type'),
            'precision': f.get('precision'),
            'scale': f.get('scale'),
            'length': f.get('length'),
        }

    # build lists of metadata objects for added/removed
    added_meta = []
    for n in added:
        meta = _meta_from_field(new_by_name.get(n))
        # if new_by_name missing, fall back to name-only object
        if not meta:
            meta = {'name': n}
        added_meta.append(meta)

    removed_meta = []
    for n in removed:
        meta = _meta_from_field(old_by_name.get(n))
        if not meta:
            meta = {'name': n}
        removed_meta.append(meta)

    report = {
        'summary': {
            'fields_old': len(old_names),
            'fields_new': len(new_names),
            'added': len(added_meta),
            'removed': len(removed_meta),
            'modified': len(modified),
        },
        'added_fields': added_meta,
        'removed_fields': removed_meta,
        'modified_fields': modified,
    }
    return report


def print_summary(report):
    def _safe_print(*parts, sep=' ', end='\n'):
        s = sep.join(str(p) for p in parts) + end
        try:
            # normal print (may raise UnicodeEncodeError on some consoles)
            sys.stdout.write(s)
        except UnicodeEncodeError:
            # write bytes utf-8 replacing unencodable chars
            sys.stdout.buffer.write(s.encode('utf-8', errors='replace'))

    s = report.get('summary', {})
    _safe_print('Old fields:', s.get('fields_old'))
    _safe_print('New fields:', s.get('fields_new'))
    _safe_print('Added fields:', s.get('added'))
    _safe_print('Removed fields:', s.get('removed'))
    _safe_print('Modified fields:', s.get('modified'))
    _safe_print('')

    if report.get('added_fields'):
        _safe_print('Added:')
        for entry in report['added_fields']:
            if isinstance(entry, dict):
                _safe_print('  +', entry.get('name') or entry.get('label') or entry)
                # print some metadata inline
                _safe_print('    -', 'label:', entry.get('label'), 'type:', entry.get('type'), 'custom:', entry.get('custom'))
                if entry.get('picklistValues'):
                    try:
                        pv_vals = [p.get('value') or p.get('label') for p in entry.get('picklistValues')]
                        _safe_print('    -', 'picklistValues:', ','.join(pv_vals))
                    except Exception:
                        _safe_print('    -', 'picklistValues: (unprintable)')
            else:
                _safe_print('  +', entry)
    if report.get('removed_fields'):
        _safe_print('Removed:')
        for entry in report['removed_fields']:
            if isinstance(entry, dict):
                _safe_print('  -', entry.get('name') or entry.get('label') or entry)
                _safe_print('    -', 'label:', entry.get('label'), 'type:', entry.get('type'), 'custom:', entry.get('custom'))
                if entry.get('picklistValues'):
                    try:
                        pv_vals = [p.get('value') or p.get('label') for p in entry.get('picklistValues')]
                        _safe_print('    -', 'picklistValues:', ','.join(pv_vals))
                    except Exception:
                        _safe_print('    -', 'picklistValues: (unprintable)')
            else:
                _safe_print('  -', entry)
    if report.get('modified_fields'):
        _safe_print('\nModified:')
        for name, info in report['modified_fields'].items():
            _safe_print(' *', name)
            for d in info['diffs']:
                if 'detail' in d:
                    _safe_print('    -', d['attribute'], json.dumps(d['detail'], ensure_ascii=False))
                else:
                    _safe_print('    -', d['attribute'], '->', 'old:', d.get('old'), 'new:', d.get('new'))


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
        for entry in report['added_fields']:
            if isinstance(entry, dict):
                nm = entry.get('name') or entry.get('label') or ''
                out_lines.append(f"  + {nm}")
                out_lines.append(f"    - label: {entry.get('label')} type: {entry.get('type')} custom: {entry.get('custom')}")
                if entry.get('picklistValues'):
                    try:
                        pv_vals = [p.get('value') or p.get('label') for p in entry.get('picklistValues')]
                        out_lines.append(f"    - picklistValues: {','.join(pv_vals)}")
                    except Exception:
                        out_lines.append(f"    - picklistValues: (unprintable)")
            else:
                out_lines.append(f"  + {entry}")
    if report.get('removed_fields'):
        out_lines.append('Removed:')
        for entry in report['removed_fields']:
            if isinstance(entry, dict):
                nm = entry.get('name') or entry.get('label') or ''
                out_lines.append(f"  - {nm}")
                out_lines.append(f"    - label: {entry.get('label')} type: {entry.get('type')} custom: {entry.get('custom')}")
                if entry.get('picklistValues'):
                    try:
                        pv_vals = [p.get('value') or p.get('label') for p in entry.get('picklistValues')]
                        out_lines.append(f"    - picklistValues: {','.join(pv_vals)}")
                    except Exception:
                        out_lines.append(f"    - picklistValues: (unprintable)")
            else:
                out_lines.append(f"  - {entry}")
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
