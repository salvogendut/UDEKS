# UDEKS filesystem interface direction

## Root namespace contract (#26)

**Checkpoint, 2026-09-30:** the C resolver/classifier is linked into the live
bank-1 filesystem service. Bootstrap mounts the system disk at `/`, loads
`/bin/ush`, and the shell reads `/etc/rc`. `/mnt` starts unmounted. UTRQ 0.8
adds `CHDIR`/`GETCWD` and executable-candidate OPEN. General `.SH` execution
is not implemented: scripts are classified, listed and readable, but rejected
by the UDEX loader. General script execution is deferred under #27; the suffix
does not promise a POSIX/Bash interpreter. The user accepts the namespace
test (latest platform unspecified); no new platform-specific hardware claim
is inferred.

### Volumes and boot

- The system volume backs `/`, default IEC device **8**. `/bin` and `/etc` are
  views of that same volume, not additional mounts. `/mnt` starts unmounted.
- `mount 9 /mnt` attaches a separate data volume. Its mount/unmount and errors
  must never change the device used for `/bin/ush`, commands, or `/etc/rc`.
  Supported device numbers remain 8–11. The device is mount state, not encoded
  in the path: a future explicit boot-device choice can select another root.
- Bootstrap establishes and validates root access **before** loading
  `USH.BIN` and reading `RC.ETC`. `/etc/rc` configures later mounts and optional
  applications; it does not have to mount the volume containing itself.
- A failed system mount or shell load enters the existing explicit bootfs
  recovery path. Never silently execute a same-named program from `/mnt`.
  Recovery has its own bootfs namespace; a new public `/boot` tree is not part
  of this slice. The current recovery path must keep working during migration.
- Root cannot be unmounted/replaced by ordinary session commands in this
  milestone (`EBUSY`). `/mnt` may be unmounted and rebound when not in use.

### Paths and flat-disk mapping

The private resolver uses directory tokens `/`=0, `/bin`=1, `/etc`=2, `/mnt`=3;
the first two preserve today's root-session values. These are not a new public
struct ABI. A result has one directory token and an optional leaf name.
Resolving a path does not prove that the file or its backing mount exists.

Input is an explicit length of 1–23 ASCII bytes (the existing request payload
leaves one byte for NUL). Paths may be absolute or cwd-relative. Repeated `/`,
`.` and `..` work; `..` at root stays there and `/mnt/..` reaches `/`.
`file/`, `file/.`, and `file/..` fail `ENOTDIR`: do not lexically erase a
component that would have to be a directory. No arbitrary subdirectories,
symlinks, wildcard expansion, DOS command syntax, or implicit truncation.
An empty path, invalid cwd, overlong path/name, NUL, or unsupported character
returns `EINVAL`. Rejection leaves output and live state untouched.

| Physical system filename | Virtual path | File kind |
| --- | --- | --- |
| `USH.BIN` | `/bin/ush` | UDEX binary, still subject to header/slot validation |
| `STARTUP.SH` | `/bin/startup` | Shell script, never feed it to the UDEX loader |
| `RC.ETC` | `/etc/rc` | Configuration; this one designated file runs at boot |
| `NOTES.TXT`, `OLD.RC`, `DATA.USR` | `/notes.txt`, `/old.rc`, `/data.usr` | Ordinary data; no `.RC`/`.USR` classification |

Only the final suffix classifies. There is no raw root alias for classified
files (`/ush.bin` is not another spelling of `/bin/ush`). Physical names remain
16 bytes maximum including suffix: BIN/ETC stems at most 12, SH stems at most
13. Ordinary data filenames allow 16. No persistent mapping/index is needed.

ASCII case and both PETSCII letter alphabets compare case-insensitively;
canonical logical names are lowercase. Supported name characters are letters,
digits, space, period, underscore and hyphen. Directory inputs are exactly
16 bytes with trailing `$A0` padding, not C strings; malformed padding and
empty or dot-only stems are rejected. This does not add quoting to ush.
On `/mnt`, suffixes have **no special meaning**: `FOO.BIN` remains the raw file
`/mnt/foo.bin`. "Raw" does not mean case-sensitive. The underlying DOS disk is
unchanged, including ordinary SEQ/PRG/USR/REL type metadata.

Directory enumeration filters actual entries; unsupported/unaddressable names
must not be mistaken for loadable files. The transport filters deleted slots
and validates closed/type/chain status separately. A suffix is not permission
to execute a splat/REL file or an invalid UDEX image.

### Lookup, collisions and ownership

Bare command search uses system `/bin`, not the data mount or directory order.
Explicit paths resolve against cwd. A `/bin` lookup considers both BIN and SH;
selecting a 13-byte SH stem must not fail merely because adding BIN would be
too long. Script interpretation and its bounds still require integration tests;
only `/etc/rc` auto-runs, never every ETC/SH file discovered on the volume.

`udeks_fs_consider` is a bounded streaming match helper. Initialize its selected
kind to NONE, scan the **whole** directory, then use the unique result. A first
match is provisional. A second match is `EEXIST` (17), including BIN-vs-SH,
same-suffix duplicates and folded-case duplicates. Physical root files called
`BIN`, `ETC` or `MNT` also conflict with virtual directories. Listing and opening
must agree about ambiguity; do not pick a winner by physical order. An I/O
error later in the scan invalidates an earlier match. No cache is introduced.
The existing bounded CBM directory walk supplies the transport traversal bound.

The integration retains one serialized IEC stream/descriptor slot, not a new
multi-open implementation. Each handle must retain its owning root/data mount
until CLOSE, including after EOF or read failure. Validation precedes I/O:

- A second file open returns `EMFILE`. A mount probe or BAM query that would
  interrupt the active transport returns `EBUSY`, without disturbing the file.
- Unmounting `/mnt` with a data handle or cwd inside it returns `EBUSY`. A root
  handle must not be closed or rebound when an unused data mount is removed.
- Missing backing media/mount must not trigger cross-volume fallback. The pure
  device selector returns `ENODEV` for an unavailable mount; a completed lookup
  with no file returns `ENOENT`. Preserve actual media/chain errors as `EIO`.
- `cd`, `pwd`, `ls`, `cat`, `df`, disk-shell loading and managed-app loading must
  use the same route. `df /` reports the system device, `df /mnt` the data
  device. Cwd updates occur only after directory/mount validation succeeds.

### Placement and qualification

Recovery bootfs is now bounded to bank-1 `$A000-$AFFF` (4 KiB). Filesystem
policy owns `$B000-$C6FF`; graphics delivery and retained commands own
`$C700-$CFFF`. The old `$8A00-$8FFF` policy reservation now holds the two
native graphical tasks' software stacks.
Linker, secondary packer, bootfs builder and lookup limits enforce the split.
Service state is
bounded to `$E000-$E17F`, leaving at least 128 bytes below its `$E200` software
stack. The IEC driver stays at `$E300-$E8FF`, below the shell stack. Public
gateways and resident/window placements do not move.

Directory handles hold an index, not a filename cache or open channel.
Enumeration re-scans to prove uniqueness; lookup scans to EOF before using a
match. This prioritizes correctness over speed. The single-stream and directory
traversal bounds remain. Working directory is shared root-session state, not
yet isolated for independently scheduled processes.

The third disk build adds [D81 / 1581 support](../docs/D81.md): geometry is
detected on each open, 16-bit directory enumeration covers all 296 slots,
and `statfs` sums both BAM sectors, excluding directory track 40. D64/D71
retain their zone-based sector bounds. The read-only service omits the unused
outgoing filename encoder (`UDEKS_FS_READ_ONLY`); host tests retain its full
contract for a future write service. No public request layout changes.

`tools/root_namespace_probe.py` checks true-drive VICE D64/1541 and D71/1571,
an independent device-9 disk, cwd-relative I/O, graphics-active commands and
missing-shell bootfs recovery. `tools/1986_storage_smoke_build.py
--root-namespace` checks native input and repeated window dragging; its one
physical-drive harness tests a device-8 data alias, not independent device 9.
`tools/startup_probe.py` checks valid, invalid and absent RC. Exact candidate
disks and results are preserved under `bench/{artifacts,results}/2026-09-30-root-namespace`.

## Create-only writes (Storage 0.3 / UTRQ 0.14)

Storage 0.3 added explicit writable mount/remount permission and
create-exclusive ordinary data files. The Storage 0.4 branch now explicitly
requests RW for the normal disk root at boot; recovery bootfs and unqualified
MOUNT requests remain RO. Runtime RO remounts do not persist across reboot.
The namespace and single serialized descriptor do not change. See the
[exact public request contract](task-request.md#create-only-disk-streams-014)
and [qualification/limits](../docs/STORAGE-0.3.md). The earlier placement/read-only
qualification above describes that milestone, not the current guarded writer.
No overwriting, app/config installation, append or deletion is exposed.

## Broader filesystem direction

UDEKS user programs see one hierarchical pathname namespace. Device drivers,
IEC transports, bootfs, and disk filesystem implementations remain behind VFS
service endpoints; commands never parse a disk or touch an IEC register.

The user-facing operation names and behavior will follow small Unix/Linux
conventions where they fit the C128:

- `open`/`openat`, `read`, `write`, `seek`, and `close` for byte streams;
- `getdents` for bounded directory enumeration;
- `stat`/`fstat` for type, size, and device metadata;
- `chdir` and `getcwd` for per-process working-directory state;
- `mount`/`umount` through a privileged service interface.

Descriptors are small integers and errors are stable UDEKS codes translated by
the C library into an `errno`-style value. Paths use `/`, `.` and `..`; relative
paths resolve against the process working directory. The ABI uses explicit
byte layouts rather than compiler-native `struct` packing.

Bootfs is mounted read-only as `/bin` during early boot. A storage-backed root
filesystem later takes over the namespace, with bootfs retained as a fallback
for recovery tools. Consequently `/bin/ls` uses the same `getdents` and `stat`
operations for both sources. Initial intended behavior is:

```text
ls
ls /
ls -l /bin
```

Related Bash-like user commands will include `pwd`, `cd` (implemented by the
shell because it changes shell state), `cat`, `mkdir`, `rm`, `cp`, `mv`,
`mount`, `umount`, and `df`. Their availability depends on the mounted
filesystem's capabilities; read-only bootfs correctly rejects mutation.

`cd` and `pwd` now use service requests, and separately loaded `ls` forwards
`.` to that same resolver. The common-RAM root-session token remains
transitional; future task isolation must make cwd genuinely per-process.
