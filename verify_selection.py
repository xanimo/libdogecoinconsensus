#!/usr/bin/env python3
"""
verify_selection.py — prove the sorted-array reduction is equivalent to Core's
BST walk at every boundary.

Core resolves consensus-by-height by walking a binary search tree
(chainparams.cpp GetConsensus). The C API will instead binary-search a sorted
array. This asserts the two agree — including the pCandidate guard case at
371336 that a naive tree port gets wrong.

Run:  ./verify_selection.py spec.json
"""

import json
import sys
from pathlib import Path


class Node:
    """Mirror of Core's Consensus::Params tree node."""
    def __init__(self, name, height):
        self.name = name
        self.nHeightEffective = height
        self.pLeft = None
        self.pRight = None

    def GetConsensus(self, nTargetHeight):
        """Faithful port of chainparams.cpp:494-506."""
        if nTargetHeight < self.nHeightEffective and self.pLeft:
            return self.pLeft.GetConsensus(nTargetHeight)
        elif nTargetHeight > self.nHeightEffective and self.pRight:
            pCandidate = self.pRight.GetConsensus(nTargetHeight)
            # the guard that keeps 371336 on digishield
            if pCandidate.nHeightEffective <= nTargetHeight:
                return pCandidate
        return self


def argmax_rule(schedule, height):
    """The reduction: greatest nHeightEffective <= height.
    This is what the C API will do via binary search."""
    best = None
    for ep in schedule:  # schedule is sorted ascending
        if ep["nHeightEffective"] <= height:
            best = ep
        else:
            break
    return best


def build_tree(net):
    """Reconstruct Core's tree from extracted consensus_nodes + links."""
    nodes = {}
    for name, n in net["consensus_nodes"].items():
        h = 0
        for st in net["activation_schedule"]:
            if st["node"] == name:
                h = st["nHeightEffective"]
        nodes[name] = Node(name, h)
    for name, n in net["consensus_nodes"].items():
        for side in ("pLeft", "pRight"):
            tgt = n.get("links", {}).get(side)
            if tgt and tgt in nodes:
                setattr(nodes[name], side, nodes[tgt])
    root_name = net.get("consensus_links", {}).get("root")
    return nodes.get(root_name), nodes


def main():
    if len(sys.argv) < 2:
        print("usage: ./verify_selection.py spec.json", file=sys.stderr)
        return 2
    spec = json.loads(Path(sys.argv[1]).read_text())

    total_fail = 0
    for class_name, net in spec["networks"].items():
        root, nodes = build_tree(net)
        sched = net["activation_schedule"]
        if root is None:
            print(f"{class_name}: no pConsensusRoot found — SKIP", file=sys.stderr)
            continue

        print(f"\n=== {class_name} ===")
        print(f"  root: {root.name}  nodes: {[n.name for n in nodes.values()]}")

        # test every boundary: h-1, h, h+1 for each epoch, plus extremes
        heights = {0, 1}
        for ep in sched:
            h = ep["nHeightEffective"]
            heights.update({max(0, h - 1), h, h + 1})
        for ep in sched:  # also the block before the NEXT epoch
            heights.add(max(0, ep["nHeightEffective"] - 2))
        heights.add(10_000_000)

        fails = 0
        for h in sorted(heights):
            tree_result = root.GetConsensus(h).name
            arr = argmax_rule(sched, h)
            arr_result = arr["node"] if arr else None
            ok = tree_result == arr_result
            if not ok:
                fails += 1
                print(f"  !! MISMATCH h={h}: tree={tree_result} array={arr_result}")

        # explicit named boundary checks from the directive
        checks = {
            "CMainParams": [(144999, "consensus"), (145000, "digishieldConsensus"),
                            (371336, "digishieldConsensus"), (371337, "auxpowConsensus")],
            "CTestNetParams": [(144999, "consensus"), (145000, "digishieldConsensus"),
                               (157499, "digishieldConsensus"), (157500, "minDifficultyConsensus"),
                               (158099, "minDifficultyConsensus"), (158100, "auxpowConsensus")],
        }
        for h, want in checks.get(class_name, []):
            got_tree = root.GetConsensus(h).name
            got_arr = argmax_rule(sched, h)["node"]
            status = "ok " if (got_tree == want == got_arr) else "FAIL"
            if status == "FAIL":
                fails += 1
            print(f"  [{status}] h={h:<7} want={want:<24} tree={got_tree:<24} array={got_arr}")

        print(f"  {len(heights)} heights checked, {fails} failure(s)")
        total_fail += fails

    print()
    if total_fail:
        print(f"FAILED: {total_fail} mismatch(es) — the reduction is NOT equivalent")
        return 1
    print("OK: sorted-array argmax is equivalent to Core's BST walk at every boundary tested.")
    print("    => the C API can binary-search the schedule; do not port the tree.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
