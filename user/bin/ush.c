/* SPDX-License-Identifier: GPL-3.0-or-later */
#include "udeks/program.h"
#include "udeks/task_request.h"

#define LINE_CAPACITY 54u
#define USH_STATUS(offset) \
    (*(volatile unsigned char *)(UDEKS_USH_STATUS_BASE + (offset)))
#define USH_COMMANDS USH_STATUS(UDEKS_USH_STATUS_COMMANDS)
#define USH_STATE USH_STATUS(UDEKS_USH_STATUS_STATE)

static unsigned char started;
static unsigned char waiting_foreground;
static unsigned char line_length;
static unsigned char line[LINE_CAPACITY + 1u];

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
    udeks_prompt();
}

static void dispatch_line(void)
{
    unsigned char command;
    unsigned char rest;
    unsigned char result;

    ++USH_COMMANDS;
    command = skip_space(0);
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

    rest = command_end(command, (const unsigned char *)"uname");
    if (rest != 0xFFu) {
        rest = skip_space(rest);
        if (line[rest] == 0) {
            write_line((const unsigned char *)"UDEKS");
            finish_command();
            return;
        }
        if (text_equal(rest, (const unsigned char *)"-a")) {
            write_line((const unsigned char *)"UDEKS 0.1.0 c128 8502");
            finish_command();
            return;
        }
    }

    rest = command_end(command, (const unsigned char *)"help");
    if (rest != 0xFFu && line[skip_space(rest)] == 0) {
        write_line((const unsigned char *)"Native ush: echo help uname");
        write_line((const unsigned char *)"Other commands use compatibility exec");
        finish_command();
        return;
    }

    result = udeks_exec_line(line, line_length);
    line_length = 0;
    line[0] = 0;
    if (result == UDEKS_TREQ_EXEC_FOREGROUND) {
        waiting_foreground = 1;
        return;
    }
    if (result == UDEKS_IO_ERROR) {
        write_line((const unsigned char *)"ush: exec request failed");
    }
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
        USH_COMMANDS = 0;
        USH_STATE = UDEKS_USH_STATE_READY;
        USH_STATUS(UDEKS_USH_STATUS_MAGIC0) = 'U';
        USH_STATUS(UDEKS_USH_STATUS_MAGIC1) = 'S';
        USH_STATUS(UDEKS_USH_STATUS_MAGIC2) = 'H';
        return UDEKS_EXIT_SUCCESS;
    }
    if (waiting_foreground != 0) {
        count = udeks_wait_foreground();
        if (count == UDEKS_IO_ERROR || count != 0) {
            return UDEKS_EXIT_SUCCESS;
        }
        waiting_foreground = 0;
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
