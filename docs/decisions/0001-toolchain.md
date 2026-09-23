# ADR 0001: Dual target toolchain

- Status: accepted
- Date: 2026-09-23

## Decision

Use cc65, ca65, and ld65 for 8502 code. Use SDCC and its `sdasz80`/linker tools
for C-linked Z80 images. Use RASM for independent handwritten Z80 images and
diagnostics. Coordinate the builds with GNU Make.

The reference environment is `my-distrobox`, but the commands remain usable in
any POSIX-like host environment with the tools on `PATH`.

## Rationale

cc65 has mature C128 support and an explicit linker-configuration model suited
to banked memory. ca65 gives C and assembly one object format on the executive
side. SDCC is already proven locally for nontrivial Z80 C in GEOBENCH. RASM is
already proven locally for large standalone Z80 assembly images.

GEOBENCH keeps SDCC and RASM at a binary boundary rather than trying to make
RASM consume SDCC relocatable objects. UDEKS retains that rule. Assembly that
must directly link with Z80 C uses `sdasz80`; RASM images communicate through a
fixed entry or jump-table ABI.

## Consequences

- The project owns both startup runtimes and all linker layouts.
- Cross-CPU interfaces cannot rely on either compiler's calling convention.
- Tool versions must be pinned and compiler-output regressions tested.
- LLVM-MOS may be evaluated experimentally, but it is not a release toolchain
  unless a later decision replaces this one with size, speed, and correctness
  evidence.
