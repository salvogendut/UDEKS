# UDEKS native shell contract 0.2

## Native arguments and completion (2026-10-09)

The #52 native-console checkpoint extends generic foreground launch to bounded
arguments. It retains the eight-token/54-character parser and copies private
UARG 0.1 before making a native task runnable (see [executable ABI](executable.md)).
Excess arguments fail before either loader is called, with status 2. The
synchronous compatibility loader remains available; graphical entries need
not use arguments. Exact `name -q` retains its existing close semantics.
Argument-bearing background launch and terminal output are described below;
this is not full job control.

For normal native foreground exit, bookkeeping reads the task's exit byte
before reaping and publishes it at `SHLL+10` (`$F17A`). Background retirement
does not replace it. Once WAIT reports completion, ush snapshots that byte into
its own `last_status` before issuing the next prompt. This is a root-shell
completion contract, not a general wait-result pointer for arbitrary tasks.
Existing synchronous completion/loader-error bytes use the same field.

The exact command `echo $?` prints the previous eight-bit status in decimal;
echo itself then succeeds with status 0. Empty lines preserve status. Builtin
failures set nonzero status; this does not promise POSIX errno/exit remapping,
general expansion, quoting, pipes or scripting. The older baseline below
describes the original synchronous loader and graphical job interface.

## Foreground interruption (2026-10-09)

On Ctrl+C the root terminal queues a private notice in the existing control
reply mailbox: `[READY, child-id, CANCEL_PENDING=3, 0, 0]`. Child ids 3–6 are
derived from the root session's foreground bit, not pointer focus or an app
name. This is not a public CONTROL action. Native ush consumes READY before
I/O and issues existing UTRQ CANCEL (op 14, descriptor/flags 0, three bytes:
child LE16 and status 130), while executing as the child's real parent task 1.
The resident service does not impersonate a RUNNING parent or edit scheduler
state. Match the private notice producer with the rebuilt disk/recovery ush.

A successful CANCEL retires the child through existing resource cleanup,
clears any private blocked request and publishes ZOMBIE(130). Root bookkeeping
harvests the status and releases windows/allocation before WAIT completes.
Ush reports `Interrupted` only after successful cancellation, and `echo $?`
then returns 130. The same path works with or without a graphical window.
ESRCH when normal exit wins is silent and preserves its actual completion.
Other errors report `Interrupt failed` without releasing a still-live job.

The notice is consumed during the old foreground wait, before accepting a new
command; repeated Ctrl+C cannot follow a reused task id into a later launch.
Background tasks and Ctrl+C at an idle prompt are not cancellation targets.
This remains cooperative: tight loops that never return to the scheduler are
not interruptible by this mechanism. `name -q`/`xinit -q` retain their graphical
close semantics.

## Foreground canonical input (2026-10-09)

Native foreground programs can use `udeks_read(0, buffer, count)` from the
scheduled console SDK. It blocks cooperatively through existing POLL, then
copies READ's response into the caller's private buffer (1–24 bytes). The raw
READ request remains nonblocking/EAGAIN. The editor accepts up to 54 printable
characters, with backspace/cursor editing and Enter returning a final newline;
an empty line is a one-byte newline, not EOF. There is no Ctrl+D/raw mode yet.

READ/POLL authorize the actual scheduler caller: root/ush when no foreground
child exists, otherwise only that child. Background callers receive EIO (5)
before any editor change, consumption or wait registration. There is no
SIGTTIN/task suspension. A permitted foreground read/poll opens an unprefixed
editor at the current output cursor (or a new row if needed for 55 cells).
Partially consumed lines remain readable without reopening the editor.

Application input cannot recall shell history and is never saved into it.
The shell's next PROMPT discards partial or unread application input, clears
editor state and restores command history. Ctrl+C uses the existing parent
cancellation even while POLL is blocked; no window is necessary. A graphical
background peer continues while input is awaited. Counted output preserves
that active editor as described below.

## Background launch and output (2026-10-09)

A whitespace-separated final `&` launches a native UDEX 0.2 command in a free
compatible allocation without taking foreground ownership. For example,
`ticker Alpha mixed-case &` supplies three argv entries; `&` is not one of
them. The eight-argument limit still includes the program name, but excludes
the operator. Trailing spaces/tabs are allowed. Embedded or nonfinal `&` is
ordinary argument text. A bare `&` or too many arguments fails with
`Invalid command` and status 2 before either loader runs. Successful background
launch reports 0, not a stale synchronous exit byte. Legacy synchronous images
are not silently run in the background; they fail native-image validation.

Each validated UTRQ WRITE to fd 1/2 is a synchronous byte-stream transaction.
While a shell or application line is being edited, output uses a separate
cursor in the rows above it. Only those rows scroll or clear: the prompt/input
prefix, draft, edit cursor and history survive. If the editor is at row zero,
its complete row moves down once to make room. Output cursor state persists
between WRITE chunks and resets when a new editor session starts. No newline
is inserted between chunks. A zero-count WRITE changes nothing. Outside
editing, ordinary full-console stream behavior remains unchanged.

Multiple writers may interleave between requests, including the shell's own
output. There is no whole-line atomicity, output queue, per-app terminal or
POSIX process group. Foreground READ ownership/EIO rejection and targeted
Ctrl+C remain unchanged. This does not add `jobs`, `fg`, `bg`, arbitrary
background cancellation, native file calls, preemption, quoting or pipelines.

## Original shell baseline

The root shell is a persistent bank-1 `/bin/ush` task owned and polled by init.
The terminal owns keyboard editing and publishes one bounded, NUL-terminated
line. `ush` reads it through the task-request ABI, implements `cd`, `echo`,
`help`, `pwd`, and `clear` natively, writes through descriptors 1 and 2, and
requests the next prompt. It parses `xinit`/`xclock`/`xwave` options and sends
numeric CONTROL requests; app implementations are disk files. Other commands
cross a bounded compatibility EXEC to the generic loader. There is no resident
command-name registry. Foreground ownership is observed through WAIT; ush
consumes numeric completion notices and rearms its own prompt.

The command-facing conventions intentionally resemble a small Unix shell:
handlers receive `argc`/`argv`, return zero for success and nonzero for
failure, and use descriptors 0, 1, and 2 for standard input, output, and error.
All output passes through the stream interface; the root console is merely the
initial binding for descriptors 1 and 2.

The parser accepts spaces and tabs as separators. It performs no allocation,
supports at most eight arguments including the command name, and deliberately
does not yet implement quoting, escaping, variables, pipelines, redirection,
or completion. A standalone final `&` requests background execution for a
graphical command; it must be separated by whitespace. Without it, the shell
keeps the graphical command in the foreground, withholds the next prompt, and
routes VDC-console `Ctrl+C` to that job. Pointer focus on the VIC-IIe does not
change which process owns the controlling VDC terminal. The terminal editor
independently retains six volatile command
lines for Up/Down recall. Empty lines simply produce a new prompt. Parser
limits are errors reported on standard error rather than reasons to fail the
service.

Names absent from the builtin registry are searched as executable leaf names
in the bootfs mounted at `/bin`, then on mounted `/mnt`. Explicit `/mnt/NAME`
works too. Normal bootfs has only mount, umount and recovery ush. A match is validated as UDEX and run in the
transient task slot. The loader saves and restores that complete slot around a
synchronous command, so utilities such as `date` and `cowsay` remain usable
while the background `xclock` client owns its normal image there. A missing
name reports `Unknown command`. This lookup path is generic—there is no
resident `cowsay` or `date` command record.

Eight names are handled by ush: cd, clear, echo, help, pwd and the three
graphics launch/control forms. Thirteen program names are disk-backed:
cowsay, date, ls, cat, free, df, uname, lshw, lsmod, lscpu, z80ctl, xclock,
xwave (the last two have shell launch syntax and disk implementations).
Mount/umount share the small bootfs recovery helper. Disk `USH` is the shell
program itself, not another transient utility. The current command set includes:

| Command | Behavior |
|---|---|
| `help` | List shell, disk and recovery command names. |
| `clear` | Clear and home the retained root console. |
| `echo` | Write its arguments separated by spaces. |
| `date` | Read time, or set the shared clock with `HHMMSS`, `HH:MM:SS`, or `-s`. |
| `uname` | Report system identity; `uname -a` includes version and machine. |
| `lshw` | Report detected video and expansion capabilities. |
| `lsmod` | Report service-registry startup and poll state. |
| `lscpu` | Report the honest current CPU roles. |
| `z80ctl` | Show worker status or run a bounded `NOP` lease with `z80ctl test`. |
| `xinit` | Initialize the independent VIC-IIe graphics screen; `-q` stops it. |
| `xclock` | Run the managed analog clock; `-q` stops it and `&` backgrounds it. |
| `xwave` | Run the dual-engine isometric sinc mesh; `-q` stops it and `&` backgrounds it. |

`lscpu` reports the 8502 as the resident executive and claims a ready bounded
Z80 worker only after the production mailbox self-test has completed. `z80ctl`
follows the conventional Unix utility-plus-subcommand shape; it does not expose
raw MMU or mailbox access to the command layer.

The provisional `SHLL` diagnostic record occupies 24 bytes at `$F170`. It
contains format/state/error bytes, resident command count (now zero), last argument count and
command/result identifiers, 16-bit poll, command, unknown-command, and
parse-error counters, the foreground job identifier, background-job count,
and interrupt count. The compiler-neutral task-request ABI is documented in
[`task-request.md`](task-request.md); the persistent `ush` readiness and
command counters occupy `$F3D8-$F3E7`.
