# libdogecoinconsensus
#
# Core is the source of truth. Everything below is generated from it.
#
#   make spec   CORE=~/source/repos/dogecoin    extract spec.json from Core
#   make gen                                    generate C sources
#   make check                                  build + run all tests
#   make diff   LIBDOGECOIN=~/src/libdogecoin   checkpoint drift vs libdogecoin
#   make clean

CORE        ?= ../dogecoin
LIBDOGECOIN ?= ../libdogecoin
CFLAGS      ?= -std=c99 -Wall -Wextra -Werror -O2
SRC         := src
CHAINPARAMS := $(CORE)/src/chainparams.cpp
SCRIPT_H    := $(CORE)/src/script/script.h
VALIDATION_H := $(CORE)/src/consensus/validation.h

GENERATED := $(SRC)/dogecoin_consensus.h \
             $(SRC)/dogecoin_consensus.c \
             $(SRC)/test_consensus.c \
             $(SRC)/test_consensus_exhaustive.c

GENERATED_OPS := $(SRC)/dogecoin_opcodes.h \
                 $(SRC)/dogecoin_opcodes.c \
                 $(SRC)/test_opcodes.c

GENERATED_REJECT := $(SRC)/dogecoin_reject.h \
                    $(SRC)/dogecoin_reject.c \
                    $(SRC)/test_reject.c

.PHONY: all spec opcodes reject gen verify check diff pin gate ci clean help check-libdogecoin evidence deterministic

all: check

help:
	@echo "make spec   CORE=<path>          extract spec.json from Dogecoin Core"
	@echo "make opcodes CORE=<path>         extract opcodes.json from Core script.h"
	@echo "make reject  CORE=<path>         extract reject.json from Core validation.h"
	@echo "make gen                         generate C sources into $(SRC)/"
	@echo "make verify                      prove argmax == Core's BST walk"
	@echo "make check                       build + run boundary and exhaustive tests"
	@echo "make diff   LIBDOGECOIN=<path>   checkpoint drift vs libdogecoin"
	@echo "make pin                         snapshot consensus as reviewed baseline"
	@echo "make gate                        fail if Core moved since the pin"
	@echo "make ci     CORE=<path>          everything CI runs (reproducibility + tests)"
	@echo "make clean"

# We want two things that pull against each other:
#   (a) a useful error when CORE is unset/wrong, not make's cryptic
#       "No rule to make target '.../chainparams.cpp'"
#   (b) incremental builds — don't re-extract when nothing changed
#
# A phony guard prerequisite gives (a) but breaks (b) (always out of date).
# A plain file prerequisite gives (b) but make errors before any guard runs.
#
# Resolution: resolve existence at parse time with $(wildcard). If the file is
# missing, the prerequisite list is empty, so our recipe runs and reports
# properly. If it exists, it's a normal file prerequisite and make's timestamp
# logic works as intended.
spec.json: $(wildcard $(CHAINPARAMS))
	@test -f "$(CHAINPARAMS)" || { \
	  echo ""; \
	  echo "error: cannot find $(CHAINPARAMS)"; \
	  echo "       Set CORE to your Dogecoin Core checkout:"; \
	  echo "         make $(or $(MAKECMDGOALS),spec) CORE=~/source/repos/dogecoin"; \
	  echo ""; \
	  exit 1; }
	./extract_chainparams.py $(CHAINPARAMS) -o $@

spec: spec.json

# The reduction must be re-proven whenever the spec changes: if Core adds a
# consensus regime with different tree wiring, the sorted-array assumption
# could stop holding. Cheap insurance.
verify: spec.json
	./verify_selection.py spec.json

# The generator is a prerequisite, not just the spec: a change to the emit
# lists or the codegen changes the output while spec.json's timestamp sits
# still. Without this, `make gen` reports "nothing to be done" and the tree
# keeps a stale library built by the previous generator -- silently, which is
# the one failure mode this project does not accept. The opcode and reject
# rules below already list theirs; this one was the outlier.
#
# verify_selection.py is listed for the same reason: it gates this rule, so a
# change to the proof must re-run it against the spec.
$(GENERATED): spec.json gen_consensus_c.py verify_selection.py
	./verify_selection.py spec.json
	./gen_consensus_c.py spec.json -o $(SRC)/

opcodes.json: $(wildcard $(SCRIPT_H))
	@test -f "$(SCRIPT_H)" || { \
	  echo ""; \
	  echo "error: cannot find $(SCRIPT_H)"; \
	  echo "       Set CORE to your Dogecoin Core checkout:"; \
	  echo "         make $(or $(MAKECMDGOALS),opcodes) CORE=~/source/repos/dogecoin"; \
	  echo ""; \
	  exit 1; }
	./extract_opcodes.py $(SCRIPT_H) -o $@

opcodes: opcodes.json

$(GENERATED_OPS): opcodes.json gen_opcodes_c.py
	./gen_opcodes_c.py opcodes.json -o $(SRC)/

reject.json: $(wildcard $(VALIDATION_H))
	@test -f "$(VALIDATION_H)" || { \
	  echo ""; \
	  echo "error: cannot find $(VALIDATION_H)"; \
	  echo "       Set CORE to your Dogecoin Core checkout:"; \
	  echo "         make $(or $(MAKECMDGOALS),reject) CORE=~/source/repos/dogecoin"; \
	  echo ""; \
	  exit 1; }
	./extract_constants.py $(VALIDATION_H) --prefix REJECT_ -o $@

reject: reject.json

$(GENERATED_REJECT): reject.json gen_constants_c.py
	./gen_constants_c.py reject.json -o $(SRC)/ --name reject \
	    --title "P2P reject message codes"

gen: $(GENERATED) $(GENERATED_OPS) $(GENERATED_REJECT)

check: gen
	$(CC) $(CFLAGS) -o t_bound $(SRC)/test_consensus.c $(SRC)/dogecoin_consensus.c
	./t_bound
	$(CC) $(CFLAGS) -o t_exh $(SRC)/test_consensus_exhaustive.c $(SRC)/dogecoin_consensus.c
	./t_exh
	$(CC) $(CFLAGS) -o t_ops $(SRC)/test_opcodes.c $(SRC)/dogecoin_opcodes.c
	./t_ops
	$(CC) $(CFLAGS) -o t_rej $(SRC)/test_reject.c $(SRC)/dogecoin_reject.c
	./t_rej

check-libdogecoin:
	@test -f "$(LIBDOGECOIN)/src/chainparams.c" || { \
	  echo ""; \
	  echo "error: cannot find $(LIBDOGECOIN)/src/chainparams.c"; \
	  echo "       Set LIBDOGECOIN to your libdogecoin checkout:"; \
	  echo "         make diff LIBDOGECOIN=~/source/repos/libdogecoin"; \
	  echo ""; \
	  exit 1; }

# Uses an existing spec.json; does NOT rebuild it, so `make diff` can't fail
# for the unrelated reason that CORE isn't set.
# Snapshot the current consensus definition as the reviewed baseline.
pin: spec.json
	./regression_gate.py spec.json --pin -o pinned.json

# Fail if Core's consensus definition moved since the pin. Run on a schedule
# against Core's tip: a consensus change must be REVIEWED, not absorbed.
gate: spec.json
	@test -f pinned.json || { \
	  echo "error: no pinned.json. Create the baseline first: make pin"; exit 1; }
	./regression_gate.py spec.json --check --against pinned.json

diff: check-libdogecoin
	@test -f spec.json || { \
	  echo "error: spec.json not found. Run: make spec CORE=<path>"; exit 1; }
	./diff_checkpoints.py spec.json --libdogecoin $(LIBDOGECOIN)/src/chainparams.c

# What CI runs. Reproduces the committed spec from its pinned Core commit,
# proves the reduction, builds, tests, checks the gate.
# If this passes locally it will pass in CI.
# The flattened evidence spec must stay reproducible from the sample, or the
# README's central finding degrades from "run this" back to "trust me".
# Needs no Core checkout: the whole point is that the input is a local flat
# mirror.
evidence:
	@./extract_chainparams.py sample_chainparams.cpp -o /tmp/_evidence.json 2>/dev/null
	@python3 -c "import json,sys; \
d=json.load(open('/tmp/_evidence.json')); \
m=d['networks']['CMainParams']; \
n=len(m['activation_schedule']); \
t=m['activation_schedule'][0]['effective_fields']['nPowTargetTimespan']; \
c=d['_provenance'].get('core_commit'); \
ok = (n==1 and t==14400 and c is None); \
print('  evidence: %d epoch, nPowTargetTimespan=%s, core_commit=%s' % (n,t,c)); \
sys.exit(0 if ok else 1)" || { \
	  echo "error: sample_chainparams.cpp no longer reproduces the flattened spec."; \
	  echo "       docs/flattened_v1_spec.json is evidence for the README's central"; \
	  echo "       finding; if the sample changed, the evidence is stale."; \
	  rm -f /tmp/_evidence.json; exit 1; }
	@rm -f /tmp/_evidence.json
	@echo "OK: the flattened evidence spec still reproduces from sample_chainparams.cpp"

# Generation must be a function of the spec and nothing else. src/ is not
# committed, so CI never diffs a stored copy against a fresh one -- which means
# nondeterminism would never surface: every run regenerates, every run agrees
# with itself, and the library silently differs build to build.
#
# The hazard is ordinary: one set() or dict iteration in an emit path reorders
# struct fields across runs. Same spec, incompatible ABI, all tests green --
# they compile whatever was just emitted. PYTHONHASHSEED is what makes that
# reproducible instead of a once-a-month mystery.
deterministic: spec.json
	@rm -rf .det_a .det_b
	@PYTHONHASHSEED=1   ./gen_consensus_c.py spec.json -o .det_a >/dev/null 2>&1
	@PYTHONHASHSEED=999 ./gen_consensus_c.py spec.json -o .det_b >/dev/null 2>&1
	@if diff -r .det_a .det_b >/dev/null 2>&1; then \
	  rm -rf .det_a .det_b; \
	  echo "OK: generation is deterministic (stable across PYTHONHASHSEED)"; \
	else \
	  echo "error: generation is NOT deterministic — the same spec produced two"; \
	  echo "       different libraries. Look for set()/dict iteration in an emit"; \
	  echo "       path; if it reorders struct fields, that is an ABI break that"; \
	  echo "       every test would still pass."; \
	  diff -r .det_a .det_b | head -20; \
	  rm -rf .det_a .det_b; exit 1; \
	fi

ci: spec.json opcodes.json reject.json
	./extract_chainparams.py $(CHAINPARAMS) -o spec.regen.json
	./extract_opcodes.py $(SCRIPT_H) -o opcodes.regen.json
	./extract_constants.py $(VALIDATION_H) --prefix REJECT_ -o reject.regen.json
	./compare_specs.py spec.json spec.regen.json \
	    --label-first "committed spec.json" --label-second "fresh extraction"
	./compare_specs.py opcodes.json opcodes.regen.json \
	    --label-first "committed opcodes.json" --label-second "fresh extraction"
	./compare_specs.py reject.json reject.regen.json \
	    --label-first "committed reject.json" --label-second "fresh extraction"
	@rm -f spec.regen.json opcodes.regen.json reject.regen.json
	$(MAKE) evidence
	$(MAKE) deterministic
	$(MAKE) check CORE=$(CORE)
	@if [ -f pinned.json ]; then \
	  ./regression_gate.py spec.json --check --against pinned.json; \
	else \
	  echo "no pinned.json — create the baseline with: make pin"; \
	fi

clean:
	rm -rf .det_a .det_b
	rm -f t_bound t_exh t_ops t_rej $(GENERATED) $(GENERATED_OPS) $(GENERATED_REJECT)
	rm -f spec.regen.json opcodes.regen.json reject.regen.json
	rm -rf __pycache__

# spec.json is deliberately NOT removed by clean: it's the pinned reference and
# regenerating requires a Core checkout. Use `make distclean` to drop it.
.PHONY: distclean
distclean: clean
	rm -f spec.json opcodes.json reject.json
