/* SPDX-License-Identifier: GPL-3.0-or-later */
#include "udeks/program.h"
#include "udeks/memory.h"
#include "udeks/task_request.h"
#include "udeks/service_control.h"
#ifndef UDEKS_RECOVERY
#include "udeks/startup.h"
static unsigned char startup_active;
#endif

#define LINE_CAPACITY 54u
#define USH_STATUS(offset) \
    (*(volatile unsigned char *)(UDEKS_USH_STATUS_BASE + (offset)))
#define USH_COMMANDS USH_STATUS(UDEKS_USH_STATUS_COMMANDS)
#define USH_STATE USH_STATUS(UDEKS_USH_STATUS_STATE)
#define CWD_KIND (*(volatile unsigned char *)UDEKS_ROOT_CWD_KIND)
#define CWD_ROOT 0u
#define CWD_BIN 1u

static unsigned char started;
static unsigned char waiting_foreground;
static unsigned char line_length;
static unsigned char line[LINE_CAPACITY + 1u];
extern unsigned char submit_request(unsigned char, unsigned char, unsigned char);
#define PAYLOAD ((volatile unsigned char *)(UDEKS_TASK_REQUEST_BASE + UDEKS_TREQ_PAYLOAD))
#define REPLY(n) (*(volatile unsigned char *)(UDEKS_CONTROL_REPLY_BASE + (n)))

static const unsigned char * const app_errors[] = {
    (const unsigned char *)"",
    (const unsigned char *)": not ready\n",
    (const unsigned char *)": already running\n",
    (const unsigned char *)": not found; check /bin\n",
    (const unsigned char *)": slot busy\n",
    (const unsigned char *)": bad program\n",
    (const unsigned char *)": I/O error\n"
};

static void service_notice(void)
{
    unsigned char result;
    const unsigned char *message;
    if (REPLY(0) != UDEKS_CONTROL_REPLY_READY) return;
    result = REPLY(4);
    /* Console writes do not replace this mailbox; no new command is issued
     * while its completion is being consumed. */
    REPLY(0) = 0;
    if (result == UDEKS_CONTROL_INTERRUPTED) {
        message = (const unsigned char *)"Interrupted\n";
    } else if (REPLY(1) == UDEKS_CONTROL_DESKTOP) {
        message = (const unsigned char *)(result ? "xinit: failed\n" :
            REPLY(2) ? "VIC-II graphics stopped\n" : "VIC-II graphics active\n");
    } else if (REPLY(1) == UDEKS_CONTROL_ENGINE) {
        message = (const unsigned char *)(result ? "Z80 self-test: failed\n" : "Z80 self-test: OK\n");
    } else {
        udeks_write(1, (const unsigned char *)(REPLY(1) == UDEKS_CONTROL_CLOCK ? "xclock" : "xwave"));
        if (result) {
            if (result > UDEKS_CONTROL_DISK_ERROR) result = UDEKS_CONTROL_NOT_READY;
            message = app_errors[result];
        } else message = (const unsigned char *)(REPLY(2) ? " stopped\n" :
            REPLY(3) ? " started &\n" : " running (Ctrl+C stops)\n");
    }
    udeks_write(1, message);
}

static void write_line(const unsigned char *text)
{
    udeks_write(UDEKS_STDOUT, text);
    udeks_write_byte(UDEKS_STDOUT, '\n');
}

static unsigned char skip_space(unsigned char position)
{
    while (line[position] == ' ' || line[position] == '\t') {
        ++position;
    }
    return position;
}

static unsigned char command_end(
    unsigned char position, const unsigned char *name)
{
    while (*name != 0 && line[position] == *name) {
        ++position;
        ++name;
    }
    if (*name != 0 || (line[position] != 0 &&
                       line[position] != ' ' && line[position] != '\t')) {
        return 0xFFu;
    }
    return position;
}

static unsigned char text_equal(
    unsigned char position, const unsigned char *text)
{
    while (line[position] != 0 && *text != 0 && line[position] == *text) {
        ++position;
        ++text;
    }
    return line[position] == 0 && *text == 0;
}

static void finish_command(void)
{
    line_length = 0;
    line[0] = 0;
#ifndef UDEKS_RECOVERY
    if (!startup_active)
#endif
        udeks_prompt();
}

static void dispatch_line(void)
{
    unsigned char command;
    unsigned char rest;
    unsigned char result;
    unsigned char target;

    ++USH_COMMANDS;
    command = skip_space(0);
#ifndef UDEKS_RECOVERY
    if (startup_active && line[command] == '#') {
        finish_command();
        return;
    }
#endif
    if (line[command] == 0) {
        finish_command();
        return;
    }

    rest = command_end(command, (const unsigned char *)"echo");
    if (rest != 0xFFu) {
        rest = skip_space(rest);
        write_line(line + rest);
        finish_command();
        return;
    }

    rest = command_end(command, (const unsigned char *)"help");
    if (rest != 0xFFu && line[skip_space(rest)] == 0) {
        write_line((const unsigned char *)"cd clear echo help pwd xinit xclock xwave\nDisk: cat cowsay date df free ls lscpu lshw lsmod uname z80ctl\nRecovery: mount umount");
        finish_command();
        return;
    }

    rest = command_end(command, (const unsigned char *)"clear");
    if (rest != 0xFFu && line[skip_space(rest)] == 0) {
        udeks_write_byte(1, '\f');
        finish_command();
        return;
    }

    target = UDEKS_CONTROL_DESKTOP;
    rest = command_end(command, (const unsigned char *)"xinit");
    if (rest == 0xFFu) {
        target = UDEKS_CONTROL_CLOCK;
        rest = command_end(command, (const unsigned char *)"xclock");
    }
    if (rest == 0xFFu) {
        target = UDEKS_CONTROL_WAVE;
        rest = command_end(command, (const unsigned char *)"xwave");
    }
    if (rest != 0xFFu) {
        rest = skip_space(rest);
        PAYLOAD[0] = target; PAYLOAD[1] = 0; PAYLOAD[2] = 0;
        if (text_equal(rest, (const unsigned char *)"-q")) PAYLOAD[1] = UDEKS_CONTROL_STOP;
        else if (target != UDEKS_CONTROL_DESKTOP && text_equal(rest, (const unsigned char *)"&")) PAYLOAD[2] = 1;
        else if (line[rest]) {
            write_line((const unsigned char *)"xinit [-q]; xclock/xwave [-q|&]");
            finish_command(); return;
        }
        result = submit_request(UDEKS_TREQ_OP_CONTROL, 0, UDEKS_CONTROL_COUNT);
    } else {

    rest = command_end(command, (const unsigned char *)"pwd");
    if (rest != 0xFFu && line[skip_space(rest)] == 0) {
        if (submit_request(UDEKS_TREQ_OP_GETCWD, 0, 0) != UDEKS_IO_ERROR)
            write_line((const unsigned char *)PAYLOAD);
        finish_command();
        return;
    }

    rest = command_end(command, (const unsigned char *)"cd");
    if (rest != 0xFFu) {
        rest = skip_space(rest);
        result = 0;
        while (line[rest] && result < 23u) PAYLOAD[result++] = line[rest++];
        if (!result) PAYLOAD[result++] = '/';
        PAYLOAD[result] = 0;
        if (line[rest] || submit_request(UDEKS_TREQ_OP_CHDIR, 0, result) == UDEKS_IO_ERROR)
            write_line((const unsigned char *)"cd: not a directory or unavailable");
        finish_command();
        return;
    }

    result = udeks_exec_line(line, line_length);
    }
    line_length = 0;
    line[0] = 0;
    if (result == UDEKS_TREQ_EXEC_FOREGROUND) {
        waiting_foreground = 1;
        return;
    }
    if (result == UDEKS_IO_ERROR) {
        write_line((const unsigned char *)"ush: failed");
    }
#ifndef UDEKS_RECOVERY
    if (!startup_active)
#endif
        udeks_prompt();
}

unsigned char udeks_ush_poll(void)
{
    unsigned char buffer[UDEKS_TASK_REQUEST_PAYLOAD_SIZE];
    unsigned char count;
    unsigned char index;

    if (started == 0) {
        started = 1;
        line_length = 0;
        waiting_foreground = 0;
        CWD_KIND = CWD_ROOT;
        USH_COMMANDS = 0;
        USH_STATE = UDEKS_USH_STATE_READY;
        USH_STATUS(UDEKS_USH_STATUS_MAGIC0) = 'U';
        USH_STATUS(UDEKS_USH_STATUS_MAGIC1) = 'S';
        USH_STATUS(UDEKS_USH_STATUS_MAGIC2) = 'H';
#ifndef UDEKS_RECOVERY
        if (USH_STATUS(UDEKS_USH_BOOT_SOURCE) == 1) {
            startup_active = udeks_startup_begin(USH_STATUS(UDEKS_USH_BOOT_DEVICE));
            if (startup_active == UDEKS_IO_ERROR) {
                startup_active = 0;
                write_line((const unsigned char *)"ush: RC failed");
                udeks_prompt();
            }
        }
        USH_STATUS(UDEKS_USH_STARTUP_STATE) = startup_active ? 1 : 2;
#endif
        return UDEKS_EXIT_SUCCESS;
    }
    if (waiting_foreground != 0) {
        service_notice();
        count = udeks_wait_foreground();
        if (count == UDEKS_IO_ERROR || count != 0) {
            return UDEKS_EXIT_SUCCESS;
        }
        waiting_foreground = 0;
        finish_command();
        return UDEKS_EXIT_SUCCESS;
    }

#ifndef UDEKS_RECOVERY
    if (startup_active) {
        line_length = udeks_startup_next(line);
        if (line_length) {
            /* Use the normal dispatcher, one command per cooperative turn. */
            if (line[skip_space(0)] != '#') {
                if (startup_active == 1) udeks_write_byte(UDEKS_STDOUT, '\n');
                startup_active = 2;
                udeks_write(UDEKS_STDOUT, line);
                udeks_write_byte(UDEKS_STDOUT, '\n');
            }
            dispatch_line();
        } else {
            if (startup_active == 2) udeks_prompt();
            startup_active = 0;
            USH_STATUS(UDEKS_USH_STARTUP_STATE) = 2;
        }
        return UDEKS_EXIT_SUCCESS;
    }
#endif

    if (udeks_poll(UDEKS_STDIN, UDEKS_TREQ_POLL_FOREVER) != 1u) {
        return UDEKS_EXIT_SUCCESS;
    }
    count = udeks_read(UDEKS_STDIN, buffer, sizeof(buffer));
    if (count == UDEKS_IO_ERROR) {
        return UDEKS_EXIT_SUCCESS;
    }
    for (index = 0; index < count; ++index) {
        if (buffer[index] == '\n') {
            line[line_length] = 0;
            dispatch_line();
            return UDEKS_EXIT_SUCCESS;
        }
        if (line_length < LINE_CAPACITY) {
            line[line_length] = buffer[index];
            ++line_length;
        }
    }
    return UDEKS_EXIT_SUCCESS;
}
