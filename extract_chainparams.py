#!/usr/bin/env python3
"""
extract_chainparams.py — parse Dogecoin Core src/chainparams.cpp into a
machine-readable consensus spec (JSON).

Core is the source of truth. This walks the CChainParams subclass constructors
with tree-sitter and lifts every assignment into structured data, so downstream
consumers (libdogecoin headers, other implementations, differential tests) can
be *generated* from Core rather than hand-transcribed.

Usage:
    ./extract_chainparams.py path/to/chainparams.cpp [-o spec.json]

Design notes:
  * tree-sitter, not regex: assignments span lines, contain nested calls, and
    regex over C++ is how you get subtly wrong constants.
  * We extract *syntax*, not semantics. `4 * 60 * 60` is preserved as both the
    literal expression and its evaluated value. Never silently fold.
  * Unknown/unparsed fields are recorded in `_unparsed` rather than dropped.
    Silent omission is the failure mode that would defeat the whole point.
"""

import argparse
import hashlib
import json
import re
import subprocess
import sys
from pathlib import Path

import tree_sitter_cpp
from tree_sitter import Language, Parser

CPP = Language(tree_sitter_cpp.language())

# Dogecoin Core builds a *tree* of consensus params, not a single struct.
# Named copies (digishieldConsensus = consensus; auxpowConsensus = digishield...)
# are mutated and linked via pLeft/pRight, rooted at pConsensusRoot, and selected
# by height via nHeightEffective. Flattening this is a consensus-breaking bug.
CONSENSUS_NODE_RE = re.compile(r"^(consensus|\w*[Cc]onsensus)$")
LIST_OF_RE = re.compile(r"list_of\s*((?:\(\s*0x[0-9a-fA-F]+\s*\)|\(\s*\d+\s*\))+)")
LIST_OF_ITEM_RE = re.compile(r"\(\s*(0x[0-9a-fA-F]+|\d+)\s*\)")

# checkpointData = (CCheckpointData) { boost::assign::map_list_of
#     (      0, uint256S("0x1a91e3...")) ( 104679, uint256S("0x35eb87...")) ... }
# Each pair is (height, uint256S("0xhash")). Heights are decimal, hashes hex.
CHECKPOINT_PAIR_RE = re.compile(
    r"\(\s*(\d+)\s*,\s*uint256S\(\s*\"(0x[0-9a-fA-F]+)\"\s*\)\s*\)")


def src(node, code: bytes) -> str:
    return code[node.start_byte:node.end_byte].decode("utf8", errors="replace")


def safe_eval_int(expr: str):
    """Evaluate simple integer arithmetic (4 * 60 * 60) without executing C++.
    Returns None if it isn't a pure arithmetic literal expression."""
    cleaned = expr.strip().rstrip("uUlL")
    # only allow digits, hex, operators, parens, whitespace
    allowed = set("0123456789abcdefABCDEFx+-*/() \t")
    if not cleaned or not set(cleaned) <= allowed:
        return None
    try:
        val = eval(cleaned, {"__builtins__": {}}, {})  # noqa: S307 - charset-restricted
        return val if isinstance(val, int) else None
    except Exception:
        return None


def find_class_constructors(root, code: bytes):
    """Yield (class_name, constructor_body_node) for each CChainParams subclass."""
    for node in walk(root):
        if node.type != "class_specifier":
            continue
        name_node = node.child_by_field_name("name")
        if name_node is None:
            continue
        class_name = src(name_node, code)
        body = node.child_by_field_name("body")
        if body is None:
            continue
        for member in walk(body):
            if member.type != "function_definition":
                continue
            decl = member.child_by_field_name("declarator")
            if decl is None:
                continue
            # constructor: declarator name matches class name
            fname = None
            for sub in walk(decl):
                if sub.type == "identifier":
                    fname = src(sub, code)
                    break
            if fname == class_name:
                fbody = member.child_by_field_name("body")
                if fbody is not None:
                    yield class_name, fbody


def walk(node):
    yield node
    for child in node.children:
        yield from walk(child)


def subscript_index(node, code: bytes):
    """Extract the index text from a subscript_expression.
    This grammar wraps indices in a `subscript_argument_list` under field
    `indices` (not `index`). Getting this wrong silently collapses
    pchMessageStart[0..3] into one key — so we assert we found something."""
    idx = node.child_by_field_name("indices")
    if idx is None:
        idx = node.child_by_field_name("index")  # older grammar fallback
    if idx is None:
        return None
    if idx.type == "subscript_argument_list":
        inner = [c for c in idx.named_children]
        if not inner:
            return None
        return src(inner[0], code)
    return src(idx, code)


def parse_lhs(lhs_node, code: bytes):
    """Turn an assignment LHS into a structured key.
    Handles: consensus.X, consensus.vDeployments[E].field, pchMessageStart[0],
             base58Prefixes[KEY], bare identifiers."""
    text = src(lhs_node, code)
    if lhs_node.type == "subscript_expression":
        arg = lhs_node.child_by_field_name("argument")
        return {
            "kind": "subscript",
            "base": src(arg, code) if arg else None,
            "index": subscript_index(lhs_node, code),
            "raw": text,
        }
    if lhs_node.type == "field_expression":
        # could be consensus.vDeployments[X].bit  -> argument is subscript_expression
        arg = lhs_node.child_by_field_name("argument")
        field = lhs_node.child_by_field_name("field")
        if arg is not None and arg.type == "subscript_expression":
            inner = parse_lhs(arg, code)
            return {
                "kind": "deployment_field",
                "base": inner.get("base"),
                "index": inner.get("index"),
                "field": src(field, code) if field else None,
                "raw": text,
            }
        return {
            "kind": "field",
            "base": src(arg, code) if arg else None,
            "field": src(field, code) if field else None,
            "raw": text,
        }
    return {"kind": "identifier", "raw": text}


def parse_checkpoints(expr: str):
    """Extract (height, hash) pairs from a CCheckpointData map_list_of chain.

    Returns None if this doesn't look like a checkpoint block at all, so the
    caller can leave it in _unparsed rather than silently claiming zero
    checkpoints. An empty list and 'not a checkpoint block' are different
    facts and must not be conflated."""
    if "map_list_of" not in expr:
        return None
    pairs = CHECKPOINT_PAIR_RE.findall(expr)
    if not pairs:
        return None
    out = []
    seen = set()
    for h, hsh in pairs:
        height = int(h)
        if height in seen:
            # duplicate height in Core would be a real anomaly; surface it
            out.append({"height": height, "hash": hsh, "_duplicate": True})
        else:
            seen.add(height)
            out.append({"height": height, "hash": hsh})
    out.sort(key=lambda c: c["height"])
    return out


def parse_rhs(rhs_node, code: bytes):
    """Structure an assignment RHS, preserving the literal expression."""
    text = src(rhs_node, code).strip()
    out = {"expr": text}

    # boost::assign::list_of(0x02)(0xfa)(0xca)(0xfd).convert_to_container<...>()
    # Real Core uses this for EXT_PUBLIC_KEY / EXT_SECRET_KEY. The bytes are in
    # the chained call syntax, not an initializer_list.
    m = LIST_OF_RE.search(text)
    if m:
        items = LIST_OF_ITEM_RE.findall(m.group(1))
        vals = [int(x, 16) if x.lower().startswith("0x") else int(x) for x in items]
        if vals:
            out["type"] = "bytes"
            out["value"] = vals
            out["note"] = "boost::assign::list_of"
            return out

    # uint256S("0x...") -> hash literal
    if rhs_node.type == "call_expression":
        fn = rhs_node.child_by_field_name("function")
        fn_name = src(fn, code) if fn else ""
        args = rhs_node.child_by_field_name("arguments")
        arg_list = []
        if args:
            for c in args.named_children:
                arg_list.append(src(c, code))
        out["call"] = fn_name
        out["args"] = arg_list
        if fn_name == "uint256S" and arg_list:
            out["type"] = "hash"
            out["value"] = arg_list[0].strip('"')
            return out
        if fn_name == "CreateGenesisBlock":
            out["type"] = "genesis"
            out["fields"] = dict(zip(
                ["nTime", "nNonce", "nBits", "nVersion", "genesisReward"], arg_list))
            return out
        # std::vector<unsigned char>(1,30)
        if "vector" in fn_name and len(arg_list) == 2:
            v = safe_eval_int(arg_list[1])
            out["type"] = "byte"
            out["value"] = v
            return out
        out["type"] = "call"
        return out

    if rhs_node.type in ("number_literal",):
        v = safe_eval_int(text)
        out["type"] = "int"
        out["value"] = v
        return out

    if rhs_node.type in ("true", "false"):
        out["type"] = "bool"
        out["value"] = text == "true"
        return out

    if rhs_node.type == "string_literal":
        out["type"] = "string"
        out["value"] = text.strip('"')
        return out

    if rhs_node.type == "initializer_list":
        vals = []
        for c in rhs_node.named_children:
            vals.append(safe_eval_int(src(c, code)))
        out["type"] = "bytes"
        out["value"] = vals
        return out

    # arithmetic like 4 * 60 * 60
    v = safe_eval_int(text)
    if v is not None:
        out["type"] = "int"
        out["value"] = v
        return out

    out["type"] = "unparsed"
    return out


def core_provenance(path: Path):
    """Pin what we extracted from. A spec without provenance is a rumor.

    Records the git commit of the Core checkout (if the file is in a repo) and
    a SHA-256 of chainparams.cpp itself, so the spec can always be traced back
    to exact source bytes even if the working tree was dirty."""
    prov = {"file_sha256": hashlib.sha256(path.read_bytes()).hexdigest()}
    try:
        repo = path.resolve().parent
        for _ in range(5):  # walk up looking for .git
            if (repo / ".git").exists():
                break
            repo = repo.parent
        else:
            repo = None
        if repo:
            def git(*args):
                return subprocess.run(
                    ["git", "-C", str(repo), *args],
                    capture_output=True, text=True, timeout=10).stdout.strip()
            prov["core_commit"] = git("rev-parse", "HEAD") or None
            # describe resolves to the nearest reachable TAG. On a long-running
            # untagged master this can be far behind (e.g. v1.14.3-1190-g699f62c
            # while the software self-reports 1.14.99). It is decoration; the
            # commit hash is the identity.
            prov["core_describe"] = git("describe", "--tags", "--always") or None
            prov["core_describe_dirty"] = git("describe", "--tags", "--always", "--dirty") or None
            # The in-development version Core reports about itself, which is NOT
            # the nearest tag. Convention: master carries a .99 minor.
            try:
                cfg = repo / "configure.ac"
                if cfg.exists():
                    txt = cfg.read_text(errors="replace")
                    parts = {}
                    for k in ("MAJOR", "MINOR", "REVISION", "BUILD"):
                        m = re.search(
                            r"define\(_CLIENT_VERSION_" + k + r",\s*(\d+)\)", txt)
                        if m:
                            parts[k] = m.group(1)
                    if parts:
                        prov["core_client_version"] = ".".join(
                            parts.get(k, "?") for k in ("MAJOR", "MINOR", "REVISION", "BUILD"))
                    m = re.search(r"define\(_CLIENT_VERSION_IS_RELEASE,\s*(\w+)\)", txt)
                    if m:
                        prov["core_is_release"] = m.group(1).lower() == "true"
            except Exception:
                pass
            branch = git("rev-parse", "--abbrev-ref", "HEAD")
            prov["core_branch"] = branch or None
            prov["core_detached"] = (branch == "HEAD")
            # tree_dirty: ANY file in the repo modified (what --dirty reports)
            prov["tree_dirty"] = bool(git("status", "--porcelain"))
            # file_dirty: THE EXTRACTED FILE modified. This is the one that
            # invalidates provenance — a dirty tree elsewhere is irrelevant.
            status = git("status", "--porcelain", str(path))
            prov["file_dirty"] = bool(status)
            if status:
                prov["_warning"] = ("chainparams.cpp has uncommitted changes; "
                                    "core_commit does not describe this file")
    except Exception as e:  # provenance is best-effort, never fatal
        prov["_error"] = f"{type(e).__name__}: {e}"
    return prov


def extract(path: Path):
    code = path.read_bytes()
    parser = Parser(CPP)
    tree = parser.parse(code)

    spec = {
        "_source": str(path),
        "_note": "Generated from Dogecoin Core. Core is the source of truth. Do not hand-edit.",
        "_provenance": core_provenance(path),
        "networks": {},
    }

    for class_name, body in find_class_constructors(tree.root_node, code):
        net = {"_class": class_name,
               "consensus_nodes": {},   # name -> {fields, links, derived_from}
               "checkpoints": [],       # [{height, hash}] sorted by height
               "consensus_links": {},   # pLeft/pRight/pConsensusRoot wiring
               "deployments": {},
               "base58Prefixes": {}, "messageStart": {}, "other": {},
               "_unparsed": []}

        for node in walk(body):
            if node.type != "assignment_expression":
                continue
            lhs_node = node.child_by_field_name("left")
            rhs_node = node.child_by_field_name("right")
            if lhs_node is None or rhs_node is None:
                continue
            lhs = parse_lhs(lhs_node, code)
            rhs = parse_rhs(rhs_node, code)

            k = lhs.get("kind")

            if k in ("subscript", "deployment_field") and lhs.get("index") is None:
                net["_unparsed"].append({
                    "lhs": lhs["raw"], "rhs": rhs["expr"],
                    "error": "could not extract subscript index (grammar mismatch?)"})
                continue

            # --- consensus fork tree handling ---------------------------------
            # `digishieldConsensus = consensus;` : a new node derived from another
            if k == "identifier" and CONSENSUS_NODE_RE.match(lhs["raw"]):
                base = rhs["expr"].strip().rstrip(";")
                net["consensus_nodes"].setdefault(lhs["raw"], {
                    "derived_from": base if CONSENSUS_NODE_RE.match(base) else None,
                    "fields": {}, "links": {}})
                continue

            # `pConsensusRoot = &digishieldConsensus;`
            if k == "identifier" and lhs["raw"] == "pConsensusRoot":
                net["consensus_links"]["root"] = rhs["expr"].lstrip("&").strip()
                continue

            # `digishieldConsensus.pLeft = &consensus;`
            if k == "field" and CONSENSUS_NODE_RE.match(lhs.get("base") or ""):
                nodename = lhs["base"]
                field = lhs["field"]
                net["consensus_nodes"].setdefault(nodename, {
                    "derived_from": None, "fields": {}, "links": {}})
                if field in ("pLeft", "pRight"):
                    net["consensus_nodes"][nodename]["links"][field] = \
                        rhs["expr"].lstrip("&").strip()
                else:
                    net["consensus_nodes"][nodename]["fields"][field] = rhs
                continue
            # ------------------------------------------------------------------

            # --- checkpoints ---------------------------------------------------
            if k == "identifier" and lhs["raw"] == "checkpointData":
                cps = parse_checkpoints(rhs["expr"])
                if cps is None:
                    net["_unparsed"].append({
                        "lhs": lhs["raw"], "rhs": rhs["expr"],
                        "error": "checkpointData present but no (height, uint256S) "
                                 "pairs matched — structure may have changed"})
                else:
                    net["checkpoints"] = cps
                continue
            # ------------------------------------------------------------------

            if rhs.get("type") == "unparsed":
                net["_unparsed"].append({"lhs": lhs["raw"], "rhs": rhs["expr"]})

            if k == "deployment_field":
                dep = lhs.get("index") or "?"
                net["deployments"].setdefault(dep, {})[lhs["field"]] = rhs
            elif k == "subscript" and lhs.get("base") == "pchMessageStart":
                net["messageStart"][lhs["index"]] = rhs
            elif k == "subscript" and lhs.get("base") == "base58Prefixes":
                net["base58Prefixes"][lhs["index"]] = rhs
            else:
                net["other"][lhs["raw"]] = rhs

        # resolve the fork tree into an ordered activation schedule
        net["activation_schedule"] = build_schedule(net)
        spec["networks"][class_name] = net

    return spec


def build_schedule(net):
    """Resolve consensus nodes into an ordered list by nHeightEffective, with
    each node's *effective* field set (inherited from its derived_from chain,
    overridden by its own mutations).

    This is the whole point: Core selects params by height. A flat struct is a
    consensus-breaking lie."""
    nodes = net["consensus_nodes"]
    if not nodes:
        return []

    def resolve(name, seen=None):
        seen = seen or set()
        if name in seen or name not in nodes:
            return {}
        seen.add(name)
        n = nodes[name]
        base = resolve(n["derived_from"], seen) if n.get("derived_from") else {}
        merged = dict(base)
        merged.update(n["fields"])
        return merged

    sched = []
    for name, n in nodes.items():
        eff = resolve(name)
        h = eff.get("nHeightEffective", {}).get("value")
        sched.append({
            "node": name,
            "nHeightEffective": h if h is not None else 0,
            "derived_from": n.get("derived_from"),
            "links": n.get("links", {}),
            "own_mutations": sorted(n["fields"].keys()),
            "effective_fields": {k: v.get("value", v.get("expr"))
                                 for k, v in eff.items()},
        })
    sched.sort(key=lambda x: x["nHeightEffective"])
    return sched


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("source", type=Path, help="path to chainparams.cpp")
    ap.add_argument("-o", "--out", type=Path, default=None, help="output JSON (default stdout)")
    args = ap.parse_args()

    if not args.source.exists():
        print(f"error: {args.source} not found", file=sys.stderr)
        return 1

    spec = extract(args.source)
    text = json.dumps(spec, indent=2)
    if args.out:
        args.out.write_text(text)
        print(f"wrote {args.out}", file=sys.stderr)
    else:
        print(text)

    # summary to stderr so stdout stays clean JSON
    prov = spec.get("_provenance", {})
    commit = prov.get("core_commit")
    if commit:
        desc = prov.get("core_describe")
        branch = prov.get("core_branch")
        where = "detached HEAD" if prov.get("core_detached") else branch
        print(f"  core commit: {commit[:12]}  ({where})", file=sys.stderr)
        cv = prov.get("core_client_version")
        if cv:
            rel = prov.get("core_is_release")
            tag = "release" if rel else "in-development"
            print(f"  client version: {cv}  ({tag})", file=sys.stderr)
        if desc:
            # describe resolves to the nearest reachable TAG, which may be far
            # behind master. It is decoration; the commit is the truth.
            print(f"  nearest tag: {desc}", file=sys.stderr)
    print(f"  chainparams.cpp sha256: {prov.get('file_sha256','?')[:16]}...", file=sys.stderr)
    if prov.get("file_dirty"):
        print("  !! chainparams.cpp has UNCOMMITTED CHANGES — core_commit does not "
              "describe this file; trust the sha256, not the commit", file=sys.stderr)
    elif prov.get("tree_dirty"):
        print("  (working tree has changes elsewhere; chainparams.cpp itself is clean)",
              file=sys.stderr)

    for name, net in spec["networks"].items():
        sched = net.get("activation_schedule", [])
        print(f"  {name}: {len(net['consensus_nodes'])} consensus nodes "
              f"({len(sched)} in schedule), "
              f"{len(net['deployments'])} deployments, "
              f"{len(net['base58Prefixes'])} prefixes, "
              f"{len(net['_unparsed'])} unparsed", file=sys.stderr)
        for st in sched:
            muts = ",".join(st["own_mutations"]) or "(base)"
            print(f"      h={st['nHeightEffective']:<9} {st['node']:<26} mutates: {muts}",
                  file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
