/* SPDX-License-Identifier: GPL-3.0-or-later */
/* Ordinary disk multicall executable; no private resident symbol imports. */
#include <string.h>
#include "udeks/program.h"
#include "udeks/capability.h"
#include "udeks/service.h"
#include "udeks/z80_worker.h"
#include "udeks/service_control.h"
#define H ((volatile unsigned char *)UDEKS_CAPABILITY_STATUS_BASE)
#define M ((volatile unsigned char *)UDEKS_SERVICE_STATUS_BASE)
#define W ((volatile unsigned char *)UDEKS_Z80_WORKER_STATUS_BASE)
#define P ((volatile unsigned char *)(UDEKS_TASK_REQUEST_BASE + UDEKS_TREQ_PAYLOAD))
unsigned char __fastcall__ file_request(unsigned char, unsigned char, unsigned char);
static void out(const char *s) { udeks_write(1, (const unsigned char *)s); }
static void number(unsigned int n)
{
    unsigned char digits[5], count = 0;
    do { digits[count++] = '0' + n % 10u; n /= 10u; } while (n);
    while (count) udeks_write_byte(1, digits[--count]);
}
static unsigned char fail(const char *s)
{
    udeks_write(2, (const unsigned char *)s); return 1;
}
unsigned char udeks_program_main(unsigned char argc, unsigned char **argv)
{
    const unsigned char *name, *s;
    unsigned char kind;
    name = s = argv[0];
    while (*s) if (*s++ == '/') name = s;
    kind = name[0] | 32u;
    if (kind == 'u') {
        if (argc == 1) out("UDEKS\n");
        else if (argc == 2 && !strcmp((const char *)argv[1], "-a")) out("UDEKS 0.1.0 c128 8502\n");
        else return fail("usage: uname [-a]\n");
    } else if (kind == 'z') {
        if (argc == 2 && !strcmp((const char *)argv[1], "test")) {
            P[0] = UDEKS_CONTROL_ENGINE; P[1] = UDEKS_CONTROL_TEST; P[2] = 0;
            if (file_request(UDEKS_TREQ_OP_CONTROL, 0, 3) != 1)
                return fail("z80ctl: request failed\n");
        } else if (argc == 1 || (argc == 2 && !strcmp((const char *)argv[1], "status"))) {
            out(W[5] == UDEKS_Z80_WORKER_READY ? "State: ready\n" : "State: offline\n");
            out("Transactions: "); number(W[12] | ((unsigned int)W[13] << 8)); out("\n");
        } else return fail("usage: z80ctl [status|test]\n");
    } else {
        if (argc != 1) return fail("usage: lshw | lsmod | lscpu\n");
        kind = name[2] | 32u;
        if (kind == 'h') {
            out(H[7] == UDEKS_VIDEO_PAL ? "Video: PAL, VDC " : "Video: NTSC, VDC ");
            out(H[9] == UDEKS_VDC_FAMILY_8568 ? "8568, " : "8563, "); number(H[10]); out(" KB\n");
            out("Expansion: REU "); out(H[12] ? "present" : "absent");
            out(", GeoRAM "); out(H[13] ? "present\n" : "absent\n");
        } else if (kind == 'm') {
            out("Modules: "); number(M[8]); out("/"); number(M[17]); out(" resident\nPoll passes: ");
            number(M[18] | ((unsigned int)M[19] << 8)); out("\n");
        } else {
            out("8502: resident executive\n");
            out(W[5] == UDEKS_Z80_WORKER_READY ? "Z80: bounded worker; ready (stock timing)\n" : "Z80: worker offline\n");
        }
    }
    return 0;
}
