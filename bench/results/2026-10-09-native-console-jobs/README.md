# Background console jobs — 2026-10-09

Issue #52, after accepted/pushed foreground-input commit `9c9bfad`. This is
increment 2's final bounded launch/output slice, not a full Unix terminal.

## Reproduce

```sh
distrobox-enter my-distrobox -- make -j8 boot native-console-input-fixtures \
  placement-check graphics-apps-check service-layout-check \
  native-console-input-check native-console-parser-check service-request-check
make native-console-jobs-probe
distrobox-enter my-distrobox -- python3 tools/1986_storage_smoke_build.py \
  --four-native --emulator /var/home/salvogendut/Dev/1986 \
  --roms /var/home/salvogendut/Dev/1986/roms --disk build/boot/udeks.d64 \
  --output build/native-console/jobs-1986
make check
```

`build/` holds exact base media and actual normal/panic/scheduler maps.
ASK/TICKER (plus BGREAD on D81) reconstruct each disposable test image; the
host test checks their hashes against the reports. Normal D64 content is
unchanged: omitting only the additional BGREAD test peer avoids overfilling it.
Raw monitor `.bin` captures include two address bytes. Repeated diagnostic
filenames retain the last observation; each completed scenario has its own
console/code/guard captures. `source/` retains changed implementations and
proof fixtures. The manifest covers everything except this narrative.

## Results and limits

VICE Flatpak x128 3.10, PAL/default RAM and true-drive D64/1541 and D81/1581:

- Eight argv entries plus trailing `&`, mixed-case arguments and private UARG
  survive sleeps. The operator is not passed to the program. Background launch
  returns the prompt; normal background return 37 never replaces shell status.
- A partially typed `echo drft`, with the cursor moved into the middle, survives
  repeated ticker stdout/stderr requests. Inserting `a` and Enter executes
  `echo draft`. Chunked `tick ` / digit / newline output is not broken into
  separate lines. History recall still works afterward.
- Output from a background ticker preserves an ASK input line while a clock
  runs. Enter echoes the exact input, which is not executed as a shell command.
  On D81 a fourth, silent BGREAD task proves background READ/POLL still fail EIO.
- Ctrl+C cancels only foreground ASK, leaves ticker/clock alive, reports 130,
  and allows another shell command. Background completion remains isolated.
- Bare `&`, excess arguments and missing executable fail without accidental
  launch. Code bytes and private stack guards remain intact; clock closes.

Only keyboard queues are injected. No requests, task code, lifecycle records
or program results are fabricated. Warp is off, but frequent paused-monitor
observations mean this is a functional proof, **not a latency benchmark**.
Native 1986 (`d360c114e33216bf38a086f65af27533f581f6ba`) separately passes its
four-graphical-app keyboard/1351 drag/resize, outlines, worker reuse,
calculator/drawing, capacity/reload, Ctrl+C, guards and canvas regression.
That is not a native 1986 TICKER/ASK scenario. No new physical-C128, D71 runtime
or periodic-NMI stress qualification is claimed. All probe VICE processes exit.

Host tests execute the real terminal/editor/console for all 21 rows and draft
lengths 0–54, mid-line cursor preservation, zero-count writes, multiple full
24-byte requests, wrapping, formfeed and submission. Root-console tests also
check split streams, control characters, NUL guards and resumed normal scrolling.
Shell tests use the real C tokenizer and assert launch arguments, parse rejection,
background ownership, stale-exit suppression and no synchronous-loader fallback.
The existing CPU parser/UARG, input owner/reader and service stack tests all pass,
including their intentional negative controls (`cpu/gates.log`).
Final `make check` passes 1,600 tests; placement, graphical-app and service-layout
gates pass. Rebuilt D64/D81 are byte-identical to the preserved base media.

Early runs found probe assumptions, not product failures: output may legitimately
interleave between separate shell WRITEs, and compatibility NOT_FOUND is status
11, not errno 3. The final assertions account for both; only final successful
runs are retained. Adding all three test apps to D64 exceeded its free blocks;
the final D64 proof and manual candidate add ASK/TICKER only.

## Memory and scope

Normal/panic BSS ends `$93A7`, leaving 40 bytes before `$93D0`. HIGHBSS ends
`$E2E0` (one byte free), module ends `$E631` (18 free), and TASKREQUEST occupies
247/265 bytes. Scheduler remains through `$C862`. All allocations, stack
guards, display areas, service slots and public gates retain their bounds.

The existing console grid holds both output and editor; only three cursor/row
state bytes are added. Bounded row copies/fills, sharing the existing cell
writer and cc65 size-oriented C compilation pay for the feature without
shrinking buffers. Serialized root-service scratch is never used from IRQs.

Atomicity is one counted WRITE, not a whole command or line. No separate output
queue, per-process terminal, general jobs/fg/bg/kill, native file SDK, pipes,
quoting or preemption. Legacy synchronous utilities still block cooperative
execution until return. Manual candidates are `build/native-console/jobs.d64`
and `.d81` inside the feature worktree; published PR #51 downloads are unchanged.
