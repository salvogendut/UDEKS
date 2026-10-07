/* SPDX-License-Identifier: GPL-3.0-or-later */
#include "udeks/program.h"
const unsigned char *udeks_error_string(unsigned char error)
{
    switch(error) {
    case 2: return (const unsigned char *)"No such file or directory";
    case 5: return (const unsigned char *)"Input/output error";
    case 9: return (const unsigned char *)"Bad file descriptor";
    case 16: return (const unsigned char *)"Device or resource busy";
    case 17: return (const unsigned char *)"File exists";
    case 19: return (const unsigned char *)"No such device";
    case 21: return (const unsigned char *)"Is a directory";
    case 24: return (const unsigned char *)"Too many open files";
    case 28: return (const unsigned char *)"No space left on device";
    case 30: return (const unsigned char *)"Read-only filesystem";
    default: return (const unsigned char *)"Invalid or unsupported request";
    }
}
