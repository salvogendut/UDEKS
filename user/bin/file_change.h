/* SPDX-License-Identifier: GPL-3.0-or-later */
/* Shared command-line presentation, no filesystem policy or raw DOS access. */
#include <string.h>
#include "udeks/program.h"
#include "udeks/file_mutation.h"

unsigned char udeks_program_main(unsigned char argc, unsigned char **argv)
{
    unsigned char options = 1, result;
    const unsigned char *message, *source;
#if FILE_OPERANDS == 2
    const unsigned char *destination;
#endif
    if (argc > 1 && !strcmp((const char *)argv[1], "--")) {
        --argc; ++argv; options = 0;
    }
    if (argc != 1 + FILE_OPERANDS) goto usage;
    source = argv[1];
#if FILE_OPERANDS == 2
    destination = argv[2];
#endif
    if (!source[0] || (options && source[0] == '-')
#if FILE_OPERANDS == 2
        || !destination[0] || (options && destination[0] == '-')
#endif
        ) {
usage:
        udeks_write(2, (const unsigned char *)(FILE_COMMAND " [--] " FILE_USAGE "\n"));
        return 1;
    }
#if FILE_OPERANDS == 2
    result = FILE_OPERATION(source, destination);
#else
    result = FILE_OPERATION(source);
#endif
    if (result != UDEKS_IO_ERROR) return 0;
    message = udeks_errno == UDEKS_FILE_EXDEV ? (const unsigned char *)"Invalid cross-device link" :
              udeks_errno == 22 ? (const unsigned char *)"Invalid argument" : udeks_error_string(udeks_errno);
    udeks_write(2, (const unsigned char *)(FILE_COMMAND ": "));
    udeks_write(2, message);
    udeks_write_byte(2, '\n');
    return 1;
}
