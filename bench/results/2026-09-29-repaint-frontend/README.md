# Frontend / view-packing budget

Issue #14 host and link-only experiment, 2026-09-29. No new emulator, hardware,
live app/paging/NMI, delivery or input-latency qualification. No boot disk change.

Added private C frontend: gate 48 + control 98 + one-step poll/view packing 440
= **586 CODE**. Original manager allocation remains 88 bytes; no hidden frontend
state. Same newly linked runtime closure as the preceding raster: 72 bytes.
Both full normal/panic links have CODE growth 1,240 bytes while legacy composition
remains. These experimental links are unbootable and must not be packaged.

Component lower bound **2,599**, against an optimistic 2,113-byte allowance:
**486 bytes short**, before admission/delivery/call-site/provider/busy/teardown.
Additional old helpers total 722 bytes but are not reclaimed; compatibility paths
still call them. The earlier 100-byte drawing-only headroom is not a full fit.

Host tests exercise real table packing/dispatcher/lane/receipt/raster code with
modeled client/page copy. Complete overlap canvases, sparse/hidden handles,
bounded step counts, unacknowledged delegation, local work after packet clobber,
pending-only requests, fences/poisoned title, geometry wrap, exhaustion/abort and
atomic lease/cache/graphics/drag deferrals pass. Lease value 1 is a trusted caller
assertion; production admission and ownership are not implemented by this test.

`budget.json` seals sources and build outputs. The matching artifacts directory
contains exact library/providers, generated C/ASM, objects and all split outputs/
normal+panic maps. SHA manifests cover every file, including nested manifests.
See `docs/WINDOW-REPAINT-FRONTEND.md` for contracts, limitations and next gate.
