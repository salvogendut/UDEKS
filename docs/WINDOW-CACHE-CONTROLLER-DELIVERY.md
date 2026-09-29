# Whole C controller delivery — 2026-09-28

Status: separate experimental D71/D64 disks cold-boot in VICE and 1986 and
preserve the complete qualified controller through application/console/graphics
lifetimes. **The controller is not invoked from these disks. Normal boot images
are unchanged; GUI pixel-cache moves remain disabled.** Standalone execution
is qualified separately in [WINDOW-CACHE-CONTROLLER.md](WINDOW-CACHE-CONTROLLER.md).

## Resolved source collision

The 3,977-byte controller links at bank-1 `$4200–$5188`. It cannot coexist with
the canonical scheduler's temporary source beginning at `$5000`. The experimental
secondary LOAD now starts at `$4200`, with the unchanged scheduler payload at
`$6000`. Installed scheduler/task addresses remain unchanged. The scheduler
source ends at `$7228`, below sprite memory, and is consumed before graphics
can clear/reuse the VIC bitmap. No extra LOAD or resident copier is introduced.

| Boot payload material | Bank-1 range | Lifetime |
| --- | --- | --- |
| Whole qualified controller | `$4200–$5188` | Preserved throughout run |
| Zero code slack | `$5189–$520F` | Reserved for this delivery proof |
| Private `VCC2` 0.1 identity | `$5210–$521F` | Preserved; not runtime-validated |
| Zero prefix beyond identity | `$5220–$5FFF` | Disposable; future state/stack/image and VIC screen |
| Exact USOV 0.3 scheduler/context/tail | `$6000–$7228` | Boot source only, retired before graphics |

The identity encodes entry `$4200`, length, additive checksum, C dispatch `$42D5`
and packed capacity 2,224. Captures compare the **entire 4,128-byte code/identity
slot**, not only its header/checksum. The module bytes are taken from the immutable
machine-qualified controller archive, with every archive hash verified first.

Only eight emitted bytes change across existing loader/installer images:
two stage-1 LOAD/end operands, three scheduler source operands, two activation
source operands, and one boot-console checksum operand. Both installer lengths
are unchanged. Build checks reject any difference outside the measured source
relocations or the regenerated console checksum operands. The page/tail/context
payload and its installed destinations are byte-identical to canonical input.
Zero additional resident delivery bytes does **not** mean runtime validation or
compositor integration is free.

## Qualification and evidence

Both formats pass:

- VICE cold boot and exact slot capture after boot, xinit, xclock, xwave,
  completed wave, cowsay/ls/cd/pwd/echo, graphics shutdown and restart.
- Native 1986 input/history, foreground wave, 32 scripted drags with a background
  clock, completion/replay, Ctrl+C and subsequent console use; final full slot
  capture remains identical.

This is delivery/lifetime qualification, not execution of the delivered
controller, a pixel-cache speed claim, runtime corruption rejection, NMI stress
of the new boot chain, or physical hardware qualification. The native log's
"cached" timing label refers to existing cached **vertices**, not pixel pastes.

Each run binds the exact build-report hash, both disk hashes and all raw capture/
log/provenance hashes. Preservation rechecks inputs, normal disks, generated
artifacts, run bindings, every expected capture and the native 32-drag gate;
it refuses to overwrite evidence. No ROMs or complete emulator snapshots are
archived. Evidence:
`bench/{artifacts,results}/2026-09-28-window-cache-controller-delivery-r1`.
The earlier non-r1 archive remains historical/incomplete: it omitted the
standalone canonical scheduler input (the bytes were still in its secondary
payload). The archival input test caught this; r1 binds and preserves that
input explicitly. It is the qualified/reproducible checkpoint.

```sh
# Normal production inputs must exist first.
distrobox enter my-distrobox -- python3 tools/window_cache_controller_delivery.py build
distrobox enter my-distrobox -- python3 tools/window_cache_controller_delivery.py 1986
python3 tools/window_cache_controller_delivery.py vice
python3 tools/window_cache_controller_delivery.py preserve
```

Experimental output disks live only in `build/window-cache-controller-delivery`.
The normal `build/boot/udeks.d71` and `.d64` remain byte-identical to the
window-manager checkpoint. The VICE probe terminates only its own sessions.

## Next: resident acceptance and compositor hooks

Remaining bank-0 padding is 502; the uninstalled shared binding costs 241,
leaving 261 **before** acceptance/validation, persistent tickets, marshalling,
hooks and locks. All of those must be measured in an actual normal/panic link.
There is still no complete integration fit claim.

Before invoking this module, validate delivery/version/entry/layout/checksum
without executing an unvalidated banked C dispatcher. Account for a persistent
accepted/disabled state and the original content ticket: common `$F7xx` request
bytes are overwritten by other VIC gateways and cannot retain continuation
state between polls. Mutable row-core operands mean a whole-code checksum is
an initial acceptance gate, not an unconditional checksum before every row.

Compositor hooks must preserve explicit completion, freeze the source across
capture and destination across paste, run at most one row per poll, invalidate
before content mutation/resize/restack/destruction/handle reuse/shutdown or
cancellation, and retain normal redraw on failure/partial/obscured/oversize
images. Starting a drag during capture must fall back safely, not clear the
source under a live continuation. Background recomposition must not accidentally
invalidate an intentionally retained READY image before paste. A second drag,
clock update or command during paste must not change geometry under it.

Do not borrow USH, app slots, common gateways/stack guards, module reservations,
scheduler padding or bootfs space. Repeat actual cache execution with the full
normal services, input, Z80, cancellation, overlap/resize, bitmap and NMI gates
before enabling pixel-cache moves. No new manual test is needed for this
uninvoked delivery checkpoint.
