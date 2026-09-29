# Compact resident raster qualification

Issue #14, 2026-09-29. This is a private replacement experiment, **not an
installed window manager, a latency result or a new test disk**. Normal OS and
application binaries are unchanged. Application-specific xwave work remains
outside this manager increment.

## Measured component budget

The compact C chrome renderer shares twelve explicitly allocated HIGHBSS bytes
for scalar row parameters. It keeps title pointers automatic and transient,
uses the existing glyph table, and fills top/bottom rows directly with their
final color. Serialized execution is required: no drawing callback, poll,
interrupt renderer or other client may reuse these parameters during a step.
The compact manager's 76 bytes plus these twelve equal the original 88-byte
manager allocation; drag/cache state and stack guards are not overlaid.

| Component | Resident CODE bytes |
| --- | ---: |
| One-row chrome plus shared span/pixel helpers | 975 |
| Bounded clear/chrome/commit backend | 755 |
| Real C receipt validation/acknowledgement wrappers | 127 |
| Private banked-policy binding, including gateway image | 84 |
| Newly linked runtime helpers | 72 |
| Component total | **2,013** |

Chrome/backend save **913 bytes** against the preceding 1,468/1,175-byte draft.
The helper closure is measured in both full normal and panic links:
`memcpy.o` 60, `return0.o` 4 and `ult.o` 8. No existing helper disappears;
RODATA/DATA/BSS sizes and the complete frozen HIGHBSS segment remain unchanged.
The exact runtime library, objects, generated assembly, split outputs and maps
are archived, rather than inferring helper costs from source or imports alone.

Granting eventual retirement of the old glyph/title/chrome/paint/compose bodies
(1,976 bytes) and the compact-manager reserve (137) leaves **100 bytes of
provisional headroom**. This is only a component lower bound. Real poll/view
packing, delivery/admission, painter/cache providers, busy state and cancellation/
teardown costs are not yet charged. It does **not** prove the complete adapter
fits. The isolated sizing link retains synchronous legacy composition and grows
CODE by 654 bytes; its moved shadow and stale generated bridges make it
**unbootable**, so it must never be packaged as a test disk.

## Receipts, scratch and bounded work

The backend validates a copied receipt through the banked C policy before any
pixel or clip mutation. A successful step clears at most four rows, draws one
chrome row, or commits one dirty page (only 64 visible bytes on page 31), resets
the clip, then acknowledges. Invalid geometry, page/row cursors, or stale work
are rejected. CLIENT/RESTORE remain delegated; no synchronous app callback is
smuggled into a supposedly bounded step.

Receipt wrappers copy values into the existing private packet and call the
qualified banked binding. They acquire no persistent state. The caller must hold
a serialized graphics lease in kernel-I/O mode and keep work/receipts in local
storage: common packet/gateway scratch may be overwritten by another drawing
primitive. A rejected receipt can change RPC scratch, but not pixels, dirty
pages, clip state or lane progress. The banked state remains authoritative.
Production lease admission, NMI/RESTORE drain and live task/app interlocks remain
unqualified; the standalone gateway is not a production installer.

## Pixel and runtime proof

Host tests compare complete canvases, clipping, borders, mixed-case/long titles,
buttons and resize grips against the original full-window renderer. The backend
tests exercise real C receipt wrappers with a host dispatcher and independently
check stale-title poisoning and bounded dirty-page work. An additional oracle
test compares the independent native bitmap reference directly with the old
full-window C renderer, including yellow pixels overwriting resize strokes.

The standalone target links the **real C chrome/backend/receipt code, real
8502 pixel/span assembly and the exact previously qualified banked C policy**.
Eight edge/fullscreen/flag/title scenes pass in both 1986 and VICE. Per-scene
checksums supplement the host canvas tests; the final 8,000 bitmap bytes are
also compared exactly, not just by a checksum. The experiment checks stale
rejection, compiler/MMU/status restoration and private-stack/cache/bootfs guards.
IRQ arrivals occur between policy calls. The client is a mock one-row painter,
and page commit is a bank-0 memory model, **not the real VIC gateway**. There are
no live applications, task paging, Z80 handoffs or NMI injection.

The observed private-stack offset is diagnostic coverage, not a worst-case
stack-depth bound. Full-image scans and guard checks make this standalone probe
deliberately heavy; its frame termination budget is not an input-latency target
or a real renderer performance measurement. Physical hardware and live input
service gaps must be qualified after integration.

## Reproduction and next gate

From the issue worktree in the reference container:

```
make repaint-raster
python3 tools/window_repaint_raster.py run --engine 1986 \
  --emulator-root /var/home/salvogendut/Dev/1986
```

From the host with VICE flatpak installed:

```
python3 tools/window_repaint_raster.py run --engine vice
python3 tools/window_repaint_raster.py preserve
```

Runs verify input/build hashes before and after execution and bind results to
the exact build report. Preserved evidence lives under
`bench/{artifacts,results}/2026-09-29-repaint-raster`, with complete SHA manifests.
Preservation refuses to overwrite an existing qualification.

Next: measure the actual delivery/admission and poll/provider adapter against
the remaining budget, recovering or relocating more service code if required.
Qualify serialized gateway/private-stack reuse and NMI/cancellation cleanup
before a production link. Only then produce a visible disk for input-latency,
drag/release, resize, close/stack and RESTORE testing. No public UAPP ABI changes
are implied by this private experiment.
