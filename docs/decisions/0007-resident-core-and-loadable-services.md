# ADR 0007: Resident core and loadable system boundary

- Status: accepted
- Date: 2026-09-25

## Context

The bring-up image proved native boot, dual-CPU handoff, two display engines,
input, a terminal, a shell, overlapping windows, and graphical applications.
Most of those components have separate descriptors and C modules, but many are
still linked into the `$2000-$CFFF` resident image. That placement has reached
its limit and, more importantly, does not satisfy the intended microkernel
dependency boundary.

The attempt to add the small `cowsay` command made the problem measurable: a
command with no privileged responsibility displaced the resident VIC shadow
region. Growing the kernel or assigning another permanent low-memory slot to
one command would preserve the wrong architecture.

## Decision

Only mechanisms that must remain authoritative across every task and service
stay resident:

- reset, trap, interrupt, panic, and context entry/exit;
- task scheduling and lifecycle primitives;
- MMU profiles, bank ownership, memory-region validation, and allocation;
- IPC, capability/handle validation, and the stable syscall gate;
- 8502/Z80 ownership transfer and bounded-lease enforcement;
- the minimal registry needed to address tasks and service endpoints.

The native boot stages are privileged bootstrap code but are not part of the
resident kernel. They load the core and an initial service bundle, then cease
to exist.

Everything else is outside the kernel:

| Current component | Target role |
|---|---|
| Hardware capability probing | Bootstrap hardware-discovery server |
| CIA time policy | Time server |
| VDC console and optional framebuffer | Console/display server |
| VIC-IIe graphics transport and policy | Display server; only bounded MMU/device gates remain privileged |
| Keyboard, joystick, and mouse policy | Input server |
| Root console, terminal editor, and streams | Terminal server |
| Window manager and compositor | Window server |
| Native shell and parser | User-level shell |
| Workload-specific Z80 operations | Engine server above the kernel handoff primitive |
| `xclock`, `xwave`, `cowsay`, and `xmandel` | User executables |

The C128 has no protection unit, so this is a validated software boundary, not
a claim of hardware isolation. A server or program may share an address space
during early implementation, but it may call only the published syscall and
message interfaces. Link placement must not create private cross-module calls.

## Bootstrap sequence

Filesystem availability cannot be a prerequisite for the driver that provides
that filesystem. The transition therefore uses two loader backends:

1. Stage 1 installs the resident core plus a bounded read-only bootfs.
2. The kernel loader validates UDEX headers and starts the minimum storage,
   console, input, terminal, and init services from that filesystem.
3. The storage and filesystem servers mount the system volume.
4. Init asks the terminal service to create the root session and loads
   `/bin/ush` as that session's first user process.
5. Later services and programs are resolved from the filesystem.
6. `ush` loads `/bin` programs on invocation and releases transient memory
   after exit.

Bootfs is a bootstrap filesystem backend, not a second executable format. Its
entries contain the same UDEX byte streams later stored as ordinary files.

## Migration order

1. Define UDEX 0.1, a syscall-vector ABI, task slots, and loader validation.
2. Make `cowsay` the first transient 8502 executable.
3. Convert the two former boot-preloaded graphical slots into loader-managed
   task slots and package `xclock` and `xwave` as UDEX programs. (Complete.)
4. Move the terminal, window, display, input, time, and engine policy into
   bootfs services, then have init launch the shell as `/bin/ush`.
5. Add IEC storage and filesystem servers and resolve noncritical modules from
   disk.
6. Replace the static service pointer table with endpoint discovery from init.

Every extraction must leave the production image bootable and its existing
behavior testable. Until a service has crossed a real syscall/message boundary,
documentation must call its static placement transitional.

## Consequences

- Resident-image pressure is treated as an architectural failure signal, not
  an invitation to hide applications in permanent kernel space.
- Programs no longer link against moving kernel C symbols; a fixed syscall
  veneer becomes their only kernel dependency.
- Filesystem implementation is necessary for the final system but does not
  block development of the executable loader and boot services.
- The loader, allocator, scheduler, IPC, and syscall validation become kernel
  work. Device behavior, presentation, command parsing, and application logic
  do not.
