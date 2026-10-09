# UDEKS native shell contract 0.2

## Native arguments and completion (2026-10-09)

The #52 native-console checkpoint extends generic foreground launch to bounded
arguments. It retains the eight-token/54-character parser and copies private
UARG 0.1 before making a native task runnable (see [executable ABI](executable.md)).
Excess arguments fail before either loader is called, with status 2. The
synchronous compatibility loader remains available; graphical entries need
not use arguments. Bare `name &` and exact `name -q` retain their existing
semantics. Argument-bearing background launches, foreground stdin and Ctrl+C
for a no-window task still need terminal policy; this is not full job control.

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
