# Native console files / scheduled CAT — 2026-10-09

Issue #52 increment 3, based on `a1a3c27` plus this change. SDK and application
source snapshots, exact media, map layouts and raw captures are checksummed.
Published PR #51 downloads and earlier qualification records are unchanged.

## What ran

- VICE Flatpak x128, cold boot with ROM-backed 1541/D64 and 1581/D81.
  `tools/native_console_file_probe.py` starts from an immutable system image
  and adds EMPTY/ONE/LONG; D81 also adds the two SDK clients. Routine commands
  run in warp; live CAT cancellation/concurrency runs at normal speed.
- Both formats: native CAT reads normal, empty, one-byte and multi-chunk files;
  missing/directory/usage errors return 1/1/2. Clock and wave occupy tasks 4/5;
  foreground CAT uses task 3. Ctrl+C returns 130, advances the file-owner
  generation once and frees the slot. A subsequent read and full LONG read
  succeed. Clock's private SLEEP deadline changes **while CAT is still live**;
  no inference from a global timer or the minute-only face repaint.
- D81: a preloaded rival attempts READ/WRITE/CLOSE on another task's fd 4 and
  gets EBADF, then OPEN gets EMFILE. Rival exit leaves the owner's stream
  intact; owner reads its original bytes and deliberately leaks on return.
  Writer exit and Ctrl+C also deliberately leak, exercising real cleanup.
  An existing-name create fails EEXIST. Independent `cp` preserves each closed
  binary file; after emulator shutdown both saved files are exactly
  `00 ff 80 4e 61 74 69 76 65 0a`. All original file streams are unchanged.
- Native 1986 `d360c114e33216bf38a086f65af27533f581f6ba` (clean tracked tree),
  compiled through `my-distrobox` against SDL3: disk-service RC/date/clock/
  stop/reload plus CAT success/missing-file status, actual keyboard and 1351
  dragging. Separate four-native-app input/drag/resize/Ctrl+C/guard regression.
  The 1986 run does not execute FHOLD/FRIVAL's write-cleanup scenarios.

Only keyboard queue events and named test-client release flags are written by
the VICE probe. No request/results, owner identity, application return values,
service implementation or scheduler state is patched. Bank-qualified captures
check installed relocated code, private BSS and both software-stack guards.

`before` media reconstruct from `build/udeks.*`, the archived clients and
`make_fixture()` in the saved probe source. D81 `after.d81` independently proves
binary persistence; D64's post-run hash must equal its fixture hash. Normal
system disks differ from the previous accepted disk's file streams only in
CAT.BIN. Resident and scheduler segment maps are unchanged. D64 has 16 free
blocks and omits only the existing XSPRDEF exclusion.

## Reproduce

From the `build/native-console` feature worktree:

```sh
distrobox-enter my-distrobox -- make -j8 boot native-console-file-fixtures
make native-console-file-probe
make check
```

Native 1986 runners:

```sh
distrobox-enter my-distrobox -- python3 tools/1986_storage_smoke_build.py \
  --disk-service --emulator /var/home/salvogendut/Dev/1986 \
  --roms /var/home/salvogendut/Dev/1986/roms --disk build/boot/udeks.d64 \
  --output build/native-console/files-1986
# Repeat with --four-native instead of --disk-service, a separate --output.
```

Placement, graphics/service layout, parser/UARG, input and service-request CPU
gates and the panic D71 build pass. Host tests also cover real SDK + CAT error
paths, no retries, binary chunks, EOF, close-error precedence, foreign owner /
generation behavior and the scheduler's non-owned common minor-byte caveat.
Final `make check`: 1,616 tests pass, including exact evidence hashes. All VICE
sessions created by the probes are closed.

## Limits and acceptance

No new physical-C128/Pi1541 or periodic-NMI claim. This is one task-owned global
file stream, not multi-open or asynchronous disk I/O. A disk launch may fail
while another task holds the stream. Individual IEC requests mask IRQs; native
clients must sleep between chunks. Other shipped utilities are synchronous.
CAT fits three of the four ordinary allocations, not task 6; no extra console
slot or resident reservation is added. This is correctness evidence, not a
latency benchmark.

Manual candidates `build/native-console/files.d64` / `.d81` contain LONG:
start `xclock &`, `xwave &`, run `cat /long`, interrupt with Ctrl+C, check
`echo $?` = 130, then `cat /hello` and drag both windows. Also test
`cat /nofile` (status 1) and normal EOF. User acceptance remains pending.
