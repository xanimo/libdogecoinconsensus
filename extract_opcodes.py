#!/usr/bin/env python3
"""
extract_opcodes.py — parse Dogecoin Core's script/script.h opcode enum
into a machine-readable spec.

Same discipline as extract_chainparams.py: tree-sitter, never regex; nothing
silently dropped; Core is the source of truth.

Opcodes are pure data — a name/byte table — so they're portable and belong in
libdogecoinconsensus. Script *semantics* (what each opcode does) are behavior,
not data, and are explicitly out of scope (see DIRECTIVE §6).

The wrinkle is aliases. Core writes:

    OP_0 = 0x00,
    OP_FALSE = OP_0,                        // same byte, second name
    OP_CHECKLOCKTIMEVERIFY = 0xb1,
    OP_NOP2 = OP_CHECKLOCKTIMEVERIFY,       // alias to an earlier name

So the mapping is name -> byte (many-to-one), NOT byte -> name. Any reverse
map has to pick a canonical name per byte; we record aliases explicitly rather
than letting the last one silently win.

Usage:
    ./extract_opcodes.py path/to/script/script.h -o opcodes.json
"""

import argparse
import hashlib
import json
import subprocess
import sys
from pathlib import Path

import tree_sitter_cpp
from tree_sitter import Language, Parser

CPP = Language(tree_sitter_cpp.language())


def src(node, code: bytes) -> str:
    return code[node.start_byte:node.end_byte].decode("utf8", errors="replace")


def walk(node):
    yield node
    for child in node.children:
        yield from child_walk(child)


def child_walk(node):
    yield node
    for child in node.children:
        yield from child_walk(child)


def parse_int(text: str):
    """0x4c -> 76. Returns None if not a plain integer literal."""
    t = text.strip().rstrip("uUlL")
    try:
        return int(t, 0)
    except ValueError:
        return None


def find_enum(root, code: bytes, name: str):
    for node in walk(root):
        if node.type != "enum_specifier":
            continue
        n = node.child_by_field_name("name")
        if n is not None and src(n, code) == name:
            return node.child_by_field_name("body")
    return None


def provenance(path: Path):
    prov = {"file_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
            "source": str(path)}
    try:
        repo = path.resolve().parent
        for _ in range(6):
            if (repo / ".git").exists():
                break
            repo = repo.parent
        else:
            repo = None
        if repo:
            def git(*a):
                return subprocess.run(["git", "-C", str(repo), *a],
                                      capture_output=True, text=True,
                                      timeout=10).stdout.strip()
            prov["core_commit"] = git("rev-parse", "HEAD") or None
            prov["core_describe"] = git("describe", "--tags", "--always") or None
            prov["file_dirty"] = bool(git("status", "--porcelain", str(path)))
    except Exception as e:
        prov["_error"] = f"{type(e).__name__}: {e}"
    return prov


def extract(path: Path, enum_name: str = "opcodetype"):
    code = path.read_bytes()
    tree = Parser(CPP).parse(code)
    body = find_enum(tree.root_node, code, enum_name)
    if body is None:
        raise SystemExit(f"error: enum '{enum_name}' not found in {path}")

    spec = {
        "_note": "Generated from Dogecoin Core script.h. Core is the source of "
                 "truth. Do not hand-edit.",
        "_provenance": provenance(path),
        "_enum": enum_name,
        "opcodes": [],      # [{name, value, alias_of?}] in declaration order
        "_unparsed": [],
    }

    # name -> value, resolved as we go so aliases can refer to earlier names
    values = {}

    for child in body.named_children:
        if child.type != "enumerator":
            continue
        name_node = child.child_by_field_name("name")
        val_node = child.child_by_field_name("value")
        if name_node is None:
            continue
        name = src(name_node, code)

        if val_node is None:
            # implicit value (previous + 1). Core's opcode enum always assigns
            # explicitly; if this fires, the file changed shape.
            spec["_unparsed"].append({
                "name": name,
                "error": "enumerator has no explicit value; implicit numbering "
                         "is not modelled"})
            continue

        text = src(val_node, code)
        v = parse_int(text)
        if v is not None:
            values[name] = v
            spec["opcodes"].append({"name": name, "value": v})
            continue

        # alias: OP_FALSE = OP_0
        target = text.strip()
        if target in values:
            values[name] = values[target]
            spec["opcodes"].append({"name": name, "value": values[target],
                                    "alias_of": target})
            continue

        spec["_unparsed"].append({
            "name": name, "expr": text,
            "error": "value is neither an integer literal nor a known earlier "
                     "enumerator (forward reference or expression?)"})

    return spec


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("header", type=Path, help="path to script/script.h")
    ap.add_argument("-o", "--out", type=Path)
    ap.add_argument("--enum", default="opcodetype")
    args = ap.parse_args()

    if not args.header.exists():
        print(f"error: {args.header} not found", file=sys.stderr)
        return 1

    spec = extract(args.header, args.enum)
    text = json.dumps(spec, indent=2)
    if args.out:
        args.out.write_text(text)
        print(f"wrote {args.out}", file=sys.stderr)
    else:
        print(text)

    ops = spec["opcodes"]
    aliases = [o for o in ops if "alias_of" in o]
    distinct = len({o["value"] for o in ops})
    prov = spec["_provenance"]
    if prov.get("core_commit"):
        print(f"  core commit: {prov['core_commit'][:12]}", file=sys.stderr)
    print(f"  script.h sha256: {prov['file_sha256'][:16]}...", file=sys.stderr)
    if prov.get("file_dirty"):
        print("  !! script.h has UNCOMMITTED CHANGES", file=sys.stderr)
    print(f"  {len(ops)} enumerators, {distinct} distinct bytes, "
          f"{len(aliases)} alias(es), {len(spec['_unparsed'])} unparsed",
          file=sys.stderr)
    for a in aliases:
        print(f"      {a['name']} = {a['alias_of']} (0x{a['value']:02x})",
              file=sys.stderr)
    for u in spec["_unparsed"]:
        print(f"  !! unparsed: {u['name']}: {u['error']}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
