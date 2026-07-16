#!/usr/bin/env python3
"""
extract_constants.py — parse `static const <type> NAME = <value>;` declarations
from a Core header into a machine-readable spec.

Written for rejection codes (`src/consensus/validation.h`), which are NOT an
enum — they're free-standing `static const unsigned char` declarations:

    static const unsigned char REJECT_MALFORMED = 0x01;
    static const unsigned char REJECT_INVALID = 0x10;

so extract_opcodes.py (which walks enum_specifier) doesn't see them at all.

Filter by name prefix so we pick up exactly the family we mean and nothing
else. Without a prefix this would hoover up every constant in the header —
including unrelated ones whose meaning we haven't checked — and a table of
"constants we happened to find" is not a specification of anything.

Usage:
    ./extract_constants.py path/to/validation.h --prefix REJECT_ -o reject.json
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
    for c in node.children:
        yield from walk(c)


def parse_int(text: str):
    t = text.strip().rstrip("uUlL")
    try:
        return int(t, 0)
    except ValueError:
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


def extract(path: Path, prefix: str):
    code = path.read_bytes()
    tree = Parser(CPP).parse(code)

    spec = {
        "_note": "Generated from Dogecoin Core. Core is the source of truth. "
                 "Do not hand-edit.",
        "_provenance": provenance(path),
        "_prefix": prefix,
        "constants": [],     # [{name, value, type}]
        "_unparsed": [],
    }

    seen = {}
    for node in walk(tree.root_node):
        if node.type != "declaration":
            continue
        text = src(node, code)
        # only free-standing static consts, not class members or locals
        if "static" not in text or "const" not in text:
            continue

        type_node = node.child_by_field_name("type")
        ctype = src(type_node, code) if type_node else "?"

        for decl in node.named_children:
            if decl.type != "init_declarator":
                continue
            d = decl.child_by_field_name("declarator")
            v = decl.child_by_field_name("value")
            if d is None or v is None:
                continue
            name = src(d, code)
            if not name.startswith(prefix):
                continue

            vtext = src(v, code)
            val = parse_int(vtext)
            if val is None:
                spec["_unparsed"].append({
                    "name": name, "expr": vtext,
                    "error": "value is not an integer literal"})
                continue

            if name in seen and seen[name] != val:
                spec["_unparsed"].append({
                    "name": name,
                    "error": f"declared twice with different values "
                             f"({seen[name]} then {val})"})
                continue
            if name in seen:
                continue

            seen[name] = val
            spec["constants"].append({"name": name, "value": val,
                                      "type": ctype})

    spec["constants"].sort(key=lambda c: c["value"])
    return spec


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("header", type=Path)
    ap.add_argument("--prefix", required=True,
                    help="only extract names starting with this (e.g. REJECT_)")
    ap.add_argument("-o", "--out", type=Path)
    args = ap.parse_args()

    if not args.header.exists():
        print(f"error: {args.header} not found", file=sys.stderr)
        return 1

    spec = extract(args.header, args.prefix)
    text = json.dumps(spec, indent=2)
    if args.out:
        args.out.write_text(text)
        print(f"wrote {args.out}", file=sys.stderr)
    else:
        print(text)

    prov = spec["_provenance"]
    if prov.get("core_commit"):
        print(f"  core commit: {prov['core_commit'][:12]}", file=sys.stderr)
    print(f"  {args.header.name} sha256: {prov['file_sha256'][:16]}...",
          file=sys.stderr)
    if prov.get("file_dirty"):
        print(f"  !! {args.header.name} has UNCOMMITTED CHANGES", file=sys.stderr)

    n = len(spec["constants"])
    print(f"  {n} constant(s) matching '{args.prefix}', "
          f"{len(spec['_unparsed'])} unparsed", file=sys.stderr)
    if n == 0:
        print(f"  !! no constants matched '{args.prefix}' — wrong header, or "
              f"the naming changed. Not emitting an empty table silently.",
              file=sys.stderr)
        return 2
    for c in spec["constants"]:
        print(f"      0x{c['value']:02x}  {c['name']}", file=sys.stderr)
    for u in spec["_unparsed"]:
        print(f"  !! unparsed: {u['name']}: {u['error']}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
