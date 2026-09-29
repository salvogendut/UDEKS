# Window-manager state-reclaim preparation

Issue #14, `graphics-bounded-repaint`, 2026-09-29. This is preparation for a
compact bounded compositor, not its implementation or a latency improvement.

The private candidate eliminates three redundant bytes per window. Host
differential tests preserve full canvases, diagnostics and callback counts
across occlusion/partial paste, sparse slots, all owner byte values, dragging,
close/reuse and reset. The public owner argument remains accepted; neither
implementation checks ownership. Create still rejects non-bitmap surfaces.

Both isolated normal and panic links save 117 CODE and 12 HIGHBSS bytes:
manager CODE 7,762 -> 7,645; manager state 88 -> 76. Imported helpers and actual
linked library module sizes match. The exact reference runtime archive is
preserved as `build/none.lib`, alongside the objects, listings and maps.
The full reference job still needs 22 state bytes; this does not solve all
continuation/backend state placement.

All split linker outputs were redirected into the private experiment. Its
`kernel.bin` files are **UNBOOTABLE budget artifacts**: the unpadded shadow
moves to $A16B and private import bridges have not been regenerated. Do not
load them. No production source/ABI/disk changed, and no emulator was launched.

Reproduce the sizing with the accepted normal/panic providers present:

```
distrobox enter my-distrobox -- make repaint-compact
python3 -m unittest discover -s tests -p 'test_window_repaint_compact*.py'
```

`budget.json` binds inputs and measured outputs; the paired artifact directory
preserves them. `SHA256SUMS` covers every preserved file in each directory.
Next is the specialized continuation/state layout and bounded raster driver,
checked against the generic reference before any resident candidate is linked.
