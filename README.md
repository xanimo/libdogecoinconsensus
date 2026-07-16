# libdogecoinconsensus

A Core-derived consensus definition for Dogecoin.

Dogecoin Core is the source of truth. This repo parses Core's `chainparams.cpp`,
`script.h`, and `validation.h` into machine-readable specs, and generates a
portable C library from them. Nothing here is hand-transcribed.

**Status:** research prototype. Validated against Core `699f62ccba` (1.14.99.0).

---

## Why

Consensus knowledge that is hand-transcribed from another implementation
produces a recurring bug *class* rather than isolated bugs: two implementations
of one specification, drifting. You cannot audit your way out of that class —
each individual bug is findable, but the supply is unbounded. You eliminate it
by deriving one side from the other.

## What this is *not*

- **Not a replacement for `libdogecoin`.** They answer different questions.
  `libdogecoin` talks to the network — wallet, keys, transaction construction —
  and its flat parameters are correct for that job. This library *agrees with*
  the network: consensus rules by height. See [The boundary](#the-boundary).
- **Not an extraction of Core's validation engine.** Lifting C++ internals would
  destroy portability, which is the whole point of a C library. **We extract
  definitions, not logic.** Consensus behavior lives mostly in constants,
  layouts, parameter tables, and activation schedules — all pure data, all
  portable.
- **Not a script interpreter.** Opcode *names and bytes* are data and are
  generated here. Opcode *semantics* are behavior; the right tool for those is
  differential fuzzing, not codegen.

---

## The central finding

**Core's consensus is not a struct. It's a height-indexed binary tree.**

```cpp
digishieldConsensus = consensus;                    // copy
digishieldConsensus.nHeightEffective = 145000;
digishieldConsensus.fDigishieldDifficultyCalculation = true;
digishieldConsensus.nPowTargetTimespan = 60;        // was 4*60*60
digishieldConsensus.nCoinbaseMaturity = 240;        // was 30

auxpowConsensus = digishieldConsensus;              // copy of the copy
auxpowConsensus.nHeightEffective = 371337;
auxpowConsensus.fAllowLegacyBlocks = false;

pConsensusRoot = &digishieldConsensus;              // BST root
digishieldConsensus.pLeft  = &consensus;
digishieldConsensus.pRight = &auxpowConsensus;
```

There is no single `consensus`. There is a tree of consensus regimes, linked by
`pLeft`/`pRight`, rooted at `pConsensusRoot`, selected at runtime by block
height via `nHeightEffective`.

Extracted from real Core:

| network | nodes | schedule |
|---|---|---|
| mainnet | 3 | `consensus`@0 → `digishield`@145000 → `auxpow`@371337 |
| testnet | **4** | `consensus`@0 → `digishield`@145000 → `minDifficulty`@157500 → `auxpow`@158100 |
| regtest | 3 | `consensus`@0 → `digishield`@10 → `auxpow`@20 |

Note testnet's 600-block window (157500–158100) where `minDifficultyConsensus`
sets both `fPowAllowMinDifficultyBlocks` and
`fPowAllowDigishieldMinDifficultyBlocks`, and `auxpowConsensus` then flips
`fPowAllowDigishieldMinDifficultyBlocks` back. That window has its own
difficulty semantics.

**The first version of this extractor flattened all of it.** It reported
`MAINNET.nPowTargetTimespan = 14400` — the pre-Digishield value — and silently
discarded the post-145000 regimes. A client generated from that spec would
hard-fork itself off the network at block 145,000. That artifact is kept in
[`docs/`](docs/) as evidence.

What caught it: the rule that **nothing is ever silently dropped**. The tree
wiring landed in `_unparsed` instead of vanishing. That invariant is the only
reason the bug was visible.

---

## Selection semantics: inclusive

From `chainparams.cpp` (`Consensus::Params::GetConsensus`), both comparisons in
the walk are **strict**:

```cpp
if      (nTargetHeight < this->nHeightEffective && pLeft)  return pLeft->GetConsensus(...);
else if (nTargetHeight > this->nHeightEffective && pRight) { /* candidate check */ }
return this;   // equal height falls through to HERE
```

Equality falls through to `return this`. **A node whose `nHeightEffective`
equals the target height is selected for that height** — the block *at* the
effective height runs under the new params.

Boundary trace (mainnet: root=digishield@145000, pLeft=consensus@0, pRight=auxpow@371337):

| height | resolves to | why |
|---|---|---|
| 144999 | `consensus` | `< 145000` → descend left; consensus has no right child |
| **145000** | **`digishield`** | equal → neither branch taken → `return this` |
| 371336 | `digishield` | `> 145000` → descend right, but candidate check rejects auxpow |
| 371337 | `auxpow` | equal at the auxpow node → returns auxpow |

The `pCandidate->nHeightEffective <= nTargetHeight` guard is load-bearing.
**Without it, a naive BST port is wrong for every height from 145001 to
371336** — 226,336 blocks handed to auxpow instead of digishield. Not a boundary
nit; the whole middle of the chain.

### The reduction — don't port the tree

The tree expresses one rule:

> Pick the epoch with the greatest `nHeightEffective` that is `<= height`.

`argmax{ nHeightEffective : nHeightEffective <= height }`. A sorted array +
binary search is equivalent at every boundary, has no pointers, and is MCU-safe.

**This equivalence is proven, not asserted.** `verify_selection.py` reconstructs
Core's tree from the extracted links, ports `GetConsensus` faithfully (guard
included), and checks it against the argmax rule at every epoch boundary ±1 on
all networks. The generated C is then checked exhaustively against a linear
reference — 1.4M heights, zero mismatches.

**Carry into any API:** the height is the *block's own* height (in Core's miner,
`pindexPrev->nHeight + 1`). The epoch switches **on** the block at
`nHeightEffective`, not after it.

---

## The boundary

| | `libdogecoin` | `libdogecoinconsensus` |
|---|---|---|
| **job** | talk to the network | **agree with** the network |
| **scope** | wallet, keys, tx construction | consensus rules by height |
| **params** | flat — correctly so | height-indexed schedule |
| **targets** | MCU, low-mem, no C++ toolchain | hosts doing validation |

`libdogecoin` has no consensus height dimension, and **that is correct**. It
doesn't validate — it constructs transactions and manages keys, where
`nPowTargetTimespan` never comes up. The gap is invisible because of what
`libdogecoin` is. The two libraries answer different questions.

Consumers of this library: anything that must reproduce Core's rules at a given
height — header validation, compact block filters, alternative implementations.

---

## Pipeline

```
Dogecoin Core (C++)          read-only, never patched
        |
        +-- extract_chainparams.py  -> spec.json     (tree-sitter)
        +-- extract_opcodes.py      -> opcodes.json
        +-- extract_constants.py    -> reject.json
                    |
                    +-- verify_selection.py   proves argmax == Core's BST walk
                    +-- gen_consensus_c.py    -> C API, epoch tables, tests
                    +-- gen_opcodes_c.py      -> opcode enum + name tables
                    +-- gen_constants_c.py    -> reject enum + name tables
                    +-- diff_checkpoints.py   -> libdogecoin checkpoints vs Core
                    +-- regression_gate.py    -> fail if Core moved since the pin
```

## Usage

```bash
pip install tree_sitter tree_sitter_cpp --break-system-packages

make check CORE=~/source/repos/dogecoin
```

Or step by step:

```bash
CORE=~/source/repos/dogecoin

./extract_chainparams.py $CORE/src/chainparams.cpp -o spec.json
./verify_selection.py spec.json                    # prove the reduction
./gen_consensus_c.py spec.json -o src/             # generate

cc -std=c99 -Wall -Wextra -Werror -O2 -o t_bound \
   src/test_consensus.c src/dogecoin_consensus.c && ./t_bound
```

Targets: `spec`, `opcodes`, `reject`, `verify`, `gen`, `check`, `diff`, `pin`,
`gate`, `ci`, `clean`. `make help` lists them.

## API

```c
#include "dogecoin_consensus.h"

/* The consensus epoch in force AT `height` — inclusive.
 * `height` is the block's OWN height (Core: pindexPrev->nHeight + 1). */
const dogecoin_consensus_params *p =
    dogecoin_consensus_at_height(DOGECOIN_CHAIN_MAINNET, 145000);
/* p->name == "digishieldConsensus"
   p->nPowTargetTimespan == 60
   p->nCoinbaseMaturity == 240 */

/* BIP9 deployments */
const dogecoin_deployment *d =
    dogecoin_deployment_get(DOGECOIN_CHAIN_MAINNET, DOGECOIN_DEPLOYMENT_SEGWIT);
/* d->nTimeout == DOGECOIN_DEPLOYMENT_NO_TIMEOUT */

/* Script opcodes */
const char *name = dogecoin_opcode_name(0xb1);   /* "OP_CHECKLOCKTIMEVERIFY" */
uint8_t op;
dogecoin_opcode_from_name("OP_NOP2", &op);       /* 0xb1 — aliases resolve */
```

Epoch fields are **fully resolved** at generation time — values inherited
through Core's derivation chain are folded in, so an epoch is self-contained and
needs no parent lookup at runtime.

---

## Details worth knowing

Things the generators get right that a plausible implementation gets wrong.

**Deployment timeouts are `int64_t`, not `uint32_t`.** Regtest uses
`999999999999`, which truncates to `3567587327` in 32 bits — turning "never
times out" into "times out in 2083". `nTimeout = 0` is Core's *never* sentinel,
exposed as `DOGECOIN_DEPLOYMENT_NO_TIMEOUT` so it can't be misread as a 1970
timeout.

**Opcode aliases.** Core writes `OP_FALSE = OP_0` and
`OP_NOP2 = OP_CHECKLOCKTIMEVERIFY`, so `name → byte` is a function but
`byte → name` is not — it needs a canonical choice. Letting the last declaration
win means a disassembler prints `OP_NOP2` for `0xb1`, which is true and useless.
Policy: the **first** declaration is canonical, matching Core's `GetOpName()`.
Aliases still resolve in `name → byte`, so both directions work and neither is a
guess.

**Direct pushes.** Bytes `0x01..0x4b` are push lengths, not named opcodes.
`dogecoin_opcode_name()` returns NULL for them;
`dogecoin_opcode_is_direct_push()` identifies them.

**`chainTxData`'s `dTxRate` is a double** (e.g. `4.23`) — the only non-integer
value in the whole spec. It's fee estimation, not consensus, but it's extracted
anyway: a permanently nonzero `_unparsed` trains you to ignore it, and
`_unparsed` is the mechanism that caught the fork tree. The invariant only works
if zero is the normal state.

**Field coverage is enforced, not assumed.** The generator's emit lists are
hand-maintained, so rule 1 needs enforcing at the generator too, not just the
extractor. Every consensus field in the spec must be accounted for exactly
once: emitted, or in `EXCLUDED_FIELDS` with a stated reason. A field Core adds
tomorrow matches nothing and is a hard error rather than a silent omission —
otherwise it vanishes into a plausible library, which is the original
flattening bug arriving through a different door. The reverse is checked too: a
name in an emit list that the spec never had is a typo, and a typo emits as a
defaulted zero — a wrong constant.

**uint256 fields are big-endian.** `powLimit`, `nMinimumChainWork`, `BIP34Hash`
and `defaultAssumeValid` are emitted as `uint8_t[32]` in the order Core's
`uint256S()` literal is *written*, which is not `uint256`'s internal
little-endian layout. A consumer comparing against a serialized hash must
reverse.

**`hashGenesisBlock` is excluded.** Core computes it at runtime
(`genesis.GetHash()`), so `chainparams.cpp` has no literal to extract — the
value appears only in the adjacent `assert()`. Reaching it would mean either
extracting assertions (assertions aren't assignments) or hashing genesis
ourselves (that's logic, not a definition).

**Reject codes aren't an enum.** They're free-standing
`static const unsigned char` declarations, which is why they need a different
extractor than opcodes.

---

## Provenance

Every run records what it extracted from:

```
core commit: 699f62ccba4e  (detached HEAD)
client version: 1.14.99.0  (in-development)
nearest tag: v1.14.7-239-g699f62ccba
chainparams.cpp sha256: 150d3733903d05f2...
```

The **commit hash is the identity**. `git describe` resolves to the nearest
reachable *tag*, which on a long-running untagged master can be far behind the
software's self-reported version — and it abbreviates the hash to however many
characters are unambiguous in that particular clone, so the same commit renders
differently in a full clone than a partial one. The sha256 is the truth: it
describes the exact bytes parsed, even if the working tree was dirty.

A spec without provenance is a rumor.

## CI

Two jobs, deliberately split:

- **`verify`** — every push/PR. Clones Core at the **pinned commit** from
  `spec.json`'s own provenance, re-extracts, and asserts the committed spec
  reproduces exactly. If it doesn't, the pin is a lie. Then runs all five test
  tiers.
- **`drift`** — weekly, against Core's `master` tip. Fails if the consensus
  definition moved. **Expected to fail sometimes; that's the point.** It also
  runs the field-coverage gate (`--check-fields-only`) against the tip: `verify`
  generates from the *pinned* Core, where by construction no field is unknown,
  so this is the only job that can ever see a field the generator hasn't been
  taught about. That question is distinct from the regression gate, which
  flattens fields generically and reports a new one as just another changed
  value — "Core moved", not "the library would drop this".

If drift detection ran on every PR, a Core change would redden unrelated pull
requests and people would learn to ignore red. A scheduled job that fails loudly
and rarely stays meaningful.

`make ci CORE=<path>` runs locally exactly what CI runs.

---

## Design rules

Non-negotiable.

1. **Never silently drop an assignment.** Anything not understood goes to
   `_unparsed` with its raw text. Omission is the one unrecoverable failure —
   and this rule is what caught the fork tree.
2. **Never regex C++.** Assignments span lines and nest calls. Use tree-sitter.
3. **Never fold without preserving the literal.** `14400` keeps `4 * 60 * 60`
   next to it so a reviewer can check the arithmetic.
4. **Never hand-edit generated output.** If the header is wrong, the generator
   is wrong. Fix upstream.
5. **Core is truth.** If a spec and Core disagree, the spec is wrong.
6. **Never flatten the height dimension.**
7. **Loud over clever.** A crash beats a wrong constant. Every generator refuses
   incomplete input rather than emitting a plausible table.
8. **Pin the Core commit.**

**A spec that is confidently wrong is worse than no spec.**

An illustration of rule 7: the tree-sitter grammar exposes subscript indices
under field `indices`, not `index`. The first implementation used `index`, got
`None`, and silently collapsed `pchMessageStart[0..3]` into a single key —
producing a plausible-looking, wrong spec. The extractor now records a loud
`_unparsed` entry with an explicit error whenever a subscript index fails to
resolve.

---

## Decisions

**Authoritative Core: `master`.** The pipeline is branch-agnostic; only the pin
changes.

**Regtest is included.** Cheap to carry, and it exercises the fork tree at small
heights (10/20) — catching schedule bugs that mainnet's 145000/371337 wouldn't
surface until much later.

**Generated C is not committed.** `spec.json`, `opcodes.json`, `reject.json`,
and `pinned.json` are, as pinned references. The tradeoff is real: not
committing means the library isn't readable on GitHub and CI needs a Core
checkout; committing makes it auditable in review at the cost of a regeneration
step that can be forgotten. Currently: not committed, with CI asserting
reproducibility instead.

## Files

| file | purpose |
|---|---|
| `extract_chainparams.py` | `chainparams.cpp` → `spec.json` |
| `extract_opcodes.py` | `script/script.h` → `opcodes.json` |
| `extract_constants.py` | `static const` families (e.g. `REJECT_*`) → JSON |
| `verify_selection.py` | proves argmax ≡ Core's BST walk |
| `gen_consensus_c.py` | `spec.json` → C API, epoch tables, tests |
| `gen_opcodes_c.py` | `opcodes.json` → opcode enum + name tables |
| `gen_constants_c.py` | constants JSON → enum + name tables |
| `diff_checkpoints.py` | libdogecoin checkpoints vs Core |
| `regression_gate.py` | pin/check the consensus definition vs Core drift |
| `compare_specs.py` | semantic spec comparison (ignores paths, not the pin) |

## License

MIT. See [`LICENSE`](LICENSE).

Same terms as Dogecoin Core and libdogecoin, so code and definitions can move
between them without a licensing question.
