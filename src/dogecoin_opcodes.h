/* dogecoin_opcodes.h — script opcodes
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


#ifndef DOGECOIN_OPCODES_H
#define DOGECOIN_OPCODES_H

#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

/* Opcode values, in Core's declaration order.
 * Aliases are included: several names may share a byte
 * (e.g. OP_FALSE == OP_0, OP_NOP2 == OP_CHECKLOCKTIMEVERIFY). */
typedef enum {
    DOGECOIN_OP_0 = 0x00,
    DOGECOIN_OP_FALSE = 0x00,  /* alias of OP_0 */
    DOGECOIN_OP_PUSHDATA1 = 0x4c,
    DOGECOIN_OP_PUSHDATA2 = 0x4d,
    DOGECOIN_OP_PUSHDATA4 = 0x4e,
    DOGECOIN_OP_1NEGATE = 0x4f,
    DOGECOIN_OP_RESERVED = 0x50,
    DOGECOIN_OP_1 = 0x51,
    DOGECOIN_OP_TRUE = 0x51,  /* alias of OP_1 */
    DOGECOIN_OP_2 = 0x52,
    DOGECOIN_OP_3 = 0x53,
    DOGECOIN_OP_4 = 0x54,
    DOGECOIN_OP_5 = 0x55,
    DOGECOIN_OP_6 = 0x56,
    DOGECOIN_OP_7 = 0x57,
    DOGECOIN_OP_8 = 0x58,
    DOGECOIN_OP_9 = 0x59,
    DOGECOIN_OP_10 = 0x5a,
    DOGECOIN_OP_11 = 0x5b,
    DOGECOIN_OP_12 = 0x5c,
    DOGECOIN_OP_13 = 0x5d,
    DOGECOIN_OP_14 = 0x5e,
    DOGECOIN_OP_15 = 0x5f,
    DOGECOIN_OP_16 = 0x60,
    DOGECOIN_OP_NOP = 0x61,
    DOGECOIN_OP_VER = 0x62,
    DOGECOIN_OP_IF = 0x63,
    DOGECOIN_OP_NOTIF = 0x64,
    DOGECOIN_OP_VERIF = 0x65,
    DOGECOIN_OP_VERNOTIF = 0x66,
    DOGECOIN_OP_ELSE = 0x67,
    DOGECOIN_OP_ENDIF = 0x68,
    DOGECOIN_OP_VERIFY = 0x69,
    DOGECOIN_OP_RETURN = 0x6a,
    DOGECOIN_OP_TOALTSTACK = 0x6b,
    DOGECOIN_OP_FROMALTSTACK = 0x6c,
    DOGECOIN_OP_2DROP = 0x6d,
    DOGECOIN_OP_2DUP = 0x6e,
    DOGECOIN_OP_3DUP = 0x6f,
    DOGECOIN_OP_2OVER = 0x70,
    DOGECOIN_OP_2ROT = 0x71,
    DOGECOIN_OP_2SWAP = 0x72,
    DOGECOIN_OP_IFDUP = 0x73,
    DOGECOIN_OP_DEPTH = 0x74,
    DOGECOIN_OP_DROP = 0x75,
    DOGECOIN_OP_DUP = 0x76,
    DOGECOIN_OP_NIP = 0x77,
    DOGECOIN_OP_OVER = 0x78,
    DOGECOIN_OP_PICK = 0x79,
    DOGECOIN_OP_ROLL = 0x7a,
    DOGECOIN_OP_ROT = 0x7b,
    DOGECOIN_OP_SWAP = 0x7c,
    DOGECOIN_OP_TUCK = 0x7d,
    DOGECOIN_OP_CAT = 0x7e,
    DOGECOIN_OP_SUBSTR = 0x7f,
    DOGECOIN_OP_LEFT = 0x80,
    DOGECOIN_OP_RIGHT = 0x81,
    DOGECOIN_OP_SIZE = 0x82,
    DOGECOIN_OP_INVERT = 0x83,
    DOGECOIN_OP_AND = 0x84,
    DOGECOIN_OP_OR = 0x85,
    DOGECOIN_OP_XOR = 0x86,
    DOGECOIN_OP_EQUAL = 0x87,
    DOGECOIN_OP_EQUALVERIFY = 0x88,
    DOGECOIN_OP_RESERVED1 = 0x89,
    DOGECOIN_OP_RESERVED2 = 0x8a,
    DOGECOIN_OP_1ADD = 0x8b,
    DOGECOIN_OP_1SUB = 0x8c,
    DOGECOIN_OP_2MUL = 0x8d,
    DOGECOIN_OP_2DIV = 0x8e,
    DOGECOIN_OP_NEGATE = 0x8f,
    DOGECOIN_OP_ABS = 0x90,
    DOGECOIN_OP_NOT = 0x91,
    DOGECOIN_OP_0NOTEQUAL = 0x92,
    DOGECOIN_OP_ADD = 0x93,
    DOGECOIN_OP_SUB = 0x94,
    DOGECOIN_OP_MUL = 0x95,
    DOGECOIN_OP_DIV = 0x96,
    DOGECOIN_OP_MOD = 0x97,
    DOGECOIN_OP_LSHIFT = 0x98,
    DOGECOIN_OP_RSHIFT = 0x99,
    DOGECOIN_OP_BOOLAND = 0x9a,
    DOGECOIN_OP_BOOLOR = 0x9b,
    DOGECOIN_OP_NUMEQUAL = 0x9c,
    DOGECOIN_OP_NUMEQUALVERIFY = 0x9d,
    DOGECOIN_OP_NUMNOTEQUAL = 0x9e,
    DOGECOIN_OP_LESSTHAN = 0x9f,
    DOGECOIN_OP_GREATERTHAN = 0xa0,
    DOGECOIN_OP_LESSTHANOREQUAL = 0xa1,
    DOGECOIN_OP_GREATERTHANOREQUAL = 0xa2,
    DOGECOIN_OP_MIN = 0xa3,
    DOGECOIN_OP_MAX = 0xa4,
    DOGECOIN_OP_WITHIN = 0xa5,
    DOGECOIN_OP_RIPEMD160 = 0xa6,
    DOGECOIN_OP_SHA1 = 0xa7,
    DOGECOIN_OP_SHA256 = 0xa8,
    DOGECOIN_OP_HASH160 = 0xa9,
    DOGECOIN_OP_HASH256 = 0xaa,
    DOGECOIN_OP_CODESEPARATOR = 0xab,
    DOGECOIN_OP_CHECKSIG = 0xac,
    DOGECOIN_OP_CHECKSIGVERIFY = 0xad,
    DOGECOIN_OP_CHECKMULTISIG = 0xae,
    DOGECOIN_OP_CHECKMULTISIGVERIFY = 0xaf,
    DOGECOIN_OP_NOP1 = 0xb0,
    DOGECOIN_OP_CHECKLOCKTIMEVERIFY = 0xb1,
    DOGECOIN_OP_NOP2 = 0xb1,  /* alias of OP_CHECKLOCKTIMEVERIFY */
    DOGECOIN_OP_CHECKSEQUENCEVERIFY = 0xb2,
    DOGECOIN_OP_NOP3 = 0xb2,  /* alias of OP_CHECKSEQUENCEVERIFY */
    DOGECOIN_OP_NOP4 = 0xb3,
    DOGECOIN_OP_NOP5 = 0xb4,
    DOGECOIN_OP_NOP6 = 0xb5,
    DOGECOIN_OP_NOP7 = 0xb6,
    DOGECOIN_OP_NOP8 = 0xb7,
    DOGECOIN_OP_NOP9 = 0xb8,
    DOGECOIN_OP_NOP10 = 0xb9,
    DOGECOIN_OP_SMALLINTEGER = 0xfa,
    DOGECOIN_OP_PUBKEYS = 0xfb,
    DOGECOIN_OP_PUBKEYHASH = 0xfd,
    DOGECOIN_OP_PUBKEY = 0xfe,
    DOGECOIN_OP_INVALIDOPCODE = 0xff,
} dogecoin_opcode;

/* Canonical name for a byte, e.g. 0xb1 -> "OP_CHECKLOCKTIMEVERIFY".
 *
 * Canonical = FIRST declaration in Core's enum, matching Core's
 * GetOpName(). Aliases are NOT returned here — 0xb1 is
 * OP_CHECKLOCKTIMEVERIFY, never OP_NOP2.
 *
 * Returns NULL for bytes with no name. Note bytes 0x01-0x4b are
 * direct-push lengths, not named opcodes; they return NULL. */
const char *dogecoin_opcode_name(uint8_t op);

/* Byte for a name. Accepts aliases: both "OP_0" and "OP_FALSE"
 * resolve to 0x00. Returns false if unknown. */
bool dogecoin_opcode_from_name(const char *name, uint8_t *out);

/* True if `op` is a data push whose length is the opcode itself
 * (0x01..0x4b). These have no name. */
bool dogecoin_opcode_is_direct_push(uint8_t op);

#ifdef __cplusplus
}
#endif

#endif /* DOGECOIN_OPCODES_H */
