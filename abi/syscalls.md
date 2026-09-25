# 8502 syscall and program-entry ABI 0.3

The initial 8502 user ABI separates program binaries from resident link-time
symbols. A program links only its own code, its required compiler runtime, and
small user-side veneers. Those veneers call fixed, versioned kernel entry
points in bank-0 RAM.

## Syscall table

The table begins at `$CF00` and occupies one reserved 256-byte page. The first
16 bytes describe the table:

| Offset | Size | Meaning |
|---:|---:|---|
| 0 | 4 | ASCII magic `USYS` |
| 4 | 1 | ABI major (`0`) |
| 5 | 1 | ABI minor (`3`) |
| 6 | 1 | Implemented vector count (`4`) |
| 7 | 1 | Header size (`16`) |
| 8 | 8 | Reserved; zero |

Each vector owns a 16-byte slot. Programs enter a vector with `JSR`; the gate
returns with the status in `A`. Version 0.3 provides:

| Address | Operation | Input |
|---:|---|---|
| `$CF10` | `write_byte` | `A` descriptor, `X` byte |
| `$CF20` | `write` | `A` descriptor, `X` pointer low, `Y` pointer high |
| `$CF30` | `task_request` | Common `$F359` request record |
| `$CF40` | `clock_set` | `A` hour, `X` minute, `Y` second; binary 24-hour values |

Descriptors follow the Unix convention already used by the shell: `0` is
standard input, `1` standard output, and `2` standard error. The two initial
write operations accept only descriptors 1 and 2. Strings are zero-terminated
and must lie completely inside the calling task's validated readable region.
The current gate delegates to the terminal stream service; later gates will
send an IPC request without changing these user-visible addresses.

The register contract is compiler-neutral. `user/lib/syscall.s` is the cc65
adapter; another compiler may supply a different adapter without changing the
program or kernel ABI. User binaries never import `_udeks_stream_write` or any
other private resident symbol.

`clock_set` rejects values outside `00:00:00` through `23:59:59`, updates
CIA1 TOD, and synchronizes the BASIC-compatible 24-bit TI counter at
`$A0-$A2`. Reading time remains a time-service operation rather than a second
syscall: the common `TIME` record publishes coherent binary fields.

## 8502 program entry

UDEX 0.1 entry receives:

- `A`: argument count;
- `X`: low byte of the argument-vector pointer;
- `Y`: high byte of the argument-vector pointer.

The vector is an array of little-endian 16-bit pointers followed by a null
pointer. Each string is zero-terminated and belongs to the task allocation.
Returning from entry terminates the foreground program; `A` is its eight-bit
exit status. `user/lib/entry.s` converts this contract to the cc65 C function
`udeks_program_main(argc, argv)`.

Before entry, the loader must validate the UDEX image, reserve its declared
image and BSS spans, clear BSS, copy bounded arguments, give it a private cc65
software-stack span, and save the executive context. On return it restores the
executive stack and the previous slot image before publishing the exit status.
These task-lifecycle operations are the next implementation milestone; the ABI
and independently linked executable exist now, but no shell command invokes
the program yet.

Transient version 0.1 programs execute from bank 0, where `$CF00` is visible.
Persistent bank-1 tasks call the common `$FF16` gate, which swaps runtime
contexts before invoking `$CF30`; they never jump into hidden bank-0 code.
