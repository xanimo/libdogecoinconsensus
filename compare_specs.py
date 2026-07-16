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

What is NOT ignored: file_sha256, and the extracted content itself. Those are
the pin. If they differ, the specs genuinely describe different source and the
check must fail.

core_commit is recorded but NOT compared. It identifies the repository state;
file_sha256 identifies the bytes actually parsed. Those come apart constantly:
a docs, depends, test, or whitespace commit moves the commit hash without
touching chainparams.cpp. Failing on that is crying wolf -- and the remedy it
demands (re-pin to a commit whose consensus definition is byte-identical)
teaches the reader that re-pinning is an empty ritual. That is precisely how a
real drift gets waved through.

The sha256 is the truth: it describes the exact bytes parsed, even if the
working tree was dirty. A commit that differs while every extracted file hashes
identically is reported as a note, not a failure.

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
    # NOT the identity of what was parsed -- see the module docstring.
    # file_sha256 is. A commit hash moves on any change to the repo; the
    # sha256 moves only when the extracted bytes move, which is the only
    # thing that can change what this library says the rules are.
    "core_commit",
    "core_client_version",   # tracks the tree, not the parsed file
    "core_is_release",
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

    # Raw provenance: normalize() strips core_commit, so read it pre-strip.
    ra = json.loads(args.first.read_text()).get("_provenance", {})
    rb = json.loads(args.second.read_text()).get("_provenance", {})

    diffs = list(walk_diff(a, b))
    if not diffs:
        print(f"OK: {la} is semantically identical to {lb}")
        # Same bytes, different commit: not a failure, but not nothing either.
        # Say it out loud so the pin can be refreshed deliberately rather than
        # discovered by surprise later.
        if ra.get("core_commit") != rb.get("core_commit"):
            print(f"note: extracted from the same bytes "
                  f"(sha256 {str(ra.get('file_sha256'))[:16]}...) but different")
            print(f"      Core commits -- {str(ra.get('core_commit'))[:12]} vs "
                  f"{str(rb.get('core_commit'))[:12]}.")
            print("      The consensus definition did not move; the repository did.")
            print("      Refresh the pin with `make spec` when convenient.")
        return 0

    print(f"DIFFERS: {la} vs {lb}")
    print()
    for d in diffs[:50]:
        print(f"  {d}")
    if len(diffs) > 50:
        print(f"  ... and {len(diffs) - 50} more")
    print()

    # The most common real cause is worth naming explicitly. Key on the
    # sha256, not the commit: the sha256 is what identifies the parsed bytes.
    sa = ra.get("file_sha256")
    sb = rb.get("file_sha256")
    ca = ra.get("core_commit")
    cb = rb.get("core_commit")
    if sa != sb:
        print(f"  file_sha256 differs: {str(sa)[:16]}... vs {str(sb)[:16]}...")
        print("  => these specs were parsed from DIFFERENT bytes. Not a bug in the")
        print("     extractor; regenerate against the intended commit.")
        if ca != cb:
            print(f"     (core_commit: {str(ca)[:12]} vs {str(cb)[:12]})")
    else:
        print("  Same file_sha256, different content: the SAME bytes parsed two")
        print("  different ways. The committed spec was hand-edited, or the")
        print("  extractor changed. Both need review.")
        if ca != cb:
            print(f"  (core_commit differs -- {str(ca)[:12]} vs {str(cb)[:12]} -- but")
            print("   that is not the cause: the parsed bytes are identical.)")
    return 1


if __name__ == "__main__":
    sys.exit(main())
