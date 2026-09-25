# `/bin/ush` migration

`ush` is the planned native UDEKS shell. It is a user process owned by init,
not a kernel service. Its command grammar and names remain Bash-like while its
implementation stays small enough for a stock C128.

## Current transition

The production image still executes the shell policy from the resident image,
but the registry no longer owns a shell descriptor. A minimal init service owns
the root session and delegates start/poll calls to that bootstrap shell. The
dependency-free tokenizer already lives under `user/lib/`; executable lookup
is generic and searches the read-only `/bin` bootfs rather than containing a
`cowsay` builtin.

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

Init will validate and install `/bin/ush`, then invoke that poll entry after the
terminal service. The shell will use only public operations for terminal input,
streams, process execution, job control, system queries, and filesystem access.

## Extraction gates

- [x] Put init, not the static registry, in charge of the root session.
- [x] Move tokenization into the user source tree.
- [x] Resolve non-builtin commands through `/bin` bootfs.
- [x] Define and link the bounded bank-1 8502 cooperative-task context gate.
- [x] Define the common-RAM task request protocol and public stream wrappers.
- [x] Add nonblocking terminal-read and bounded terminal-write requests.
- [ ] Add prompt, task-yield, exec, wait, and signal operations.
- [ ] Replace direct graphical builtins with `/bin` programs or service calls.
- [ ] Link `ush.udx` without resident private symbols.
- [ ] Have init install and poll `/bin/ush` at boot.
- [ ] Remove the resident shell descriptor, implementation, and compatibility
  delegation completely.
- [ ] Resolve `/bin/ush` and other commands from the mounted disk filesystem,
  retaining bootfs only as an early/recovery fallback.
