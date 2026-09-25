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

The current native-boot image admits at most `$2DBB` bytes inside a `$3100`-byte
relocation reservation. Stage 1 gathers its split staging image into bank-1
`$A000-$D0FF`, separate from bank-0 kernel memory at the same logical
addresses. The packer sorts directory entries and the loader resolves `ush`,
`xclock`, and `xwave` by name, so directory ordering does not change init or
managed-application contracts.

Bootfs is a bootstrap filesystem backend, not the permanent on-disk format.
The future VFS resolver will search `/bin` through the mounted storage
filesystem first and may use bootfs as the early-boot fallback.
