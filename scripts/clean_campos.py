
import argparse
import json
import os
import sys


def simplify_field(f):
    name = f.get("name")
    label = f.get("label")
    custom = f.get("custom")
    ftype = f.get("type")
    precision = f.get("precision")
    scale = f.get("scale")
    length = f.get("length")

    raw_pick = f.get("picklistValues") or []
    picklist_values = []
    for pv in raw_pick:
        if pv is None:
            continue
        if isinstance(pv, dict):
            picklist_values.append({
                "active": pv.get("active"),
                "label": pv.get("label"),
                "value": pv.get("value"),
            })
        else:
            picklist_values.append({"active": None, "label": pv, "value": pv})

    reference_to = f.get("referenceTo") or []

    out = {
        "label": label,
        "name": name,
        "custom": custom,
        "picklistValues": picklist_values,
        "referenceTo": reference_to,
        "type": ftype,
        "precision": precision,
        "scale": scale,
        "length": length,
    }

    return out


def find_fields(obj):
    if isinstance(obj, dict):
        if "fields" in obj and isinstance(obj["fields"], list):
            return obj["fields"]
        if "result" in obj and isinstance(obj["result"], dict):
            r = obj["result"]
            if "fields" in r and isinstance(r["fields"], list):
                return r["fields"]
    return []


def main():
    parser = argparse.ArgumentParser(description="Simplify Salesforce object fields JSON")
    parser.add_argument("input", help="Input JSON file path")
    parser.add_argument("output", nargs="?", help="Output JSON file path (optional)")
    args = parser.parse_args()

    inp = args.input
    if not os.path.isfile(inp):
        print(f"Error: input file not found: {inp}")
        sys.exit(2)

    with open(inp, "r", encoding="utf-8") as fh:
        data = json.load(fh)

    fields = find_fields(data)
    simplified = [simplify_field(f) for f in fields]

    out_obj = {"fields": simplified}

    out = args.output
    if not out:
        base, ext = os.path.splitext(inp)
        out = base + "_simplified.json"

    with open(out, "w", encoding="utf-8") as fh:
        json.dump(out_obj, fh, ensure_ascii=False, indent=2)

    print(f"Wrote {len(simplified)} fields to {out}")


if __name__ == "__main__":
    main()
