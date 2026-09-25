# UDEKS filesystem interface direction

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
