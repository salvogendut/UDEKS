# UDEKS executable format 0.1

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
| 7 | 1 | Flags; zero in format 0.1 |
| 8 | 2 | Required load address |
| 10 | 2 | Image byte count, excluding this header |
| 12 | 2 | Zero-filled BSS byte count following the image |
| 14 | 2 | Absolute entry address inside the image |

A loader must reject an unknown major version or CPU, nonzero format-0.1
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

`tools/build_udex.py` is the canonical host-side packer. It performs all
format-level bounds checks without assuming a filesystem. The early
[bootfs](bootfs.md) and future storage-backed filesystem consume the same byte
stream.
