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

## Provisional operations

| Opcode | Name | Arguments | Result |
|---:|---|---|---|
| 0 | `NOP` | none | zero |
| 1 | `COPY` | arg0 source, arg1 destination, length byte count | copied byte count |
| 2 | `CHECKSUM16` | arg0 source, length byte count | unsigned sum of bytes modulo 65,536 |
| 3 | `XOR_ROL` | arg0 source, arg1 destination, length byte count | transformed byte count |

`XOR_ROL` writes `ROL8(source[i] XOR $A5)` to each destination byte. These
operations are provisional benchmark contracts. They become kernel ABI only
when this document reaches ABI 1.0; their current purpose is to measure
end-to-end delegation thresholds with independently verifiable results.

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

ABI 0.1 deliberately does not assign the requester role to either processor.
The benchmark harness will exercise the same state machine in both directions;
ADR 0002 will establish the normal direction before this ABI is frozen.
