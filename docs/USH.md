# `/bin/ush` migration

`ush` is the planned native UDEKS shell. It is a user process owned by init,
not a kernel service. Its command grammar and names remain Bash-like while its
implementation stays small enough for a stock C128.

## Current transition

The production image now packages a minimal persistent `ush.udx` in the
read-only `/bin` bootfs. Init resolves it by name through the common-RAM UDEX
loader, which validates and allocates it at bank-1 `$9000`; init then invokes
one bounded poll on every service pass. `ush` now owns
submitted terminal lines and implements `echo`, `help`, and `uname` natively
through the public stream ABI. Commands not yet extracted cross a bounded
compatibility-exec request, so existing graphical commands and standalone
program loading remain usable. Foreground jobs use an explicit wait request
and retain the existing `Ctrl+C` behavior. The registry no longer owns a shell
descriptor, although init continues polling resident compatibility state for
forwarded jobs.

The common-RAM diagnostic block at `$F3D8-$F3E7` exposes the dispatched
command counter at offset 0 and shell state at offset 1. The byte sequence
`A5 55 53 48` at offsets 1 through 4 (`$A5`, `USH`) means that `ush` has
completed its first poll and is ready to accept submitted input.

This is deliberately called a transition, not a completed user-space shell.
The resident implementation still calls private terminal, graphics, window,
and application functions and therefore cannot be wrapped honestly in UDEX.

## Required execution model

The two low bank-0 application slots remain occupied by `xclock` and `xwave`.
`ush` will therefore run from a persistent bank-1 8502 task allocation, outside
the resident Z80 image and VIC-IIe display window. A bounded common-RAM gate now
supplies the context switch. The complete task path must:

1. preserve the resident cc65 zero page and software-stack pointer;
2. enter the bank-1 task profile and call one cooperative `ush` poll;
3. marshal service requests synchronously through common RAM and return from
   the shell poll when the task must yield;
4. return to the service loop without disturbing Z80 or VIC ownership;
5. retain the shell's BSS, history-facing state, and working directory between
   polls.

The host image builder validates the packaged `/bin/ush`; stage 1 only
relocates bootfs. Init invokes the loader's persistent entry before resetting
and polling the task gate. The completed shell will use only public operations for terminal
input, streams, process execution, job control, system queries, and filesystem
access.

## Extraction gates

- [x] Put init, not the static registry, in charge of the root session.
- [x] Move tokenization into the user source tree.
- [x] Resolve non-builtin commands through `/bin` bootfs.
- [x] Define and link the bounded bank-1 8502 cooperative-task context gate.
- [x] Define the common-RAM task request protocol and public stream wrappers.
- [x] Add nonblocking terminal-read and bounded terminal-write requests.
- [x] Add prompt, compatibility-exec, and foreground-wait operations.
- [ ] Add scheduler yield and signal operations.
- [ ] Replace direct graphical builtins with `/bin` programs or service calls.
- [x] Link a minimal `ush.udx` without resident private symbols.
- [x] Validate, initially boot-preload, and have init poll `/bin/ush` alongside the
  compatibility shell.
- [x] Replace the fixed boot preload with init-driven persistent-task loading.
- [ ] Remove the resident shell descriptor, implementation, and compatibility
  delegation completely.
- [ ] Resolve `/bin/ush` and other commands from the mounted disk filesystem,
  retaining bootfs only as an early/recovery fallback.
