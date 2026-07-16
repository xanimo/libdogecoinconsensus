/* test_opcodes.c — generated
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
#include <stdio.h>
#include <string.h>

static int failures = 0;

static void ck_name(uint8_t op, const char *want)
{
    const char *got = dogecoin_opcode_name(op);
    int ok = got && strcmp(got, want) == 0;
    if (!ok) {
        printf("  FAIL name(0x%02x): want %s got %s\n",
               op, want, got ? got : "(null)");
        failures++;
    }
}

static void ck_from(const char *name, uint8_t want)
{
    uint8_t got = 0;
    if (!dogecoin_opcode_from_name(name, &got) || got != want) {
        printf("  FAIL from_name(%s): want 0x%02x got 0x%02x\n",
               name, want, got);
        failures++;
    }
}

int main(void)
{
    printf("opcode tests (120 enumerators, 116 distinct, 4 aliases)\n");

    /* every name resolves to its byte, aliases included */
    ck_from("OP_0", 0x00);
    ck_from("OP_FALSE", 0x00);
    ck_from("OP_PUSHDATA1", 0x4c);
    ck_from("OP_PUSHDATA2", 0x4d);
    ck_from("OP_PUSHDATA4", 0x4e);
    ck_from("OP_1NEGATE", 0x4f);
    ck_from("OP_RESERVED", 0x50);
    ck_from("OP_1", 0x51);
    ck_from("OP_TRUE", 0x51);
    ck_from("OP_2", 0x52);
    ck_from("OP_3", 0x53);
    ck_from("OP_4", 0x54);
    ck_from("OP_5", 0x55);
    ck_from("OP_6", 0x56);
    ck_from("OP_7", 0x57);
    ck_from("OP_8", 0x58);
    ck_from("OP_9", 0x59);
    ck_from("OP_10", 0x5a);
    ck_from("OP_11", 0x5b);
    ck_from("OP_12", 0x5c);
    ck_from("OP_13", 0x5d);
    ck_from("OP_14", 0x5e);
    ck_from("OP_15", 0x5f);
    ck_from("OP_16", 0x60);
    ck_from("OP_NOP", 0x61);
    ck_from("OP_VER", 0x62);
    ck_from("OP_IF", 0x63);
    ck_from("OP_NOTIF", 0x64);
    ck_from("OP_VERIF", 0x65);
    ck_from("OP_VERNOTIF", 0x66);
    ck_from("OP_ELSE", 0x67);
    ck_from("OP_ENDIF", 0x68);
    ck_from("OP_VERIFY", 0x69);
    ck_from("OP_RETURN", 0x6a);
    ck_from("OP_TOALTSTACK", 0x6b);
    ck_from("OP_FROMALTSTACK", 0x6c);
    ck_from("OP_2DROP", 0x6d);
    ck_from("OP_2DUP", 0x6e);
    ck_from("OP_3DUP", 0x6f);
    ck_from("OP_2OVER", 0x70);
    ck_from("OP_2ROT", 0x71);
    ck_from("OP_2SWAP", 0x72);
    ck_from("OP_IFDUP", 0x73);
    ck_from("OP_DEPTH", 0x74);
    ck_from("OP_DROP", 0x75);
    ck_from("OP_DUP", 0x76);
    ck_from("OP_NIP", 0x77);
    ck_from("OP_OVER", 0x78);
    ck_from("OP_PICK", 0x79);
    ck_from("OP_ROLL", 0x7a);
    ck_from("OP_ROT", 0x7b);
    ck_from("OP_SWAP", 0x7c);
    ck_from("OP_TUCK", 0x7d);
    ck_from("OP_CAT", 0x7e);
    ck_from("OP_SUBSTR", 0x7f);
    ck_from("OP_LEFT", 0x80);
    ck_from("OP_RIGHT", 0x81);
    ck_from("OP_SIZE", 0x82);
    ck_from("OP_INVERT", 0x83);
    ck_from("OP_AND", 0x84);
    ck_from("OP_OR", 0x85);
    ck_from("OP_XOR", 0x86);
    ck_from("OP_EQUAL", 0x87);
    ck_from("OP_EQUALVERIFY", 0x88);
    ck_from("OP_RESERVED1", 0x89);
    ck_from("OP_RESERVED2", 0x8a);
    ck_from("OP_1ADD", 0x8b);
    ck_from("OP_1SUB", 0x8c);
    ck_from("OP_2MUL", 0x8d);
    ck_from("OP_2DIV", 0x8e);
    ck_from("OP_NEGATE", 0x8f);
    ck_from("OP_ABS", 0x90);
    ck_from("OP_NOT", 0x91);
    ck_from("OP_0NOTEQUAL", 0x92);
    ck_from("OP_ADD", 0x93);
    ck_from("OP_SUB", 0x94);
    ck_from("OP_MUL", 0x95);
    ck_from("OP_DIV", 0x96);
    ck_from("OP_MOD", 0x97);
    ck_from("OP_LSHIFT", 0x98);
    ck_from("OP_RSHIFT", 0x99);
    ck_from("OP_BOOLAND", 0x9a);
    ck_from("OP_BOOLOR", 0x9b);
    ck_from("OP_NUMEQUAL", 0x9c);
    ck_from("OP_NUMEQUALVERIFY", 0x9d);
    ck_from("OP_NUMNOTEQUAL", 0x9e);
    ck_from("OP_LESSTHAN", 0x9f);
    ck_from("OP_GREATERTHAN", 0xa0);
    ck_from("OP_LESSTHANOREQUAL", 0xa1);
    ck_from("OP_GREATERTHANOREQUAL", 0xa2);
    ck_from("OP_MIN", 0xa3);
    ck_from("OP_MAX", 0xa4);
    ck_from("OP_WITHIN", 0xa5);
    ck_from("OP_RIPEMD160", 0xa6);
    ck_from("OP_SHA1", 0xa7);
    ck_from("OP_SHA256", 0xa8);
    ck_from("OP_HASH160", 0xa9);
    ck_from("OP_HASH256", 0xaa);
    ck_from("OP_CODESEPARATOR", 0xab);
    ck_from("OP_CHECKSIG", 0xac);
    ck_from("OP_CHECKSIGVERIFY", 0xad);
    ck_from("OP_CHECKMULTISIG", 0xae);
    ck_from("OP_CHECKMULTISIGVERIFY", 0xaf);
    ck_from("OP_NOP1", 0xb0);
    ck_from("OP_CHECKLOCKTIMEVERIFY", 0xb1);
    ck_from("OP_NOP2", 0xb1);
    ck_from("OP_CHECKSEQUENCEVERIFY", 0xb2);
    ck_from("OP_NOP3", 0xb2);
    ck_from("OP_NOP4", 0xb3);
    ck_from("OP_NOP5", 0xb4);
    ck_from("OP_NOP6", 0xb5);
    ck_from("OP_NOP7", 0xb6);
    ck_from("OP_NOP8", 0xb7);
    ck_from("OP_NOP9", 0xb8);
    ck_from("OP_NOP10", 0xb9);
    ck_from("OP_SMALLINTEGER", 0xfa);
    ck_from("OP_PUBKEYS", 0xfb);
    ck_from("OP_PUBKEYHASH", 0xfd);
    ck_from("OP_PUBKEY", 0xfe);
    ck_from("OP_INVALIDOPCODE", 0xff);

    /* canonical name per byte: first declaration wins */
    ck_name(0x00, "OP_0");
    ck_name(0x4c, "OP_PUSHDATA1");
    ck_name(0x4d, "OP_PUSHDATA2");
    ck_name(0x4e, "OP_PUSHDATA4");
    ck_name(0x4f, "OP_1NEGATE");
    ck_name(0x50, "OP_RESERVED");
    ck_name(0x51, "OP_1");
    ck_name(0x52, "OP_2");
    ck_name(0x53, "OP_3");
    ck_name(0x54, "OP_4");
    ck_name(0x55, "OP_5");
    ck_name(0x56, "OP_6");
    ck_name(0x57, "OP_7");
    ck_name(0x58, "OP_8");
    ck_name(0x59, "OP_9");
    ck_name(0x5a, "OP_10");
    ck_name(0x5b, "OP_11");
    ck_name(0x5c, "OP_12");
    ck_name(0x5d, "OP_13");
    ck_name(0x5e, "OP_14");
    ck_name(0x5f, "OP_15");
    ck_name(0x60, "OP_16");
    ck_name(0x61, "OP_NOP");
    ck_name(0x62, "OP_VER");
    ck_name(0x63, "OP_IF");
    ck_name(0x64, "OP_NOTIF");
    ck_name(0x65, "OP_VERIF");
    ck_name(0x66, "OP_VERNOTIF");
    ck_name(0x67, "OP_ELSE");
    ck_name(0x68, "OP_ENDIF");
    ck_name(0x69, "OP_VERIFY");
    ck_name(0x6a, "OP_RETURN");
    ck_name(0x6b, "OP_TOALTSTACK");
    ck_name(0x6c, "OP_FROMALTSTACK");
    ck_name(0x6d, "OP_2DROP");
    ck_name(0x6e, "OP_2DUP");
    ck_name(0x6f, "OP_3DUP");
    ck_name(0x70, "OP_2OVER");
    ck_name(0x71, "OP_2ROT");
    ck_name(0x72, "OP_2SWAP");
    ck_name(0x73, "OP_IFDUP");
    ck_name(0x74, "OP_DEPTH");
    ck_name(0x75, "OP_DROP");
    ck_name(0x76, "OP_DUP");
    ck_name(0x77, "OP_NIP");
    ck_name(0x78, "OP_OVER");
    ck_name(0x79, "OP_PICK");
    ck_name(0x7a, "OP_ROLL");
    ck_name(0x7b, "OP_ROT");
    ck_name(0x7c, "OP_SWAP");
    ck_name(0x7d, "OP_TUCK");
    ck_name(0x7e, "OP_CAT");
    ck_name(0x7f, "OP_SUBSTR");
    ck_name(0x80, "OP_LEFT");
    ck_name(0x81, "OP_RIGHT");
    ck_name(0x82, "OP_SIZE");
    ck_name(0x83, "OP_INVERT");
    ck_name(0x84, "OP_AND");
    ck_name(0x85, "OP_OR");
    ck_name(0x86, "OP_XOR");
    ck_name(0x87, "OP_EQUAL");
    ck_name(0x88, "OP_EQUALVERIFY");
    ck_name(0x89, "OP_RESERVED1");
    ck_name(0x8a, "OP_RESERVED2");
    ck_name(0x8b, "OP_1ADD");
    ck_name(0x8c, "OP_1SUB");
    ck_name(0x8d, "OP_2MUL");
    ck_name(0x8e, "OP_2DIV");
    ck_name(0x8f, "OP_NEGATE");
    ck_name(0x90, "OP_ABS");
    ck_name(0x91, "OP_NOT");
    ck_name(0x92, "OP_0NOTEQUAL");
    ck_name(0x93, "OP_ADD");
    ck_name(0x94, "OP_SUB");
    ck_name(0x95, "OP_MUL");
    ck_name(0x96, "OP_DIV");
    ck_name(0x97, "OP_MOD");
    ck_name(0x98, "OP_LSHIFT");
    ck_name(0x99, "OP_RSHIFT");
    ck_name(0x9a, "OP_BOOLAND");
    ck_name(0x9b, "OP_BOOLOR");
    ck_name(0x9c, "OP_NUMEQUAL");
    ck_name(0x9d, "OP_NUMEQUALVERIFY");
    ck_name(0x9e, "OP_NUMNOTEQUAL");
    ck_name(0x9f, "OP_LESSTHAN");
    ck_name(0xa0, "OP_GREATERTHAN");
    ck_name(0xa1, "OP_LESSTHANOREQUAL");
    ck_name(0xa2, "OP_GREATERTHANOREQUAL");
    ck_name(0xa3, "OP_MIN");
    ck_name(0xa4, "OP_MAX");
    ck_name(0xa5, "OP_WITHIN");
    ck_name(0xa6, "OP_RIPEMD160");
    ck_name(0xa7, "OP_SHA1");
    ck_name(0xa8, "OP_SHA256");
    ck_name(0xa9, "OP_HASH160");
    ck_name(0xaa, "OP_HASH256");
    ck_name(0xab, "OP_CODESEPARATOR");
    ck_name(0xac, "OP_CHECKSIG");
    ck_name(0xad, "OP_CHECKSIGVERIFY");
    ck_name(0xae, "OP_CHECKMULTISIG");
    ck_name(0xaf, "OP_CHECKMULTISIGVERIFY");
    ck_name(0xb0, "OP_NOP1");
    ck_name(0xb1, "OP_CHECKLOCKTIMEVERIFY");
    ck_name(0xb2, "OP_CHECKSEQUENCEVERIFY");
    ck_name(0xb3, "OP_NOP4");
    ck_name(0xb4, "OP_NOP5");
    ck_name(0xb5, "OP_NOP6");
    ck_name(0xb6, "OP_NOP7");
    ck_name(0xb7, "OP_NOP8");
    ck_name(0xb8, "OP_NOP9");
    ck_name(0xb9, "OP_NOP10");
    ck_name(0xfa, "OP_SMALLINTEGER");
    ck_name(0xfb, "OP_PUBKEYS");
    ck_name(0xfd, "OP_PUBKEYHASH");
    ck_name(0xfe, "OP_PUBKEY");
    ck_name(0xff, "OP_INVALIDOPCODE");

    /* aliases resolve, but are NOT the canonical name */
    ck_from("OP_FALSE", 0x00);
    if (strcmp(dogecoin_opcode_name(0x00), "OP_FALSE") == 0) {
        printf("  FAIL 0x00 canonical name is the alias OP_FALSE, want OP_0\n");
        failures++;
    }
    ck_from("OP_TRUE", 0x51);
    if (strcmp(dogecoin_opcode_name(0x51), "OP_TRUE") == 0) {
        printf("  FAIL 0x51 canonical name is the alias OP_TRUE, want OP_1\n");
        failures++;
    }
    ck_from("OP_NOP2", 0xb1);
    if (strcmp(dogecoin_opcode_name(0xb1), "OP_NOP2") == 0) {
        printf("  FAIL 0xb1 canonical name is the alias OP_NOP2, want OP_CHECKLOCKTIMEVERIFY\n");
        failures++;
    }
    ck_from("OP_NOP3", 0xb2);
    if (strcmp(dogecoin_opcode_name(0xb2), "OP_NOP3") == 0) {
        printf("  FAIL 0xb2 canonical name is the alias OP_NOP3, want OP_CHECKSEQUENCEVERIFY\n");
        failures++;
    }

    /* direct pushes 0x01..0x4b have no name */
    for (int i = 0x01; i <= 0x4b; i++) {
        if (!dogecoin_opcode_is_direct_push((uint8_t)i)) {
            printf("  FAIL 0x%02x should be a direct push\n", i);
            failures++;
        }
        if (dogecoin_opcode_name((uint8_t)i) != NULL) {
            printf("  FAIL 0x%02x is a direct push but has name %s\n",
                   i, dogecoin_opcode_name((uint8_t)i));
            failures++;
        }
    }

    /* unknown name must fail, not crash */
    uint8_t dummy;
    if (dogecoin_opcode_from_name("OP_NOT_A_REAL_OPCODE", &dummy)) {
        printf("  FAIL unknown name resolved\n"); failures++;
    }
    if (dogecoin_opcode_from_name(NULL, &dummy)) {
        printf("  FAIL NULL name resolved\n"); failures++;
    }

    printf("%s: %d failure(s)\n", failures ? "FAILED" : "OK", failures);
    return failures ? 1 : 0;
}
