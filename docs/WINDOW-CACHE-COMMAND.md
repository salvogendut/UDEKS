# Bounded cache command and completion seam — 2026-09-28

Two separate increments are qualified. Neither enables cached GUI moves yet.

## Combined private C service

`cache_overlay.c` combines generation/geometry policy, row preparation, the
qualified ASM row transfer, and acknowledgement into one bounded command.
Each STEP performs exactly one row and returns in the kernel I/O profile.
It never calls an application, yields, or polls another service while the
private C stack is mapped. Stale owner/generation commands are rejected before
touching row parameters, pixels, or lease state.

The candidate link is 3,116 bytes at bank-1 `$4200-$4E2B`, with 22 state bytes
at `$4EE0-$4EF5`. Its private software stack is `$4F00-$4FEF`, with a 16-byte
upper guard. The packed image is `$5000-$5BFF` (3,072 bytes). Default 168×104
windows fit (2,184 bytes); 220×160 must redraw. This supersedes the earlier
`$4D00` stack / 3,584-byte candidate, not its preserved evidence.

One 217-byte common gateway includes the C entry and row read/write entries.
The resident binding uses 241 bytes including that gateway source, no BSS and
no additional zero page. All twelve compiler-runtime addresses are asserted;
all 26 runtime bytes are saved/restored. The shell stack remains untouched.
The 213-byte row core is byte-identical to its earlier proof.

Both 1986 and VICE pass:

- 66 alignment/edge images, 132 transfers and 543 command entries;
- one default image captured once, then pasted twice at different alignments
  after erasing its source: 312 transfers and 336 commands;
- independent oracles for every bitmap byte and logical dirty flag;
- active CIA1 IRQs, all four I/D modes and runtime/stack/memory guards;
- three one-byte live faults: IRQ leakage, shifted ZP restore and using the
  shell stack, each detected despite correct final pixels.

Host tests execute the actual C command for atomic rejection, cancellation
between rows, repeated reuse, eligibility and capacity boundaries. The lowest
observed changed private stack byte is `$4FD9`, not a worst-case SP bound.
Do not shrink the stack from that observation. Diagnostic runtime is not GUI
timing. That checkpoint did not qualify NMI; the subsequent
[deferred-NMI gate](WINDOW-CACHE-NMI.md) does.

Evidence: `bench/{artifacts,results}/2026-09-28-window-cache-command`.

```sh
distrobox enter my-distrobox -- python3 tools/window_cache_command.py build
distrobox enter my-distrobox -- python3 tools/window_cache_command.py run --engine 1986
python3 tools/window_cache_command.py run --engine vice
```

## Installed completion seam

Normal builds advertise UAPP 0.3. All 53 existing JMP vectors and runtime ZP
addresses are preserved. The optional fastcall pointer occupies `$CF58-$CF59`
in the existing header, not `$D000` I/O. The opt-in helper returns INVALID on
older kernels without reading reserved bytes as an address. Only xwave links it.

Xwave explicitly notifies the window manager after all 21 rows are rendered.
A private descriptor bit accepts only live, visible, topmost bitmaps with no
drag in progress. Paint begin or intersecting compositor damage withdraws it
before changing pixels; end-paint alone never certifies an image. Creation
masks public flags so clients cannot forge completion. The seam adds 158 CODE
bytes, no BSS, charged against shared-raster padding (294 → 136).
The shadow and scheduler placements remain unchanged.

Both formats cold-boot and publish the actual completed-wave descriptor in
VICE. The 1986 normal smoke gate verifies input/history, mouse dragging,
foreground cancellation, background clock survival and recertification after
post-drag redraw without new Z80 samples. Shadow clear, scheduler installation
and bank-0/bank-1 bitmap equality also pass. These are correctness gates, not
an improved drag-latency claim.

Evidence: `bench/{artifacts,results}/2026-09-28-window-completion`.
The shadow/install/placement blocks are independently preserved in
`bench/results/2026-09-28-window-completion-layout`, bound to that same disk.

```sh
python3 tools/window_completion_probe.py build
distrobox enter my-distrobox -- python3 tools/window_completion_probe.py 1986
python3 tools/window_completion_probe.py vice
```

## Remaining gates

The completion checkpoint left 358 resident padding bytes. Installed deferred
NMI ownership subsequently spends 77, leaving **281**. The uninstalled binding
would use 241, leaving **40 before** manager marshalling/continuations and
delivery validation at that checkpoint. Private manager savings subsequently
recover 221: **502 total, 261 after the binding**. The actual resident flow is
still at least 739 bytes short. See [WINDOW-MANAGER-BUDGET.md](WINDOW-MANAGER-BUDGET.md).
Both emulator NMI gates pass; platform-identified physical confirmation remains.
See [WINDOW-CACHE-NMI.md](WINDOW-CACHE-NMI.md).
Bootfs is exactly its 11,708-byte staging limit; grow no application or command
without a fresh capacity proof.

Qualify the production-shaped manager/delivery link before
enabling cache calls. Capture only explicitly completed, topmost, unoccluded
images; abort on painting/resize/closure/shutdown. Keep redraw for partial,
newly raised or oversized windows. The delivery experiment contains only the
old row core, not this C module. Normal builds still redraw moves.
