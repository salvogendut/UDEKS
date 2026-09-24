/* SPDX-License-Identifier: GPL-3.0-or-later */
#include "udeks/capability.h"
#include "udeks/line_editor.h"
#include "udeks/root_terminal.h"
#include "udeks/service.h"
#include "udeks/shell.h"
#include "udeks/stream.h"

#define STATUS_BYTE(offset) \
    (*(volatile unsigned char *)(UDEKS_SHELL_STATUS_BASE + (offset)))

#define STATUS_POLLS_LO          12u
#define STATUS_COMMANDS_LO       14u
#define STATUS_UNKNOWN_LO        16u
#define STATUS_PARSE_ERRORS_LO   18u

typedef unsigned char (*command_handler)(
    unsigned char count, unsigned char **arguments);

struct shell_command {
    const unsigned char *name;
    const unsigned char *summary;
    command_handler handler;
};

static unsigned char command_line[UDEKS_LINE_EDITOR_CAPACITY + 1u];
static unsigned char argument_offsets[UDEKS_SHELL_MAX_ARGUMENTS];
static unsigned char *arguments[UDEKS_SHELL_MAX_ARGUMENTS];

static void write_text(
    unsigned char descriptor, const unsigned char *text)
{
    udeks_stream_write(descriptor, text);
}

static void write_line(
    unsigned char descriptor, const unsigned char *text)
{
    write_text(descriptor, text);
    udeks_stream_write_byte(descriptor, '\n');
}

static void write_decimal(unsigned char descriptor, unsigned int value)
{
    unsigned char digits[5];
    unsigned char count;

    count = 0;
    do {
        digits[count] = (unsigned char)('0' + value % 10u);
        value /= 10u;
        ++count;
    } while (value != 0);
    while (count != 0) {
        --count;
        udeks_stream_write_byte(descriptor, digits[count]);
    }
}

static unsigned char strings_equal(
    const unsigned char *left, const unsigned char *right)
{
    while (*left != 0 && *right != 0 && *left == *right) {
        ++left;
        ++right;
    }
    return *left == *right;
}

static unsigned char command_clear(
    unsigned char count, unsigned char **arguments)
{
    (void)count;
    (void)arguments;
    udeks_stream_write_byte(UDEKS_STDOUT, '\f');
    return UDEKS_SHELL_OK;
}

static unsigned char command_echo(
    unsigned char count, unsigned char **arguments)
{
    unsigned char index;

    for (index = 1; index < count; ++index) {
        if (index != 1) {
            udeks_stream_write_byte(UDEKS_STDOUT, ' ');
        }
        write_text(UDEKS_STDOUT, arguments[index]);
    }
    udeks_stream_write_byte(UDEKS_STDOUT, '\n');
    return UDEKS_SHELL_OK;
}

static unsigned char command_uname(
    unsigned char count, unsigned char **arguments)
{
    if (count > 1 && strings_equal(
            arguments[1], (const unsigned char *)"-a")) {
        write_line(
            UDEKS_STDOUT,
            (const unsigned char *)"UDEKS 0.1.0 c128 8502");
    } else {
        write_line(UDEKS_STDOUT, (const unsigned char *)"UDEKS");
    }
    return UDEKS_SHELL_OK;
}

static unsigned char command_lshw(
    unsigned char count, unsigned char **arguments)
{
    volatile unsigned char *capability;

    (void)count;
    (void)arguments;
    capability = (volatile unsigned char *)UDEKS_CAPABILITY_STATUS_BASE;
    write_text(UDEKS_STDOUT, (const unsigned char *)"Video: ");
    write_text(UDEKS_STDOUT, capability[7] == UDEKS_VIDEO_PAL ?
        (const unsigned char *)"PAL, VDC " :
        (const unsigned char *)"NTSC, VDC ");
    write_text(UDEKS_STDOUT, capability[9] == UDEKS_VDC_FAMILY_8568 ?
        (const unsigned char *)"8568, " :
        (const unsigned char *)"8563, ");
    write_decimal(UDEKS_STDOUT, capability[10]);
    write_line(UDEKS_STDOUT, (const unsigned char *)" KB");
    write_text(UDEKS_STDOUT, (const unsigned char *)"Expansion: REU ");
    write_text(UDEKS_STDOUT, capability[12] != 0 ?
        (const unsigned char *)"present, GeoRAM " :
        (const unsigned char *)"absent, GeoRAM ");
    write_line(UDEKS_STDOUT, capability[13] != 0 ?
        (const unsigned char *)"present" :
        (const unsigned char *)"absent");
    return UDEKS_SHELL_OK;
}

static unsigned char command_lsmod(
    unsigned char count, unsigned char **arguments)
{
    volatile unsigned char *registry;
    unsigned int polls;

    (void)count;
    (void)arguments;
    registry = (volatile unsigned char *)UDEKS_SERVICE_STATUS_BASE;
    write_text(UDEKS_STDOUT, (const unsigned char *)"Modules: ");
    write_decimal(UDEKS_STDOUT, registry[8]);
    udeks_stream_write_byte(UDEKS_STDOUT, '/');
    write_decimal(UDEKS_STDOUT, registry[17]);
    write_line(UDEKS_STDOUT, (const unsigned char *)" resident");
    polls = (unsigned int)registry[18] |
        ((unsigned int)registry[19] << 8);
    write_text(UDEKS_STDOUT, (const unsigned char *)"Poll passes: ");
    write_decimal(UDEKS_STDOUT, polls);
    udeks_stream_write_byte(UDEKS_STDOUT, '\n');
    return UDEKS_SHELL_OK;
}

static unsigned char command_lscpu(
    unsigned char count, unsigned char **arguments)
{
    (void)count;
    (void)arguments;
    write_line(UDEKS_STDOUT, (const unsigned char *)"8502: resident executive");
    write_line(UDEKS_STDOUT, (const unsigned char *)"Z80: staged; lease pending");
    return UDEKS_SHELL_OK;
}

static unsigned char command_help(
    unsigned char count, unsigned char **arguments);

static const struct shell_command commands[] = {
    {(const unsigned char *)"help", (const unsigned char *)"List commands", command_help},
    {(const unsigned char *)"clear", (const unsigned char *)"Clear the console", command_clear},
    {(const unsigned char *)"echo", (const unsigned char *)"Write arguments", command_echo},
    {(const unsigned char *)"uname", (const unsigned char *)"Show system identity", command_uname},
    {(const unsigned char *)"lshw", (const unsigned char *)"Show detected hardware", command_lshw},
    {(const unsigned char *)"lsmod", (const unsigned char *)"Show resident services", command_lsmod},
    {(const unsigned char *)"lscpu", (const unsigned char *)"Show CPU roles", command_lscpu}
};

#define COMMAND_COUNT ((unsigned char)(sizeof(commands) / sizeof(commands[0])))

static unsigned char command_help(
    unsigned char count, unsigned char **arguments)
{
    unsigned char index;

    (void)count;
    (void)arguments;
    for (index = 0; index < COMMAND_COUNT; ++index) {
        write_text(UDEKS_STDOUT, commands[index].name);
        write_text(UDEKS_STDOUT, (const unsigned char *)" - ");
        write_line(UDEKS_STDOUT, commands[index].summary);
    }
    return UDEKS_SHELL_OK;
}

static void increment_counter(unsigned char low_offset)
{
    ++STATUS_BYTE(low_offset);
    if (STATUS_BYTE(low_offset) == 0) {
        ++STATUS_BYTE(low_offset + 1u);
    }
}

static unsigned char shell_fail(unsigned char code)
{
    STATUS_BYTE(6) = code;
    STATUS_BYTE(5) = (unsigned char)(UDEKS_SHELL_STATE_ERROR | code);
    return code;
}

static unsigned char dispatch_line(void)
{
    unsigned char count;
    unsigned char index;
    unsigned char result;

    count = udeks_shell_tokenize(
        command_line, argument_offsets, UDEKS_SHELL_MAX_ARGUMENTS);
    if (count == UDEKS_SHELL_PARSE_TOO_MANY) {
        increment_counter(STATUS_PARSE_ERRORS_LO);
        write_line(UDEKS_STDERR, (const unsigned char *)"Too many arguments");
        return UDEKS_SHELL_OK;
    }
    STATUS_BYTE(8) = count;
    if (count == 0) {
        return UDEKS_SHELL_OK;
    }
    for (index = 0; index < count; ++index) {
        arguments[index] = command_line + argument_offsets[index];
    }
    for (index = 0; index < COMMAND_COUNT; ++index) {
        if (strings_equal(
                arguments[0], commands[index].name)) {
            STATUS_BYTE(9) = index;
            result = commands[index].handler(count, arguments);
            STATUS_BYTE(10) = result;
            increment_counter(STATUS_COMMANDS_LO);
            return result;
        }
    }
    STATUS_BYTE(9) = 0xFFu;
    increment_counter(STATUS_UNKNOWN_LO);
    write_text(UDEKS_STDERR, (const unsigned char *)"Unknown command: ");
    write_line(UDEKS_STDERR, arguments[0]);
    return UDEKS_SHELL_OK;
}

unsigned char udeks_shell_start(void)
{
    unsigned char offset;

    for (offset = 0; offset < UDEKS_SHELL_STATUS_SIZE; ++offset) {
        STATUS_BYTE(offset) = 0;
    }
    STATUS_BYTE(0) = 'S';
    STATUS_BYTE(1) = 'H';
    STATUS_BYTE(2) = 'L';
    STATUS_BYTE(3) = 'L';
    STATUS_BYTE(4) = 1;
    STATUS_BYTE(5) = UDEKS_SHELL_STATE_STARTING;
    STATUS_BYTE(7) = COMMAND_COUNT;
    if (*(volatile unsigned char *)(UDEKS_ROOT_TERMINAL_STATUS_BASE + 5u) !=
            UDEKS_ROOT_TERMINAL_READY) {
        return shell_fail(UDEKS_SHELL_DEPENDENCY);
    }
    STATUS_BYTE(5) = UDEKS_SHELL_STATE_READY;
    return UDEKS_SHELL_OK;
}

unsigned char udeks_shell_poll(void)
{
    unsigned char result;

    increment_counter(STATUS_POLLS_LO);
    result = udeks_line_editor_get_line(
        command_line, sizeof(command_line));
    if (result == UDEKS_LINE_EDITOR_EMPTY) {
        return UDEKS_SHELL_OK;
    }
    if (result != UDEKS_LINE_EDITOR_OK) {
        return shell_fail(UDEKS_SHELL_INPUT);
    }
    result = dispatch_line();
    if (result != UDEKS_SHELL_OK) {
        return shell_fail(result);
    }
    if (udeks_root_terminal_prompt() != UDEKS_ROOT_TERMINAL_OK) {
        return shell_fail(UDEKS_SHELL_PROMPT);
    }
    return UDEKS_SHELL_OK;
}
