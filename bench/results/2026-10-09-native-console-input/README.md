# Foreground console input — 2026-10-09

Issue #52 / `tasking-native-console`, after user-accepted and pushed `98ff762`
(acceptance platform unspecified). This qualifies foreground canonical stdin
and background read rejection, not general job control or background output.

## Reproduce

```sh
distrobox-enter my-distrobox -- make -j8 boot native-console-input-fixtures \
  native-console-input-check placement-check graphics-apps-check service-layout-check
make native-console-input-probe
distrobox-enter my-distrobox -- make service-request-check
distrobox-enter my-distrobox -- python3 tools/1986_storage_smoke_build.py \
  --four-native --emulator /var/home/salvogendut/Dev/1986 \
  --roms /var/home/salvogendut/Dev/1986/roms --disk build/boot/udeks.d64 \
  --output build/native-console/input-1986
make check
```

`build/` preserves exact base media and actual normal/panic/scheduler maps.
ASK and BGREAD are independent UDEX programs, not disk boot contents. Tests
reconstruct the disposable VICE disks from the base and those two programs,
checking their hashes. Raw monitor files have a two-byte address prefix.
`source/` preserves the changed implementations and proof runners. CPU logs
and exact sim6502 test images are retained. SHA256SUMS covers all evidence
except this narrative. Older archives and root download snapshots are unchanged.

## Results and limitations

VICE Flatpak x128 3.10, PAL/default RAM, true-drive D64/1541 and D81/1581 pass:

- ASK receives mixed-case, backspace-edited, empty and 54-character lines;
  the last exercises three counted READ chunks. Input is echoed intact and
  ush does not execute it. Normal return gives `echo $?` = 0.
- The same independent image uses all four native allocations (6, 5, 3, 4),
  with clock/drawing and silent reader peers. Input wait is WAITING/INPUT;
  completion reaps each task. Console-only use does not initialize the VIC.
- Ctrl+C while partially typing into ASK cancels INPUT waits in slots 6/4,
  clears all ten private wait fields, reaps and returns 130. Later input and
  slot reuse succeed without executing leftover application text.
- Silent BGREAD peers repeatedly attempt immediate/infinite POLL, SDK READ
  and raw READ. Each receives EIO without touching its destination. They
  cannot steal a partially typed shell command or the foreground app's line.
- The final suite uses warp for functional checks; no timing/latency claim.
  Keyboard queue injection exercises terminal/editor/request ownership, not
  physical keyboard transport. No program, request or lifecycle injection.

The separate native 1986 four-app run at revision
`d360c114e33216bf38a086f65af27533f581f6ba` passes actual keyboard/1351 drag and
resize, held outlines, worker reuse, arithmetic/drawing, capacity/reload,
Ctrl+C, guards and canvas. It is **not** an ASK/BGREAD run. The service request
CPU regression also passes 1,832 calls and its missing-stack-bridge negative
control. No new real-C128, D71 runtime or periodic-NMI qualification is claimed.

The new CPU proof executes the production ownership adapter for all 256 caller
ids against eight foreground masks (2,048 cases), a renderer-error mapping
case, and 6,270 guarded whole-line reader cases. Removing foreground comparison
must fail the negative control. The trusted caller query is stubbed only in
that isolated CPU test; preserved actual router bytes must query the actual
scheduler's current-task address. Host tests cover SDK errors/malformed replies,
input bounds, timeout encoding, no-copy rejection, history separation and prompt
cleanup without erasing history.

Early probe failures were observer issues: missing command-consumption
synchronization, bank-implicit private-memory reads, and an incorrect free-slot
assumption after closing the clock. Final observations force the kernel map
and respect actual allocation order; both final media reruns pass. Only their
successful records are preserved. All owned VICE processes terminate.

## Memory and scope

Resident BSS ends `$93CE` (one byte before TIME); module ends `$E631` (18 bytes
free); request gateway uses 264/265 bytes. Scheduler ends `$C862`, 29 bytes
before storage. The private current-task query occupies `$C8FC-$C8FF` in the
existing router reservation. No allocations, stacks, displays or public gates
move. Reusing the line-copy helper, a compact guarded whole-line reader and a
bounded contiguous wait-reset loop pay for ownership without reducing buffers.

Foreground READ/POLL opens the bounded editor; application input neither
recalls nor adds command history. Returning to PROMPT drops partial/unread data.
READ on the wire remains nonblocking; the independent SDK sleeps through POLL.
Background reads return EIO, not SIGTTIN. No raw mode, EOF key, prompt-safe
background output, argument-bearing `&`, file SDK or preemption is added here.
Manual ASK/TICKER media are `build/native-console/input.d64` / `.d81` inside
the feature worktree; earlier `try.*` media are retained.
