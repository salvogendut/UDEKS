# Repaint caller audit — 2026-09-29

Actual source graph: ten synchronous compositions, two direct `void` painters.
The shared damage-to-lane marshaller costs 78 CODE bytes in both complete
normal/panic isolated links, no new runtime helpers/state. Optimistic shortfall
is **at least 255 bytes before any actual caller or provider**. This is a
source/size audit, not an installed manager, emulator timing result or manual
test disk. `budget.json` binds the precise source, object and link inputs.
