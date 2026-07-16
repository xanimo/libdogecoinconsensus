#!/usr/bin/env python3
"""
diff_checkpoints.py — compare libdogecoin's hand-transcribed checkpoint arrays
against Core's, as extracted into spec.json.

This is the one place a libdogecoin-vs-Core diff is meaningful. Per DIRECTIVE
§2b libdogecoin has no consensus height dimension (correctly — it doesn't
validate), so comparing consensus params is a category error. But it DOES carry
checkpoints, hand-typed from Core years ago. Those can drift, and drift is
silent: a stale checkpoint doesn't fail loudly, it just stops protecting.

libdogecoin's form (src/chainparams.c):

    const dogecoin_checkpoint dogecoin_mainnet_checkpoint_array[] = {
        {0, "1a91e3dace36e2be3bf030a65679fe821aa1d6ef92e7c9902eb318182c355691", 1386325540, 0x1e0ffff0},
        {104679, "35eb87ae90d44b98898fec8c39577b76cb1eb08e1261cfc10706c8ce9a1d01cf", 1392637497, ...},
        ...
    };

Note libdogecoin hashes have no 0x prefix; Core's uint256S does. Normalized.

Usage:
    ./diff_checkpoints.py spec.json --libdogecoin ~/source/repos/libdogecoin/src/chainparams.c
"""

import argparse
import json
import re
import sys
from pathlib import Path

# {height, "hash", timestamp, bits}  — trailing fields vary, so match leniently
LIBDOGE_ENTRY_RE = re.compile(
    r"\{\s*(\d+)\s*,\s*\"([0-9a-fA-F]{64})\"")

ARRAY_RE = re.compile(
    r"dogecoin_checkpoint\s+dogecoin_(\w+?)_checkpoint_array\s*\[\s*\]\s*=\s*\{",
    re.MULTILINE)

# map libdogecoin array names -> spec network class names
ARRAY_TO_CLASS = {
    "mainnet": "CMainParams",
    "testnet": "CTestNetParams",
    "regtest": "CRegTestParams",
}


def norm(h: str) -> str:
    """Core writes 0x-prefixed; libdogecoin doesn't. Compare lowercase bare hex."""
    h = h.strip().lower()
    return h[2:] if h.startswith("0x") else h


def parse_libdogecoin(path: Path):
    """Extract {array_name: [(height, hash)]} from libdogecoin's chainparams.c.

    Brace-matched rather than regexed to the closing '};' so a nested initializer
    can't truncate the array early."""
    src = path.read_text(errors="replace")
    arrays = {}
    for m in ARRAY_RE.finditer(src):
        name = m.group(1)
        start = m.end()          # just past the opening {
        depth = 1
        i = start
        while i < len(src) and depth > 0:
            if src[i] == "{":
                depth += 1
            elif src[i] == "}":
                depth -= 1
            i += 1
        body = src[start:i - 1]
        entries = [(int(h), norm(hs)) for h, hs in LIBDOGE_ENTRY_RE.findall(body)]
        entries.sort()
        arrays[name] = entries
    return arrays


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("spec", type=Path)
    ap.add_argument("--libdogecoin", type=Path, required=True,
                    help="path to libdogecoin src/chainparams.c")
    args = ap.parse_args()

    spec = json.loads(args.spec.read_text())
    prov = spec.get("_provenance", {})
    libd = parse_libdogecoin(args.libdogecoin)

    print("=" * 72)
    print("CHECKPOINT DIFF — libdogecoin vs Dogecoin Core")
    print(f"  core:        {prov.get('core_commit','?')[:12]} "
          f"({prov.get('core_client_version','?')})")
    print(f"  libdogecoin: {args.libdogecoin}")
    print("=" * 72)

    if not libd:
        print("\n!! no dogecoin_*_checkpoint_array[] found — wrong file, or the")
        print("   array naming changed. Not reporting 'no drift' on no data.")
        return 2

    total_bad = 0
    for arr_name, entries in sorted(libd.items()):
        cls = ARRAY_TO_CLASS.get(arr_name)
        net = spec["networks"].get(cls) if cls else None
        print(f"\n--- {arr_name} ({len(entries)} in libdogecoin) ---")
        if net is None:
            print(f"    ?  no matching network in spec (expected {cls}); skipped")
            continue

        core = {c["height"]: norm(c["hash"]) for c in net.get("checkpoints", [])}
        mine = dict(entries)

        mismatched = [(h, core[h], mine[h]) for h in sorted(set(core) & set(mine))
                      if core[h] != mine[h]]
        missing = sorted(set(core) - set(mine))     # Core has, libdogecoin lacks
        extra = sorted(set(mine) - set(core))       # libdogecoin has, Core lacks

        if mismatched:
            print(f"    !! {len(mismatched)} HASH MISMATCH — same height, different hash:")
            for h, c, m in mismatched:
                print(f"       h={h}")
                print(f"         core:        {c}")
                print(f"         libdogecoin: {m}   <-- WRONG")
            total_bad += len(mismatched)

        if missing:
            print(f"    ?  {len(missing)} checkpoint(s) in Core but NOT libdogecoin:")
            for h in missing:
                print(f"       h={h:<9} {core[h]}")

        if extra:
            # "Core pruned these" and "these were never upstream" are not the
            # same claim, and which one applies is decidable: compare against
            # Core's highest checkpoint. Below it, a gap is plausibly a prune.
            # ABOVE it, Core never had a checkpoint at that height at all, so
            # pruning is impossible -- libdogecoin is asserting a consensus
            # fact Core has not asserted. Reporting both under one hedge makes
            # the interesting case invisible.
            core_max = max(core) if core else -1
            beyond = [h for h in extra if h > core_max]
            within = [h for h in extra if h <= core_max]

            if within:
                print(f"    ?  {len(within)} checkpoint(s) in libdogecoin but "
                      f"NOT Core, below Core's highest ({core_max}):")
                for h in within:
                    print(f"       h={h:<9} {mine[h]}")
                print("       (plausibly pruned upstream, or never upstream.)")

            if beyond:
                print(f"    !! {len(beyond)} checkpoint(s) in libdogecoin BEYOND "
                      f"Core's highest checkpoint ({core_max}):")
                for h in beyond:
                    print(f"       h={h:<9} {mine[h]}")
                print("       Core has NO checkpoint at these heights, so these")
                print("       cannot be prunes. libdogecoin is asserting checkpoints")
                print("       Core does not assert. Not necessarily wrong -- but it")
                print("       is a consensus claim with no upstream source, which is")
                print("       the thing this repo exists to make visible.")

        if not (mismatched or missing or extra):
            print(f"    ok  identical: {len(core)} checkpoints match exactly")

    print()
    print("=" * 72)
    if total_bad:
        print(f"FAILED: {total_bad} hash mismatch(es) — libdogecoin disagrees with Core")
        print("        A wrong checkpoint hash means accepting a chain Core rejects.")
        return 1
    print("OK: no hash mismatches. (Coverage gaps above are informational —")
    print("    a missing checkpoint is weaker protection, not a wrong answer.)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
