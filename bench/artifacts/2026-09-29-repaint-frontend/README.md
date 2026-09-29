# Private frontend measurement artifacts

`inputs/` archives the sources and provider objects/maps sealed by the matching
result `budget.json`; `build/` contains exact library, generated C/ASM, objects,
and isolated normal/panic baseline/replacement split outputs and maps.

The replacement images retain synchronous legacy composition and stale private
import bridges. They are **unbootable**, not release candidates or native tests.
Do not use them to build a disk. Tests/results qualify host semantics and actual
link budget only, not production admission/ownership, NMI or live apps.

See `docs/WINDOW-REPAINT-FRONTEND.md` and the result README. The root SHA manifest
covers all preserved files, including nested earlier qualification manifests.
