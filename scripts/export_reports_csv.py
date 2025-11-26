#!/usr/bin/env python3
"""Export report_objects/*.json into a single CSV with the requested columns.

CSV columns produced:
    objeto, change_type, api_name, label, type, details,
    fields_old, fields_new, added_count, removed_count, modified_count

Each row corresponds to a single field-level change (added/removed/modified).
"""

import argparse
import csv
import json
import os
from pathlib import Path
from typing import Any, Dict, List, Optional


def _load_json(path: Path) -> Optional[Any]:
    try:
        with path.open('r', encoding='utf-8') as f:
            return json.load(f)
    except FileNotFoundError:
        return None
    except Exception:
        try:
            with path.open('r', encoding='latin-1') as f:
                return json.load(f)
        except Exception:
            return None


def _search_field_in_data(data: Any, field_name: str) -> Optional[Dict[str, Any]]:
    if data is None:
        return None
    if isinstance(data, dict):
        if field_name in data and isinstance(data[field_name], dict):
            return data[field_name]
        fname = data.get('name') or data.get('apiName') or data.get('field') or data.get('fullName')
        if fname == field_name:
            return data
        for v in data.values():
            res = _search_field_in_data(v, field_name)
            if res:
                return res
    elif isinstance(data, list):
        for item in data:
            res = _search_field_in_data(item, field_name)
            if res:
                return res
    return None


def find_field_meta(obj_name: str, field_entry: Any, simplified_dir: Path, baseline_dir: Path) -> Optional[Dict[str, Any]]:
    # if already metadata dict
    if isinstance(field_entry, dict) and field_entry.get('name'):
        return field_entry
    field_name = str(field_entry)
    simplified_file = simplified_dir / f'simplified-{obj_name}.json'
    baseline_file = baseline_dir / f'baseline-{obj_name}.json'
    incoming_file = Path('incoming_objects') / f'incoming-{obj_name}.json'
    for p in (simplified_file, baseline_file, incoming_file):
        data = _load_json(p) if p.exists() else None
        if not data:
            continue
        found = _search_field_in_data(data, field_name)
        if found:
            return found
    return None


def summarize_report(path: Path, simplified_dir: Path, baseline_dir: Path) -> List[Dict[str, Any]]:
    data = _load_json(path)
    if not data:
        return []
    name = path.stem
    obj = name[len('report-'):] if name.startswith('report-') else name

    summary = data.get('summary', {})
    fields_old = summary.get('fields_old', '')
    fields_new = summary.get('fields_new', '')
    added_count = summary.get('added', 0)
    removed_count = summary.get('removed', 0)
    modified_count = summary.get('modified', 0)

    added = data.get('added_fields', []) or []
    removed = data.get('removed_fields', []) or []
    modified = data.get('modified_fields', {}) or {}

    rows: List[Dict[str, Any]] = []

    def _details(obj: Any) -> str:
        try:
            return json.dumps(obj, ensure_ascii=False, separators=(',', ':'))
        except Exception:
            return str(obj)

    def _fmt_pick_item(it: Any) -> str:
        if isinstance(it, dict):
            val = it.get('value') if it.get('value') is not None else it.get('label')
            lab = it.get('label')
            act = it.get('active')
            return f"value={val},label={lab},active={act}"
        return str(it)

    # Added fields
    for fld in added:
        meta = find_field_meta(obj, fld, simplified_dir, baseline_dir)
        api_name = meta.get('name') if isinstance(meta, dict) else (fld if isinstance(fld, str) else '')
        label = meta.get('label') if isinstance(meta, dict) else ''
        dtype = meta.get('type') if isinstance(meta, dict) else ''
        details = _details(meta) if meta else _details(fld)
        picklist_added = ''
        if isinstance(meta, dict) and meta.get('picklistValues'):
            try:
                picklist_added = ';'.join([_fmt_pick_item(pv) for pv in meta.get('picklistValues')])
            except Exception:
                picklist_added = ''
        rows.append({
            'objeto': obj,
            'change_type': 'added',
            'api_name': api_name,
            'label': label,
            'type': dtype,
            'attribute': '',
            'old': '',
            'new': '',
            'detail': details,
            'picklist_added': picklist_added,
            'picklist_removed': '',
            'fields_old': fields_old,
            'fields_new': fields_new,
            'added_count': added_count,
            'removed_count': removed_count,
            'modified_count': modified_count,
        })

    # Removed fields
    for fld in removed:
        meta = find_field_meta(obj, fld, simplified_dir, baseline_dir)
        api_name = meta.get('name') if isinstance(meta, dict) else (fld if isinstance(fld, str) else '')
        label = meta.get('label') if isinstance(meta, dict) else ''
        dtype = meta.get('type') if isinstance(meta, dict) else ''
        details = _details(meta) if meta else _details(fld)
        picklist_removed = ''
        if isinstance(meta, dict) and meta.get('picklistValues'):
            try:
                picklist_removed = ';'.join([_fmt_pick_item(pv) for pv in meta.get('picklistValues')])
            except Exception:
                picklist_removed = ''
        rows.append({
            'objeto': obj,
            'change_type': 'removed',
            'api_name': api_name,
            'label': label,
            'type': dtype,
            'attribute': '',
            'old': '',
            'new': '',
            'detail': details,
            'picklist_added': '',
            'picklist_removed': picklist_removed,
            'fields_old': fields_old,
            'fields_new': fields_new,
            'added_count': added_count,
            'removed_count': removed_count,
            'modified_count': modified_count,
        })

    # Modified: per-diff rows
    if isinstance(modified, dict):
        items = modified.items()
    else:
        items = []

    # handle dict-style modified
    for name, det in items:
        fld = name
        meta = find_field_meta(obj, fld, simplified_dir, baseline_dir)
        api_name = meta.get('name') if isinstance(meta, dict) else fld
        label = meta.get('label') if isinstance(meta, dict) else (det.get('new', {}).get('label') if isinstance(det, dict) else '')
        dtype = meta.get('type') if isinstance(meta, dict) else (det.get('new', {}).get('type') if isinstance(det, dict) else '')
        diffs = det.get('diffs') if isinstance(det, dict) else None
        if isinstance(diffs, list) and diffs:
            for d in diffs:
                attr = d.get('attribute')
                picklist_added_field = ''
                picklist_removed_field = ''
                if 'detail' in d and isinstance(d['detail'], dict) and attr == 'picklistValues':
                    pd = d['detail']
                    added_vals = pd.get('added', []) or []
                    removed_vals = pd.get('removed', []) or []
                    changed_vals = pd.get('changed', []) or []
                    picklist_added_list = []
                    picklist_removed_list = []
                    for x in added_vals:
                        if isinstance(x, dict):
                            picklist_added_list.append(_fmt_pick_item(x))
                        else:
                            mf = find_field_meta(obj, fld, simplified_dir, baseline_dir)
                            found = None
                            if isinstance(mf, dict) and mf.get('picklistValues'):
                                for pv in mf.get('picklistValues'):
                                    if pv.get('value') == x or pv.get('label') == x:
                                        found = pv
                                        break
                            picklist_added_list.append(_fmt_pick_item(found) if found else str(x))
                    for x in removed_vals:
                        if isinstance(x, dict):
                            picklist_removed_list.append(_fmt_pick_item(x))
                        else:
                            mf = find_field_meta(obj, fld, simplified_dir, baseline_dir)
                            found = None
                            if isinstance(mf, dict) and mf.get('picklistValues'):
                                for pv in mf.get('picklistValues'):
                                    if pv.get('value') == x or pv.get('label') == x:
                                        found = pv
                                        break
                            picklist_removed_list.append(_fmt_pick_item(found) if found else str(x))
                    picklist_added_field = ';'.join(picklist_added_list) if picklist_added_list else ''
                    picklist_removed_field = ';'.join(picklist_removed_list) if picklist_removed_list else ''
                    # prepare detail for changed items too
                    parts = []
                    if added_vals:
                        parts.append('added:' + ';'.join(picklist_added_list))
                    if removed_vals:
                        parts.append('removed:' + ';'.join(picklist_removed_list))
                    if changed_vals:
                        changed_parts = []
                        for c in changed_vals:
                            val = c.get('value')
                            old_label = c.get('old', {}).get('label') if isinstance(c.get('old'), dict) else None
                            new_label = c.get('new', {}).get('label') if isinstance(c.get('new'), dict) else None
                            if old_label is not None and new_label is not None:
                                changed_parts.append(f"{val}: {old_label} -> {new_label}")
                            else:
                                changed_parts.append(str(val))
                        parts.append('changed:' + ';'.join(changed_parts))
                    detail = '; '.join(parts) if parts else _details(d.get('detail'))
                    old_val = ''
                    new_val = ''
                elif 'detail' in d and isinstance(d['detail'], dict) and attr == 'referenceTo':
                    pd = d['detail']
                    a = pd.get('added', []) or []
                    r = pd.get('removed', []) or []
                    parts = []
                    if a:
                        parts.append('added:' + ','.join(map(str, a)))
                    if r:
                        parts.append('removed:' + ','.join(map(str, r)))
                    detail = '; '.join(parts) if parts else _details(d.get('detail'))
                    old_val = ''
                    new_val = ''
                else:
                    # simple old/new diffs
                    old_val = d.get('old', '')
                    new_val = d.get('new', '')
                    detail = _details(d.get('detail')) if 'detail' in d else ''

                rows.append({
                    'objeto': obj,
                    'change_type': 'modified',
                    'api_name': api_name,
                    'label': label,
                    'type': dtype,
                    'attribute': attr,
                    'old': old_val,
                    'new': new_val,
                    'detail': detail,
                    'picklist_added': picklist_added_field,
                    'picklist_removed': picklist_removed_field,
                    'fields_old': fields_old,
                    'fields_new': fields_new,
                    'added_count': added_count,
                    'removed_count': removed_count,
                    'modified_count': modified_count,
                })

    # handle list-style modified (rare case)
    if isinstance(modified, list):
        for item in modified:
            if isinstance(item, dict) and 'field' in item:
                fld = item.get('field')
                det = item
            else:
                fld = str(item)
                det = item
            meta = find_field_meta(obj, fld, simplified_dir, baseline_dir)
            api_name = meta.get('name') if isinstance(meta, dict) else fld
            label = meta.get('label') if isinstance(meta, dict) else ''
            dtype = meta.get('type') if isinstance(meta, dict) else ''
            diffs = det.get('diffs') if isinstance(det, dict) else None
            if isinstance(diffs, list) and diffs:
                for d in diffs:
                    attr = d.get('attribute')
                    if 'detail' in d and isinstance(d['detail'], dict) and attr == 'picklistValues':
                        # reuse same logic as above for picklist
                        pd = d['detail']
                        added_vals = pd.get('added', []) or []
                        removed_vals = pd.get('removed', []) or []
                        picklist_added_list = []
                        picklist_removed_list = []
                        for x in added_vals:
                            if isinstance(x, dict):
                                picklist_added_list.append(_fmt_pick_item(x))
                            else:
                                mf = find_field_meta(obj, fld, simplified_dir, baseline_dir)
                                found = None
                                if isinstance(mf, dict) and mf.get('picklistValues'):
                                    for pv in mf.get('picklistValues'):
                                        if pv.get('value') == x or pv.get('label') == x:
                                            found = pv
                                            break
                                picklist_added_list.append(_fmt_pick_item(found) if found else str(x))
                        for x in removed_vals:
                            if isinstance(x, dict):
                                picklist_removed_list.append(_fmt_pick_item(x))
                            else:
                                mf = find_field_meta(obj, fld, simplified_dir, baseline_dir)
                                found = None
                                if isinstance(mf, dict) and mf.get('picklistValues'):
                                    for pv in mf.get('picklistValues'):
                                        if pv.get('value') == x or pv.get('label') == x:
                                            found = pv
                                            break
                                picklist_removed_list.append(_fmt_pick_item(found) if found else str(x))
                        detail = ''
                        if added_vals:
                            detail = 'added:' + ';'.join(picklist_added_list)
                        if removed_vals:
                            detail = (detail + '; ' if detail else '') + 'removed:' + ';'.join(picklist_removed_list)
                        rows.append({
                            'objeto': obj,
                            'change_type': 'modified',
                            'api_name': api_name,
                            'label': label,
                            'type': dtype,
                            'attribute': attr,
                            'old': '',
                            'new': '',
                            'detail': detail,
                            'picklist_added': ';'.join(picklist_added_list) if picklist_added_list else '',
                            'picklist_removed': ';'.join(picklist_removed_list) if picklist_removed_list else '',
                            'fields_old': fields_old,
                            'fields_new': fields_new,
                            'added_count': added_count,
                            'removed_count': removed_count,
                            'modified_count': modified_count,
                        })
                    else:
                        old_val = d.get('old', '')
                        new_val = d.get('new', '')
                        rows.append({
                            'objeto': obj,
                            'change_type': 'modified',
                            'api_name': api_name,
                            'label': label,
                            'type': dtype,
                            'attribute': d.get('attribute'),
                            'old': old_val,
                            'new': new_val,
                            'detail': _details(d.get('detail')) if 'detail' in d else '',
                            'picklist_added': '',
                            'picklist_removed': '',
                            'fields_old': fields_old,
                            'fields_new': fields_new,
                            'added_count': added_count,
                            'removed_count': removed_count,
                            'modified_count': modified_count,
                        })

    return rows


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument('--reports-dir', '-r', default='report_objects', help='Directory with report-*.json files')
    p.add_argument('--simplified-dir', '-s', default='simplified_objects', help='Directory with simplified-<object>.json')
    p.add_argument('--baseline-dir', '-b', default='baseline_objects', help='Directory with baseline-<object>.json')
    p.add_argument('--out', '-o', default=os.path.join('report_objects', 'reports_summary.csv'), help='Output CSV file')
    args = p.parse_args()

    reports_dir = Path(args.reports_dir)
    simplified_dir = Path(args.simplified_dir)
    baseline_dir = Path(args.baseline_dir)
    out_csv = Path(args.out)
    out_csv.parent.mkdir(parents=True, exist_ok=True)

    files = sorted(reports_dir.glob('report-*.json'))
    if not files:
        print('No report-*.json files found in', reports_dir)
        return 0

    rows: List[Dict[str, Any]] = []
    for f in files:
        try:
            r = summarize_report(f, simplified_dir, baseline_dir)
            rows.extend(r)
        except Exception as e:
            print('Skipping', f.name, 'due to error:', e)

    cols = ['objeto', 'change_type', 'api_name', 'label', 'type', 'attribute', 'old', 'new', 'detail', 'picklist_value_label', 'picklist_value_api', 'picklist_value_active']

    # Expand rows: for any row that has picklist_added/picklist_removed with multiple items,
    # also emit one row per picklist option with columns picklist_value_label, picklist_value_api, picklist_value_active.
    final_rows: List[Dict[str, Any]] = []
    def _parse_pick_item_str(s: str):
        # s expected like "value=USD,label=U.S. Dollar,active=True" or a plain token
        if not s:
            return (None, None, None, None)
        parts = s.split(',')
        kv = {}
        for p in parts:
            if '=' in p:
                k, v = p.split('=', 1)
                kv[k.strip()] = v.strip()
        if kv:
            label = kv.get('label') or kv.get('value')
            value = kv.get('value') or kv.get('label')
            active_raw = kv.get('active')
            # try to convert active to boolean if possible
            if isinstance(active_raw, str):
                if active_raw.lower() in ('true', '1', 'yes'):
                    active = True
                elif active_raw.lower() in ('false', '0', 'no'):
                    active = False
                else:
                    active = active_raw
            else:
                active = active_raw
            obj = {'active': active, 'label': label, 'value': value}
            return (label, value, active, obj)
        # fallback: treat s as value and label
        obj = {'active': None, 'label': s, 'value': s}
        return (s, s, None, obj)

    for r in rows:
        # keep original row
        final_rows.append(r.copy())
        # handle added picklist entries -> emit one row per option
        pa = r.get('picklist_added') or ''
        if pa:
            items = [it for it in pa.split(';') if it]
            for it in items:
                lbl, api, act, obj = _parse_pick_item_str(it)
                nr = r.copy()
                nr['change_type'] = 'picklist_value_added'
                nr['picklist_value_label'] = lbl or ''
                nr['picklist_value_api'] = api or ''
                nr['picklist_value_active'] = act if act is not None else ''
                try:
                    nr['detail'] = json.dumps(obj, ensure_ascii=False, separators=(',', ':'))
                except Exception:
                    nr['detail'] = r.get('detail', '')
                final_rows.append(nr)
        # handle removed picklist entries -> emit one row per option
        pr = r.get('picklist_removed') or ''
        if pr:
            items = [it for it in pr.split(';') if it]
            for it in items:
                lbl, api, act, obj = _parse_pick_item_str(it)
                nr = r.copy()
                nr['change_type'] = 'picklist_value_removed'
                nr['picklist_value_label'] = lbl or ''
                nr['picklist_value_api'] = api or ''
                nr['picklist_value_active'] = act if act is not None else ''
                try:
                    nr['detail'] = json.dumps(obj, ensure_ascii=False, separators=(',', ':'))
                except Exception:
                    nr['detail'] = r.get('detail', '')
                final_rows.append(nr)

    with out_csv.open('w', encoding='utf-8', newline='') as outf:
        writer = csv.DictWriter(outf, fieldnames=cols)
        writer.writeheader()
        for r in final_rows:
            outrow = {k: (r.get(k) if r.get(k) is not None else '') for k in cols}
            writer.writerow(outrow)

    print('Wrote', len(rows), 'rows to', out_csv)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
