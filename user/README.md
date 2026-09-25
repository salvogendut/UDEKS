# UDEKS user programs

This tree contains programs that execute outside the resident microkernel.

- `bin/` contains command and application sources.
- `include/udeks/` contains the user-visible ABI only. It must not expose
  private kernel or service symbols.
- `lib/shell_parser.c` is the allocation-free tokenizer shared with the
  transitional resident compatibility dispatcher and available to later
  user-program revisions.
- `lib/task_stream.c` provides the public request-backed stream operations used
  by persistent bank-1 tasks.

`make user-sources` compiles staged programs independently of the kernel.
`make user-programs` links and packages them in the
[UDEX executable format](../abi/executable.md) against only the public
[syscall ABI](../abi/syscalls.md). It then installs the early programs in the
read-only [boot filesystem](../abi/bootfs.md), mounted as `/bin`. The same UDEX
files will later be installed in the storage-backed filesystem without format
conversion.

The current bootfs contains the standalone `/bin/cowsay` acceptance program
and persistent `/bin/ush`. Init polls that shell image from bank 1. `ush` owns
terminal-line input and implements `echo`, `help`, and `uname`; commands not
yet extracted use the bounded compatibility exec/wait requests so their
existing behavior remains available during migration.

Do not add a shell builtin or resident service merely to launch a program.
