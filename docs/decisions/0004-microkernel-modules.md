# ADR 0004: Assembly-oriented microkernel and C service modules

- Status: accepted
- Date: 2026-09-24

## Context

UDEKS must remain understandable and responsive on a 128 KiB machine while
supporting two CPUs, two display engines, banked memory, and varied storage and
expansion hardware. A monolithic kernel would couple every driver and policy
change to the most timing-sensitive code. A purely C kernel would also obscure
the exact interrupt, MMU, stack, and CPU-handoff behavior that this machine
requires us to control.

The C128 has no memory-protection unit. It cannot provide Unix-like protected
server processes, but it can still enforce modular responsibilities, versioned
interfaces, bounded messages, and explicit ownership.

## Decision

UDEKS is a microkernel organized around a small resident 8502 core and modular
system services.

The microkernel owns only:

- reset, interrupt, NMI, and syscall entry;
- context switching and scheduling mechanisms;
- IPC queues and minimal event delivery;
- MMU profiles, bank leases, and buffer ownership;
- capability/handle validation;
- 8502/Z80 ownership transfer and worker admission;
- the smallest hardware primitives needed to implement those mechanisms.

These core, machine-facing paths are implemented primarily in assembly and
expose narrow, versioned C-callable entry points. Policy is kept out of the
assembly core.

I/O stacks, device drivers above their register-level primitives, filesystems,
graphics, display composition, consoles, protocols, and other system policy are
service modules written predominantly in C. Applications and services use
messages, handles, and public jump tables; they do not call private kernel or
peer-module symbols.

Essential modules may be statically linked during bring-up. Static linking is
a placement choice, not permission to violate module boundaries. The module
descriptor and lifecycle ABI will allow services to become loadable and
replaceable as the loader and allocator mature.

The Z80 worker is exposed as a kernel-mediated service, not as a second kernel.
Its operations remain bounded and selected by measured benefit.

## Consequences

- Assembly is concentrated in boot, interrupt, context, MMU, IPC fast paths,
  CPU handoff, and low-level hardware access; most new functionality is C.
- Module APIs require explicit versions, byte layouts, ownership rules, and
  failure results from their first implementation.
- A faulty module can still corrupt memory. Validation, canaries, capability
  checks, watchdogs, and restartable service state provide best-effort
  containment where hardware isolation is unavailable.
- Filesystem, graphics, and device-policy choices can evolve without expanding
  or relinking against private microkernel internals.
- Performance exceptions require measurement and an ADR update; convenience
  alone is not sufficient reason to move policy into the kernel.

## Related decisions

- [ADR 0002](0002-executive-cpu.md): 8502 executive and bounded Z80 worker.
- [ADR 0003](0003-memory-bootstrap.md): native memory and bootstrap contract.
