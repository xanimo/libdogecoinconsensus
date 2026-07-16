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

GENERATED := $(SRC)/dogecoin_consensus.h \
             $(SRC)/dogecoin_consensus.c \
             $(SRC)/test_consensus.c \
             $(SRC)/test_consensus_exhaustive.c

.PHONY: all spec gen verify check diff pin gate clean help check-libdogecoin

all: check

help:
	@echo "make spec   CORE=<path>          extract spec.json from Dogecoin Core"
	@echo "make gen                         generate C sources into $(SRC)/"
	@echo "make verify                      prove argmax == Core's BST walk"
	@echo "make check                       build + run boundary and exhaustive tests"
	@echo "make diff   LIBDOGECOIN=<path>   checkpoint drift vs libdogecoin"
	@echo "make pin                         snapshot consensus as reviewed baseline"
	@echo "make gate                        fail if Core moved since the pin"
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

$(GENERATED): spec.json gen_consensus_c.py verify_selection.py
	./verify_selection.py spec.json
	./gen_consensus_c.py spec.json -o $(SRC)/

gen: $(GENERATED)

check: gen
	$(CC) $(CFLAGS) -o t_bound $(SRC)/test_consensus.c $(SRC)/dogecoin_consensus.c
	./t_bound
	$(CC) $(CFLAGS) -o t_exh $(SRC)/test_consensus_exhaustive.c $(SRC)/dogecoin_consensus.c
	./t_exh

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

clean:
	rm -f t_bound t_exh $(GENERATED)
	rm -rf __pycache__

# spec.json is deliberately NOT removed by clean: it's the pinned reference and
# regenerating requires a Core checkout. Use `make distclean` to drop it.
.PHONY: distclean
distclean: clean
	rm -f spec.json
