#!/usr/bin/env python3
"""
regression_gate.py — detect unreviewed changes to the consensus definition.

Pin a known-good spec. Re-extract against Core on a schedule. If the consensus
definition changed, fail — so a Core update can't silently alter what this
library says the rules are.

This is NOT "libdogecoin vs Core". That comparison is a category error: per
DIRECTIVE §2b libdogecoin has no consensus height dimension, correctly, because
it doesn't validate. For the one surface where a libdogecoin comparison IS
meaningful, see diff_checkpoints.py.

Usage:
    ./regression_gate.py --pin    spec.json -o pinned.json     # snapshot
    ./regression_gate.py --check  spec.json --against pinned.json

Exit: 0 identical, 1 changed, 2 error.
"""

import argparse
import json
import sys
from pathlib import Path


def flatten(spec):
    """spec -> {key: value}, height-qualified.

    Keys are height-qualified because Dogecoin's consensus is height-indexed.
    A flat NETWORK.field comparison is meaningless: nPowTargetTimespan is 14400
    before block 145000 and 60 after. Comparing one value is how you ship a
    client that forks itself off the network."""
    flat = {}
    for cls, net in spec.get("networks", {}).items():
        p = cls.replace("Params", "").replace("C", "", 1).upper()

        for st in net.get("activation_schedule", []):
            h = st["nHeightEffective"]
            for f, v in st.get("effective_fields", {}).items():
                if v is not None:
                    flat[f"{p}@{h}.{f}"] = v

        ms = net.get("messageStart", {})
        if len(ms) == 4:
            try:
                flat[f"{p}.messageStart"] = [ms[str(i)]["value"] for i in range(4)]
            except (KeyError, TypeError):
                pass

        for k, v in net.get("base58Prefixes", {}).items():
            if v.get("value") is not None:
                flat[f"{p}.base58.{k}"] = v["value"]

        for dep, fields in net.get("deployments", {}).items():
            short = dep.split("::")[-1]
            for f, v in fields.items():
                if v.get("value") is not None:
                    flat[f"{p}.deploy.{short}.{f}"] = v["value"]

        for c in net.get("checkpoints", []):
            flat[f"{p}.checkpoint.{c['height']}"] = c["hash"]

        ctd = net.get("chainTxData")
        if ctd:
            for f, v in ctd.items():
                flat[f"{p}.chainTxData.{f}"] = v

    return flat


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("spec", type=Path)
    ap.add_argument("--pin", action="store_true", help="write a pinned snapshot")
    ap.add_argument("--check", action="store_true", help="compare against a pin")
    ap.add_argument("--against", type=Path, help="pinned snapshot to compare to")
    ap.add_argument("-o", "--out", type=Path, help="output for --pin")
    args = ap.parse_args()

    spec = json.loads(args.spec.read_text())
    flat = flatten(spec)

    if not flat:
        print("error: spec produced no comparable keys — wrong file, or a "
              "pre-v2 spec with no activation_schedule", file=sys.stderr)
        return 2

    if args.pin:
        out = args.out or Path("pinned.json")
        payload = {
            "_pinned_from": spec.get("_provenance", {}),
            "values": flat,
        }
        out.write_text(json.dumps(payload, indent=2, sort_keys=True))
        print(f"pinned {len(flat)} values -> {out}", file=sys.stderr)
        return 0

    if not args.check or not args.against:
        ap.error("use --pin, or --check --against <pinned.json>")

    pinned = json.loads(args.against.read_text())
    old = pinned.get("values", {})
    oldprov = pinned.get("_pinned_from", {})
    newprov = spec.get("_provenance", {})

    changed = [(k, old[k], flat[k]) for k in sorted(set(old) & set(flat))
               if old[k] != flat[k]]
    added = sorted(set(flat) - set(old))
    removed = sorted(set(old) - set(flat))

    print("=" * 70)
    print("CONSENSUS REGRESSION GATE")
    print(f"  pinned at: {oldprov.get('core_commit','?')[:12]} "
          f"({oldprov.get('core_client_version','?')})")
    print(f"  now at:    {newprov.get('core_commit','?')[:12]} "
          f"({newprov.get('core_client_version','?')})")
    print("=" * 70)

    if changed:
        print(f"\n!! {len(changed)} VALUE(S) CHANGED:")
        for k, o, n in changed:
            print(f"   {k}")
            print(f"      was: {o}")
            print(f"      now: {n}")
    if added:
        print(f"\n+  {len(added)} new key(s):")
        for k in added:
            print(f"   {k} = {flat[k]}")
    if removed:
        print(f"\n-  {len(removed)} key(s) gone:")
        for k in removed:
            print(f"   {k} (was {old[k]})")

    n = len(changed) + len(added) + len(removed)
    print()
    if n == 0:
        print(f"OK: {len(flat)} values identical to the pin.")
        return 0
    print(f"CHANGED: {len(changed)} modified, {len(added)} added, {len(removed)} removed")
    print()
    print("Core's consensus definition moved. This is not automatically a bug —")
    print("but it must be REVIEWED, not absorbed silently. If the change is")
    print("intended, re-pin:")
    print(f"    ./regression_gate.py --pin {args.spec} -o {args.against}")
    return 1


if __name__ == "__main__":
    sys.exit(main())
