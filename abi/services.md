# UDEKS service-module ABI 0.1

UDEKS services are discovered through compiler-neutral 16-byte descriptors.
The format is byte-oriented and little-endian; it is not a C structure.

| Offset | Size | Meaning |
|---:|---:|---|
| 0 | 4 | ASCII magic `USVC` |
| 4 | 1 | ABI major version (`0`) |
| 5 | 1 | ABI minor version (`1`) |
| 6 | 1 | Service class |
| 7 | 1 | Instance number within the class |
| 8 | 1 | Flags |
| 9 | 1 | Descriptor size (`16`) |
| 10 | 2 | Start-vector address; mandatory |
| 12 | 2 | Poll-vector address; zero if unsupported |
| 14 | 2 | Stop-vector address; zero if unsupported |

Lifecycle vectors use the cc65 C calling convention, take no arguments, and
return an eight-bit result in `.A`. Zero means success. A module publishes its
own versioned request interface separately; the lifecycle ABI does not expose
private module functions.

The initial flags are:

- bit 0: resident for the lifetime of the kernel;
- bit 1: critical to system bring-up.

Initial service classes are console (`1`), hardware capability discovery (`2`),
display (`3`), and machine policy (`4`). Capability discovery precedes the
machine-clock transition so PAL/NTSC probing can use the VIC raster. The clock
service then blanks the VIC and verifies 2 MHz operation before the console;
the first framebuffer display instance temporarily follows the qualified text
console. The next display milestone makes that console a framebuffer client
instead of a separate VDC owner.

The display service's provisional resident-C request surface is specified in
the [framebuffer client API](framebuffer.md). It is not yet a compiler-neutral
or cross-CPU service request ABI.

The static image emits descriptors and a pointer table in assembly so vector
addresses are linker-resolved without relying on compiler packing. The C
registry validates every descriptor before invoking it. Future disk-loaded
modules must submit the same bytes to the same validation path before being
registered.

The registry publishes this 24-byte `SREG` diagnostic record at `$F090`:

| Offset | Size | Meaning |
|---:|---:|---|
| 0 | 4 | ASCII magic `SREG` |
| 4 | 1 | Status format (`1`) |
| 5 | 1 | State: starting (`1`), ready (`2`), or error (`$80 | code`) |
| 6 | 1 | Failure code, zero on success |
| 7 | 1 | Descriptors discovered |
| 8 | 1 | Services started |
| 9 | 1 | Services failed |
| 10 | 1 | Last service class |
| 11 | 1 | Last service instance |
| 12 | 1 | Last start result |
| 13 | 1 | Registry ABI major |
| 14 | 1 | Registry ABI minor |
| 15 | 1 | Last descriptor size |
| 16 | 1 | Last service flags |
| 17 | 1 | Static table count |
| 18 | 6 | Reserved; zero |

Failure codes distinguish an empty table, invalid magic/version/size/class,
a missing start vector, and a start function that returned an error. The
decoder intentionally rejects inconsistent table, discovery, and started
counts even when the state byte says ready.

ABI 0.1 defines startup only. Poll and stop slots are reserved so lifecycle
growth does not change descriptor size; scheduling and unload semantics remain
provisional.
