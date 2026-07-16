#!/usr/bin/env python3
"""
compare_specs.py — is spec A semantically identical to spec B?

Used by CI to assert the committed spec matches a fresh extraction from the
Core commit it claims to come from. If it doesn't, the pin is a lie: either
someone hand-edited the spec, or it was generated from a different Core than
its provenance says.

Environment-dependent fields are ignored, because they legitimately differ
between machines and comparing them would make the check fail for reasons that
aren't bugs:

  _source              a filesystem path (~/src/dogecoin vs CI's ./core)
  _provenance.source   same
  _provenance.*dirty   local working-tree state
  _provenance.core_branch / core_detached
                       CI checks out a detached commit; a developer is on a branch

What is NOT ignored: core_commit and file_sha256. Those are the pin. If they
differ, the specs genuinely describe different source and the check must fail.

A CI check that cries wolf gets disabled, and a disabled check protects nothing.
So this ignores exactly what it must and nothing more.

Usage:
    ./compare_specs.py committed.json regenerated.json
Exit: 0 identical, 1 differs, 2 error.
"""

import argparse
import json
import sys
from pathlib import Path

# Fields that legitimately vary by environment. Everything else is compared.
IGNORE_TOP = {"_source"}
IGNORE_PROV = {
    "source",           # path
    "file_dirty",       # local working tree
    "tree_dirty",
    "core_branch",      # CI detaches HEAD; devs are on a branch
    "core_detached",
    "core_describe_dirty",
    # `git describe` abbreviates the hash to however many hex chars are needed
    # to be unambiguous IN THAT REPO. A full clone needs more than a partial
    # one, so the same commit renders as v1.14.7-239-g699f62ccba locally and
    # v1.14.7-239-g699f62ccb in CI. Same commit, different string. The identity
    # is core_commit (full 40 chars), which is NOT ignored; describe is
    # decoration, per DIRECTIVE §9.
    "core_describe",
    "_warning",
    "_error",
}


def normalize(spec):
    """Strip environment-dependent fields, keeping the pin (commit + sha256)."""
    out = {k: v for k, v in spec.items() if k not in IGNORE_TOP}
    prov = out.get("_provenance")
    if isinstance(prov, dict):
        out["_provenance"] = {k: v for k, v in prov.items()
                              if k not in IGNORE_PROV}
    return out


def walk_diff(a, b, path=""):
    """Yield human-readable differences."""
    if type(a) is not type(b):
        yield f"{path or '<root>'}: type {type(a).__name__} vs {type(b).__name__}"
        return
    if isinstance(a, dict):
        for k in sorted(set(a) | set(b)):
            p = f"{path}.{k}" if path else k
            if k not in a:
                yield f"{p}: missing in first, second has {b[k]!r}"
            elif k not in b:
                yield f"{p}: present in first ({a[k]!r}), missing in second"
            else:
                yield from walk_diff(a[k], b[k], p)
    elif isinstance(a, list):
        if len(a) != len(b):
            yield f"{path}: length {len(a)} vs {len(b)}"
            return
        for i, (x, y) in enumerate(zip(a, b)):
            yield from walk_diff(x, y, f"{path}[{i}]")
    elif a != b:
        yield f"{path}: {a!r} != {b!r}"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("first", type=Path)
    ap.add_argument("second", type=Path)
    ap.add_argument("--label-first", default=None)
    ap.add_argument("--label-second", default=None)
    args = ap.parse_args()

    for p in (args.first, args.second):
        if not p.exists():
            print(f"error: {p} not found", file=sys.stderr)
            return 2

    a = normalize(json.loads(args.first.read_text()))
    b = normalize(json.loads(args.second.read_text()))

    la = args.label_first or str(args.first)
    lb = args.label_second or str(args.second)

    diffs = list(walk_diff(a, b))
    if not diffs:
        print(f"OK: {la} is semantically identical to {lb}")
        return 0

    print(f"DIFFERS: {la} vs {lb}")
    print()
    for d in diffs[:50]:
        print(f"  {d}")
    if len(diffs) > 50:
        print(f"  ... and {len(diffs) - 50} more")
    print()

    # The most common real cause is worth naming explicitly.
    ca = a.get("_provenance", {}).get("core_commit")
    cb = b.get("_provenance", {}).get("core_commit")
    if ca != cb:
        print(f"  core_commit differs: {ca} vs {cb}")
        print("  => these specs describe DIFFERENT Core source. Not a bug in the")
        print("     extractor; regenerate against the intended commit.")
    else:
        print("  Same core_commit, different content. Either the committed spec was")
        print("  hand-edited, or the extractor changed. Both need review.")
    return 1


if __name__ == "__main__":
    sys.exit(main())
