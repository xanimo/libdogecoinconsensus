# libdogecoinconsensus

A Core-derived consensus definition for Dogecoin.

Dogecoin Core is the source of truth. This repo parses Core's `chainparams.cpp`
into a machine-readable spec, and generates a portable C library from it.
Nothing here is hand-transcribed.

**Status:** research prototype. Validated against Core `699f62ccba` (1.14.99.0).

---

## Why

`libdogecoin` was derived from `libbtc` and adapted. Its consensus knowledge is
a hand-transcription, not a derivation — which produces a recurring bug *class*
(two implementations of one spec, drifting) rather than isolated bugs.

You can't audit your way out of that class. You eliminate it by deriving one
side from the other.

## What this is *not*

- **Not a replacement for libdogecoin.** They answer different questions.
  libdogecoin talks to the network (wallet, keys, tx construction) and its flat
  params are correct for that job. This library *agrees with* the network —
  consensus rules by height. See `DIRECTIVE.md` §2c.
- **Not an extraction of Core's validation engine.** That's libbitcoinkernel's
  problem and it has consumed multiple engineer-years upstream. Linking C++
  internals would destroy portability, which is the whole point of a C library.
  **We extract definitions, not logic.**

## The central finding

Core's consensus is not a struct — it's a **height-indexed binary tree** of
regimes (`consensus` → `digishield` → `auxpow`, plus `minDifficulty` on
testnet), selected at runtime by block height. Flattening it produces a client
that hard-forks itself off the network at block 145,000.

The first version of the extractor did exactly that. See `DIRECTIVE.md` §2a.

The tree reduces to one rule:

> `argmax{ nHeightEffective : nHeightEffective <= height }`

`verify_selection.py` proves the reduction is equivalent to Core's BST walk at
every boundary, so the generated C binary-searches a sorted array instead of
porting the tree. No pointers, no allocation, MCU-safe.

---

## Pipeline

```
Dogecoin Core (C++)          read-only, never patched
        |
        | extract_chainparams.py      (tree-sitter)
        v
    spec.json                consensus_nodes, links, activation_schedule,
        |                    checkpoints, deployments, provenance
        |
        +-- verify_selection.py   proves argmax == Core's BST walk
        +-- gen_consensus_c.py    -> C API + epoch tables + tests
        +-- diff_checkpoints.py   -> libdogecoin checkpoints vs Core
        +-- regression_gate.py    -> fail if Core moved since the reviewed pin
```

## Usage

```bash
pip install tree_sitter tree_sitter_cpp --break-system-packages

CORE=~/source/repos/dogecoin

# 1. extract
./extract_chainparams.py $CORE/src/chainparams.cpp -o spec.json

# 2. prove the reduction still holds
./verify_selection.py spec.json

# 3. generate
./gen_consensus_c.py spec.json -o src/

# 4. test
cc -std=c99 -Wall -Wextra -Werror -O2 -o t_bound \
   src/test_consensus.c src/dogecoin_consensus.c && ./t_bound
cc -std=c99 -Wall -Wextra -Werror -O2 -o t_exh \
   src/test_consensus_exhaustive.c src/dogecoin_consensus.c && ./t_exh
```

Or: `make check CORE=$CORE`

## API

```c
#include "dogecoin_consensus.h"

/* The consensus epoch in force AT `height` — inclusive.
 * `height` is the block's OWN height (Core: pindexPrev->nHeight + 1).
 * The epoch switches ON the block at nHeightEffective, not after it. */
const dogecoin_consensus_params *p =
    dogecoin_consensus_at_height(DOGECOIN_CHAIN_MAINNET, 145000);
/* p->name == "digishieldConsensus"
   p->nPowTargetTimespan == 60
   p->nCoinbaseMaturity == 240 */
```

Epoch fields are **fully resolved** at generation time — values inherited
through Core's derivation chain are folded in, so an epoch is self-contained
and needs no parent lookup at runtime.

---

## Open decisions

### Generated vs committed

`.gitignore` currently **excludes** generated C and `spec.json`. That's a
defensible default (single source of truth, no stale artifacts) but it has a
real cost: you can't read the library on GitHub, and CI must have a Core
checkout to build anything.

The alternative — commit them, with the Core commit hash in the banner — makes
the output auditable and diffable in review, at the cost of a regeneration step
that can be forgotten.

**Not yet decided.** If you commit them, drop the first two blocks from
`.gitignore` and add a CI check that regeneration produces no diff.

### Which Core is authoritative

Upstream has `master` and `1.21-dev`, which may carry different chainparams.
The spec is only meaningful relative to a chosen branch. Currently pointed at
whatever the local checkout is; provenance records the commit.

---

## Provenance

Every run records what it extracted from:

```
core commit: 699f62ccba4e  (detached HEAD)
client version: 1.14.99.0  (in-development)
nearest tag: v1.14.7-239-g699f62ccba
chainparams.cpp sha256: 150d3733903d05f2...
```

`git describe` resolves to the nearest reachable *tag*, which on a long-running
untagged master can be far behind the software's self-reported version. The
**commit hash is the identity**; the tag is decoration; the sha256 is the truth.

A spec without provenance is a rumor.

---

## Design rules

Non-negotiable, in `DIRECTIVE.md` §5. The short version:

1. **Never silently drop an assignment.** Anything unparsed goes to `_unparsed`
   with raw text. This rule is what caught the fork tree.
2. **Never regex C++.** Use tree-sitter.
3. **Never fold without preserving the literal.** `14400` keeps `4 * 60 * 60`.
4. **Never hand-edit generated output.**
5. **Core is truth.** If the spec and Core disagree, the spec is wrong.
6. **Never flatten the height dimension.**
7. **Loud over clever.** A crash beats a wrong constant.
8. **Pin the Core commit.**

A spec that is confidently wrong is worse than no spec.

## Files

| file | purpose |
|---|---|
| `extract_chainparams.py` | `chainparams.cpp` → `spec.json` |
| `extract_opcodes.py` | `script/script.h` → `opcodes.json` |
| `gen_opcodes_c.py` | `opcodes.json` → opcode enum + name tables |
| `verify_selection.py` | proves argmax ≡ Core's BST walk |
| `gen_consensus_c.py` | `spec.json` → C API, epoch tables, tests |
| `diff_checkpoints.py` | libdogecoin checkpoints vs Core |
| `regression_gate.py` | pin/check the consensus definition vs Core drift |
| `DIRECTIVE.md` | full design doc, findings, phases |

## License

TBD — match libdogecoin (MIT) unless there's a reason not to.
