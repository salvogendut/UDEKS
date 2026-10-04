# Relocatable executable qualification — 2026-10-04

Exact inputs: `bench/artifacts/2026-10-04-relocatable-apps`.

## Same binary, independent C tasks

`vice-d64` / `vice-d71`: VICE 3.10 x128 Flatpak, true-drive 1541/1571 cold
boot. `tools/banked_loader_probe.py --reloc` calls the private loader from a
self-restoring normal service-poll hook. It loads **the same RELOCAPP.BIN** at
`$2300` and `$3500`; both images/BSS match the reference relocator before
activation. `app3.bin`/`app4.bin` retain these captures. Tasks run concurrently
with distinct private contexts; each has tag 3 and exits with status 43.
DATA/function/BSS pointers, split LOW/HIGH references, a numeric address
lookalike and the absolute syscall gate are exercised. Recursive C frames
survive SLEEP/YIELD; canaries, independent counters, exit, reap and clean reload
pass. Existing clock, wave and Z80 code match before/after; console and later
calculator launch work.

Malformed count, past-end/duplicate/unsorted patch offsets, wrong canonical
base, entry, flags, truncated/trailing data all return ENOEXEC without
publishing ownership or disturbing the peer. Legacy malformed fixed images,
ownership, stopped/zombie and reaping checks also pass. Full-capacity fixed
fixtures are omitted from this mode to fit a D64; they remain in the ordinary
banked-loader probe. This is not native mouse testing or automatic allocation.

`build-result.json` records the independent flat-link oracle comparison at
both destinations. The packed UDEX omits o65 timestamp/filename options.
Raw VICE `.bin` captures include a two-byte monitor load-address prefix.

## Existing desktop regression

`four-apps-vice-d64`: the regular four-app probe passes arithmetic, drawing,
drag, focus/close/reload, panel, console, targeted Ctrl+C, shutdown, stack
guards and completed shadow/bitmap equality. Input uses injected WM events,
not native device events.

`native-input-d64`: unmodified 1986 `81485cc7`, raw IEC and actual emulated
keyboard/1351 input, passes the four-app regression. It verifies the changed
loader/access delivery with the existing fixed-address apps; it does **not**
independently qualify UDEX 0.2 execution (VICE above does). No emulator source
was modified. Physical-C128 confirmation remains pending.

Reproduce after the container build:

```sh
make reloc-probe
python3 tools/xcalc_probe.py --four-apps --disk build/boot/udeks.d64 \
  --output build/generic-apps/four-apps-vice-d64
distrobox enter my-distrobox -- python3 tools/1986_storage_smoke_build.py \
  --emulator ../1986 --roms ../1986/roms --four-apps \
  --output build/generic-apps/native-input-d64
```

`clean-result.json` records eight byte-identical outputs from a parallel,
isolated source-copy build. Both normal/panic and graphics placement gates
pass. `layout.json` records the tightened storage/lookup bounds, extension
reservations, unchanged CPU pages/stacks and 45-byte resident headroom.
All test-owned VICE sessions were terminated. Historical evidence is unchanged.
