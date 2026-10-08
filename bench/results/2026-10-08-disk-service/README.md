# Disk-loaded time service: boot integration

Issue #49, 2026-10-08. This qualifies the **isolated candidate**, not normal
`make boot`. Normal boot still links the resident clock pending acceptance.

## Passed

- VICE true-drive D64/1541, D71/1571 and D81/1581: cold boot executes bounded
  RC, loading SVC.BIN and TIME.SVC through real disk I/O. The installed 710-byte
  module matches the emitted file byte for byte.
- Ordinary shell commands set/read time, create xclock, stop the service
  (clock window retires), reject unavailable date, reject missing files, reload,
  reject duplicate load as busy, relaunch/close clock, and read `/hello`.
- A separately sealed revision-2 module is loaded from a different disk file;
  every installed byte matches, with no kernel relink or memory injection.
- D64 missing-file and **checksum-only corruption** at boot leave the console
  usable and recover via `svc load /TIME2.SVC`. The corrupt case preserves
  the format/header/vector fields except the checksum itself.
- Native 1986 D64/1571: real keyboard and 1351 input, including clock drag,
  stop/reload/duplicate refusal, native window retirement and console recovery.
- Normal and candidate placement/graphics builds pass. Two fresh parallel
  candidate builds yield identical disks; hashes are in `rebuild-hashes.txt`.

D64 has **19 free blocks** with only `xsprdef` omitted. D71/D81 retain all apps.
D71 uses its second-side BAM; D64 is built independently using side-one-only
allocation. No second-side file chain is truncated into the D64.

## Evidence and reproduction

`build.json` identifies the successful source/maps and three source disk hashes.
`inputs.json` hashes the copied build inputs. `TIME.SVC` and `SVC.BIN` are exact
emitted files. Format directories preserve command reports plus installed and
replacement bytes. The 1986 directory records the emulator revision, command
log and exit status. Probe sources used for the checks are preserved alongside.
Source-image hashes match across the earlier VICE build and later identical
rebuild used by 1986; absolute paths in reports are provenance, not dependencies.

From this worktree:

```sh
distrobox-enter my-distrobox -- make service-boot
python3 tools/service_boot_probe.py --format d64
python3 tools/service_boot_probe.py --format d71
python3 tools/service_boot_probe.py --format d81
python3 tools/service_boot_probe.py --mode missing
python3 tools/service_boot_probe.py --mode corrupt
```

For 1986, use the copied `source/tools/1986_storage_smoke_build.py` in the
candidate source directory identified by `latest.json`, with `--disk-service`,
`--disk` pointing to that candidate's D64, and `--emulator` / `--roms` pointing
to the sibling 1986 tree and authorized ROMs. Run inside my-distrobox for SDL3.
All probes use disposable media; VICE processes are terminated on success/error.

## Limits and corrected fixtures

No new physical-C128 acceptance. No arbitrary timer-NMI stress, ejection during
module load, or hung foreground-program cancellation is claimed. Read/close
failures remain host-loader injection tests. This is one provisional module slot,
not an arbitrary service allocator; the independent scheduler remains resident.

The first RC had overlong comment lines and was correctly rejected by ush's
54-character limit; a real-parser regression now covers the shipped script.
The first 1986 drag fixture omitted the pointer's (12,40) hardware coordinate
bias and clicked outside the title bar; the corrected ordinary-input run passes.
Neither failed fixture is counted as a passing result.
