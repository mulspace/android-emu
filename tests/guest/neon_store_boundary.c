/* SPDX-License-Identifier: Apache-2.0
 * ARM32 standalone regression candidate for overlarge TCG translation blocks.
 * No Android app, account, network, or device API is used.
 */
#include <stdint.h>
#include <stdio.h>
#include <string.h>

#define STORE_BYTES (1024 * 32)
static uint8_t guarded[STORE_BYTES + 128] __attribute__((aligned(64)));
extern void neon_store_block(uint8_t *destination);

/* 1024 guest stores span a complete 4 KiB instruction page. Each interleaving store expands
 * into many software-MMU operations, stressing 16-bit host-offset bookkeeping.
 * Only caller-saved ARM/NEON registers are changed.
 */
__asm__(
    ".text\n"
    ".arm\n"
    ".fpu neon\n"
    ".global neon_store_block\n"
    ".type neon_store_block, %function\n"
    "neon_store_block:\n"
    "vmov.i8 d0, #0x5a\n"
    "vmov.i8 d1, #0x5a\n"
    "vmov.i8 d2, #0x5a\n"
    "vmov.i8 d3, #0x5a\n"
    "b 1f\n"
    ".balign 4096\n"
    "1:\n"
    ".rept 1024\n"
    "vst4.8 {d0-d3}, [r0]!\n"
    ".endr\n"
    "bx lr\n"
    ".size neon_store_block, .-neon_store_block\n"
);

int main(void)
{
    memset(guarded, 0xa5, sizeof(guarded));
    puts("BEGIN neon_store_boundary");
    fflush(stdout);
    neon_store_block(guarded + 64);
    for (unsigned i = 0; i < sizeof(guarded); ++i) {
        uint8_t expected = (i >= 64 && i < STORE_BYTES + 64) ? 0x5a : 0xa5;
        if (guarded[i] != expected) {
            fprintf(stderr, "FAIL byte %u: %02x != %02x\n", i, guarded[i], expected);
            return 1;
        }
    }
    puts("PASS neon_store_boundary: 32768 data bytes and 128 guard bytes");
    return 0;
}
