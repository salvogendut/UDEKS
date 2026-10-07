# Storage 0.3 — create-only disk writes

Work on [issue #44](https://github.com/salvogendut/UDEKS/issues/44), branch
`storage-0.3-disk-write`, lives in `build/storage-disk-write`.

## Current checkpoint: private backend with exact empty files

`src/services/filesystem/cbm_write.c` implements a single, serialized,
create-only SEQ writer in C. The optional `UDEKS_IEC_WRITE` assembly transport
extension sends binary bytes through the existing slow IEC handshakes. It
never emits replace, scratch, format or BAM-allocation commands. DOS manages
allocation and file finalization; the narrowly scoped empty-file correction
below uses one checked U2 write to the newly allocated data sector.

This is **not linked into UDEKS** yet. Boot images, recovery, the request ABI
(currently UTRQ 0.13), mounts, console WRITE and the read service are unchanged.
Applications cannot save files through the public API yet. The probe calls
the private backend directly; it is not the roadmap's standalone console app.

The initial backend was committed and pushed as `ad01c45`. Follow-up `5e0aa88` adds
exact empty-file finalization, qualified on all three VICE drive types. All
1,215 host tests and the container build/layout gates pass. All three normal
boot images remain byte-identical. The initial diagnostic is
[preserved](../bench/results/2026-10-07-iec-write/README.md), alongside the
[new exact-empty results](../bench/results/2026-10-07-iec-write-r1/README.md).

The implementation validates the complete physical name before touching the
transport, uses `0:NAME,S,W` without `@`, and checks DOS status after OPEN,
each counted chunk and CLOSE. A chunk has at most 24 bytes, including NUL and
all other byte values. Only the last byte of a non-empty chunk carries EOI.
Acknowledged bytes are counted separately from errors; an error is sticky
until CLOSE and no failed chunk is retried. CLOSE releases local ownership
even when the drive fails. No code closes command channel 15, which would
affect other drive channels. Cancellation cleanup and task ownership belong
in the forthcoming service integration, not in this transport backend.

The caller must serialize this backend with the reader, finish namespace and
case-folded collision checks, and validate mount permissions **before** calling
it. DOS's exact-name rejection alone is not the UDEKS collision policy.

### Exact empty-file finalization

Closing a newly opened SEQ file without sending data produced one byte, CR
(`$0D`), on all three tested VICE drives in the first probe. A successful DOS
CLOSE alone does **not** establish exact zero-length semantics. The DOS source
inserts CR when no block or byte was written. See
[the reconstructed Commodore DOS close routine](https://github.com/mist64/dos1541/blob/master/close.s).

The writer now remembers its successful exclusive-create name and whether any
data was submitted. Only a clean zero-data CLOSE enters the private finalizer:

1. Reopen a direct-access buffer and scan the complete directory for exactly
   one matching 16-byte physical name: closed, unlocked SEQ, one block.
2. Reject metadata tracks, invalid geometry, duplicate names and other live
   directory entries sharing the first sector. Read the complete sector;
   require a final one-byte CR block, or accept an already-zero-length block
   without writing. Any malformed/truncated scan or transfer fails closed.
3. Use standard `B-P` to select byte 1 in that drive buffer, change its count
   from 2 to 1, and issue U2 to **that same data sector**. Check status, reread
   the disk length/link, and close the buffer on both success and failure.

No directory or BAM sector is rewritten by this correction. It is not a raw
sector API or general-purpose truncate operation: only the writer's fresh
create path can call it. Failed OPEN/WRITE/CLOSE and all non-empty writes skip
it. The reader is unchanged; ordinary CR files stay one byte. This assumes a
healthy DOS filesystem and exclusive service ownership, not an fsck or proof
against arbitrary corrupt cross-links or physical media replacement. Live
media-removal and cancellation qualification remain due before public release.
On failure the new file may still contain CR, already be empty, or be partial;
there is no rollback/power-loss guarantee. Never retry a failed transaction.

### Reproduce safely

```sh
# In this branch's worktree:
distrobox-enter my-distrobox -- make -j8 storage-write-backend
python3 -m unittest discover -s tests -p 'test_cbm_write.py'
# Host, with the net.sf.VICE Flatpak:
python3 tools/storage_write_probe.py
```

The probe creates new disposable images under `build/storage/write-probe/`;
it accepts **no source-disk argument**. Each run has its own directory. It
checks write protection, twelve files (0, 1, 2, 23, 24, 253, 254, 255, 256,
508 and 515 bytes, plus an ordinary CR file), duplicate-create rejection, exact readback through the
UDEKS sector reader, and readback in a fresh VICE process. The host independently
walks the resulting directory and sector chains, verifies a pre-existing KEEP
file, and checks that the read-only restart did not change the image. A final
empty create also exercises a maximum-length 16-byte physical name. All private VICE
sessions are terminated by the existing capture harness.

The C fault-injection tests cover invalid names/counts, attempted command
injection, second-open exclusion, all partial-prefix positions, sticky errors,
malformed/truncated status, failed finalization and slot reuse. A separate
finalizer suite proves a one-byte-only disk change, no directory/BAM/sentinel
mutation, duplicate/cross-link rejection, bounded malformed chains, transfer
failures before U2, ignored/failed U2 and failed cleanup. DOS 26 maps to
EROFS, 63 to EEXIST, 72 to ENOSPC, 74 to ENODEV; other failures remain explicit.
The command/status basis is the original
[1541 manual](https://www.zimmers.net/anonftp/pub/cbm/manuals/drives/1541-manual.txt).
Live disk-full, media-removal, cancellation, 1986 and real-C128/PI1541 checks
are still integration gates, not inferred from the host fault tests.

## Placement: actual baseline, not assumed free pages

Measured in the reference container before any production-link changes:

| Bank-1 reservation | End in current map | Free bytes |
| --- | --- | ---: |
| Module `$1200–$187F` | `$1831` | 78 |
| Filesystem policy `$B000–$C5FF` | `$C50C` | 243 |
| Driver/BAM query `$E300–$E8FF` | `$E8F9` | 6 |
| Private state `$E000–$E17F` | `$E112` | 109 |

The state allowance excludes the existing `$E180–$E1FF` software-stack
headroom. Do not consume app slots, recovery bootfs or common gateways to make
the linker pass. Switching only the policy compiler options to `-Os` saves
155 code bytes, not enough for the writer. That experiment is not enabled in
the normal build.

The writer object now uses 1,116 code and 35 BSS bytes. Exact-empty finalization
adds 857 code, 49 read-only-data and 10 BSS bytes to the sector module; the
optional IEC extension adds 96 code and six filename bytes. Together that is
2,118 code/data and 51 state bytes beyond the production objects. These
are object measurements, **not** a complete linked integration budget:
namespace encoding, mount/owner state, cleanup hooks, dispatch and extra
compiler helpers also cost space. The current layout cannot simply absorb
the additions. Consolidate shared DOS-status logic and measure the complete
service before selecting any new reservation; retain actual-map assertions.

## Service integration checkpoint — compile-only, 2026-10-07

The actual `iec_service.c`, behind **`UDEKS_STORAGE_WRITES`**, now implements
the policy and dispatch described below. This is not a second model of the
service. The normal build does **not** define that flag or link the writer.
`storage_write.h` is a private integration contract; UTRQ still advertises
0.13 and the resident gateway has not been changed. Applications cannot yet
use the provisional 0.14 values.

- OPEN mode 3 is write-only/create-exclusive for ordinary data under `/` or
  `/mnt`, including relative paths. `/bin` and `/etc` creation is deferred;
  root suffix aliases remain rejected. The complete directory scan precedes
  CREATE, including folded collisions, splat/locked entries and transport errors.
- MOUNT flag 1 requests RW; flag 2 requests a same-device remount (3 = remount
  RW, 2 = remount RO). These are accepted only for the provisional minor.
  Legacy/boot mounts remain RO; recovery bootfs cannot be written. Root may
  be remounted after boot without replacing the disk identity or changing cwd.
  No RW alias is allowed in either direction, even when the other alias is RO.
  A live handle blocks remounting; STATFS reports effective permissions.
- One fd 4 remains shared by readers/directories/writers. Every handle is
  bound to a trusted, nonzero **instance identity**, not request payload or a
  reusable task-slot number. Only that instance may read/write/close it.
  The trusted `udeks_storage_cleanup(instance)` function closes only a matching
  handle, releases it even on failure and leaves the shared request untouched.
- Counted binary WRITE returns an accepted prefix once; any error then stays
  sticky through subsequent writes and CLOSE. CLOSE always checks the backend
  and releases ownership. Console descriptors 1/2 keep their existing route.

**Not implemented yet:** the trusted caller provider, scheduler exit/cancel
and synchronous-loader cleanup call sites, banked cleanup entry, resident
WRITE routing, mount-command options, SDK wrapper, production placement and
public-API probe. Cleanup is tested as a function, **not** claimed to run on
real task exit yet. The caller provider intentionally remains an unresolved
external in the compile-only object; do not substitute a task number or request
field to make a link pass. It must distinguish foreground invocations too,
and cleanup must precede identity reuse/wrap and task-memory reclamation.

`tests/test_storage_write_service.py` runs **61 cases**: 36 inherited read-only
compatibility cases plus 25 write-policy/lifetime cases against the real
dispatcher/namespace/sector reader, with a writer stub for fault injection.
The real writer/empty-finalizer/IEC behavior remains separately qualified by
the backend tests and preserved VICE results; these policy tests are not a
new end-to-end drive qualification.

```sh
python3 -m unittest discover -s tests -p test_storage_write_service.py
distrobox-enter my-distrobox -- make -j8 storage-write-policy
# Inspect actual emitted segments; this target does not link a boot image.
distrobox-enter my-distrobox -- od65 --dump-segments \
  build/storage-write-policy/iec_service.o \
  build/storage-write-policy/fs_namespace.o
```

Measured with the normal policy compiler flags:

| Object | Read-only code / rodata / BSS | Write-enabled code / rodata / BSS |
| --- | ---: | ---: |
| `iec_service.o` | 2,814 / 25 / 103 | 3,737 / 25 / 113 |
| `fs_namespace.o` | 2,330 / 0 / 70 | 3,037 / 14 / 76 |

Thus policy plus outgoing-name encoding adds **1,644 code/data and 16 BSS
bytes**. With the backend delta above the total is **3,762 code/data and 67
BSS bytes**, before extra linked helpers and resident hooks. Existing BSS
would grow from 275 to at least 342 bytes within the 384-byte state reservation;
the separate stack headroom is not available for code or state. The code
deficit is at least **3,435 bytes** after the current 327-byte free budget,
even ignoring fragmentation. This requires a real placement/delivery decision,
not enabling a flag or shaving a few instruction bytes. Preserve the four app
allocations, recovery bootfs, graphics cache and both software/hardware stacks.

Verification: **1,276 host tests**, cc65 compile-only target, normal boot and
placement/graphics checks. Production storage blobs and D64/D71/D81 hashes
remain identical to `5e0aa88`. No new VICE/1986/hardware qualification is
claimed for this service increment.

## Placement candidate — guarded top-RAM window, 2026-10-07

Policy checkpoint **`c674c97`** is committed/pushed. This placement
checkpoint supplies a bounded link candidate and a separate executable mapping
proof. It does **not** enable writes or change memory ownership in normal boot.

The candidate uses physical **bank-1 `$F000–$FEFF`**, hidden by the ordinary
bank-0 common window, only during an IRQ-masked, synchronous storage lease.
Clear only `$D506` bit 3, preserving the common-size/bottom-sharing/VIC-bank
bits; restore it before returning to any common code or scheduler. The entire
`$FF00–$FFFF` page is excluded from C code/data for the MMU mirrors and mirrored
NMI/vector handling. This uses stock 128 KiB RAM, not an expansion or an app
allocation. The register behavior follows Commodore's original
[C128/C128D Service Manual, MMU section](https://retro-bobbel.de/zimmers/cbm/schematics/computers/c128/servicemanuals/Commodore_128_128D_Service_Manual_314001-08_%281987_Nov%29_Alt_Ver.pdf).

The full service/policy/backend objects and compiler helpers link within:

| Physical bank-1 region | Linked end (inclusive) | Free bytes |
| --- | --- | ---: |
| `$1200–$187F` module | `$1873` | 12 |
| `$B000–$C5FF` policy | `$C5A1` | 94 |
| `$E000–$E17F` state | `$E155` | 42 |
| `$E300–$E8FF` driver | `$E7A5` | 346 |
| `$F000–$FEFF` hidden code/constants | `$FEFD` | 2 |

Namespace code uses cc65 `-Os`; the namespace and empty-file finalizer go in
`STORAGEHIGH`, constants alongside them, and BAM-query code moves from the
driver to policy. The existing production object layout is unchanged unless
the private candidate flags/config are selected. **Two free high bytes are
not integration headroom:** the low driver/policy slack must pay for the
entry/snapshot/cleanup machinery. The 42 BSS bytes are also a tight bound, not
permission to use stack headroom. The link-only caller stub returns zero
(denying OPEN); it is not a substitute for a trusted caller provider.

The standalone ASM proof runs actual instructions in the hidden bank-1
window, checks registers/carry/stack, compares all 3,840 common bytes below
`$FF00` with their preimage, and injects CIA2 timer NMIs into visible, hidden
and mapping-boundary windows. A hidden NMI must write a **private pending
byte below `$F000`**, not a flag that vanishes when common mapping returns.
On exit, restore common mapping **first**, then forward that low-memory flag
by setting (never clearing) the real `$FFF5`. This avoids losing an NMI in
the last instructions before remapping. Mirrored vectors/stub are installed
with native CIA2 sources masked and acknowledged before enabling them.

VICE and 1986 both pass 128 rounds per VIC-bank case (`$D506=$09` and `$49`):
215 visible + 169 hidden NMIs = 384, with 128 observed in the boundary window.
The negative control removes only pending forwarding and fails with code 1
on both emulators. Exact artifacts/results are under
`bench/{artifacts,results}/2026-10-07-storage-window` and verified by host tests.
No disks are attached or modified by this proof.

```sh
distrobox-enter my-distrobox -- make -j8 storage-window
python3 tools/storage_window_probe.py
distrobox-enter my-distrobox -- python3 tools/storage_window_probe.py --engine 1986
```

**Still required:** boot delivery/one-time mirror installation before input
starts; an entry/exit stub below `$F000`; private request/cwd/boot/caller
snapshots (common records are hidden during C dispatch); real owner and cleanup
hooks; stack-depth and relocated CPU-page checks with the actual service;
integrated NMI/RESTORE, graphics, IEC and physical-C128 qualification. The
standalone proof pins CPU pages to bank 0 and does not exercise the filesystem,
scheduler, Z80 or cartridge-generated NMIs. Do not install the candidate blobs
directly or claim production placement accepted from this proof alone.

Verification: **1,283 host tests**, candidate link, normal boot and
placement/graphics gates pass. Production storage blobs and all three disk
images still have their pre-change hashes; no VICE sessions remain.

## Proposed public contract — not advertised or frozen yet

The intended next UTRQ minor keeps operations READ=1, WRITE=2, OPEN=6 and
CLOSE=9, and preserves OPEN modes 0 (read), 1 (directory), 2 (exec).
The private service implementation above proposes mode 3 for
write-only/create-exclusive: no append, replace or truncate. Filename
encoding uses the existing namespace policy; the initial application use
case is ordinary data files, not an installer for executables. The new
mode/flag values remain unadvertised until the full integration is qualified.

- **Mounts:** old mounts and boot defaults remain read-only. Add explicit
  opt-in read-write mounting and same-device remounting, including the root
  disk on a single-drive C128. Root stays mounted; bootfs never becomes
  writable. Reject a writable alias of a device already mounted elsewhere,
  and permission changes while a handle is open. No implicit writable `/mnt`
  alias may bypass a read-only root. Expose effective permission in STATFS.
- **Preflight:** resolve the full path, permission, file kind, physical name,
  reserved names and complete folded directory scan before OPEN mutates DOS.
  Existing names, splat entries and suffix/case collisions are not overwritten.
  Unsupported/ambiguous create targets fail without issuing write commands.
- **One handle:** retain fd 4 and the single serialized slot. Track the owning
  task instance and volume, including foreground loader context and task-ID
  reuse. Another task cannot write or close it. Close it on exit/cancel before
  reclaiming its owner. Do not claim scheduler fairness: current IEC requests
  are synchronous and IRQ-masked at the bank gateway.
- **WRITE:** binary counted payload, 0–24 bytes. Console descriptors 1/2 retain
  their existing semantics. Invalid descriptors/modes/counts do not mutate
  data. A short accepted prefix is reported once, followed by the stored error;
  no implicit retry can duplicate bytes. Acceptance is not disk durability.
- **CLOSE:** check final DOS status, release the handle even on failure, retain
  the first write error, and report the finalization error if no earlier error
  exists. The caller must check CLOSE, even after every WRITE appeared to work.
  Cleanup cannot promise deletion of a partial file or power-loss safety.

## Next concrete deliverable

Integrate and qualify the guarded-window entry and boot delivery within the
measured candidate budget, wire trusted caller identity and exit/loader cleanup,
then add versioned request routing
and one independent console save/readback command. That is the next
user-testable checkpoint. Qualify it on disposable
D64/D71/D81 media, 1986 and then C128+PI1541 before merge. Sprite-editor saving
and shell redirection are consumers later, not prerequisites.
