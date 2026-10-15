# Engine service slice 1 — contract and placement

Issue [#60](https://github.com/salvogendut/UDEKS/issues/60), branch
`services-engine-ipc`, baseline merged IPC `923e4a4`.

Four host tests and the complete 1,754-test host suite pass. The actual worker C
matches the frozen existing wave profile across 8,192 phase/step/count inputs;
NOP and output tails preserve guards. Separately linked server/client probes
fit tasks 3/5 and coexist with clock/draw in all 24 launch orders. No resident
bytes, permanent slot, normal boot image or existing worker user changes.

EPLSRV/EPLCLI are compiler placement probes, **not runnable service delivery**.
They do not implement complete authentication, peer state, STOP/ACK or cleanup.
The compiled size is a checkpoint, not a bound on future lifecycle code growth.
Live service/SDK and machine qualification remain subsequent slices. Surface
rows exceed the reply capacity and require a future chunking contract.

Reproduce with `make engine-contract-check engine-placement` and `make check`.
The message contract and [development plan](../../../docs/ENGINE-IPC.md) explain
the limits. Native emulator checks will use sibling `../1986`; no emulator
result is claimed here. ROMs and snapshots are excluded. SHA256SUMS binds the
programs, maps, reports, logs and source snapshots in this archive.
