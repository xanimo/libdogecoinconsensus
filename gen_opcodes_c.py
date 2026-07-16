#!/usr/bin/env python3
"""
gen_opcodes_c.py — emit opcode tables from opcodes.json.

Generates:
    dogecoin_opcodes.h   enum + name/byte lookup API
    dogecoin_opcodes.c   tables
    test_opcodes.c       generated round-trip and alias tests

The alias problem, stated plainly:

    OP_0 = 0x00,  OP_FALSE = OP_0        -> two names, one byte
    OP_1 = 0x51,  OP_TRUE  = OP_1
    OP_CHECKLOCKTIMEVERIFY = 0xb1,  OP_NOP2 = OP_CHECKLOCKTIMEVERIFY

name -> byte is a function. byte -> name is NOT: it needs a canonical choice.
Silently letting the last declaration win is how you end up printing
"OP_NOP2" for 0xb1 in a disassembler, which is technically true and useless.

Policy: the FIRST declaration in Core's enum is canonical; later ones are
aliases. That matches Core's own GetOpName(), which returns the primary
spelling. Aliases still resolve in name->byte lookups, so both directions work
and neither is a guess.

Usage:
    ./gen_opcodes_c.py opcodes.json -o outdir/
"""

import argparse
import json
import sys
from pathlib import Path


def banner(spec, what):
    p = spec.get("_provenance", {})
    return f"""/* {what}
 *
 * GENERATED — DO NOT EDIT. Regenerate with gen_opcodes_c.py.
 *
 * Source of truth: Dogecoin Core, enum {spec.get('_enum', '?')}
 *   commit:          {p.get('core_commit', '?')}
 *   nearest tag:     {p.get('core_describe', '?')}
 *   script.h sha256:
 *     {p.get('file_sha256', '?')}
 *
 * If this file and Core disagree, this file is wrong. Regenerate.
 */
"""


def canonical_map(spec):
    """byte -> canonical name (first declaration wins), and the alias list."""
    canon = {}
    aliases = []
    for op in spec["opcodes"]:
        v = op["value"]
        if "alias_of" in op:
            aliases.append(op)
            continue
        if v not in canon:
            canon[v] = op["name"]
        else:
            # two non-alias declarations sharing a byte: Core shouldn't do this
            aliases.append({**op, "alias_of": canon[v],
                            "_implicit_duplicate": True})
    return canon, aliases


def gen_header(spec):
    ops = spec["opcodes"]
    canon, aliases = canonical_map(spec)

    out = [banner(spec, "dogecoin_opcodes.h — script opcodes"), ""]
    out.append("#ifndef DOGECOIN_OPCODES_H")
    out.append("#define DOGECOIN_OPCODES_H")
    out.append("")
    out.append("#include <stdbool.h>")
    out.append("#include <stddef.h>")
    out.append("#include <stdint.h>")
    out.append("")
    out.append("#ifdef __cplusplus")
    out.append('extern "C" {')
    out.append("#endif")
    out.append("")
    out.append("/* Opcode values, in Core's declaration order.")
    out.append(" * Aliases are included: several names may share a byte")
    out.append(" * (e.g. OP_FALSE == OP_0, OP_NOP2 == OP_CHECKLOCKTIMEVERIFY). */")
    out.append("typedef enum {")
    for op in ops:
        note = f"  /* alias of {op['alias_of']} */" if "alias_of" in op else ""
        out.append(f"    DOGECOIN_{op['name']} = 0x{op['value']:02x},{note}")
    out.append("} dogecoin_opcode;")
    out.append("")
    out.append("/* Canonical name for a byte, e.g. 0xb1 -> \"OP_CHECKLOCKTIMEVERIFY\".")
    out.append(" *")
    out.append(" * Canonical = FIRST declaration in Core's enum, matching Core's")
    out.append(" * GetOpName(). Aliases are NOT returned here — 0xb1 is")
    out.append(" * OP_CHECKLOCKTIMEVERIFY, never OP_NOP2.")
    out.append(" *")
    out.append(" * Returns NULL for bytes with no name. Note bytes 0x01-0x4b are")
    out.append(" * direct-push lengths, not named opcodes; they return NULL. */")
    out.append("const char *dogecoin_opcode_name(uint8_t op);")
    out.append("")
    out.append("/* Byte for a name. Accepts aliases: both \"OP_0\" and \"OP_FALSE\"")
    out.append(" * resolve to 0x00. Returns false if unknown. */")
    out.append("bool dogecoin_opcode_from_name(const char *name, uint8_t *out);")
    out.append("")
    out.append("/* True if `op` is a data push whose length is the opcode itself")
    out.append(" * (0x01..0x4b). These have no name. */")
    out.append("bool dogecoin_opcode_is_direct_push(uint8_t op);")
    out.append("")
    out.append("#ifdef __cplusplus")
    out.append("}")
    out.append("#endif")
    out.append("")
    out.append("#endif /* DOGECOIN_OPCODES_H */")
    return "\n".join(out) + "\n"


def gen_impl(spec):
    ops = spec["opcodes"]
    canon, aliases = canonical_map(spec)

    out = [banner(spec, "dogecoin_opcodes.c — generated opcode tables"), ""]
    out.append('#include "dogecoin_opcodes.h"')
    out.append("#include <string.h>")
    out.append("")
    out.append("/* byte -> canonical name. Sparse: most bytes have no opcode name.")
    out.append(" * Indexed directly by the byte; 256 pointers is 2KB on 64-bit,")
    out.append(" * which buys O(1) lookup with no search. */")
    out.append("static const char *const k_names[256] = {")
    for v in sorted(canon):
        out.append(f'    [0x{v:02x}] = "{canon[v]}",')
    out.append("};")
    out.append("")
    out.append("/* name -> byte, INCLUDING aliases. Sorted by name so lookup can")
    out.append(" * binary-search rather than scan. */")
    out.append("static const struct { const char *name; uint8_t value; } k_by_name[] = {")
    for op in sorted(ops, key=lambda o: o["name"]):
        note = "  /* alias */" if "alias_of" in op else ""
        out.append(f'    {{ "{op["name"]}", 0x{op["value"]:02x} }},{note}')
    out.append("};")
    out.append("")
    out.append("const char *dogecoin_opcode_name(uint8_t op)")
    out.append("{")
    out.append("    return k_names[op];")
    out.append("}")
    out.append("")
    out.append("bool dogecoin_opcode_is_direct_push(uint8_t op)")
    out.append("{")
    out.append("    /* 0x01..0x4b push that many bytes; the opcode IS the length. */")
    out.append("    return op >= 0x01 && op <= 0x4b;")
    out.append("}")
    out.append("")
    out.append("bool dogecoin_opcode_from_name(const char *name, uint8_t *out)")
    out.append("{")
    out.append("    if (!name) return false;")
    out.append("    size_t lo = 0, hi = sizeof(k_by_name) / sizeof(k_by_name[0]);")
    out.append("    while (lo < hi) {")
    out.append("        size_t mid = lo + (hi - lo) / 2;")
    out.append("        int c = strcmp(k_by_name[mid].name, name);")
    out.append("        if (c == 0) {")
    out.append("            if (out) *out = k_by_name[mid].value;")
    out.append("            return true;")
    out.append("        }")
    out.append("        if (c < 0) lo = mid + 1;")
    out.append("        else hi = mid;")
    out.append("    }")
    out.append("    return false;")
    out.append("}")
    return "\n".join(out) + "\n"


def gen_tests(spec):
    ops = spec["opcodes"]
    canon, aliases = canonical_map(spec)

    out = [banner(spec, "test_opcodes.c — generated"), ""]
    out.append('#include "dogecoin_opcodes.h"')
    out.append("#include <stdio.h>")
    out.append("#include <string.h>")
    out.append("")
    out.append("static int failures = 0;")
    out.append("")
    out.append("static void ck_name(uint8_t op, const char *want)")
    out.append("{")
    out.append("    const char *got = dogecoin_opcode_name(op);")
    out.append("    int ok = got && strcmp(got, want) == 0;")
    out.append("    if (!ok) {")
    out.append('        printf("  FAIL name(0x%02x): want %s got %s\\n",')
    out.append('               op, want, got ? got : "(null)");')
    out.append("        failures++;")
    out.append("    }")
    out.append("}")
    out.append("")
    out.append("static void ck_from(const char *name, uint8_t want)")
    out.append("{")
    out.append("    uint8_t got = 0;")
    out.append("    if (!dogecoin_opcode_from_name(name, &got) || got != want) {")
    out.append('        printf("  FAIL from_name(%s): want 0x%02x got 0x%02x\\n",')
    out.append("               name, want, got);")
    out.append("        failures++;")
    out.append("    }")
    out.append("}")
    out.append("")
    out.append("int main(void)")
    out.append("{")
    out.append(f'    printf("opcode tests ({len(ops)} enumerators, '
               f'{len(canon)} distinct, {len(aliases)} aliases)\\n");')
    out.append("")
    out.append("    /* every name resolves to its byte, aliases included */")
    for op in ops:
        out.append(f'    ck_from("{op["name"]}", 0x{op["value"]:02x});')
    out.append("")
    out.append("    /* canonical name per byte: first declaration wins */")
    for v in sorted(canon):
        out.append(f'    ck_name(0x{v:02x}, "{canon[v]}");')

    if aliases:
        out.append("")
        out.append("    /* aliases resolve, but are NOT the canonical name */")
        for a in aliases:
            v = a["value"]
            out.append(f'    ck_from("{a["name"]}", 0x{v:02x});')
            out.append(f'    if (strcmp(dogecoin_opcode_name(0x{v:02x}), '
                       f'"{a["name"]}") == 0) {{')
            out.append(f'        printf("  FAIL 0x{v:02x} canonical name is the '
                       f'alias {a["name"]}, want {canon.get(v, "?")}\\n");')
            out.append("        failures++;")
            out.append("    }")

    out.append("")
    out.append("    /* direct pushes 0x01..0x4b have no name */")
    out.append("    for (int i = 0x01; i <= 0x4b; i++) {")
    out.append("        if (!dogecoin_opcode_is_direct_push((uint8_t)i)) {")
    out.append('            printf("  FAIL 0x%02x should be a direct push\\n", i);')
    out.append("            failures++;")
    out.append("        }")
    out.append("        if (dogecoin_opcode_name((uint8_t)i) != NULL) {")
    out.append('            printf("  FAIL 0x%02x is a direct push but has name %s\\n",')
    out.append("                   i, dogecoin_opcode_name((uint8_t)i));")
    out.append("            failures++;")
    out.append("        }")
    out.append("    }")
    out.append("")
    out.append("    /* unknown name must fail, not crash */")
    out.append("    uint8_t dummy;")
    out.append('    if (dogecoin_opcode_from_name("OP_NOT_A_REAL_OPCODE", &dummy)) {')
    out.append('        printf("  FAIL unknown name resolved\\n"); failures++;')
    out.append("    }")
    out.append("    if (dogecoin_opcode_from_name(NULL, &dummy)) {")
    out.append('        printf("  FAIL NULL name resolved\\n"); failures++;')
    out.append("    }")
    out.append("")
    out.append('    printf("%s: %d failure(s)\\n", failures ? "FAILED" : "OK", failures);')
    out.append("    return failures ? 1 : 0;")
    out.append("}")
    return "\n".join(out) + "\n"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("spec", type=Path)
    ap.add_argument("-o", "--outdir", type=Path, default=Path("."))
    args = ap.parse_args()

    spec = json.loads(args.spec.read_text())

    if not spec.get("opcodes"):
        print("error: spec has no opcodes", file=sys.stderr)
        return 2
    if spec.get("_unparsed"):
        print(f"error: spec has {len(spec['_unparsed'])} unparsed enumerator(s). "
              "Refusing to generate an incomplete opcode table.", file=sys.stderr)
        for u in spec["_unparsed"]:
            print(f"       {u.get('name')}: {u.get('error')}", file=sys.stderr)
        return 2

    args.outdir.mkdir(parents=True, exist_ok=True)
    for name, text in {
        "dogecoin_opcodes.h": gen_header(spec),
        "dogecoin_opcodes.c": gen_impl(spec),
        "test_opcodes.c": gen_tests(spec),
    }.items():
        (args.outdir / name).write_text(text)
        print(f"wrote {args.outdir / name}", file=sys.stderr)

    canon, aliases = canonical_map(spec)
    print(f"  {len(spec['opcodes'])} enumerators, {len(canon)} distinct bytes, "
          f"{len(aliases)} alias(es)", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
