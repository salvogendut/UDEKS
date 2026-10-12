# IPC foundation qualification

Slice 1 of [issue 57](https://github.com/salvogendut/UDEKS/issues/57) adds two
named endpoints, one copied 16-byte message per endpoint, nonblocking operations
and trusted retirement. The [ABI](../../../abi/ipc.md) specifies ownership,
stale handles, queue errors and exhaustion. The candidate is based on merged
`4644a4c`, on `ipc-0.1-foundation` in `build/ipc-foundation`.

## Qualified behavior

CPU simulation executes production request dispatch, IPC policy, reply code
and the retirement hook. Tests include 3,000 transitions checked against an
independent queue model and exhaustion of the full 16-bit handle space.
Removing the IPC retirement call makes the queued-message cleanup check fail.
MMU registers are ordinary RAM in this simulator; it cannot qualify banking.

VICE 3.8 cold-boots disposable D64/1541 and D81/1581 disks and launches the
raw-gate fixture as ordinary native tasks. The fixture tests authenticated
sender ownership, foreign receive/close rejection, exact 16-byte copied data,
full/empty queues, short receive without consumption and stale handles. Actual
EXIT purges a queued message in the surviving peer; normal EXIT and foreground
Ctrl+C both retire endpoints before reuse. IPC continues after `xinit -q`, and
the clock remains live during the exchange. App code and stack guards are
checked against the independent executable. Monitor writes release a fixture
wait and inject keyboard events; they do not start tasks or fabricate IPC
responses. The fixture is test infrastructure, not the slice-2 SDK/demo.

The host suite passes **1,735 tests**. Normal/panic boot, placement and
`graphics-apps-check` gates pass, as does the existing D81 native-console
argument/concurrency/drag regression. The four-app D81 probe passes coexistence,
calculator/drawing input, move/resize, reload, unknown clients, invalid-image
rejection and slot reuse. Its original 0.3-second click injection overwrote
pending events on this slower machine; the corrected probe waits for each
click to be consumed before sending the next, without changing product code.
The original failure log and passing rerun are both preserved.

IPC adds 32 resident code bytes, 602 bytes
of code under I/O and 64 state bytes. Both links retain 24 resident and 68
hidden bytes free. The established four image/stack allocations, recovery
bootfs and drawing pool are preserved. See the archived maps and layout.

## Candidate disks

- [D64](../../artifacts/2026-10-11-ipc-foundation/udeks-ipc.d64)
- [D81](../../artifacts/2026-10-11-ipc-foundation/udeks-ipc.d81)

These include `IPCTEST.BIN` in addition to the normal system files. A small
manual cleanup check is `ipctest hold`, Ctrl+C, `echo $?` (130), then
`ipctest solo`, `echo $?` (0). Repeat with `xclock &` running. The fuller
owner/queue tests use the automated fixture and are not a public IPC workflow.
Published root download images remain unchanged.

## Limits and reproducibility

The public SDK and independent server/client demo belong to slice 2. General
blocking IPC, transferred file handles, service migration and hardware
acceptance are outside this foundation. Native 1986 IPC is **unqualified**:
this machine has the Flatpak but lacks sibling emulator source for the native
harness. GUI/headless attempts loaded the supplied machine/drive ROMs but did
not finish; they were stopped without recording a pass. Physical C128 IPC
acceptance is also open.

The local compilers are Debian cc65 2.19-1 (V2.18) and SDCC 4.2.0 revision 13081.
Source snapshots, build/test logs, negative-control output and raw VICE RAM
captures are retained here; candidate images/maps are in the artifact directory.
SHA256SUMS binds both records. No ROM-bearing emulator snapshot is archived.
The prior REU evidence now has exact baseline source snapshots, so its original
hashes remain meaningful after the live Makefile evolves.
