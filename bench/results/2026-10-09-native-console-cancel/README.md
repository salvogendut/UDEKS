# Task-based foreground Ctrl+C — 2026-10-09

Issue #52 / `tasking-native-console`, after user-accepted `bca650a` (platform
unspecified). This qualifies the cancellation part of increment 2, not stdin,
background terminal arbitration, full job control or preemption.

The root terminal now publishes a private notice instead of an advisory
window-close event. Native ush, running as the real parent, sends existing
UTRQ CANCEL with exit 130. The normal retire hook, wait cleanup and reap path
are used unchanged. No scheduler/common-gate/loader mutation or expanded RAM
reservation was needed. Rebuilt disk and recovery ush consume the new notice.

## Reproduction

```sh
distrobox-enter my-distrobox -- make -j8 boot native-console-cancel-fixtures \
  placement-check graphics-apps-check service-layout-check
make native-console-cancel-probe
distrobox-enter my-distrobox -- python3 tools/1986_storage_smoke_build.py \
  --four-native --emulator /var/home/salvogendut/Dev/1986 \
  --roms /var/home/salvogendut/Dev/1986/roms --disk build/boot/udeks.d64 \
  --output build/native-console/cancel-1986
make check
```

Exact base D64/D81 and NAP/TICKER files are preserved here. Tests reconstruct
the live fixtures and check their hashes. Source disks were not changed.
`SHA256SUMS` covers evidence except this narrative; monitor binaries have a
two-byte load-address prefix. Previous argument/execution evidence and published
PR #51 downloads are untouched. Current manual test media live in the feature
worktree at `build/native-console/try.d64` / `.d81`.

## Results and limits

VICE 3.10 Flatpak x128, PAL/default RAM, true-drive D64/1541 and D81/1581 pass.
Warp accelerates boot/command delivery; cancellation observations and the old
sleep-deadline check run with warp off. Commands and Ctrl+C use keyboard queues;
the probe does not edit requests, lifecycle state, executable code or window
ownership. All owned VICE processes are terminated on success or failure.

- Silent NAP has no window and never returns normally. Cancellation succeeds
  in all four native slots (6, 5, 3, 4), with the other admitted peers intact.
- Every target is observed as a sleeping root child before Ctrl+C. It is then
  FREE, its allocation ownership is zero and all ten private wait fields are
  zero. The storage context generation advances exactly once; peer generations
  are unchanged. Each shell `echo $?` reports 130 after `Interrupted`.
- The first cancelled NAP remains stopped for more than its old 600-tick sleep
  deadline, with an unchanged step counter. TICKER reuses the slot, takes an
  argument and exits normally with 37. VIC diagnostic bytes are unchanged by
  the initial windowless launch/cancel.
- A foreground clock also cancels with 130 and loses its window while a drawing
  window and sleeping background NAP survive. Ctrl+C at the idle prompt does
  not retire those background jobs; subsequent console output works.
- The native 1986 D64/1571 four-app regression at
  `d360c114e33216bf38a086f65af27533f581f6ba` passes actual keyboard/1351 drag,
  resize, arithmetic/drawing, capacity/reload, foreground graphical Ctrl+C,
  guards, canvas and console cleanup. It does not test windowless NAP. Its
  script adds existing fixture files to a disposable disk; it does not modify
  the sibling emulator or inject app/task/request state.

`make check` passes 1,580 tests; final rebuilds match the qualified disks.
Host tests exercise every foreground-id mapping, no side effects before the
parent request, coalesced keys, no idle/fallback cancellation, exact CANCEL
payload, deferred prompt, one-time notice consumption, normal-exit race and
unexpected error reporting. Two early probe attempts exposed harness issues
(non-atomic clock-state sampling and checking queue head instead of count);
these are corrected in the probe. Only fresh successful runs are preserved.

Actual normal/panic resident BSS ends at `$93C4`, leaving 11 bytes before TIME.
Ush's BSS ends `$9F44`; its full header reservation ends `$9F4B`, below `$A000`.
Loader CODE/RELOC/ACCESS remain 11/18/1 bytes spare. NAP is 1,231 file bytes,
1,045 image + 5 BSS, fitting all four allocations. It is a test-only binary,
not a new boot-resident service or production background command.

No physical-C128, D71 live, periodic-NMI or timing/performance acceptance is
inferred. Programs must still cooperate with the scheduler. `name -q`, GUI
Close and `xinit -q` retain their existing advisory graphical-close semantics.
Foreground stdin and background read/output policy remain the next slice.
