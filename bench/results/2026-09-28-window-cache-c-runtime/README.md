# Private C cache runtime results

Both 1986 and VICE pass 66 alignment/edge images (547 dispatcher calls / 132 rows)
and the 168×104 complete image (439 calls / 208 rows). Each includes one rejected
selector, giving 546/438 actual C function invocations. All 8,000 shadow bytes
and 32 logical dirty flags match the independent oracle. Runtime restoration,
four caller I/D modes, returned software SP, hardware/caller/private stack
guards and the seeded bank-1 shell-stack area pass.

All three actual one-byte fault programs are detected and rejected by the
normal decoder even with correct pixels. The diagnostic wrapper repairs a
bad ZP restore only after recording it; the candidate binding has no repair.

32-bit IRQ counts: matrix/default 19,383/29,259 in 1986, 19,327/29,141 in VICE.
The lowest observed changed private-stack byte is `$4DDE` in all positive
cases; this is not an instrumented minimum-SP or a worst-case depth bound.
These runs do not qualify NMI, live GUI input/tasks/Z80 or physical hardware.

`report.json`, run-to-program hashes, raw records and emulator provenance are
preserved; no ROMs or full snapshots. `SHA256SUMS` covers all evidence except
this explanatory README.
