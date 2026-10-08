/* SPDX-License-Identifier: GPL-3.0-or-later */
/* Exact-file SDK, linked by --file-mutations builds. */
#include "udeks/program.h"
#include "udeks/task_request.h"
#include "udeks/file_mutation.h"
#ifdef UDEKS_FS_CLIENT_TEST
extern unsigned char udeks_file_payload[24];
#define PAYLOAD udeks_file_payload
#else
#define PAYLOAD ((volatile unsigned char *)0xf367)
#endif
unsigned char __fastcall__ udeks_mutation_request(unsigned char op, unsigned char fd, unsigned char count);

unsigned char udeks_file_change(unsigned char op, const unsigned char *source,
                               const unsigned char *destination);
#if !defined(UDEKS_MUTATION_PART) || UDEKS_MUTATION_PART == 0
unsigned char udeks_file_change(unsigned char op, const unsigned char *source,
                            const unsigned char *destination)
{
    unsigned char n = 0, i, fd, result, error;
    if (op != UDEKS_FILE_UNLINK) {
        if (!destination) goto invalid;
        while (destination[n]) {
            if (n == 23u) goto invalid;
            ++n;
        }
        if (!n) goto invalid;
    }
    fd = udeks_open(source, UDEKS_O_RDONLY);
    if (fd == UDEKS_IO_ERROR) return fd;
    if (destination) for (i = 0; i <= n; ++i) PAYLOAD[i] = destination[i];
    result = udeks_mutation_request(op, fd, n);
    /* Ordinary console programs are still synchronous. Each poll releases
     * the storage lease/IRQ mask; no context switch is attempted from the
     * legacy foreground allocation. Never repeat the original DOS command. */
    while (result == 1u) result = udeks_mutation_request(op | 128u, fd, 0);
    error = udeks_errno;
    /* Preflight rejection leaves the descriptor open; accepted operations
     * consume it. Always close, but never hide the original operation error. */
    i = udeks_close(fd);
    if (result != UDEKS_IO_ERROR && i == UDEKS_IO_ERROR && udeks_errno != UDEKS_TREQ_EBADF) {
        result = i; error = udeks_errno;
    }
    udeks_errno = error;
    return result;
invalid:
    udeks_errno = UDEKS_TREQ_EINVAL;
    return UDEKS_IO_ERROR;
}
#endif

#if !defined(UDEKS_MUTATION_PART) || UDEKS_MUTATION_PART == 1
unsigned char udeks_rename(const unsigned char *source, const unsigned char *destination)
{ return udeks_file_change(UDEKS_FILE_RENAME, source, destination); }
#endif
#if !defined(UDEKS_MUTATION_PART) || UDEKS_MUTATION_PART == 2
unsigned char udeks_copy(const unsigned char *source, const unsigned char *destination)
{ return udeks_file_change(UDEKS_FILE_COPY, source, destination); }
#endif
#if !defined(UDEKS_MUTATION_PART) || UDEKS_MUTATION_PART == 3
unsigned char udeks_unlink(const unsigned char *source)
{ return udeks_file_change(UDEKS_FILE_UNLINK, source, 0); }
#endif
