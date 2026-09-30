# UDEKS boot filesystem 0.1

Bootfs is a small, immutable directory used before the storage and filesystem
servers are available. Init mounts it as `/bin`; directory entries therefore
store leaf names rather than absolute paths. Its file payloads are ordinary
UDEX byte streams and need no repackaging when copied to a later disk
filesystem.

All multi-byte values are little-endian. The 16-byte header is:

| Offset | Size | Meaning |
|---:|---:|---|
| 0 | 4 | ASCII magic `UBFS` |
| 4 | 1 | ABI major (`0`) |
| 5 | 1 | ABI minor (`1`) |
| 6 | 1 | Directory-entry count |
| 7 | 1 | Directory-entry size (`24`) |
| 8 | 2 | Directory offset (`16`) |
| 10 | 2 | File-data offset |
| 12 | 2 | Total image size |
| 14 | 2 | Flags; zero in ABI 0.1 |

Each 24-byte directory entry contains:

| Offset | Size | Meaning |
|---:|---:|---|
| 0 | 1 | Flags; bit 0 marks an executable |
| 1 | 1 | Leaf-name length (`1..16`) |
| 2 | 2 | File offset from the bootfs base |
| 4 | 2 | File size |
| 6 | 2 | Reserved; zero |
| 8 | 16 | ASCII leaf name, zero-padded |

Names may contain letters, digits, `.`, `_`, `+`, and `-`; `/` is excluded
because this format represents exactly one mounted directory. Entries are
sorted by name and duplicates are rejected. The loader validates all bounds
before interpreting a file as UDEX.

Different names may reference an identical complete file extent. The packer
deduplicates byte-identical payloads (currently `mount` and `umount`, whose
program selects its operation from argv[0]); entries remain separate and
sorted. Bootfs is immutable, so shared extents do not introduce writable aliases.

The native-boot image admits at most `$1000` bytes. The secondary `SCHEDOVR`
file delivers bootfs directly into bank-1 `$A000-$AFFF`, separate from bank-0
kernel memory at the same logical addresses. It no longer uses the former
split Z80/shadow staging container. The packer validates the empty destination,
header and total size before insertion; stage 1 checks the secondary load end.
The current recovery image uses 3,957 of 4,096 bytes. Namespace policy owns
`$B000-$CFFF`; further recovery programs require a packaging decision, not
unchecked growth. Normal bootfs holds only `mount`, `umount`, and recovery
`ush`; graphics apps and normal utilities are ordinary disk .BIN files.
The packer sorts entries and the loader resolves names, never entry order.

Bootfs is a bootstrap filesystem backend, not the permanent on-disk format.
The live resolver searches system `/bin` on disk. A failed root/shell bootstrap
explicitly releases the root mount and selects bootfs recovery. It never
silently substitutes a data-disk program for a missing system command.
