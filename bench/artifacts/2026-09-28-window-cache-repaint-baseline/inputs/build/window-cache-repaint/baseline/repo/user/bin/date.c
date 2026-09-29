/* SPDX-License-Identifier: GPL-3.0-or-later */
#include "udeks/program.h"
#include "udeks/time.h"

#define TIME_BYTE(offset) \
    (*(volatile unsigned char *)(UDEKS_TIME_STATUS_BASE + (offset)))

static void write_two(unsigned char value)
{
    unsigned char tens;

    tens = 0;
    while (value >= 10u) {
        value = (unsigned char)(value - 10u);
        ++tens;
    }
    udeks_write_byte(UDEKS_STDOUT, (unsigned char)('0' + tens));
    udeks_write_byte(UDEKS_STDOUT, (unsigned char)('0' + value));
}

static unsigned char pair_value(unsigned char tens, unsigned char ones)
{
    while (tens != 0) {
        ones = (unsigned char)(ones + 10u);
        --tens;
    }
    return ones;
}

static void print_time(void)
{
    write_two(TIME_BYTE(8));
    udeks_write_byte(UDEKS_STDOUT, ':');
    write_two(TIME_BYTE(9));
    udeks_write_byte(UDEKS_STDOUT, ':');
    write_two(TIME_BYTE(10));
    udeks_write_byte(UDEKS_STDOUT, '\n');
}

static unsigned char digit(unsigned char value, unsigned char *result)
{
    if (value < '0' || value > '9') {
        return 0;
    }
    *result = (unsigned char)(value - '0');
    return 1;
}

static unsigned char parse_time(
    const unsigned char *text, unsigned char *hour,
    unsigned char *minute, unsigned char *second)
{
    unsigned char digits[6];
    unsigned char source;
    unsigned char target;

    source = 0;
    target = 0;
    while (text[source] != 0 && target < 6u) {
        if ((source == 2u || source == 5u) && text[source] == ':') {
            ++source;
            continue;
        }
        if (digit(text[source], &digits[target]) == 0) {
            return 0;
        }
        ++source;
        ++target;
    }
    if (target != 6u || text[source] != 0) {
        return 0;
    }
    *hour = pair_value(digits[0], digits[1]);
    *minute = pair_value(digits[2], digits[3]);
    *second = pair_value(digits[4], digits[5]);
    return *hour < 24u && *minute < 60u && *second < 60u;
}

unsigned char udeks_program_main(
    unsigned char count, unsigned char **arguments)
{
    const unsigned char *value;
    unsigned char hour;
    unsigned char minute;
    unsigned char second;

    if (count == 1u) {
        print_time();
        return UDEKS_EXIT_SUCCESS;
    }
    value = 0;
    if (count == 2u) {
        value = arguments[1];
    } else if (count == 3u && arguments[1][0] == '-' &&
               arguments[1][1] == 's' && arguments[1][2] == 0) {
        value = arguments[2];
    }
    if (value == 0 || parse_time(value, &hour, &minute, &second) == 0) {
        udeks_write(UDEKS_STDERR,
            (const unsigned char *)"date: usage: date [-s] HHMMSS|HH:MM:SS\n");
        return UDEKS_EXIT_FAILURE;
    }
    if (udeks_clock_set(hour, minute, second) != 0) {
        udeks_write(UDEKS_STDERR, (const unsigned char *)"date: invalid time\n");
        return UDEKS_EXIT_FAILURE;
    }
    print_time();
    return UDEKS_EXIT_SUCCESS;
}
