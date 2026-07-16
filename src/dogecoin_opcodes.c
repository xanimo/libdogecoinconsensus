/* dogecoin_opcodes.c — generated opcode tables
 *
 * GENERATED — DO NOT EDIT. Regenerate with gen_opcodes_c.py.
 *
 * Source of truth: Dogecoin Core, enum opcodetype
 *   commit:          699f62ccba4e9c886a44d578c3923b4e14ef0a08
 *   nearest tag:     v1.14.7-239-g699f62ccba
 *   script.h sha256:
 *     ad612f17b44361d08992558108a7a4f43d177c7b171137dbc37cdaeb31739591
 *
 * If this file and Core disagree, this file is wrong. Regenerate.
 */


#include "dogecoin_opcodes.h"
#include <string.h>

/* byte -> canonical name. Sparse: most bytes have no opcode name.
 * Indexed directly by the byte; 256 pointers is 2KB on 64-bit,
 * which buys O(1) lookup with no search. */
static const char *const k_names[256] = {
    [0x00] = "OP_0",
    [0x4c] = "OP_PUSHDATA1",
    [0x4d] = "OP_PUSHDATA2",
    [0x4e] = "OP_PUSHDATA4",
    [0x4f] = "OP_1NEGATE",
    [0x50] = "OP_RESERVED",
    [0x51] = "OP_1",
    [0x52] = "OP_2",
    [0x53] = "OP_3",
    [0x54] = "OP_4",
    [0x55] = "OP_5",
    [0x56] = "OP_6",
    [0x57] = "OP_7",
    [0x58] = "OP_8",
    [0x59] = "OP_9",
    [0x5a] = "OP_10",
    [0x5b] = "OP_11",
    [0x5c] = "OP_12",
    [0x5d] = "OP_13",
    [0x5e] = "OP_14",
    [0x5f] = "OP_15",
    [0x60] = "OP_16",
    [0x61] = "OP_NOP",
    [0x62] = "OP_VER",
    [0x63] = "OP_IF",
    [0x64] = "OP_NOTIF",
    [0x65] = "OP_VERIF",
    [0x66] = "OP_VERNOTIF",
    [0x67] = "OP_ELSE",
    [0x68] = "OP_ENDIF",
    [0x69] = "OP_VERIFY",
    [0x6a] = "OP_RETURN",
    [0x6b] = "OP_TOALTSTACK",
    [0x6c] = "OP_FROMALTSTACK",
    [0x6d] = "OP_2DROP",
    [0x6e] = "OP_2DUP",
    [0x6f] = "OP_3DUP",
    [0x70] = "OP_2OVER",
    [0x71] = "OP_2ROT",
    [0x72] = "OP_2SWAP",
    [0x73] = "OP_IFDUP",
    [0x74] = "OP_DEPTH",
    [0x75] = "OP_DROP",
    [0x76] = "OP_DUP",
    [0x77] = "OP_NIP",
    [0x78] = "OP_OVER",
    [0x79] = "OP_PICK",
    [0x7a] = "OP_ROLL",
    [0x7b] = "OP_ROT",
    [0x7c] = "OP_SWAP",
    [0x7d] = "OP_TUCK",
    [0x7e] = "OP_CAT",
    [0x7f] = "OP_SUBSTR",
    [0x80] = "OP_LEFT",
    [0x81] = "OP_RIGHT",
    [0x82] = "OP_SIZE",
    [0x83] = "OP_INVERT",
    [0x84] = "OP_AND",
    [0x85] = "OP_OR",
    [0x86] = "OP_XOR",
    [0x87] = "OP_EQUAL",
    [0x88] = "OP_EQUALVERIFY",
    [0x89] = "OP_RESERVED1",
    [0x8a] = "OP_RESERVED2",
    [0x8b] = "OP_1ADD",
    [0x8c] = "OP_1SUB",
    [0x8d] = "OP_2MUL",
    [0x8e] = "OP_2DIV",
    [0x8f] = "OP_NEGATE",
    [0x90] = "OP_ABS",
    [0x91] = "OP_NOT",
    [0x92] = "OP_0NOTEQUAL",
    [0x93] = "OP_ADD",
    [0x94] = "OP_SUB",
    [0x95] = "OP_MUL",
    [0x96] = "OP_DIV",
    [0x97] = "OP_MOD",
    [0x98] = "OP_LSHIFT",
    [0x99] = "OP_RSHIFT",
    [0x9a] = "OP_BOOLAND",
    [0x9b] = "OP_BOOLOR",
    [0x9c] = "OP_NUMEQUAL",
    [0x9d] = "OP_NUMEQUALVERIFY",
    [0x9e] = "OP_NUMNOTEQUAL",
    [0x9f] = "OP_LESSTHAN",
    [0xa0] = "OP_GREATERTHAN",
    [0xa1] = "OP_LESSTHANOREQUAL",
    [0xa2] = "OP_GREATERTHANOREQUAL",
    [0xa3] = "OP_MIN",
    [0xa4] = "OP_MAX",
    [0xa5] = "OP_WITHIN",
    [0xa6] = "OP_RIPEMD160",
    [0xa7] = "OP_SHA1",
    [0xa8] = "OP_SHA256",
    [0xa9] = "OP_HASH160",
    [0xaa] = "OP_HASH256",
    [0xab] = "OP_CODESEPARATOR",
    [0xac] = "OP_CHECKSIG",
    [0xad] = "OP_CHECKSIGVERIFY",
    [0xae] = "OP_CHECKMULTISIG",
    [0xaf] = "OP_CHECKMULTISIGVERIFY",
    [0xb0] = "OP_NOP1",
    [0xb1] = "OP_CHECKLOCKTIMEVERIFY",
    [0xb2] = "OP_CHECKSEQUENCEVERIFY",
    [0xb3] = "OP_NOP4",
    [0xb4] = "OP_NOP5",
    [0xb5] = "OP_NOP6",
    [0xb6] = "OP_NOP7",
    [0xb7] = "OP_NOP8",
    [0xb8] = "OP_NOP9",
    [0xb9] = "OP_NOP10",
    [0xfa] = "OP_SMALLINTEGER",
    [0xfb] = "OP_PUBKEYS",
    [0xfd] = "OP_PUBKEYHASH",
    [0xfe] = "OP_PUBKEY",
    [0xff] = "OP_INVALIDOPCODE",
};

/* name -> byte, INCLUDING aliases. Sorted by name so lookup can
 * binary-search rather than scan. */
static const struct { const char *name; uint8_t value; } k_by_name[] = {
    { "OP_0", 0x00 },
    { "OP_0NOTEQUAL", 0x92 },
    { "OP_1", 0x51 },
    { "OP_10", 0x5a },
    { "OP_11", 0x5b },
    { "OP_12", 0x5c },
    { "OP_13", 0x5d },
    { "OP_14", 0x5e },
    { "OP_15", 0x5f },
    { "OP_16", 0x60 },
    { "OP_1ADD", 0x8b },
    { "OP_1NEGATE", 0x4f },
    { "OP_1SUB", 0x8c },
    { "OP_2", 0x52 },
    { "OP_2DIV", 0x8e },
    { "OP_2DROP", 0x6d },
    { "OP_2DUP", 0x6e },
    { "OP_2MUL", 0x8d },
    { "OP_2OVER", 0x70 },
    { "OP_2ROT", 0x71 },
    { "OP_2SWAP", 0x72 },
    { "OP_3", 0x53 },
    { "OP_3DUP", 0x6f },
    { "OP_4", 0x54 },
    { "OP_5", 0x55 },
    { "OP_6", 0x56 },
    { "OP_7", 0x57 },
    { "OP_8", 0x58 },
    { "OP_9", 0x59 },
    { "OP_ABS", 0x90 },
    { "OP_ADD", 0x93 },
    { "OP_AND", 0x84 },
    { "OP_BOOLAND", 0x9a },
    { "OP_BOOLOR", 0x9b },
    { "OP_CAT", 0x7e },
    { "OP_CHECKLOCKTIMEVERIFY", 0xb1 },
    { "OP_CHECKMULTISIG", 0xae },
    { "OP_CHECKMULTISIGVERIFY", 0xaf },
    { "OP_CHECKSEQUENCEVERIFY", 0xb2 },
    { "OP_CHECKSIG", 0xac },
    { "OP_CHECKSIGVERIFY", 0xad },
    { "OP_CODESEPARATOR", 0xab },
    { "OP_DEPTH", 0x74 },
    { "OP_DIV", 0x96 },
    { "OP_DROP", 0x75 },
    { "OP_DUP", 0x76 },
    { "OP_ELSE", 0x67 },
    { "OP_ENDIF", 0x68 },
    { "OP_EQUAL", 0x87 },
    { "OP_EQUALVERIFY", 0x88 },
    { "OP_FALSE", 0x00 },  /* alias */
    { "OP_FROMALTSTACK", 0x6c },
    { "OP_GREATERTHAN", 0xa0 },
    { "OP_GREATERTHANOREQUAL", 0xa2 },
    { "OP_HASH160", 0xa9 },
    { "OP_HASH256", 0xaa },
    { "OP_IF", 0x63 },
    { "OP_IFDUP", 0x73 },
    { "OP_INVALIDOPCODE", 0xff },
    { "OP_INVERT", 0x83 },
    { "OP_LEFT", 0x80 },
    { "OP_LESSTHAN", 0x9f },
    { "OP_LESSTHANOREQUAL", 0xa1 },
    { "OP_LSHIFT", 0x98 },
    { "OP_MAX", 0xa4 },
    { "OP_MIN", 0xa3 },
    { "OP_MOD", 0x97 },
    { "OP_MUL", 0x95 },
    { "OP_NEGATE", 0x8f },
    { "OP_NIP", 0x77 },
    { "OP_NOP", 0x61 },
    { "OP_NOP1", 0xb0 },
    { "OP_NOP10", 0xb9 },
    { "OP_NOP2", 0xb1 },  /* alias */
    { "OP_NOP3", 0xb2 },  /* alias */
    { "OP_NOP4", 0xb3 },
    { "OP_NOP5", 0xb4 },
    { "OP_NOP6", 0xb5 },
    { "OP_NOP7", 0xb6 },
    { "OP_NOP8", 0xb7 },
    { "OP_NOP9", 0xb8 },
    { "OP_NOT", 0x91 },
    { "OP_NOTIF", 0x64 },
    { "OP_NUMEQUAL", 0x9c },
    { "OP_NUMEQUALVERIFY", 0x9d },
    { "OP_NUMNOTEQUAL", 0x9e },
    { "OP_OR", 0x85 },
    { "OP_OVER", 0x78 },
    { "OP_PICK", 0x79 },
    { "OP_PUBKEY", 0xfe },
    { "OP_PUBKEYHASH", 0xfd },
    { "OP_PUBKEYS", 0xfb },
    { "OP_PUSHDATA1", 0x4c },
    { "OP_PUSHDATA2", 0x4d },
    { "OP_PUSHDATA4", 0x4e },
    { "OP_RESERVED", 0x50 },
    { "OP_RESERVED1", 0x89 },
    { "OP_RESERVED2", 0x8a },
    { "OP_RETURN", 0x6a },
    { "OP_RIGHT", 0x81 },
    { "OP_RIPEMD160", 0xa6 },
    { "OP_ROLL", 0x7a },
    { "OP_ROT", 0x7b },
    { "OP_RSHIFT", 0x99 },
    { "OP_SHA1", 0xa7 },
    { "OP_SHA256", 0xa8 },
    { "OP_SIZE", 0x82 },
    { "OP_SMALLINTEGER", 0xfa },
    { "OP_SUB", 0x94 },
    { "OP_SUBSTR", 0x7f },
    { "OP_SWAP", 0x7c },
    { "OP_TOALTSTACK", 0x6b },
    { "OP_TRUE", 0x51 },  /* alias */
    { "OP_TUCK", 0x7d },
    { "OP_VER", 0x62 },
    { "OP_VERIF", 0x65 },
    { "OP_VERIFY", 0x69 },
    { "OP_VERNOTIF", 0x66 },
    { "OP_WITHIN", 0xa5 },
    { "OP_XOR", 0x86 },
};

const char *dogecoin_opcode_name(uint8_t op)
{
    return k_names[op];
}

bool dogecoin_opcode_is_direct_push(uint8_t op)
{
    /* 0x01..0x4b push that many bytes; the opcode IS the length. */
    return op >= 0x01 && op <= 0x4b;
}

bool dogecoin_opcode_from_name(const char *name, uint8_t *out)
{
    if (!name) return false;
    size_t lo = 0, hi = sizeof(k_by_name) / sizeof(k_by_name[0]);
    while (lo < hi) {
        size_t mid = lo + (hi - lo) / 2;
        int c = strcmp(k_by_name[mid].name, name);
        if (c == 0) {
            if (out) *out = k_by_name[mid].value;
            return true;
        }
        if (c < 0) lo = mid + 1;
        else hi = mid;
    }
    return false;
}
