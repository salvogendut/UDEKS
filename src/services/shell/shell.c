/* SPDX-License-Identifier: GPL-3.0-or-later */
#include "udeks/capability.h"
#include "udeks/line_editor.h"
#include "udeks/root_terminal.h"
#include "udeks/service.h"
#include "udeks/shell.h"
#include "udeks/stream.h"
#include "udeks/mailbox.h"
#include "udeks/z80_worker.h"
#include "udeks/vic_graphics.h"
#include "udeks/window.h"
#include "udeks/xclock.h"
#include "udeks/xwave.h"

#define STATUS_BYTE(offset) \
    (*(volatile unsigned char *)(UDEKS_SHELL_STATUS_BASE + (offset)))

#define STATUS_POLLS_LO          12u
#define STATUS_COMMANDS_LO       14u
#define STATUS_UNKNOWN_LO        16u
#define STATUS_PARSE_ERRORS_LO   18u
#define STATUS_FOREGROUND        20u
#define STATUS_BACKGROUND_JOBS   21u
#define STATUS_INTERRUPTS        22u

#define JOB_NONE                 0u
#define JOB_XCLOCK               1u
#define JOB_XWAVE                2u
#define BACKGROUND_XCLOCK        0x01u
#define BACKGROUND_XWAVE         0x02u

typedef unsigned char (*command_handler)(
    unsigned char count, unsigned char **arguments);

struct shell_command {
    const unsigned char *name;
    const unsigned char *summary;
    command_handler handler;
};

#pragma bss-name(push, "HIGHBSS")
static unsigned char command_line[UDEKS_LINE_EDITOR_CAPACITY + 1u];
static unsigned char argument_offsets[UDEKS_SHELL_MAX_ARGUMENTS];
static unsigned char *arguments[UDEKS_SHELL_MAX_ARGUMENTS];
static unsigned char foreground_job;
static unsigned char launch_background;
static unsigned char foreground_interrupted;
static unsigned char background_jobs;
#pragma bss-name(pop)

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

static void publish_background_jobs(void)
{
    unsigned char count;

    if ((background_jobs & BACKGROUND_XCLOCK) != 0 &&
        udeks_xclock_is_running() == 0) {
        background_jobs &= (unsigned char)~BACKGROUND_XCLOCK;
    }
    if ((background_jobs & BACKGROUND_XWAVE) != 0 &&
        udeks_xwave_is_running() == 0) {
        background_jobs &= (unsigned char)~BACKGROUND_XWAVE;
    }
    count = (background_jobs & BACKGROUND_XCLOCK) != 0 ? 1u : 0u;
    if ((background_jobs & BACKGROUND_XWAVE) != 0) {
        ++count;
    }
    STATUS_BYTE(STATUS_BACKGROUND_JOBS) = count;
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
    volatile unsigned char *worker;

    (void)count;
    (void)arguments;
    worker = (volatile unsigned char *)UDEKS_Z80_WORKER_STATUS_BASE;
    write_line(UDEKS_STDOUT, (const unsigned char *)"8502: resident executive");
    if (worker[5] == UDEKS_Z80_WORKER_READY) {
        write_line(UDEKS_STDOUT,
            (const unsigned char *)"Z80: bounded worker; ready (stock timing)");
    } else if (worker[5] == UDEKS_Z80_WORKER_ERROR) {
        write_line(UDEKS_STDOUT,
            (const unsigned char *)"Z80: worker error; leases disabled");
    } else {
        write_line(UDEKS_STDOUT,
            (const unsigned char *)"Z80: worker offline");
    }
    return UDEKS_SHELL_OK;
}

static unsigned char command_z80ctl(
    unsigned char count, unsigned char **arguments)
{
    volatile unsigned char *worker;
    unsigned char status;
    unsigned int result;
    unsigned int transactions;

    worker = (volatile unsigned char *)UDEKS_Z80_WORKER_STATUS_BASE;
    if (count == 2 && strings_equal(
            arguments[1], (const unsigned char *)"test")) {
        status = udeks_z80_submit(UDEKS_MB_OP_NOP, 0, 0, 0, &result);
        if (status == UDEKS_Z80_OK && result == 0) {
            write_line(UDEKS_STDOUT, (const unsigned char *)"Z80 self-test: OK");
        } else {
            write_text(UDEKS_STDERR, (const unsigned char *)"Z80 self-test: failed (");
            write_decimal(UDEKS_STDERR, status);
            write_line(UDEKS_STDERR, (const unsigned char *)")");
        }
        return UDEKS_SHELL_OK;
    }
    if (count == 1 || strings_equal(
            arguments[1], (const unsigned char *)"status")) {
        write_text(UDEKS_STDOUT, (const unsigned char *)"State: ");
        write_line(UDEKS_STDOUT, worker[5] == UDEKS_Z80_WORKER_READY ?
            (const unsigned char *)"ready" :
            (const unsigned char *)"offline");
        transactions = (unsigned int)worker[12] |
            ((unsigned int)worker[13] << 8);
        write_text(UDEKS_STDOUT, (const unsigned char *)"Transactions: ");
        write_decimal(UDEKS_STDOUT, transactions);
        udeks_stream_write_byte(UDEKS_STDOUT, '\n');
        return UDEKS_SHELL_OK;
    }
    write_line(UDEKS_STDERR,
        (const unsigned char *)"Usage: z80ctl [status|test]");
    return UDEKS_SHELL_OK;
}

static unsigned char command_xinit(
    unsigned char count, unsigned char **arguments)
{
    unsigned char result;

    if (count == 2 && strings_equal(
            arguments[1], (const unsigned char *)"-q")) {
        if (udeks_xclock_is_running() != 0) {
            udeks_xclock_stop();
        }
        if (udeks_xwave_is_running() != 0) {
            udeks_xwave_stop();
        }
        foreground_job = JOB_NONE;
        background_jobs = 0;
        publish_background_jobs();
        udeks_window_manager_reset();
        result = udeks_vic_graphics_shutdown();
        if (result == UDEKS_VIC_GRAPHICS_OK) {
            write_line(UDEKS_STDOUT,
                (const unsigned char *)"VIC-II graphics stopped");
        } else {
            write_text(UDEKS_STDERR,
                (const unsigned char *)"xinit: VIC-II shutdown failed (");
            write_decimal(UDEKS_STDERR, result);
            write_line(UDEKS_STDERR, (const unsigned char *)")");
        }
        return UDEKS_SHELL_OK;
    }
    if (count != 1) {
        write_line(UDEKS_STDERR, (const unsigned char *)"Usage: xinit [-q]");
        return UDEKS_SHELL_OK;
    }
    result = udeks_vic_graphics_initialize();
    if (result == UDEKS_VIC_GRAPHICS_OK) {
        write_line(UDEKS_STDOUT,
            (const unsigned char *)"VIC-II graphics active on 40-column display");
    } else {
        write_text(UDEKS_STDERR,
            (const unsigned char *)"xinit: VIC-II setup failed (");
        write_decimal(UDEKS_STDERR, result);
        write_line(UDEKS_STDERR, (const unsigned char *)")");
    }
    return UDEKS_SHELL_OK;
}

static unsigned char command_xclock(
    unsigned char count, unsigned char **arguments)
{
    unsigned char result;

    if (count == 2 && strings_equal(
            arguments[1], (const unsigned char *)"-q")) {
        result = udeks_xclock_stop();
        if (result == UDEKS_XCLOCK_OK) {
            background_jobs &= (unsigned char)~BACKGROUND_XCLOCK;
            publish_background_jobs();
            write_line(UDEKS_STDOUT, (const unsigned char *)"xclock stopped");
        } else {
            write_line(UDEKS_STDERR, (const unsigned char *)"xclock: not running");
        }
        return UDEKS_SHELL_OK;
    }
    if (count != 1) {
        write_line(UDEKS_STDERR, (const unsigned char *)"Usage: xclock [-q]");
        return UDEKS_SHELL_OK;
    }
    if (udeks_vic_graphics_is_active() == 0) {
        result = udeks_vic_graphics_initialize();
        if (result != UDEKS_VIC_GRAPHICS_OK) {
            write_line(UDEKS_STDERR,
                (const unsigned char *)"xclock: VIC-II graphics unavailable");
            return UDEKS_SHELL_OK;
        }
    }
    result = udeks_xclock_start();
    if (result == UDEKS_XCLOCK_OK) {
        if (launch_background != 0) {
            background_jobs |= BACKGROUND_XCLOCK;
            publish_background_jobs();
            write_line(UDEKS_STDOUT,
                (const unsigned char *)"xclock started in background");
        } else {
            foreground_job = JOB_XCLOCK;
            write_line(UDEKS_STDOUT,
                (const unsigned char *)"xclock running; Ctrl+C stops it");
        }
    } else if (result == UDEKS_XCLOCK_ALREADY_RUNNING) {
        write_line(UDEKS_STDERR, (const unsigned char *)"xclock: already running");
    } else {
        write_line(UDEKS_STDERR, (const unsigned char *)"xclock: start failed");
    }
    return UDEKS_SHELL_OK;
}

static unsigned char command_xwave(
    unsigned char count, unsigned char **arguments)
{
    unsigned char result;

    if (count == 2 && strings_equal(
            arguments[1], (const unsigned char *)"-q")) {
        result = udeks_xwave_stop();
        if (result == UDEKS_XWAVE_OK) {
            background_jobs &= (unsigned char)~BACKGROUND_XWAVE;
            publish_background_jobs();
        }
        write_line(result == UDEKS_XWAVE_OK ? UDEKS_STDOUT : UDEKS_STDERR,
            result == UDEKS_XWAVE_OK ?
                (const unsigned char *)"xwave stopped" :
                (const unsigned char *)"xwave: not running");
        return UDEKS_SHELL_OK;
    }
    if (count != 1) {
        write_line(UDEKS_STDERR, (const unsigned char *)"Usage: xwave [-q] [&]");
        return UDEKS_SHELL_OK;
    }
    if (udeks_vic_graphics_is_active() == 0 &&
        udeks_vic_graphics_initialize() != UDEKS_VIC_GRAPHICS_OK) {
        write_line(UDEKS_STDERR,
            (const unsigned char *)"xwave: VIC-II graphics unavailable");
        return UDEKS_SHELL_OK;
    }
    result = udeks_xwave_start();
    if (result == UDEKS_XWAVE_OK) {
        if (launch_background != 0) {
            background_jobs |= BACKGROUND_XWAVE;
            publish_background_jobs();
            write_line(UDEKS_STDOUT,
                (const unsigned char *)"xwave started in background");
        } else {
            foreground_job = JOB_XWAVE;
            write_line(UDEKS_STDOUT,
                (const unsigned char *)"xwave running; Ctrl+C stops it");
        }
    } else if (result == UDEKS_XWAVE_ALREADY_RUNNING) {
        write_line(UDEKS_STDERR, (const unsigned char *)"xwave: already running");
    } else {
        write_line(UDEKS_STDERR, (const unsigned char *)"xwave: start failed");
    }
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
    {(const unsigned char *)"lscpu", (const unsigned char *)"Show CPU roles", command_lscpu},
    {(const unsigned char *)"z80ctl", (const unsigned char *)"Inspect or test Z80 worker", command_z80ctl},
    {(const unsigned char *)"xinit", (const unsigned char *)"Start VIC-II graphics", command_xinit},
    {(const unsigned char *)"xclock", (const unsigned char *)"Run analog clock", command_xclock},
    {(const unsigned char *)"xwave", (const unsigned char *)"Run dual-engine surface plotter", command_xwave}
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
    launch_background = 0;
    if (count > 1u && strings_equal(
            arguments[count - 1u], (const unsigned char *)"&")) {
        launch_background = 1;
        --count;
    }
    STATUS_BYTE(8) = count;
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
    foreground_job = JOB_NONE;
    launch_background = 0;
    foreground_interrupted = 0;
    background_jobs = 0;
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
    publish_background_jobs();
    if (foreground_job != JOB_NONE) {
        STATUS_BYTE(STATUS_FOREGROUND) = foreground_job;
        if ((foreground_job == JOB_XCLOCK &&
             udeks_xclock_is_running() != 0) ||
            (foreground_job == JOB_XWAVE &&
             udeks_xwave_is_running() != 0)) {
            return UDEKS_SHELL_OK;
        }
        foreground_job = JOB_NONE;
        STATUS_BYTE(STATUS_FOREGROUND) = JOB_NONE;
        if (foreground_interrupted != 0) {
            write_line(UDEKS_STDOUT, (const unsigned char *)"Interrupted");
            foreground_interrupted = 0;
        }
        if (udeks_root_terminal_prompt() != UDEKS_ROOT_TERMINAL_OK) {
            return shell_fail(UDEKS_SHELL_PROMPT);
        }
        return UDEKS_SHELL_OK;
    }

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
    STATUS_BYTE(STATUS_FOREGROUND) = foreground_job;
    if (foreground_job == JOB_NONE &&
        udeks_root_terminal_prompt() != UDEKS_ROOT_TERMINAL_OK) {
        return shell_fail(UDEKS_SHELL_PROMPT);
    }
    return UDEKS_SHELL_OK;
}

unsigned char udeks_shell_interrupt_foreground(void)
{
    unsigned char stopped;

    stopped = 0;
    if (foreground_job == JOB_XCLOCK) {
        stopped = udeks_xclock_stop() == UDEKS_XCLOCK_OK;
    } else if (foreground_job == JOB_XWAVE) {
        stopped = udeks_xwave_stop() == UDEKS_XWAVE_OK;
    }
    if (stopped != 0) {
        foreground_interrupted = 1;
        ++STATUS_BYTE(STATUS_INTERRUPTS);
    }
    return stopped;
}
