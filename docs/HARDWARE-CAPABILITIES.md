# Hardware capability discovery

UDEKS discovers usable hardware features during service startup instead of
assuming that a case style implies a particular board configuration. The C
capability service owns policy and publication; bounded 8502 assembly owns
raster timing and expansion-port register probes.

The current probes determine:

- PAL versus NTSC by observing whether the VIC raster reaches `$120` before
  wrapping;
- VDC revision from status-register bits 0–2;
- 16 versus 64 KiB VDC RAM with a save/write/read/restore alias test at
  `$1FFF` and `$9FFF`;
- REU presence using two-value readback of its expansion-address register;
- GeoRAM presence using a saved and restored byte in its selected `$DE00`
  window.

Every raster and VDC wait is bounded. VDC and GeoRAM contents and selection
registers touched by detection are restored before the service returns.

## Model reporting

The VDC revision produces a *machine-family hint*, not a chassis identity:
revisions 0–1 indicate an 8563-family machine, while revision 2 indicates the
8568 family normally associated with the C128DCR. A 64 KiB VDC does not by
itself identify a DCR because earlier machines can be upgraded, and an
integrated drive cannot be distinguished safely from an external drive by this
startup probe. User configuration may later supply the physical case model.

## Diagnostic record

The 32-byte `HCAP` record at `$F0C0` is:

| Offset | Size | Meaning |
|---:|---:|---|
| 0 | 4 | ASCII magic `HCAP` |
| 4 | 1 | Format (`1`) |
| 5 | 1 | Probing (`1`), ready (`2`), or error (`$80 | code`) |
| 6 | 1 | Failure code |
| 7 | 1 | Video standard: PAL (`1`) or NTSC (`2`) |
| 8 | 1 | VDC revision |
| 9 | 1 | VDC family: 8563 (`1`) or 8568 (`2`) |
| 10 | 1 | VDC RAM in KiB (`16` or `64`) |
| 11 | 1 | Capability flags |
| 12 | 1 | REU present |
| 13 | 1 | GeoRAM present |
| 14 | 1 | Machine-family hint |
| 15 | 1 | Completed-probe mask (`$1F`) |
| 16 | 1 | Original VDC register 28 value |
| 17 | 15 | Reserved; zero |

The initial expansion flags report presence, not capacity. Capacity discovery
belongs with the future allocator because it requires destructive wrap tests
inside expansion memory and therefore explicit ownership.

## References

- [Commodore 128 Programmer's Reference Guide](https://www.pagetable.com/docs/Commodore%20128%20Programmer%27s%20Reference%20Guide.pdf)
- [cc65 REU driver presence test](https://github.com/cc65/cc65/blob/master/libsrc/c64/emd/c64-reu.s)
- [GeoRAM register map](https://codebase64.net/doku.php?id=base%3Ageoram_registers)
