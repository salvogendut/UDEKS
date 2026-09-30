/* SPDX-License-Identifier: GPL-3.0-or-later */
/* Transient, single-invocation multicall commands; no resident command policy. */
#include <string.h>
#include "udeks/program.h"
#include "udeks/task_request.h"

#ifdef UDEKS_FILETOOLS_HOST_TEST
extern unsigned char filetools_payload[24], filetools_cwd, filetools_error;
#define PAYLOAD filetools_payload
#define CWD_KIND filetools_cwd
#define FILE_ERROR filetools_error
#else
#define PAYLOAD ((volatile unsigned char *)(UDEKS_TASK_REQUEST_BASE + UDEKS_TREQ_PAYLOAD))
#define CWD_KIND (*(volatile unsigned char *)0xf2a6)
#define FILE_ERROR (*(volatile unsigned char *)(UDEKS_TASK_REQUEST_BASE + UDEKS_TREQ_ERROR))
#endif
unsigned char __fastcall__ file_request(unsigned char op, unsigned char fd, unsigned char count);

static unsigned char fail(const char *message)
{
    udeks_write(UDEKS_STDERR, (const unsigned char *)message);
    return 1;
}

static unsigned char path_request(unsigned char op, unsigned char flags, const unsigned char *path)
{
    unsigned char n = 0;
    while (path[n]) {
        if (n == 23) { FILE_ERROR = UDEKS_TREQ_EINVAL; return UDEKS_IO_ERROR; }
        PAYLOAD[n] = path[n];
        ++n;
    }
    PAYLOAD[n] = 0;
    return file_request(op, flags, n);
}

static void decimal(unsigned int value)
{
    static const unsigned int divisors[] = {10000, 1000, 100, 10, 1};
    unsigned int divisor;
    unsigned char digit, i, started = 0;
    for (i = 0; i != 5; ++i) {
        divisor = divisors[i];
        digit = 0;
        while (value >= divisor) { value -= divisor; ++digit; }
        if (digit || started || divisor == 1) {
            udeks_write_byte(1, '0'+digit);
            started = 1;
        }
    }
}

static unsigned char list(const unsigned char *path, unsigned char long_format)
{
    unsigned char fd, n, i, type, length;
    unsigned char name[17], full[24];
    fd = path_request(UDEKS_TREQ_OP_OPEN, UDEKS_O_DIRECTORY, path);
    if (fd == UDEKS_IO_ERROR) return fail("ls: open failed\n");
    while ((n = file_request(UDEKS_TREQ_OP_GETDENTS, fd, 24)) != 0) {
        if (n == UDEKS_IO_ERROR) break;
        type = PAYLOAD[0]; length = PAYLOAD[1];
        for (i = 0; i < length; ++i) name[i] = PAYLOAD[i+2];
        name[i] = 0;
        if (long_format) {
            udeks_write(1, (const unsigned char *)(type == UDEKS_DT_DIR ? "dr-x " : "-r-x "));
            length = strlen((const char *)path);
            /* OPEN bounds path to 23 bytes, GETDENTS bounds name to 16. */
            if ((unsigned char)(length + i + 2u) <= sizeof(full)) {
                strcpy((char *)full, (const char *)path);
                if (length && full[length-1] != '/') full[length++] = '/';
                strcpy((char *)full+length, (const char *)name);
                if (path_request(UDEKS_TREQ_OP_STAT, 0, full) == UDEKS_STAT_SIZE)
                    decimal(PAYLOAD[1] | ((unsigned int)PAYLOAD[2] << 8));
                else udeks_write_byte(1, '?');
            } else udeks_write_byte(1, '?');
            udeks_write_byte(1, ' ');
        }
        udeks_write(1, name); udeks_write_byte(1, '\n');
    }
    i = file_request(UDEKS_TREQ_OP_CLOSE, fd, 0);
    /* Exhaustion and CLOSE return zero on success, IO_ERROR on failure. */
    return n || i ? fail("ls: read error\n") : 0;
}

static unsigned char cat(const unsigned char *path)
{
    unsigned char fd, n, i;
    fd = path_request(UDEKS_TREQ_OP_OPEN, UDEKS_O_RDONLY, path);
    if (fd == UDEKS_IO_ERROR)
        return fail(FILE_ERROR == UDEKS_TREQ_ENOENT ?
            "cat: No such file or directory\n" : "cat: open failed\n");
    while ((n = file_request(UDEKS_TREQ_OP_READ, fd, 24)) != 0) {
        if (n == UDEKS_IO_ERROR) break;
        for (i = 0; i < n; ++i) udeks_write_byte(1, PAYLOAD[i]);
    }
    i = file_request(UDEKS_TREQ_OP_CLOSE, fd, 0);
    return n || i ? fail("cat: read error\n") : 0;
}

unsigned char udeks_program_main(unsigned char argc, unsigned char **argv)
{
    unsigned char op, device, offset;
    const unsigned char *name, *arg;
    name = argv[0]; arg = name;
    while (*arg) { if (*arg++ == '/') name = arg; }
    if (name[0] == 'c') {
        if (argc != 2) return fail("cat FILE\n");
        return cat(argv[1]);
    }
    if (name[0] == 'l') {
        offset = 1;
        op = argc > 1 && !strcmp((const char *)argv[1], "-l");
        offset += op;
        if (argc > offset+1u) return fail("ls [-l] [PATH]\n");
        arg = (const unsigned char *)".";
        if (argc > offset) arg = argv[offset];
        /* Match the existing root/bin-only working-directory contract. */
        if (arg[0] == '.' && !arg[1])
            arg = (const unsigned char *)(CWD_KIND ? "/bin" : "/");
        return list(arg, op);
    }
    op = UDEKS_TREQ_OP_MOUNT; offset = 1;
    if (name[0] == 'u') { op = UDEKS_TREQ_OP_UMOUNT; offset = 0; }
    if (argc != offset+2u || strcmp((const char *)argv[argc-1], "/mnt"))
        return fail("mount 8 /mnt | umount /mnt\n");
    device = 0;
    if (offset) {
        arg = argv[1];
        if (!*arg) return fail("mount: device 8-11\n");
        device = *arg++ - '0';
        if (*arg) {
            if (device != 1u || arg[1] || *arg < '0' || *arg > '1')
                return fail("mount: device 8-11\n");
            device = *arg - '0' + 10;
        }
        if (device < 8 || device > 11) return fail("mount: device 8-11\n");
    }
    PAYLOAD[0] = device;
    PAYLOAD[offset] = '/'; PAYLOAD[offset+1] = 'm';
    PAYLOAD[offset+2] = 'n'; PAYLOAD[offset+3] = 't';
    return file_request(op, 0, offset+4u) == UDEKS_IO_ERROR ? fail("mount: failed\n") : 0;
}
