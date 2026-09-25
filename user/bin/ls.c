/* SPDX-License-Identifier: GPL-3.0-or-later */
#include "udeks/program.h"
#include "udeks/task_request.h"

static void line(const unsigned char *text)
{
    udeks_write(UDEKS_STDOUT, text);
    udeks_write_byte(UDEKS_STDOUT, '\n');
}

static void decimal(unsigned int value)
{
    static const unsigned int divisors[] = {10000u, 1000u, 100u, 10u, 1u};
    unsigned int divisor;
    unsigned char digit;
    unsigned char index;
    unsigned char started;

    started = 0;
    for (index = 0; index != 5u; ++index) {
        divisor = divisors[index];
        digit = 0;
        while (value >= divisor) {
            value -= divisor;
            ++digit;
        }
        if (digit != 0 || started != 0 || index == 4u) {
            udeks_write_byte(UDEKS_STDOUT, (unsigned char)('0' + digit));
            started = 1;
        }
    }
}

static void long_entry(
    const unsigned char *name, unsigned char type)
{
    unsigned char path[23];
    unsigned char status[UDEKS_STAT_SIZE];
    unsigned char index;
    unsigned char length;

    path[0] = '/';
    path[1] = 'b';
    path[2] = 'i';
    path[3] = 'n';
    path[4] = '/';
    index = 5u;
    length = 0;
    while (name[length] != 0 && index < 22u) {
        path[index++] = name[length++];
    }
    path[index] = 0;
    udeks_write_byte(UDEKS_STDOUT, type == UDEKS_DT_DIR ? 'd' : '-');
    udeks_write(UDEKS_STDOUT, (const unsigned char *)"r-x ");
    if (type == UDEKS_DT_DIR) {
        udeks_write(UDEKS_STDOUT, (const unsigned char *)"0 ");
    } else if (udeks_stat(path, status) == UDEKS_IO_ERROR) {
        udeks_write(UDEKS_STDOUT, (const unsigned char *)"? ");
    } else {
        decimal((unsigned int)status[UDEKS_STAT_SIZE_LOW] |
            ((unsigned int)status[UDEKS_STAT_SIZE_HIGH] << 8));
        udeks_write_byte(UDEKS_STDOUT, ' ');
    }
    line(name);
}

unsigned char udeks_program_main(
    unsigned char count, unsigned char **arguments)
{
    unsigned char buffer[UDEKS_TASK_REQUEST_PAYLOAD_SIZE];
    const unsigned char *path;
    unsigned char descriptor;
    unsigned char long_format;
    unsigned char result;
    unsigned char index;

    path = (const unsigned char *)".";
    long_format = 0;
    index = 1u;
    if (index < count && arguments[index][0] == '-' &&
        arguments[index][1] == 'l' && arguments[index][2] == 0) {
        long_format = 1;
        ++index;
    }
    if (index < count) {
        path = arguments[index++];
    }
    if (index != count) {
        line((const unsigned char *)"ls: usage");
        return UDEKS_EXIT_FAILURE;
    }
    descriptor = udeks_open(path, UDEKS_O_RDONLY | UDEKS_O_DIRECTORY);
    if (descriptor == UDEKS_IO_ERROR) {
        line((const unsigned char *)"ls: open failed");
        return UDEKS_EXIT_FAILURE;
    }
    while ((result = udeks_getdents(descriptor, buffer, sizeof(buffer))) != 0) {
        if (result == UDEKS_IO_ERROR) {
            line((const unsigned char *)"ls: read error");
            udeks_close(descriptor);
            return UDEKS_EXIT_FAILURE;
        }
        buffer[UDEKS_DIRENT_NAME + buffer[UDEKS_DIRENT_NAME_LENGTH]] = 0;
        if (long_format != 0) {
            long_entry(buffer + UDEKS_DIRENT_NAME,
                buffer[UDEKS_DIRENT_TYPE]);
        } else {
            line(buffer + UDEKS_DIRENT_NAME);
        }
    }
    udeks_close(descriptor);
    return UDEKS_EXIT_SUCCESS;
}
