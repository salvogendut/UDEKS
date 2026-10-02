/* SPDX-License-Identifier: GPL-3.0-or-later */
/*
 * Native UDEKS adaptation of ccowsay by Aaron / 0xAether.
 * https://github.com/0xAether/ccowsay
 *
 * The upstream program and this adaptation are distributed under the GNU
 * General Public License, version 3 or (at your option) any later version.
 */
#include "udeks/program.h"

#define COWSAY_MAX_MESSAGE       50u

static unsigned char strings_equal(
    const unsigned char *left, const unsigned char *right)
{
    while (*left != 0 && *right != 0 && *left == *right) {
        ++left;
        ++right;
    }
    return *left == *right;
}

static unsigned char text_length(const unsigned char *text)
{
    unsigned char length;

    length = 0;
    while (text[length] != 0) {
        ++length;
    }
    return length;
}

static void write_text(unsigned char descriptor, const unsigned char *text)
{
    udeks_write(descriptor, text);
}

static void write_byte(unsigned char descriptor, unsigned char value)
{
    udeks_write_byte(descriptor, value);
}

static void write_line(
    unsigned char descriptor, const unsigned char *text)
{
    write_text(descriptor, text);
    write_byte(descriptor, '\n');
}

static void write_repeat(unsigned char value, unsigned char count)
{
    while (count-- != 0) {
        write_byte(UDEKS_STDOUT, value);
    }
}

static void write_help(void)
{
    write_line(UDEKS_STDOUT,
        (const unsigned char *)"Usage: cowsay [-t] [-e X] message");
}

static unsigned char measure_message(
    unsigned char count, unsigned char **arguments, unsigned char first)
{
    unsigned char index;
    unsigned char length;
    unsigned char argument_length;

    length = 0;
    for (index = first; index < count; ++index) {
        argument_length = text_length(arguments[index]);
        if (index != first) {
            ++length;
        }
        if (argument_length > COWSAY_MAX_MESSAGE - length) {
            return 0xFFu;
        }
        length += argument_length;
    }
    return length;
}

static void write_message(
    unsigned char count, unsigned char **arguments, unsigned char first)
{
    unsigned char index;

    for (index = first; index < count; ++index) {
        if (index != first) {
            write_byte(UDEKS_STDOUT, ' ');
        }
        write_text(UDEKS_STDOUT, arguments[index]);
    }
}

/* PETSCII glyphs, because the C128 font has no ASCII backslash/underscore:
 * $CD = diagonal (\), $5E = up arrow (^), $C0 = horizontal line (_),
 * $C2 = vertical bar (|). The VDC console maps these to screen codes. */
#define COW_BACKSLASH 0xCDu
#define COW_UPARROW   0x5Eu
#define COW_LINE      0xC0u
#define COW_BAR       0xC2u

static void write_cow(
    unsigned char thought, unsigned char eyes)
{
    write_text(UDEKS_STDOUT, (const unsigned char *)" ");
    write_byte(UDEKS_STDOUT, thought != 0 ? 'O' : COW_BACKSLASH);
    write_byte(UDEKS_STDOUT, ' ');
    write_byte(UDEKS_STDOUT, ' ');
    write_byte(UDEKS_STDOUT, ' ');
    write_byte(UDEKS_STDOUT, COW_UPARROW);
    write_byte(UDEKS_STDOUT, COW_LINE);
    write_byte(UDEKS_STDOUT, COW_LINE);
    write_byte(UDEKS_STDOUT, COW_UPARROW);
    write_byte(UDEKS_STDOUT, '\n');
    write_byte(UDEKS_STDOUT, ' ');
    write_byte(UDEKS_STDOUT, ' ');
    write_byte(UDEKS_STDOUT, thought != 0 ? 'o' : COW_BACKSLASH);
    write_byte(UDEKS_STDOUT, ' ');
    write_byte(UDEKS_STDOUT, ' ');
    write_byte(UDEKS_STDOUT, '(');
    write_byte(UDEKS_STDOUT, eyes);
    write_byte(UDEKS_STDOUT, eyes);
    write_byte(UDEKS_STDOUT, ')');
    write_byte(UDEKS_STDOUT, COW_BACKSLASH);
    write_repeat(COW_LINE, 7u);
    write_byte(UDEKS_STDOUT, '\n');
    write_text(UDEKS_STDOUT, (const unsigned char *)"     (");
    write_byte(UDEKS_STDOUT, COW_LINE);
    write_byte(UDEKS_STDOUT, COW_LINE);
    write_text(UDEKS_STDOUT, (const unsigned char *)")");
    write_byte(UDEKS_STDOUT, COW_BACKSLASH);
    write_text(UDEKS_STDOUT, (const unsigned char *)"       )");
    write_byte(UDEKS_STDOUT, COW_BACKSLASH);
    write_byte(UDEKS_STDOUT, '/');
    write_byte(UDEKS_STDOUT, COW_BACKSLASH);
    write_byte(UDEKS_STDOUT, '\n');
    write_text(UDEKS_STDOUT, (const unsigned char *)"         ");
    write_byte(UDEKS_STDOUT, COW_BAR);
    write_byte(UDEKS_STDOUT, COW_BAR);
    write_text(UDEKS_STDOUT, (const unsigned char *)"----w ");
    write_byte(UDEKS_STDOUT, COW_BAR);
    write_byte(UDEKS_STDOUT, '\n');
    write_text(UDEKS_STDOUT, (const unsigned char *)"         ");
    write_byte(UDEKS_STDOUT, COW_BAR);
    write_byte(UDEKS_STDOUT, COW_BAR);
    write_text(UDEKS_STDOUT, (const unsigned char *)"     ");
    write_byte(UDEKS_STDOUT, COW_BAR);
    write_byte(UDEKS_STDOUT, COW_BAR);
    write_byte(UDEKS_STDOUT, '\n');
}

unsigned char udeks_program_main(
    unsigned char count, unsigned char **arguments)
{
    unsigned char index;
    unsigned char thought;
    unsigned char eyes;
    unsigned char length;

    index = 1u;
    thought = 0;
    eyes = 'o';
    while (index < count) {
        if (strings_equal(arguments[index],
                (const unsigned char *)"-h")) {
            write_help();
            return UDEKS_EXIT_SUCCESS;
        }
        if (strings_equal(arguments[index],
                (const unsigned char *)"-t")) {
            thought = 1u;
            ++index;
            continue;
        }
        if (strings_equal(arguments[index],
                (const unsigned char *)"-e")) {
            ++index;
            if (index >= count || arguments[index][0] == 0 ||
                arguments[index][1] != 0) {
                write_line(UDEKS_STDERR,
                    (const unsigned char *)
                        "cowsay: eyes must be one character");
                return UDEKS_EXIT_FAILURE;
            }
            eyes = arguments[index][0];
            ++index;
            continue;
        }
        if (arguments[index][0] == '-') {
            write_line(UDEKS_STDERR,
                (const unsigned char *)"cowsay: unknown option");
            return UDEKS_EXIT_FAILURE;
        }
        break;
    }
    if (index == count) {
        write_line(UDEKS_STDERR,
            (const unsigned char *)"Usage: cowsay [-t] [-e X] message");
        return UDEKS_EXIT_FAILURE;
    }
    length = measure_message(count, arguments, index);
    if (length == 0xFFu) {
        write_line(UDEKS_STDERR,
            (const unsigned char *)"cowsay: message is too long");
        return UDEKS_EXIT_FAILURE;
    }

    write_byte(UDEKS_STDOUT, ' ');
    write_repeat(COW_LINE, length + 2u);
    write_byte(UDEKS_STDOUT, '\n');
    write_byte(UDEKS_STDOUT, thought != 0 ? '(' : '<');
    write_byte(UDEKS_STDOUT, ' ');
    write_message(count, arguments, index);
    write_byte(UDEKS_STDOUT, ' ');
    write_byte(UDEKS_STDOUT, thought != 0 ? ')' : '>');
    write_byte(UDEKS_STDOUT, '\n');
    write_byte(UDEKS_STDOUT, ' ');
    write_repeat('-', length + 2u);
    write_byte(UDEKS_STDOUT, '\n');
    write_cow(thought, eyes);
    return UDEKS_EXIT_SUCCESS;
}
