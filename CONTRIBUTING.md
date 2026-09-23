# Contributing to UDEKS

UDEKS is licensed under `GPL-3.0-or-later`. By contributing, you agree that
your contribution may be distributed under those terms.

## Development workflow

1. Enter `my-distrobox` if you use the reference environment.
2. Run `make doctor` to inspect the toolchain.
3. Run `make check` before and after a change.
4. Build the affected image with `make 8502`, `make z80`, or `make z80-asm`.
5. Add a focused host or emulator regression test for behavioral changes.

## Source conventions

- Put `SPDX-License-Identifier: GPL-3.0-or-later` in source files.
- Keep hardware addresses and bit definitions in named interfaces.
- Keep interrupt entry, MMU transitions, CPU handoff, and cycle-sensitive code
  in assembly. Keep policy and state machines in C where practical.
- Use fixed-width integer types in protocols and on-disk formats.
- Do not expose compiler-native structs as an inter-CPU or on-disk ABI. Specify
  byte offsets and byte order instead.
- Avoid recursion, floating point, hidden large temporaries, and unbounded Z80
  work units.
- Treat compiler optimization changes as behavior changes until emulator and
  hardware tests demonstrate otherwise.

Architecture-affecting decisions should be added under `docs/decisions/`.
