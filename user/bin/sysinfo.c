/* SPDX-License-Identifier: GPL-3.0-or-later */
/* Standalone FREE/DF multicall image. No imports from the resident kernel. */
#include <string.h>
#include "udeks/program.h"
#include "udeks/task_request.h"
#include "udeks/task_state.h"
#include "udeks/capability.h"

#ifdef UDEKS_SYSINFO_HOST_TEST
extern unsigned char sysinfo_payload[24], sysinfo_error;
extern unsigned char sysinfo_tasks[16], sysinfo_capability[32];
#define P sysinfo_payload
#define ERROR sysinfo_error
#define T sysinfo_tasks
#define H sysinfo_capability
#else
#define P ((volatile unsigned char *)(UDEKS_TASK_REQUEST_BASE + UDEKS_TREQ_PAYLOAD))
#define ERROR (*(volatile unsigned char *)(UDEKS_TASK_REQUEST_BASE + UDEKS_TREQ_ERROR))
#define T ((volatile unsigned char *)UDEKS_LIFECYCLE_STATUS_BASE)
#define H ((volatile unsigned char *)UDEKS_CAPABILITY_STATUS_BASE)
#endif
unsigned char __fastcall__ file_request(unsigned char op, unsigned char fd, unsigned char count);

static void out(const char *s) { udeks_write(1, (const unsigned char *)s); }
static unsigned char fail(const char *s)
{
    udeks_write(2, (const unsigned char *)s);
    return 1;
}
static void number(unsigned int value)
{
    static const unsigned int divisors[] = {10000, 1000, 100, 10, 1};
    unsigned char i, digit, started = 0;
    for (i = 0; i != 5; ++i) {
        digit = 0;
        while (value >= divisors[i]) { value -= divisors[i]; ++digit; }
        if (digit || started || i == 4) {
            udeks_write_byte(1, '0'+digit); started = 1;
        }
    }
}
/* KiB from 256-byte (or larger power-of-two) DOS data blocks. */
static unsigned int to_kib(unsigned int blocks, unsigned int blocksize)
{
    if (blocksize == 0u || blocksize > 1024u) return 0u;
    return (unsigned int)(blocks / (1024u / blocksize));
}
unsigned char udeks_program_main(unsigned char argc, unsigned char **argv)
{
    const unsigned char *name, *s;
    unsigned int total, available;
    unsigned char unit, count, i, human = 0;
    name = s = argv[0];
    while (*s) if (*s++ == '/') name = s;
    if ((name[0] | 32u) == 'f') {
        if (argc != 1) return fail("usage: free\n");
        if (T[0] != 'U' || T[1] != 'T' || T[2] != 'S' || T[3] != 'K' ||
            T[4] || T[5] != 2 || T[6] != UDEKS_LIFECYCLE_READY)
            return fail("free: memory accounting unavailable\n");
        out("CPU RAM: 128 KiB; VDC RAM: "); number(H[10]); out(" KiB (video only)\n");
        /* Current scheduler has one child image slot, not a general heap.
         * Zombies retain their allocation until reaped. Do not count the
         * eight lifecycle table entries as eight physical image slots. */
        available = T[UDEKS_UTSK_CHILD_STATE] == UDEKS_LIFECYCLE_STATE_FREE ? 2560u : 0u;
        out("Native child image pool (bytes):\n  total 2560  used ");
        number(2560u-available); out("  free "); number(available);
        out("\nFixed task slot; not total unused physical RAM.\nGeneral heap: not implemented; swap: none.\n");
        return 0;
    }
    if (argc >= 2 && strcmp((const char *)argv[1], "-h") == 0) {
        human = 1; --argc; ++argv;
    }
    if (argc > 2 || (argc == 2 && strcmp((const char *)argv[1], "/mnt") &&
                                  strcmp((const char *)argv[1], "/")))
        return fail("usage: df [-h] [/|/mnt]\n");
    s = (const unsigned char *)"/";
    if (argc == 2) s = argv[1];
    count = strlen((const char *)s);
    for (i = 0; i <= count; ++i) P[i] = s[i];
    if (file_request(UDEKS_TREQ_OP_STATFS, 0, count) != UDEKS_STATFS_SIZE)
        return fail(ERROR == UDEKS_TREQ_ENOENT || ERROR == UDEKS_TREQ_ENODEV ? "df: volume is not mounted\n" :
                    ERROR == UDEKS_TREQ_EBUSY ? "df: filesystem busy\n" : "df: disk read failed\n");
    total = P[2] | ((unsigned int)P[3] << 8);
    available = P[4] | ((unsigned int)P[5] << 8); unit = P[6];
    if (human) {
        unsigned int blocksize = P[0] | ((unsigned int)P[1] << 8);
        out("Filesystem   Size-KiB  Used  Avail  Mounted on\niec");
        number(unit); out("        "); number(to_kib(total, blocksize)); out("      ");
        number(to_kib(total-available, blocksize)); out("   ");
        number(to_kib(available, blocksize)); out("        ");
        out((const char *)s); out("\nRead-only mount; sizes in KiB.\n");
        return 0;
    }
    out("Filesystem  256B-blocks  Used  Available  Mounted on\niec");
    number(unit); out("        "); number(total); out("         ");
    number(total-available); out("   "); number(available); out("        ");
    out((const char *)s); out("\nRead-only mount; DOS data blocks (directory tracks excluded).\n");
    return 0;
}
