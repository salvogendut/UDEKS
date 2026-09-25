# `cowsay` user program

`user/bin/cowsay.c` is the first source placed explicitly on the user side of
the UDEKS boundary. It is a native adaptation of
[0xAether's ccowsay](https://github.com/0xAether/ccowsay), preserving its
GPL-3.0-or-later attribution while replacing hosted `stdio`, `stdlib`, unsafe
single-character copies, and process `exit()` calls with the provisional UDEKS
program interface.

The planned command is:

```text
cowsay [-t] [-e X] message
```

It writes only to standard output or standard error, allocates no heap, uses
no device registers, and needs no Z80 lease. Alternative cow files remain
deferred until filesystem resources are available.

The program implementation is intentionally not a resident shell builtin and
is not part of the kernel link. `make user-programs` produces the independently
linked `build/user/cowsay.udx`, using only the stable write-syscall veneers.
The bootfs packer installs it as `/bin/cowsay`. It has no resident command
record or command-specific dispatch stub: after builtin lookup fails, the
bootstrap shell asks the common-RAM resolver for the matching `/bin` leaf.
The loader validates bootfs and UDEX metadata, installs the image in the first
task slot, supplies `argc`/`argv`, runs it with a private C stack and preserved
zero page, and restores the previous slot contents after exit.

This is the acceptance workload for executable loading, `argc`/`argv`,
standard descriptors, exit status, slot restoration, and memory reclamation.
The final `/bin/ush` will use the same lookup contract through a syscall, with
storage-backed `/bin` taking precedence over the early bootfs fallback.
