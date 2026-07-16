#!/usr/bin/env python3
"""
gen_constants_c.py — emit C tables from a constants spec (extract_constants.py).

Used for rejection codes. Kept generic rather than reject-specific: it's the
same shape for any `static const` family Core defines, and a second copy of
this file with s/reject/foo/ is how generators drift apart.

Usage:
    ./gen_constants_c.py reject.json -o outdir/ \\
        --name reject --title "P2P reject message codes"
"""

import argparse
import json
import re
import sys
from pathlib import Path


def banner(spec, what):
    p = spec.get("_provenance", {})
    return f"""/* {what}
 *
 * GENERATED — DO NOT EDIT. Regenerate with gen_constants_c.py.
 *
 * Source of truth: Dogecoin Core
 *   commit:      {p.get('core_commit', '?')}
 *   nearest tag: {p.get('core_describe', '?')}
 *   source:      {p.get('source', '?')}
 *   sha256:
 *     {p.get('file_sha256', '?')}
 *
 * If this file and Core disagree, this file is wrong. Regenerate.
 */
"""


def short(name, prefix):
    """REJECT_MALFORMED -> MALFORMED"""
    return name[len(prefix):] if name.startswith(prefix) else name


def canonical(spec):
    """value -> canonical name, first declaration wins; plus duplicates.

    Distinct constants CAN share a value (Core has no rule against it). A
    reverse map must therefore pick one; we record the collisions rather than
    letting the last silently win."""
    canon, dups = {}, []
    for c in spec["constants"]:
        v = c["value"]
        if v in canon:
            dups.append({**c, "collides_with": canon[v]})
        else:
            canon[v] = c["name"]
    return canon, dups


def gen_header(spec, name, title):
    prefix = spec["_prefix"]
    up = name.upper()
    consts = spec["constants"]
    canon, dups = canonical(spec)

    out = [banner(spec, f"dogecoin_{name}.h — {title}"), ""]
    out.append(f"#ifndef DOGECOIN_{up}_H")
    out.append(f"#define DOGECOIN_{up}_H")
    out.append("")
    out.append("#include <stdbool.h>")
    out.append("#include <stddef.h>")
    out.append("#include <stdint.h>")
    out.append("")
    out.append("#ifdef __cplusplus")
    out.append('extern "C" {')
    out.append("#endif")
    out.append("")
    out.append(f"/* {title}. Values are Core's. */")
    out.append("typedef enum {")
    for c in consts:
        # Keep the family in the identifier: DOGECOIN_REJECT_INVALID, not
        # DOGECOIN_INVALID. Stripping the prefix loses what family a code
        # belongs to and invites collisions with any other constant family.
        out.append(f"    DOGECOIN_{c['name']} = 0x{c['value']:02x},")
    out.append(f"}} dogecoin_{name}_code;")
    out.append("")
    if dups:
        out.append("/* NOTE: these values are shared by more than one constant;")
        out.append(" * the name lookup returns the first declared:")
        for d in dups:
            out.append(f" *   {d['name']} == {d['collides_with']} "
                       f"(0x{d['value']:02x})")
        out.append(" */")
        out.append("")
    out.append(f"/* Name for a code, e.g. 0x10 -> \"{consts[0]['name'] if consts else '?'}\"-style.")
    out.append(" * Returns NULL if the code has no name. */")
    out.append(f"const char *dogecoin_{name}_name(uint8_t code);")
    out.append("")
    out.append("/* Code for a name. Accepts the full Core spelling")
    out.append(f" * (e.g. \"{consts[0]['name'] if consts else 'X'}\"). Returns false if unknown. */")
    out.append(f"bool dogecoin_{name}_from_name(const char *name, uint8_t *out);")
    out.append("")
    out.append("#ifdef __cplusplus")
    out.append("}")
    out.append("#endif")
    out.append("")
    out.append(f"#endif /* DOGECOIN_{up}_H */")
    return "\n".join(out) + "\n"


def gen_impl(spec, name, title):
    consts = spec["constants"]
    canon, _ = canonical(spec)

    out = [banner(spec, f"dogecoin_{name}.c — generated"), ""]
    out.append(f'#include "dogecoin_{name}.h"')
    out.append("#include <string.h>")
    out.append("")
    out.append("/* code -> canonical name. Sparse; indexed by the byte. */")
    out.append("static const char *const k_names[256] = {")
    for v in sorted(canon):
        out.append(f'    [0x{v:02x}] = "{canon[v]}",')
    out.append("};")
    out.append("")
    out.append("/* name -> code, sorted for binary search. */")
    out.append("static const struct { const char *name; uint8_t value; } k_by_name[] = {")
    for c in sorted(consts, key=lambda c: c["name"]):
        out.append(f'    {{ "{c["name"]}", 0x{c["value"]:02x} }},')
    out.append("};")
    out.append("")
    out.append(f"const char *dogecoin_{name}_name(uint8_t code)")
    out.append("{")
    out.append("    return k_names[code];")
    out.append("}")
    out.append("")
    out.append(f"bool dogecoin_{name}_from_name(const char *n, uint8_t *out)")
    out.append("{")
    out.append("    if (!n) return false;")
    out.append("    size_t lo = 0, hi = sizeof(k_by_name) / sizeof(k_by_name[0]);")
    out.append("    while (lo < hi) {")
    out.append("        size_t mid = lo + (hi - lo) / 2;")
    out.append("        int c = strcmp(k_by_name[mid].name, n);")
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


def gen_tests(spec, name, title):
    prefix = spec["_prefix"]
    consts = spec["constants"]
    canon, dups = canonical(spec)

    out = [banner(spec, f"test_{name}.c — generated"), ""]
    out.append(f'#include "dogecoin_{name}.h"')
    out.append("#include <stdio.h>")
    out.append("#include <string.h>")
    out.append("")
    out.append("static int failures = 0;")
    out.append("")
    out.append("int main(void)")
    out.append("{")
    out.append(f'    printf("{name} tests ({len(consts)} constants)\\n");')
    out.append("")
    out.append("    /* enum value matches Core */")
    for c in consts:
        out.append(f"    if (DOGECOIN_{c['name']} != 0x{c['value']:02x}) {{")
        out.append(f'        printf("  FAIL DOGECOIN_{c["name"]} != '
                   f'0x{c["value"]:02x}\\n");')
        out.append("        failures++;")
        out.append("    }")
    out.append("")
    out.append("    /* name -> code round trip */")
    for c in consts:
        out.append("    {")
        out.append("        uint8_t v = 0;")
        out.append(f'        if (!dogecoin_{name}_from_name("{c["name"]}", &v) '
                   f'|| v != 0x{c["value"]:02x}) {{')
        out.append(f'            printf("  FAIL from_name({c["name"]}) -> 0x%02x, '
                   f'want 0x{c["value"]:02x}\\n", v);')
        out.append("            failures++;")
        out.append("        }")
        out.append("    }")
    out.append("")
    out.append("    /* code -> name */")
    for v in sorted(canon):
        out.append(f'    if (!dogecoin_{name}_name(0x{v:02x}) || '
                   f'strcmp(dogecoin_{name}_name(0x{v:02x}), "{canon[v]}") != 0) {{')
        out.append(f'        printf("  FAIL name(0x{v:02x}) != {canon[v]}\\n");')
        out.append("        failures++;")
        out.append("    }")
    out.append("")
    out.append("    /* unknown must fail, not crash */")
    out.append("    uint8_t d;")
    out.append(f'    if (dogecoin_{name}_from_name("{prefix}NOT_REAL", &d)) {{')
    out.append('        printf("  FAIL unknown name resolved\\n"); failures++;')
    out.append("    }")
    out.append(f"    if (dogecoin_{name}_from_name(NULL, &d)) {{")
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
    ap.add_argument("--name", required=True, help="C identifier stem, e.g. 'reject'")
    ap.add_argument("--title", default="constants", help="human description")
    args = ap.parse_args()

    if not re.fullmatch(r"[a-z][a-z0-9_]*", args.name):
        print("error: --name must be a lowercase C identifier", file=sys.stderr)
        return 2

    spec = json.loads(args.spec.read_text())

    if not spec.get("constants"):
        print("error: spec has no constants", file=sys.stderr)
        return 2
    if spec.get("_unparsed"):
        print(f"error: spec has {len(spec['_unparsed'])} unparsed constant(s). "
              "Refusing to generate an incomplete table.", file=sys.stderr)
        for u in spec["_unparsed"]:
            print(f"       {u.get('name')}: {u.get('error')}", file=sys.stderr)
        return 2

    args.outdir.mkdir(parents=True, exist_ok=True)
    for fname, text in {
        f"dogecoin_{args.name}.h": gen_header(spec, args.name, args.title),
        f"dogecoin_{args.name}.c": gen_impl(spec, args.name, args.title),
        f"test_{args.name}.c": gen_tests(spec, args.name, args.title),
    }.items():
        (args.outdir / fname).write_text(text)
        print(f"wrote {args.outdir / fname}", file=sys.stderr)

    canon, dups = canonical(spec)
    print(f"  {len(spec['constants'])} constant(s), {len(canon)} distinct value(s)"
          + (f", {len(dups)} collision(s)" if dups else ""), file=sys.stderr)
    for d in dups:
        print(f"      {d['name']} == {d['collides_with']} (0x{d['value']:02x})",
              file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
