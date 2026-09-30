/* SPDX-License-Identifier: GPL-3.0-or-later */
/* One read-only executable, installed under both mount and umount. */
#include <string.h>
#include "udeks/program.h"
#include "udeks/task_request.h"

unsigned char __fastcall__ udeks_mount_request(unsigned char device, unsigned char op);

unsigned char udeks_program_main(unsigned char argc, unsigned char **argv)
{
    unsigned char op, device, offset;
    const unsigned char *name, *arg;
    name = argv[0];
    arg = name;
    while (*arg) { if (*arg++ == '/') name = arg; }
    op = UDEKS_TREQ_OP_MOUNT;
    offset = 1;
    if (name[0] == 'u') { op = UDEKS_TREQ_OP_UMOUNT; offset = 0; }
    if (argc != offset+2u || strcmp((const char *)argv[argc-1], "/mnt"))
        goto usage;
    device = 0;
    if (offset) {
        arg = argv[1];
        if (!*arg) goto usage;
        device = *arg++ - '0';
        if (*arg) {
            if (device != 1u || arg[1]) goto usage;
            device = *arg - '0';
            if (device > 1u) goto usage;
            device += 10u;
        }
        if (device < 8u || device > 11u) goto usage;
    }
    if (!udeks_mount_request(device, op)) return 0;
    udeks_write(UDEKS_STDERR, (const unsigned char *)"mount: failed\n");
    return 1;
usage:
    udeks_write(UDEKS_STDERR, (const unsigned char *)"mount 8 /mnt | umount /mnt\n");
    return 1;
}
