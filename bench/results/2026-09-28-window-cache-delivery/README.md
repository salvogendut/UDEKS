# Cache-core delivery lifetime evidence

Both disk formats pass in VICE 3.10 and native 1986. VICE captures compare the
complete 512-byte code/identity slot after boot, xinit, clock/wave launch,
completed wave, console utilities, shutdown and restart. Native runs perform
32 scripted window drags per format with a background clock and console
cancellation, then compare the same slot.

These records show delivery and lifetime preservation, **not execution of the
delivered core**, cached GUI moves, NMI safety or real-hardware acceptance.
The companion C policy link was only host-tested and measured.

`*-results.json` records capture hashes; `*-provenance.*` identifies the
emulators, and native logs retain the input/drag outcomes. VICE captures
include a two-byte `$4200` load prefix; native captures are raw 512 bytes.
No ROMs or full snapshots are stored. `SHA256SUMS` covers all evidence except
this explanatory README.
