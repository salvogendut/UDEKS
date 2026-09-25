# 8502/Z80 mailbox ABI

Status: **provisional**, ABI version 0.3.

The mailbox is the only state transferred implicitly across a CPU ownership
change. Both processors access the same physical bytes, but never at the same
time. Publication order therefore matters even though simultaneous writes are
impossible.

The bootstrap location is 64 bytes beginning at `$F000`, within a proposed
4 KiB top-common-RAM region. The final memory-map work may relocate it before
ABI 1.0.

All multi-byte integers are unsigned and little-endian. The normative offsets
are in `include/udeks/mailbox.h`; no compiler-native structure is normative.

| Offset | Size | Field | Meaning |
|---:|---:|---|---|
| `$00` | 4 | magic | ASCII `UDEK` |
| `$04` | 1 | ABI major | Breaking protocol revision |
| `$05` | 1 | ABI minor | Backward-compatible revision |
| `$06` | 1 | state | Idle, submitted, running, complete, or error |
| `$07` | 1 | opcode | Requested worker operation |
| `$08` | 2 | sequence | Wraparound request identifier |
| `$0A` | 1 | status | Operation-specific result status |
| `$0B` | 1 | flags | Operation flags |
| `$0C` | 2 | argument 0 | Operation-defined address or scalar |
| `$0E` | 2 | argument 1 | Operation-defined address or scalar |
| `$10` | 2 | length | Operation-defined byte count |
| `$12` | 2 | result | Operation-defined scalar result |
| `$14` | 44 | reserved | Must be zero when submitting a request |

## Operations

| Opcode | Name | Arguments | Result |
|---:|---|---|---|
| 0 | `NOP` | none | zero |
| 1 | `COPY` | arg0 source, arg1 destination, length byte count | copied byte count |
| 2 | `CHECKSUM16` | arg0 source, length byte count | unsigned sum of bytes modulo 65,536 |
| 3 | `XOR_ROL` | arg0 source, arg1 destination, length byte count | transformed byte count |
| 4 | `WAVE_SAMPLES` | arg0 low byte phase, arg1 low byte phase step, length 1–64 | next phase; signed samples at `$F300-$F33F` |
| 5 | `SURFACE_ROWS` | arg0 starting row (0–20), arg1 row count (1–2), length = rows × 25 | next row; signed sinc heights at `$F300-$F33F` |

`NOP` is implemented by the resident production worker and is used for boot
self-test and explicit lease testing. `WAVE_SAMPLES` is the first production
compute operation. It writes no more than 64 signed eight-bit sine samples to
the fixed common-RAM transfer buffer and has a statically bounded loop.
`SURFACE_ROWS` is the bounded two-dimensional successor used by `xwave`. It
returns one or two rows of a 25×21 fixed-point radial sinc grid; its maximum
50 samples keep every Z80 ownership lease statically bounded.
`COPY`, `CHECKSUM16`, and `XOR_ROL`
remain benchmark-only contracts; submitting them to the production worker
returns `ERROR` with status `4` until their buffer-ownership rules are defined.
`XOR_ROL` writes `ROL8(source[i] XOR $A5)` to each destination byte.

Worker status values are zero for success, `1` for bad magic, `2` for an
unsupported ABI, `3` for an invalid state, `4` for an unsupported opcode, and
`5` for nonzero reserved bytes, and `6` for an invalid bounded length.

## Publication protocol

1. The requesting CPU waits for `IDLE`, `COMPLETE`, or `ERROR`.
2. It fills the request fields and increments the sequence number.
3. It writes `SUBMITTED` last and transfers bus ownership.
4. The secondary CPU validates magic and ABI, then writes `RUNNING`.
5. It writes result fields, then `COMPLETE` or `ERROR` last.
6. It returns bus ownership. The requester validates the sequence number before
   consuming the result.

The secondary CPU must always return ownership within the operation's
documented maximum budget. A hardware-independent timeout cannot rescue the
executive while the secondary CPU owns the bus, so secondary-engine code is
part of the trusted kernel.

The production requester additionally clears offsets `$0A-$3F` before filling
each request and validates the response state, worker status, and unchanged
sequence after ownership returns. The first working implementation is
specified by the [Z80 worker service contract](z80-worker.md).

ADR 0002 establishes the 8502 executive as the normal requester and the Z80 as
the worker. ABI 0.3 continues to exercise both directions for diagnostics, but
production Z80-to-8502 requests are not part of the normal scheduling model.
