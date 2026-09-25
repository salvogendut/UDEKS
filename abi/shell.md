# UDEKS native shell contract 0.2

The root shell is a persistent bank-1 `/bin/ush` task owned and polled by init.
The terminal owns keyboard editing and publishes one bounded, NUL-terminated
line. `ush` reads it through the task-request ABI, implements `echo`, `help`,
and `uname` natively, writes through descriptors 1 and 2, and requests the next
prompt. Commands not yet extracted cross a bounded compatibility-exec request
to the resident dispatcher; foreground jobs are observed through an explicit
wait request.

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
in the bootfs mounted at `/bin`. A match is validated as UDEX and run in the
transient task slot. A missing name reports `Unknown command`; a slot occupied
by `xclock` reports `<name>: task slot busy`. This lookup path is generic—there
is no resident `cowsay` command record.

The current native and compatibility command set contains:

| Command | Behavior |
|---|---|
| `help` | List registered commands and summaries. |
| `clear` | Clear and home the retained root console. |
| `echo` | Write its arguments separated by spaces. |
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
contains format/state/error bytes, the command count, last argument count and
command/result identifiers, 16-bit poll, command, unknown-command, and
parse-error counters, the foreground job identifier, background-job count,
and interrupt count. The compiler-neutral task-request ABI is documented in
[`task-request.md`](task-request.md); the persistent `ush` readiness and
command counters occupy `$F3D8-$F3E7`.
