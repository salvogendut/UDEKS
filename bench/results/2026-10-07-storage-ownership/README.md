# Guarded boot storage and real owner retirement — step 1

Branch `storage-0.3-disk-write`, based on `5a43574` plus the uncommitted
private-lease and boot-ownership increments. These are cold boots of the
normal integrated images, not the earlier standalone storage PRG.

| Qualification | Result |
| --- | --- |
| D64 / VICE true 1541 | foreground return, native EXIT, CANCEL/WAITPID, reuse pass |
| D71 / VICE true 1571 | same ownership suite passes |
| D81 / VICE true 1581 | same ownership suite passes |
| Missing disk ush / recovery bootfs / 1541 | fallback, mount, disk command, unmount pass |
| Four native clients / 1571 | drag, resize, disk I/O, worker, close/reload and unknown-name reuse pass |

Each owner run executes the independent LEAK command twice, HOLD native
client twice, then a native parent/child cancellation sequence. All deliberately
omit CLOSE. Generations advance once per retirement; immediate subsequent
`cat /hello` succeeds. The parent cannot CLOSE the child's fd; it CANCELs,
WAITPIDs with status 130, opens another stream, then exits leaving that stream
for the EXIT cleanup. Clock/console I/O still work afterward. The LEAK client
also verifies EPROTO for minor 14 and EINVAL for a create mode under minor 13.
UTRQ remains 0.13: **public writes are not enabled**.

No kernel/syscall hooks are patched. Keyboard-queue events provide commands;
only test-client release bytes are changed through the monitor. Legacy native
SPAWN still reads bootfs, so the disposable fixture adds a tiny CHILD there,
retaining the recovery entries. LEAK/HOLD/PARENT are independent disk programs.
The normal distribution contains none of these clients. All VICE instances
started by these probes terminate in their `finally` blocks.

The matching disks, service blobs/maps, common loader and client binaries are
in [`bench/artifacts/2026-10-07-storage-ownership`](../../artifacts/2026-10-07-storage-ownership).
`SHA256SUMS` paths are relative to the repository worktree root. Host tests
reconstruct each disposable owner fixture from the saved normal disk and
clients and compare its hash with the live report. They also verify the actual
linked sizes, gate address and initialized generations. JSON retains the
observed console output, generation transitions and regression checks.
Final verification: **1,302 host tests**, boot build and both actual-map
placement/graphics gates pass. Final rebuilt disk hashes match the archive.

Reproduce from this worktree (toolchain in `my-distrobox`, Flatpak VICE on host):

```sh
distrobox-enter my-distrobox -- make -j8 boot storage-owner-fixtures placement-check graphics-apps-check
python3 tools/storage_owner_probe.py --output build/storage-owner/repeat-1541
python3 tools/storage_owner_probe.py --disk build/boot/udeks.d71 --drive 1571 --output build/storage-owner/repeat-1571
python3 tools/storage_owner_probe.py --disk build/boot/udeks.d81 --drive 1581 --output build/storage-owner/repeat-1581
python3 tools/storage_owner_probe.py --recovery --output build/storage-owner/repeat-recovery
distrobox-enter my-distrobox -- python3 tools/build_graphical_example.py
python3 tools/four_native_probe.py --disk build/boot/udeks.d71 --drive 1571 --output build/storage-owner/repeat-four
make check
```

The integrated lifetime fixtures hold **read** streams. The preceding
[standalone actual-service proof](../2026-10-07-storage-lease/README.md)
qualifies create/WRITE/finalization separately. Public writable mounts,
scheduler-path write cancellation/failures, integrated RESTORE, 1986 and
physical-C128 acceptance are still forthcoming. Do not conflate the older
mapping-only 1986 result with this integration. No rollback/power-loss claim.

During development, two obsolete shell probes expected legacy graphics status
text/records; their partial read/namespace passes are not counted as full
qualification. The current four-native probe above supplies that regression.
A test-client indexed clear also exposed the previously known cc65 `-Os`
cached-ptr1 hazard; its payload is now cleared with `memset`. The preserved
results use the corrected client and published SPAWN result layout.
