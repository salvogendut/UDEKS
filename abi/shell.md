# UDEKS native shell contract 0.1

The initial shell is a resident C service layered above the root-terminal
policy service. The terminal owns keyboard editing and publishes one bounded,
NUL-terminated line. The shell consumes that line on the same cooperative
service pass, dispatches it through a static command registry, writes output to
the retained root console, and then rearms the terminal prompt.

The command-facing conventions intentionally resemble a small Unix shell:
handlers receive `argc`/`argv`, return zero for success and nonzero for
failure, and use descriptors 0, 1, and 2 for standard input, output, and error.
All output passes through the stream interface; the root console is merely the
initial binding for descriptors 1 and 2.

The parser accepts spaces and tabs as separators. It performs no allocation,
supports at most eight arguments including the command name, and deliberately
does not yet implement quoting, escaping, variables, pipelines, redirection,
history, or completion. Empty lines simply produce a new prompt. Parser limits
are errors reported on standard error rather than reasons to fail the service.

The first command registry contains:

| Command | Behavior |
|---|---|
| `help` | List registered commands and summaries. |
| `clear` | Clear and home the retained root console. |
| `echo` | Write its arguments separated by spaces. |
| `uname` | Report system identity; `uname -a` includes version and machine. |
| `lshw` | Report detected video and expansion capabilities. |
| `lsmod` | Report service-registry startup and poll state. |
| `lscpu` | Report the honest current CPU roles. |

`lscpu` initially reports the 8502 as the resident executive and the Z80 as
staged with its worker lease pending. It must not claim a live secondary engine
until the production mailbox, ownership transfer, and worker validation path
has completed successfully.

The provisional `SHLL` diagnostic record occupies 24 bytes at `$F170`. It
contains format/state/error bytes, the command count, last argument count and
command/result identifiers, plus 16-bit poll, command, unknown-command, and
parse-error counters. A compiler-neutral request ABI and stream handles remain
future work.
