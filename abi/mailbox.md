# 8502/Z80 mailbox ABI

Status: **provisional**, ABI version 0.1.

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

## Publication protocol

1. The 8502 waits for `IDLE`, `COMPLETE`, or `ERROR`.
2. It fills the request fields and increments the sequence number.
3. It writes `SUBMITTED` last and transfers bus ownership.
4. The Z80 validates magic and ABI, then writes `RUNNING`.
5. The Z80 writes result fields, then `COMPLETE` or `ERROR` last.
6. The Z80 returns bus ownership. The 8502 validates the sequence number before
   consuming the result.

The Z80 must always return ownership within the operation's documented maximum
budget. A hardware-independent timeout cannot rescue the 8502 while the Z80
owns the bus, so worker code is part of the trusted kernel.
