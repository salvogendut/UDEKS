# UDEKS user programs

This tree contains programs that execute outside the resident microkernel.

- `bin/` contains command and application sources.
- `include/udeks/` contains the user-visible ABI only. It must not expose
  private kernel or service symbols.
- `lib/shell_parser.c` is the first source extracted from the transitional
  resident shell for reuse by the future `/bin/ush`.

`make user-sources` compiles staged programs independently of the kernel.
`make user-programs` links and packages them in the
[UDEX executable format](../abi/executable.md) against only the public
[syscall ABI](../abi/syscalls.md). It then installs the early programs in the
read-only [boot filesystem](../abi/bootfs.md), mounted as `/bin`. The same UDEX
files will later be installed in the storage-backed filesystem without format
conversion.

Do not add a shell builtin or resident service merely to launch a program.
