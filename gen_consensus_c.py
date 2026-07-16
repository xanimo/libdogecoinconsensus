#!/usr/bin/env python3
"""
gen_consensus_c.py — emit libdogecoinconsensus C sources from spec.json.

Generates:
    dogecoin_consensus.h   public API + types
    dogecoin_consensus.c   static epoch tables + binary-search lookup
    test_consensus.c       boundary tests (the §2d trace, mechanically derived)

Design (see DIRECTIVE.md §2d):
  * Core resolves consensus-by-height with a BST walk. We do NOT port that.
    The tree expresses one rule: argmax{ nHeightEffective : nHeightEffective <= height }.
    verify_selection.py proves the equivalence at every boundary.
  * Epochs become a static const array sorted by nHeightEffective.
    Lookup is binary search. No pointers, no allocation, MCU-safe.
  * All values come from Core via the spec. Nothing here is hand-typed.

Usage:
    ./gen_consensus_c.py spec.json -o outdir/
"""

import argparse
import json
import sys
from pathlib import Path

# Fields emitted into the epoch struct. Order matters: it defines struct layout.
# Only fields that are pure data and present in Core's Consensus::Params.
INT_FIELDS = [
    ("nHeightEffective", "uint32_t"),
    ("nSubsidyHalvingInterval", "uint32_t"),
    ("nCoinbaseMaturity", "uint32_t"),
    ("nPowTargetTimespan", "uint32_t"),
    ("nPowTargetSpacing", "uint32_t"),
    ("nAuxpowChainId", "uint32_t"),
    ("nMajorityEnforceBlockUpgrade", "uint32_t"),
    ("nMajorityRejectBlockOutdated", "uint32_t"),
    ("nMajorityWindow", "uint32_t"),
    ("nRuleChangeActivationThreshold", "uint32_t"),
    ("nMinerConfirmationWindow", "uint32_t"),
    ("BIP34Height", "uint32_t"),
    ("BIP65Height", "uint32_t"),
    ("BIP66Height", "uint32_t"),
]
BOOL_FIELDS = [
    "fDigishieldDifficultyCalculation",
    "fSimplifiedRewards",
    "fPowAllowMinDifficultyBlocks",
    "fPowAllowDigishieldMinDifficultyBlocks",
    "fPowNoRetargeting",
    "fAllowLegacyBlocks",
    "fStrictChainId",
]

# uint256 fields. Empty for now: see EXCLUDED_FIELDS.
HASH_FIELDS = []

# Fields present in the spec that are deliberately NOT emitted, each with the
# reason. This is a declaration, not a dumping ground: an entry here is a claim
# that omitting the field is correct, reviewable in diff. Anything in the spec
# and absent from every list above is a hard error (see check_field_coverage).
EXCLUDED_FIELDS = {
    # Core computes this at runtime -- `consensus.hashGenesisBlock =
    # genesis.GetHash()` -- so chainparams.cpp holds no literal to extract.
    # The value only appears in the adjacent assert(). Emitting it would mean
    # either lifting that assert (a different extractor: assertions are not
    # assignments) or hashing the genesis block ourselves (that is validation
    # logic, not a definition -- we extract definitions, not logic).
    # Excluded until an extractor exists that can source it honestly.
    "hashGenesisBlock":
        "computed by Core at runtime (genesis.GetHash()); no literal in "
        "chainparams.cpp -- value lives only in the adjacent assert()",

    # These four are uint256 and consensus-critical -- powLimit in particular
    # is the difficulty clamp, and it varies by epoch. They are excluded here
    # only because this commit adds the gate, and the gate's whole point is
    # that a field is never dropped without a stated reason. Recording the
    # debt honestly is the prerequisite for paying it; the next commit emits
    # them and deletes these four entries.
    "powLimit": "uint256; not yet representable in the epoch struct",
    "nMinimumChainWork": "uint256; not yet representable in the epoch struct",
    "BIP34Hash": "uint256; not yet representable in the epoch struct",
    "defaultAssumeValid": "uint256; not yet representable in the epoch struct",
}


def check_field_coverage(spec):
    """Refuse to generate if the spec carries a consensus field we don't emit.

    Rule 1 -- never silently drop an assignment -- is what caught the fork
    tree. The extractor enforces it via `_unparsed`. This enforces it one
    layer down, where it was previously unenforced: the emit lists above are
    hand-maintained, so a field Core adds tomorrow lands in the spec, matches
    nothing here, and vanishes from the library with no diagnostic. That is
    the same failure class as the original flattening -- a plausible,
    confidently wrong artifact -- arriving through a different door.

    A spec field must be accounted for exactly once: emitted (INT/BOOL/HASH)
    or excluded with a stated reason. Anything else is a hard error.

    Rule 7: loud over clever. A crash beats a wrong table.
    """
    emitted = {f for f, _ in INT_FIELDS} | set(BOOL_FIELDS) | set(HASH_FIELDS)
    known = emitted | set(EXCLUDED_FIELDS)

    # Where each unknown field came from, so the error names a real location.
    seen = {}
    for cls, net in spec["networks"].items():
        for node_name, node in net.get("consensus_nodes", {}).items():
            for f in node.get("fields", {}):
                seen.setdefault(f, []).append(f"{cls}::{node_name}")

    unknown = sorted(set(seen) - known)
    if unknown:
        lines = [
            "error: spec contains consensus field(s) this generator does not "
            "account for.",
            "",
            "Emitting anyway would drop them silently from the library -- the "
            "exact failure",
            "class this project exists to eliminate (README rule 1).",
            "",
        ]
        for f in unknown:
            where = ", ".join(sorted(set(seen[f]))[:3])
            more = "" if len(set(seen[f])) <= 3 else f" (+{len(set(seen[f])) - 3} more)"
            lines.append(f"  {f}")
            lines.append(f"      seen in: {where}{more}")
        lines += [
            "",
            "Fix by choosing one, in gen_consensus_c.py:",
            "  * emit it   -- add to INT_FIELDS, BOOL_FIELDS, or HASH_FIELDS",
            "  * exclude it -- add to EXCLUDED_FIELDS with the reason why "
            "omitting it is correct",
            "",
            "Do not hand-edit generated output (rule 4). Fix the generator.",
        ]
        raise SystemExit("\n".join(lines))

    # The reverse direction: an emit list naming a field the spec never had is
    # also a defect -- it means a hand-typed name is wrong (a typo emits a
    # field that is always absent, and a defaulted zero is a wrong constant),
    # or Core removed a field and the list still claims it.
    stale = sorted(known - set(seen))
    if stale:
        raise SystemExit(
            "error: generator lists field(s) absent from the entire spec:\n"
            + "".join(f"  {f}\n" for f in stale)
            + "\nEither the name is misspelled (it would emit as a default -- "
              "a wrong constant),\nor Core dropped the field and the list is "
              "stale. Core is truth (rule 5).")


CHAINS = {
    "CMainParams": ("MAINNET", "main"),
    "CTestNetParams": ("TESTNET", "test"),
    "CRegTestParams": ("REGTEST", "regtest"),
}


def deployment_names(spec):
    """Deployment short names, in a stable order, validated across chains.

    Core indexes vDeployments by enum, so every chain must agree on the set --
    a chain missing one, or an extra one somewhere, means the enum changed and
    the generated indices would be wrong. Raise rather than emit a table whose
    indices silently disagree with Core's."""
    per_chain = {}
    for cls, net in spec["networks"].items():
        names = {d.split("::")[-1].replace("DEPLOYMENT_", "")
                 for d in net.get("deployments", {})}
        per_chain[cls] = names
    if not per_chain:
        return []
    sets = list(per_chain.values())
    if any(s != sets[0] for s in sets):
        detail = "; ".join(f"{c}: {sorted(n)}" for c, n in per_chain.items())
        raise SystemExit(
            "error: chains disagree on the deployment set — "
            "generated enum indices would not match Core.\n       " + detail)
    # order by bit where available, else alphabetical: stable and meaningful
    first = next(iter(spec["networks"].values())).get("deployments", {})
    order = []
    for d, fields in first.items():
        short = d.split("::")[-1].replace("DEPLOYMENT_", "")
        bit = fields.get("bit", {}).get("value")
        order.append((bit if isinstance(bit, int) else 999, short))
    order.sort()
    return [s for _, s in order]


def cname(node_name):
    """digishieldConsensus -> DIGISHIELD"""
    n = node_name.replace("Consensus", "")
    return (n or "base").upper()


def banner(spec, what):
    prov = spec.get("_provenance", {})
    return f"""/* {what}
 *
 * GENERATED — DO NOT EDIT. Regenerate with gen_consensus_c.py.
 *
 * Source of truth: Dogecoin Core.
 *   commit:         {prov.get('core_commit', '?')}
 *   client version: {prov.get('core_client_version', '?')}
 *   nearest tag:    {prov.get('core_describe', '?')}
 *   chainparams.cpp sha256:
 *     {prov.get('file_sha256', '?')}
 *
 * If this file and Core disagree, this file is wrong. Regenerate.
 */
"""


def gen_header(spec):
    out = [banner(spec, "dogecoin_consensus.h — height-indexed consensus parameters"), ""]
    out.append("#ifndef DOGECOIN_CONSENSUS_H")
    out.append("#define DOGECOIN_CONSENSUS_H")
    out.append("")
    out.append("#include <stdbool.h>")
    out.append("#include <stddef.h>")
    out.append("#include <stdint.h>")
    out.append("")
    out.append("#ifdef __cplusplus")
    out.append('extern "C" {')
    out.append("#endif")
    out.append("")
    out.append("typedef enum {")
    for cls, (up, _) in CHAINS.items():
        if cls in spec["networks"]:
            out.append(f"    DOGECOIN_CHAIN_{up},")
    out.append("    DOGECOIN_CHAIN__COUNT")
    out.append("} dogecoin_chain_t;")
    out.append("")
    out.append("/* One consensus epoch. Fields are fully resolved: values inherited")
    out.append(" * through Core's derivation chain are already folded in, so an epoch")
    out.append(" * is self-contained and needs no parent lookup. */")
    out.append("typedef struct {")
    out.append("    const char *name;   /* Core's variable name, for diagnostics */")
    for f, t in INT_FIELDS:
        out.append(f"    {t:<10} {f};")
    for f in BOOL_FIELDS:
        out.append(f"    {'bool':<10} {f};")
    out.append("} dogecoin_consensus_params;")
    out.append("")

    # ---- deployments ----
    deps = deployment_names(spec)
    if deps:
        out.append("/* BIP9 versionbits deployments. */")
        out.append("typedef enum {")
        for d in deps:
            out.append(f"    DOGECOIN_DEPLOYMENT_{d},")
        out.append("    DOGECOIN_DEPLOYMENT__COUNT")
        out.append("} dogecoin_deployment_t;")
        out.append("")
        out.append("/* Core's 'never times out' sentinel for nTimeout. */")
        out.append("#define DOGECOIN_DEPLOYMENT_NO_TIMEOUT 0")
        out.append("")
        out.append("typedef struct {")
        out.append("    const char *name;")
        out.append("    int         bit;        /* versionbits bit */")
        out.append("    /* int64_t, not uint32_t: regtest uses 999999999999, which")
        out.append("     * truncates to a 2083 timestamp in 32 bits — turning")
        out.append("     * 'never times out' into 'times out'. */")
        out.append("    int64_t     nStartTime;")
        out.append("    int64_t     nTimeout;   /* 0 == DOGECOIN_DEPLOYMENT_NO_TIMEOUT */")
        out.append("} dogecoin_deployment;")
        out.append("")
    out.append("/* Returns the consensus epoch in force AT `height`, inclusive.")
    out.append(" *")
    out.append(" * `height` is the block's OWN height. In Core's miner this is")
    out.append(" * pindexPrev->nHeight + 1 — the block being built. The epoch switches")
    out.append(" * ON the block at nHeightEffective, not the block after it.")
    out.append(" *")
    out.append(" * Rule: argmax{ nHeightEffective : nHeightEffective <= height }.")
    out.append(" * Equivalent to Core's BST walk (chainparams.cpp GetConsensus) at every")
    out.append(" * boundary; see verify_selection.py.")
    out.append(" *")
    out.append(" * Never returns NULL for a valid chain: every chain has an epoch at")
    out.append(" * height 0. Returns NULL only if `chain` is out of range. */")
    out.append("const dogecoin_consensus_params *dogecoin_consensus_at_height(")
    out.append("    dogecoin_chain_t chain, uint32_t height);")
    out.append("")
    out.append("/* Epoch table access, for callers that want to enumerate. */")
    out.append("const dogecoin_consensus_params *dogecoin_consensus_epochs(")
    out.append("    dogecoin_chain_t chain, size_t *count);")
    out.append("")
    if deps:
        out.append("/* Deployment parameters for `chain`. NULL if either arg is out of range. */")
        out.append("const dogecoin_deployment *dogecoin_deployment_get(")
        out.append("    dogecoin_chain_t chain, dogecoin_deployment_t dep);")
        out.append("")
        out.append("/* All deployments for `chain`, indexed by dogecoin_deployment_t. */")
        out.append("const dogecoin_deployment *dogecoin_deployments(")
        out.append("    dogecoin_chain_t chain, size_t *count);")
        out.append("")
    out.append("#ifdef __cplusplus")
    out.append("}")
    out.append("#endif")
    out.append("")
    out.append("#endif /* DOGECOIN_CONSENSUS_H */")
    return "\n".join(out) + "\n"


def gen_impl(spec):
    out = [banner(spec, "dogecoin_consensus.c — generated epoch tables + lookup"), ""]
    out.append('#include "dogecoin_consensus.h"')
    out.append("#include <stddef.h>")
    out.append("")

    tables = []
    for cls, (up, _) in CHAINS.items():
        net = spec["networks"].get(cls)
        if not net:
            continue
        sched = net["activation_schedule"]
        out.append(f"/* ---- {cls}: {len(sched)} epoch(s) ---- */")
        out.append(f"static const dogecoin_consensus_params k_{up.lower()}_epochs[] = {{")
        for st in sched:
            eff = st["effective_fields"]
            out.append("    {")
            out.append(f'        .name = "{st["node"]}",')
            for f, _t in INT_FIELDS:
                v = eff.get(f)
                if isinstance(v, bool) or not isinstance(v, int):
                    continue
                out.append(f"        .{f} = {v}u,")
            for f in BOOL_FIELDS:
                v = eff.get(f)
                if isinstance(v, bool):
                    out.append(f"        .{f} = {'true' if v else 'false'},")
            out.append("    },")
        out.append("};")
        out.append("")
        tables.append((up, f"k_{up.lower()}_epochs"))

    # dispatch table
    out.append("static const struct {")
    out.append("    const dogecoin_consensus_params *epochs;")
    out.append("    size_t count;")
    out.append("} k_chains[DOGECOIN_CHAIN__COUNT] = {")
    for up, tbl in tables:
        out.append(f"    [DOGECOIN_CHAIN_{up}] = {{ {tbl}, sizeof({tbl}) / sizeof({tbl}[0]) }},")
    out.append("};")
    out.append("")

    # ---- deployment tables ----
    deps = deployment_names(spec)
    if deps:
        for cls, (up, _) in CHAINS.items():
            net = spec["networks"].get(cls)
            if not net:
                continue
            by_short = {d.split("::")[-1].replace("DEPLOYMENT_", ""): f
                        for d, f in net.get("deployments", {}).items()}
            out.append(f"/* ---- {cls}: deployments ---- */")
            out.append(f"static const dogecoin_deployment k_{up.lower()}_deployments"
                       f"[DOGECOIN_DEPLOYMENT__COUNT] = {{")
            for d in deps:
                f = by_short.get(d, {})
                bit = f.get("bit", {}).get("value")
                start = f.get("nStartTime", {}).get("value")
                timeout = f.get("nTimeout", {}).get("value")
                out.append(f"    [DOGECOIN_DEPLOYMENT_{d}] = {{")
                out.append(f'        .name = "{d}",')
                if isinstance(bit, int):
                    out.append(f"        .bit = {bit},")
                if isinstance(start, int):
                    out.append(f"        .nStartTime = INT64_C({start}),")
                if isinstance(timeout, int):
                    note = "  /* never times out */" if timeout == 0 else ""
                    out.append(f"        .nTimeout = INT64_C({timeout}),{note}")
                out.append("    },")
            out.append("};")
            out.append("")

        out.append("static const dogecoin_deployment *const k_deployments"
                   "[DOGECOIN_CHAIN__COUNT] = {")
        for cls, (up, _) in CHAINS.items():
            if cls in spec["networks"]:
                out.append(f"    [DOGECOIN_CHAIN_{up}] = k_{up.lower()}_deployments,")
        out.append("};")
        out.append("")

        out.append("const dogecoin_deployment *dogecoin_deployments(")
        out.append("    dogecoin_chain_t chain, size_t *count)")
        out.append("{")
        out.append("    if ((unsigned)chain >= DOGECOIN_CHAIN__COUNT) {")
        out.append("        if (count) *count = 0;")
        out.append("        return NULL;")
        out.append("    }")
        out.append("    if (count) *count = DOGECOIN_DEPLOYMENT__COUNT;")
        out.append("    return k_deployments[chain];")
        out.append("}")
        out.append("")
        out.append("const dogecoin_deployment *dogecoin_deployment_get(")
        out.append("    dogecoin_chain_t chain, dogecoin_deployment_t dep)")
        out.append("{")
        out.append("    if ((unsigned)chain >= DOGECOIN_CHAIN__COUNT) return NULL;")
        out.append("    if ((unsigned)dep >= DOGECOIN_DEPLOYMENT__COUNT) return NULL;")
        out.append("    return &k_deployments[chain][dep];")
        out.append("}")
        out.append("")

    out.append("const dogecoin_consensus_params *dogecoin_consensus_epochs(")
    out.append("    dogecoin_chain_t chain, size_t *count)")
    out.append("{")
    out.append("    if ((unsigned)chain >= DOGECOIN_CHAIN__COUNT) {")
    out.append("        if (count) *count = 0;")
    out.append("        return NULL;")
    out.append("    }")
    out.append("    if (count) *count = k_chains[chain].count;")
    out.append("    return k_chains[chain].epochs;")
    out.append("}")
    out.append("")

    out.append("const dogecoin_consensus_params *dogecoin_consensus_at_height(")
    out.append("    dogecoin_chain_t chain, uint32_t height)")
    out.append("{")
    out.append("    if ((unsigned)chain >= DOGECOIN_CHAIN__COUNT) return NULL;")
    out.append("")
    out.append("    const dogecoin_consensus_params *e = k_chains[chain].epochs;")
    out.append("    size_t n = k_chains[chain].count;")
    out.append("    if (n == 0) return NULL;")
    out.append("")
    out.append("    /* argmax{ nHeightEffective : nHeightEffective <= height }")
    out.append("     * Table is sorted ascending by nHeightEffective and epoch 0 is")
    out.append("     * always height 0, so a match always exists.")
    out.append("     * Invariant: lo is always a valid answer; we search for a better one. */")
    out.append("    size_t lo = 0, hi = n;")
    out.append("    while (hi - lo > 1) {")
    out.append("        size_t mid = lo + (hi - lo) / 2;   /* no overflow */")
    out.append("        if (e[mid].nHeightEffective <= height) {")
    out.append("            lo = mid;                       /* mid is valid, maybe better exists */")
    out.append("        } else {")
    out.append("            hi = mid;                       /* mid is too high */")
    out.append("        }")
    out.append("    }")
    out.append("    return &e[lo];")
    out.append("}")
    return "\n".join(out) + "\n"


def gen_tests(spec):
    """Boundary tests derived mechanically from the schedule: for each epoch,
    h-1 must be the previous epoch and h must be this one (inclusive rule)."""
    out = [banner(spec, "test_consensus.c — generated boundary tests"), ""]
    out.append('#include "dogecoin_consensus.h"')
    out.append("#include <stdio.h>")
    out.append("#include <string.h>")
    out.append("")
    out.append("static int failures = 0;")
    out.append("")
    out.append("static void check(dogecoin_chain_t chain, const char *chain_name,")
    out.append("                  uint32_t height, const char *want)")
    out.append("{")
    out.append("    const dogecoin_consensus_params *p =")
    out.append("        dogecoin_consensus_at_height(chain, height);")
    out.append("    if (!p) {")
    out.append('        printf("  FAIL %-8s h=%-9u want=%-24s got=NULL\\n",')
    out.append("               chain_name, height, want);")
    out.append("        failures++;")
    out.append("        return;")
    out.append("    }")
    out.append("    int ok = strcmp(p->name, want) == 0;")
    out.append('    printf("  %s %-8s h=%-9u want=%-24s got=%s\\n",')
    out.append('           ok ? "ok  " : "FAIL", chain_name, height, want, p->name);')
    out.append("    if (!ok) failures++;")
    out.append("}")
    out.append("")
    if deployment_names(spec):
        out.append("static void check_dep(dogecoin_chain_t chain, const char *chain_name,")
        out.append("                      dogecoin_deployment_t dep, const char *want_name,")
        out.append("                      int want_bit, int64_t want_start, int64_t want_timeout)")
        out.append("{")
        out.append("    const dogecoin_deployment *d = dogecoin_deployment_get(chain, dep);")
        out.append("    if (!d) {")
        out.append('        printf("  FAIL %-8s %-12s -> NULL\\n", chain_name, want_name);')
        out.append("        failures++;")
        out.append("        return;")
        out.append("    }")
        out.append("    int ok = strcmp(d->name, want_name) == 0 &&")
        out.append("             d->bit == want_bit &&")
        out.append("             d->nStartTime == want_start &&")
        out.append("             d->nTimeout == want_timeout;")
        out.append('    printf("  %s %-8s %-12s bit=%-2d start=%-12lld timeout=%lld%s\\n",')
        out.append('           ok ? "ok  " : "FAIL", chain_name, d->name, d->bit,')
        out.append("           (long long)d->nStartTime, (long long)d->nTimeout,")
        out.append('           d->nTimeout == DOGECOIN_DEPLOYMENT_NO_TIMEOUT ? "  (never)" : "");')
        out.append("    if (!ok) {")
        out.append('        printf("       want: bit=%d start=%lld timeout=%lld\\n",')
        out.append("               want_bit, (long long)want_start, (long long)want_timeout);")
        out.append("        failures++;")
        out.append("    }")
        out.append("}")
        out.append("")
    out.append("int main(void)")
    out.append("{")
    out.append('    printf("consensus boundary tests (generated from Core)\\n");')

    for cls, (up, _) in CHAINS.items():
        net = spec["networks"].get(cls)
        if not net:
            continue
        sched = net["activation_schedule"]
        out.append("")
        out.append(f'    printf("\\n{cls}\\n");')

        # collect (height, expected_node, comment) then dedupe by height
        cases = {}

        def add(h, node, why):
            if h not in cases:
                cases[h] = (node, why)

        for i, st in enumerate(sched):
            h = st["nHeightEffective"]
            node = st["node"]
            add(h, node, "inclusive: epoch starts HERE")
            if i > 0:
                add(h - 1, sched[i - 1]["node"], "last block of prev epoch")
            if i + 1 < len(sched):
                nxt = sched[i + 1]["nHeightEffective"]
                if nxt - 1 > h:
                    add(nxt - 1, node, "pCandidate guard case")
        add(0, sched[0]["node"], "genesis")
        add(10_000_000, sched[-1]["node"], "far future stays on last epoch")

        for h in sorted(cases):
            node, why = cases[h]
            out.append(f'    check(DOGECOIN_CHAIN_{up}, "{up.lower()}", '
                       f'{h}u, "{node}");   /* {why} */')

    deps = deployment_names(spec)
    if deps:
        out.append("")
        out.append('    printf("\\ndeployments\\n");')
        for cls, (up, _) in CHAINS.items():
            net = spec["networks"].get(cls)
            if not net:
                continue
            by_short = {d.split("::")[-1].replace("DEPLOYMENT_", ""): f
                        for d, f in net.get("deployments", {}).items()}
            for d in deps:
                f = by_short.get(d, {})
                bit = f.get("bit", {}).get("value")
                start = f.get("nStartTime", {}).get("value")
                timeout = f.get("nTimeout", {}).get("value")
                if not all(isinstance(x, int) for x in (bit, start, timeout)):
                    continue
                out.append(f'    check_dep(DOGECOIN_CHAIN_{up}, "{up.lower()}", '
                           f'DOGECOIN_DEPLOYMENT_{d}, "{d}",')
                out.append(f"              {bit}, INT64_C({start}), INT64_C({timeout}));")

    out.append("")
    out.append('    printf("\\n%s: %d failure(s)\\n", failures ? "FAILED" : "OK", failures);')
    out.append("    return failures ? 1 : 0;")
    out.append("}")
    return "\n".join(out) + "\n"



def gen_exhaustive(spec):
    """Exhaustive check: binary search vs a linear-scan reference over the whole
    interesting height range. Boundary tests catch what you thought to test;
    this catches what you didn't. Binary search is where off-by-ones hide."""
    max_h = 0
    for net in spec["networks"].values():
        for st in net["activation_schedule"]:
            max_h = max(max_h, st["nHeightEffective"])
    sweep = max_h + 100000

    out = [banner(spec, "test_consensus_exhaustive.c — generated"), ""]
    out.append('#include "dogecoin_consensus.h"')
    out.append("#include <stdio.h>")
    out.append("")
    out.append("/* Reference implementation: linear scan, obviously correct. */")
    out.append("static const dogecoin_consensus_params *linear(")
    out.append("    dogecoin_chain_t c, uint32_t h)")
    out.append("{")
    out.append("    size_t n;")
    out.append("    const dogecoin_consensus_params *e = dogecoin_consensus_epochs(c, &n);")
    out.append("    const dogecoin_consensus_params *best = NULL;")
    out.append("    for (size_t i = 0; i < n; i++)")
    out.append("        if (e[i].nHeightEffective <= h) best = &e[i];")
    out.append("    return best;")
    out.append("}")
    out.append("")
    out.append("int main(void)")
    out.append("{")
    out.append("    long mismatches = 0, tested = 0;")
    out.append(f"    const uint32_t sweep = {sweep}u;")
    out.append("    for (int c = 0; c < DOGECOIN_CHAIN__COUNT; c++) {")
    out.append("        for (uint32_t h = 0; h <= sweep; h++) {")
    out.append("            const dogecoin_consensus_params *a =")
    out.append("                dogecoin_consensus_at_height((dogecoin_chain_t)c, h);")
    out.append("            const dogecoin_consensus_params *b = linear((dogecoin_chain_t)c, h);")
    out.append("            tested++;")
    out.append("            if (a != b) {")
    out.append("                if (mismatches < 5)")
    out.append('                    printf("  MISMATCH chain=%d h=%u bsearch=%s linear=%s\\n",')
    out.append('                           c, h, a ? a->name : "NULL", b ? b->name : "NULL");')
    out.append("                mismatches++;")
    out.append("            }")
    out.append("        }")
    out.append("        /* extremes, incl. UINT32_MAX */")
    out.append("        const uint32_t ext[] = {0u, 1u, 0x7fffffffu, 0xfffffffeu, 0xffffffffu};")
    out.append("        for (unsigned i = 0; i < sizeof(ext)/sizeof(ext[0]); i++) {")
    out.append("            if (dogecoin_consensus_at_height((dogecoin_chain_t)c, ext[i])")
    out.append("                != linear((dogecoin_chain_t)c, ext[i])) {")
    out.append('                printf("  MISMATCH extreme chain=%d h=%u\\n", c, ext[i]);')
    out.append("                mismatches++;")
    out.append("            }")
    out.append("            tested++;")
    out.append("        }")
    out.append("    }")
    out.append('    printf("bsearch vs linear: %ld heights, %ld mismatches\\n", tested, mismatches);')
    out.append("")
    out.append("    /* out-of-range chain must return NULL, not crash */")
    out.append("    if (dogecoin_consensus_at_height((dogecoin_chain_t)99, 100) != NULL) {")
    out.append('        printf("  FAIL: invalid chain did not return NULL\\n"); mismatches++;')
    out.append("    }")
    out.append("    if (dogecoin_consensus_at_height(DOGECOIN_CHAIN__COUNT, 100) != NULL) {")
    out.append('        printf("  FAIL: COUNT sentinel did not return NULL\\n"); mismatches++;')
    out.append("    }")
    out.append('    printf("%s\\n", mismatches ? "FAILED" : "OK: bsearch == linear everywhere");')
    out.append("    return mismatches ? 1 : 0;")
    out.append("}")
    return "\n".join(out) + "\n"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("spec", type=Path)
    ap.add_argument("-o", "--outdir", type=Path, default=Path("."))
    ap.add_argument(
        "--check-fields-only", action="store_true",
        help="run the field-coverage check and exit; emit nothing. For drift "
             "detection against a Core the generator has never seen: answers "
             "'would this spec lose a field on the way into C?' without "
             "needing an outdir or a compiler.")
    args = ap.parse_args()

    spec = json.loads(args.spec.read_text())

    # Guard: a pre-v2 spec has no activation_schedule — it flattened the fork
    # tree. Generating from it would silently produce a single-epoch table that
    # forks off the network at the first transition. Refuse loudly.
    bad = [c for c, n in spec.get("networks", {}).items()
           if "activation_schedule" not in n]
    if bad or not spec.get("networks"):
        print("error: spec has no activation_schedule for: "
              + (", ".join(bad) or "(no networks at all)"), file=sys.stderr)
        print("       This looks like a pre-v2 spec that FLATTENED the consensus",
              file=sys.stderr)
        print("       fork tree. Generating from it would emit a single-epoch table",
              file=sys.stderr)
        print("       that diverges from Core at the first height transition.",
              file=sys.stderr)
        print("       Re-extract with the current extract_chainparams.py.",
              file=sys.stderr)
        return 2

    # Guard: refuse to generate if the spec has a consensus field we neither
    # emit nor explicitly exclude. Runs before anything is written.
    check_field_coverage(spec)

    if args.check_fields_only:
        # Reached only if coverage passed: check_field_coverage raises otherwise.
        n = len({f for _, net in spec["networks"].items()
                 for node in net.get("consensus_nodes", {}).values()
                 for f in node.get("fields", {})})
        print(f"OK: all {n} consensus field(s) in the spec are accounted for "
              f"(emitted or explicitly excluded).", file=sys.stderr)
        return 0

    # Guard: every chain must have an epoch at height 0, or the lookup's
    # "a match always exists" invariant breaks.
    for cls, net in spec["networks"].items():
        sched = net["activation_schedule"]
        if not sched:
            print(f"error: {cls} has an empty activation_schedule", file=sys.stderr)
            return 2
        if sched[0]["nHeightEffective"] != 0:
            print(f"error: {cls} has no epoch at height 0 "
                  f"(lowest is {sched[0]['nHeightEffective']}). The lookup assumes "
                  f"one exists.", file=sys.stderr)
            return 2

    args.outdir.mkdir(parents=True, exist_ok=True)

    files = {
        "dogecoin_consensus.h": gen_header(spec),
        "dogecoin_consensus.c": gen_impl(spec),
        "test_consensus.c": gen_tests(spec),
        "test_consensus_exhaustive.c": gen_exhaustive(spec),
    }
    for name, text in files.items():
        (args.outdir / name).write_text(text)
        print(f"wrote {args.outdir / name}", file=sys.stderr)

    prov = spec.get("_provenance", {})
    print(f"  from core {prov.get('core_commit','?')[:12]} "
          f"({prov.get('core_client_version','?')})", file=sys.stderr)
    for cls, net in spec["networks"].items():
        print(f"  {cls}: {len(net['activation_schedule'])} epochs", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
