/* SPDX-License-Identifier: GPL-3.0-or-later */
/* Root-session compatibility bridge, NOT a command shell. Names, options and
 * presentation belong to disk ush/programs. Retains serialized EXEC and job
 * ownership until those compatibility operations migrate to native tasks. */
#include "udeks/line_editor.h"
#include "udeks/root_terminal.h"
#include "udeks/shell.h"
#include "udeks/stream.h"
#include "udeks/task.h"
#define UDEKS_CONTROL_VALIDATE
#include "udeks/service_control.h"
#include "udeks/mailbox.h"
#include "udeks/z80_worker.h"
#include "udeks/vic_graphics.h"
#include "udeks/window.h"
#include "udeks/xclock.h"
#include "udeks/xwave.h"

extern unsigned char udeks_shell_read_line(unsigned char *, unsigned char);
#ifdef UDEKS_SESSION_HOST_TEST
extern unsigned char session_memory[65536];
#define S(n) session_memory[UDEKS_SHELL_STATUS_BASE + (n)]
#define R (session_memory + UDEKS_TASK_REQUEST_BASE)
#define REPLY (session_memory + UDEKS_CONTROL_REPLY_BASE)
#define USH_READY (session_memory[UDEKS_USH_STATUS_BASE + 1u] == UDEKS_USH_STATE_READY)
#else
#define S(n) (*(volatile unsigned char *)(UDEKS_SHELL_STATUS_BASE + (n)))
#define R ((volatile unsigned char *)UDEKS_TASK_REQUEST_BASE)
#define REPLY ((volatile unsigned char *)UDEKS_CONTROL_REPLY_BASE)
#define USH_READY (*(volatile unsigned char *)(UDEKS_USH_STATUS_BASE + 1u) == UDEKS_USH_STATE_READY)
#endif

#pragma bss-name(push, "HIGHBSS")
unsigned char udeks_shell_command_line[UDEKS_LINE_EDITOR_CAPACITY + 1u];
static unsigned char offsets[UDEKS_SHELL_MAX_ARGUMENTS];
static unsigned char *arguments[UDEKS_SHELL_MAX_ARGUMENTS];
unsigned char udeks_shell_foreground_job;
#pragma bss-name(pop)
static unsigned char queued_target, queued_action, queued_background;
static unsigned char background_jobs;
#define foreground udeks_shell_foreground_job

static void increment(unsigned char offset)
{
    if (++S(offset) == 0) ++S(offset + 1u);
}

static void publish_jobs(void)
{
    if (!udeks_xclock_is_running()) background_jobs &= ~1u;
    if (!udeks_xwave_is_running()) background_jobs &= ~2u;
    S(20) = foreground;
    S(21) = (background_jobs & 1u) + ((background_jobs >> 1) & 1u);
}

/* Validate completely before changing the queue or mailbox. */
void udeks_service_control_request(void)
{
    unsigned char error = 0;
    if (R[UDEKS_TREQ_MINOR] < 7u) error = UDEKS_TREQ_ENOSYS;
    else if (R[UDEKS_TREQ_DESCRIPTOR] || R[UDEKS_TREQ_FLAGS] ||
        R[UDEKS_TREQ_COUNT] != UDEKS_CONTROL_COUNT ||
        !udeks_control_valid(R[14], R[15], R[16])) error = UDEKS_TREQ_EINVAL;
    else if (queued_target || S(23) || foreground) error = UDEKS_TREQ_EBUSY;
    if (!error) {
        queued_target = R[14]; queued_action = R[15]; queued_background = R[16];
        REPLY[0] = 0;
    }
    R[UDEKS_TREQ_RESULT] = error ? 0 : UDEKS_TREQ_EXEC_FOREGROUND;
    R[UDEKS_TREQ_ERROR] = error;
    R[UDEKS_TREQ_STATE] = error ? UDEKS_TREQ_STATE_ERROR : UDEKS_TREQ_STATE_COMPLETE;
}

static void control_reply(unsigned char target, unsigned char action,
    unsigned char background, unsigned char result)
{
    REPLY[1] = target; REPLY[2] = action; REPLY[3] = background; REPLY[4] = result;
    REPLY[0] = UDEKS_CONTROL_REPLY_READY;
    S(10) = result;
}

/* Only on the bank-0 service poll, AFTER the task gateway unwinds. */
static void run_control(void)
{
    unsigned char result, bit;
    unsigned int worker_result;
    result = 0;
    if (queued_target == UDEKS_CONTROL_ENGINE) {
        result = udeks_z80_submit(UDEKS_MB_OP_NOP, 0, 0, 0, &worker_result);
        if (!result && worker_result) result = 1;
    } else if (queued_target == UDEKS_CONTROL_DESKTOP) {
        if (queued_action == UDEKS_CONTROL_STOP) {
            if (udeks_xclock_is_running()) udeks_xclock_stop();
            if (udeks_xwave_is_running()) udeks_xwave_stop();
            foreground = background_jobs = 0;
            udeks_window_manager_reset();
            result = udeks_vic_graphics_shutdown();
        } else result = udeks_vic_graphics_initialize();
    } else {
        bit = queued_target == UDEKS_CONTROL_CLOCK ? 1u : 2u;
        if (queued_action == UDEKS_CONTROL_STOP) {
            result = bit == 1 ? udeks_xclock_stop() : udeks_xwave_stop();
            if (!result) background_jobs &= ~bit;
        } else {
            if (!udeks_vic_graphics_is_active()) result = udeks_vic_graphics_initialize();
            if (!result) result = bit == 1 ? udeks_xclock_start() : udeks_xwave_start();
            if (!result) {
                if (queued_background) background_jobs |= bit;
                else foreground = bit;
            }
        }
    }
    control_reply(queued_target, queued_action, queued_background, result);
    queued_target = 0;
    increment(14);
    publish_jobs();
}

/* Compatibility EXEC: tokenization and loading only; no builtin catalogue. */
unsigned char udeks_shell_dispatch_line(void)
{
    unsigned char count, i, result;
    unsigned int loaded;
    volatile unsigned char *task = (volatile unsigned char *)UDEKS_TASK_STATUS_BASE;
    count = udeks_shell_tokenize(udeks_shell_command_line, offsets, UDEKS_SHELL_MAX_ARGUMENTS);
    if (count == UDEKS_SHELL_PARSE_TOO_MANY) {
        increment(18);
        udeks_stream_write(2, (const unsigned char *)"Too many arguments\n");
        return 0;
    }
    S(8) = count;
    if (!count) return 0;
    for (i = 0; i < count; ++i) arguments[i] = udeks_shell_command_line + offsets[i];
    loaded = ((udeks_task_loader_entry)UDEKS_TASK_LOADER_ENTRY)(count, arguments);
    result = loaded == UDEKS_TASK_SLOT_OWNED ? UDEKS_TASK_BUSY : task[UDEKS_TASK_ERROR_OFFSET];
    S(9) = result ? 0xFFu : 0xFEu;
    S(10) = result ? result : task[UDEKS_TASK_EXIT_OFFSET];
    if (!result) { increment(14); return 0; }
    if (result == UDEKS_TASK_NOT_FOUND) {
        increment(16);
        udeks_stream_write(2, (const unsigned char *)"Unknown command: ");
        udeks_stream_write(2, arguments[0]);
        udeks_stream_write_byte(2, '\n');
    } else {
        udeks_stream_write(2, arguments[0]);
        udeks_stream_write(2, (const unsigned char *)(result == UDEKS_TASK_BUSY ?
            ": task slot busy\n" : ": loader error\n"));
    }
    return 0;
}

unsigned char udeks_shell_start(void)
{
    unsigned char i;
    for (i = 0; i < UDEKS_SHELL_STATUS_SIZE; ++i) S(i) = 0;
    S(0) = 'S'; S(1) = 'H'; S(2) = 'L'; S(3) = 'L'; S(4) = 1;
    foreground = background_jobs = queued_target = 0;
    REPLY[0] = 0;
    S(5) = UDEKS_SHELL_STATE_READY;
    return 0;
}

unsigned char udeks_shell_poll(void)
{
    unsigned char result;
    increment(12);
    publish_jobs();
    if (foreground) {
        if ((foreground == 1 && udeks_xclock_is_running()) ||
            (foreground == 2 && udeks_xwave_is_running())) return 0;
        foreground = 0;
        S(20) = 0;
        if (!USH_READY) udeks_root_terminal_prompt();
        return 0;
    }
    if (queued_target) { run_control(); return 0; }
    if (S(23)) { S(23) = 0; result = UDEKS_LINE_EDITOR_OK; }
    else result = udeks_shell_read_line(udeks_shell_command_line, sizeof(udeks_shell_command_line));
    if (result != UDEKS_LINE_EDITOR_OK) return 0;
    udeks_shell_dispatch_line();
    if (queued_target) run_control();
    if (!USH_READY && !foreground) udeks_root_terminal_prompt();
    return 0;
}

unsigned char udeks_shell_interrupt_foreground(void)
{
    unsigned char stopped = 0;
    if (foreground == 1) stopped = udeks_xclock_stop() == 0;
    else if (foreground == 2) stopped = udeks_xwave_stop() == 0;
    if (stopped) {
        control_reply(foreground + 1u, UDEKS_CONTROL_STOP, 0, UDEKS_CONTROL_INTERRUPTED);
        ++S(22);
    }
    return stopped;
}
