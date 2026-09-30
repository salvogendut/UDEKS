# UDEKS executable format 0.1

The managed-app call table at `$CF50` now advertises UAPP 0.3, 53 three-byte
vectors. All 51 UAPP 0.1 vectors and runtime zero-page addresses are unchanged.
The appended `$CFF9` `udeks_window_begin_paint(handle)` validates a topmost,
non-dragged window and clips drawing to its interior; `$CFFC`
`udeks_window_end_paint()` resets the clip and commits dirty bitmap pages.
Callers must pair a successful begin with end before returning to service
polling; these are not re-entrant compositor entry points. New xwave images
require UAPP 0.2; old managed images remain compatible with the new kernel.

UAPP 0.3 uses header bytes `$CF58-$CF59` for an optional little-endian
fastcall entry pointer to `udeks_window_image_complete(handle)`. The remaining
six reserved bytes stay zero. No vector is appended at `$D000` (I/O). A client
must verify major 0 and minor at least 3 before reading/calling that pointer;
the library returns `UDEKS_WINDOW_INVALID` on older kernels. Completion is
an explicit, idempotent assertion of a whole rendered image, not a pixel-copy
operation. See [window contract](window.md). Current xwave opts in after all
21 rows are plotted; its existing rendering still works on UAPP 0.2.

UDEKS executables use a compiler-neutral 16-byte header followed immediately
by a flat linked image. Multi-byte fields are little-endian. Format 0.1 is a
fixed-address bootstrap format: it deliberately has no relocation records,
dynamic symbol table, or implicit host-runtime dependency.

| Offset | Size | Meaning |
|---:|---:|---|
| 0 | 4 | ASCII magic `UDEX` |
| 4 | 1 | ABI major (`0`) |
| 5 | 1 | ABI minor (`1`) |
| 6 | 1 | CPU (`1` = 8502, `2` = Z80) |
| 7 | 1 | Flags; bit 0 selects a persistent cooperative poll entry, bit 1 a retained managed-application lifecycle table |
| 8 | 2 | Required load address |
| 10 | 2 | Image byte count, excluding this header |
| 12 | 2 | Zero-filled BSS byte count following the image |
| 14 | 2 | Absolute entry address inside the image |

A loader must reject an unknown major version or CPU, unsupported format-0.1
flags, a zero-length image, an entry outside the image, an address-space
overflow, or an allocation that overlaps the resident kernel, another task,
display memory, common RAM, or active module state. It copies exactly the
declared image bytes, clears exactly the declared BSS span, and transfers
control only after validating the program's syscall ABI requirement.

The initial 8502 program entry convention will receive bounded `argc`/`argv`
and standard descriptors 0, 1, and 2, and return an eight-bit exit status.
The fixed [8502 syscall and program-entry ABI](syscalls.md) supplies the initial
entry convention and standard output/error operations. A UDEX file is not
runnable merely because its container is valid: task allocation, private
software-stack setup, argument copying, cc65 zero-page preservation, and
context restoration remain loader responsibilities.

Flag bit 0 changes the entry lifecycle, not the binary container. Init invokes
a persistent program's entry once per cooperative service pass; returning
yields to init without discarding image, BSS, stack, or zero-page state. Such a
program receives no transient `argc`/`argv` registers at each poll.

Flag bit 1 identifies a retained managed application. Its absolute entry is a
six-vector table of three-byte `JMP` instructions: initialize, start, poll,
stop, is-running, and is-focused at offsets 0, 3, 6, 9, 12, and 15. The initial
loader admits these images only into the two fixed bank-0 application slots;
it loads and initializes on first invocation, then preserves code and BSS for
cooperative polling. Version 0.1 rejects all other flag bits and the two flags
cannot be combined.

`tools/build_udex.py` is the canonical host-side packer. It performs all
format-level bounds checks without assuming a filesystem. The early
[bootfs](bootfs.md) and mounted read-only IEC filesystem consume the same byte
stream.

The Storage 0.2 foreground loader accepts explicit `/mnt/NAME` for ordinary
8502 UDEX images only (flags zero, load `$0200`, image+BSS <= `$0A00`). The
DOS file is the exact UDEX byte stream, without a Commodore PRG load prefix.
It stages into a FREE bank-1 task-2 allocation and checks exact file length,
entry and allocation before replacing live bank-0 APP1. SPAWN still uses bootfs.
See [implementation and limits](../docs/STORAGE-0.2.md).

Managed first-use loads resolve `xclock` as `/bin/xclock` (bank-0 `$0200`)
and `xwave` as `/bin/xwave` (bank-0 `$1200`), backed by `XCLOCK.BIN` and
`XWAVE.BIN` on the system disk; they do not fall back to bootfs or data media.
Both require flags `$02`, load and entry equal to the requested slot base,
image+BSS <= `$0A00`, exact file length, and six absolute JMP entries whose
targets are inside the image after the 18-byte table. Validation finishes
before any live app slot is written. Task 2 must be FREE before borrowing
bank-1 staging; STOPPED and ZOMBIE also retain ownership. Successful images
stay installed for polling and subsequent restarts until reboot; this is not
general dynamic linking, unloading, or isolation from hostile machine code.
See [managed disk delivery](../docs/DISK-GRAPHICS.md).

Init's persistent load reads `/bin/ush` (`USH.BIN`) before child
tasks exist. It requires flag `$01`, load and entry `$9000`, and the same
`$1000` image+BSS bound. The fixed scheduler entry cannot currently honor an
offset entry for persistent tasks, so the loader rejects it. Init mounts the
boot device as root and retains that mount on success, releasing it for bootfs
recovery on failure. UTRQ 0.8 OPEN descriptor 2 rejects `.SH`/`.ETC` candidates
before image loading; all UDEX checks still apply. Normal bare commands search
system `/bin`; explicit paths use the filesystem's cwd resolver. SPAWN's
bootfs-only child path is unchanged. See [boot policy](../docs/BOOT-STARTUP.md).
