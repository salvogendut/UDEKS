# Reproducible compact raster artifacts

`inputs/` preserves every source, provider object/map and prior bank-proof input
listed by the matching result `budget.json`; `build/` preserves its generated
C/ASM, objects, exact library, normal/panic split links and native pixel program.
The results directory contains the build report and both decoded/raw runs.

The full sizing kernels retain legacy synchronous composition and stale import
bridges. They are **unbootable** and must not be copied into a UDEKS disk.
Only `build/native.prg` is a runnable standalone diagnostic (entry `$2000`).
Its client/commit are models; no live OS, apps, NMI or latency qualification.

See `docs/WINDOW-REPAINT-RASTER.md` and the result README for measured budgets,
scope and reproduction. SHA256SUMS covers all files, including nested manifests.
