# Private bank-1 window-cache row overlay

Standalone raw PRGs, **not UDEKS boot images**. The bank-1 core, measured
resident binding and copied gateway are actually exercised together. Normal
programs `probe-0.prg` and `probe-1.prg` qualify alignment/edges and a large
snapshot; `probe-irq-leak.prg` is a deliberately unsafe one-byte negative
control (SEI → NOP in the binding's live gateway image).

See [the qualification note](../../../docs/WINDOW-CACHE-OVERLAY.md) for
placement, reproduction, evidence and the remaining production gates.
`build/build-report.json` binds sources, exact programs and measured sizes;
SHA256SUMS covers preserved inputs and generated images/maps. This README was
added afterward and is intentionally outside that manifest.
