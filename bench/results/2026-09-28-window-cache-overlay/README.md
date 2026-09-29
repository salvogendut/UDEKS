# Overlay row proof: 1986 and VICE

Four normal full-image records pass an independent pixel/dirty oracle with
active IRQs, stack/flag checks and canaries. Two negative-control records are
deliberately rejected: byte 14 is 1, proving an IRQ arrived with the unsafe
worker-flat mapping when the lease's SEI was removed.

Run manifests bind records to the exact PRGs in the matching artifact archive.
`report.json` contains counts and pixel hashes, **not GUI latency measurements**.
No production cache-enabled disk, real service/task/input concurrency or
physical-hardware qualification is implied. See
[the qualification note](../../../docs/WINDOW-CACHE-OVERLAY.md).
This explanatory README was added after SHA256SUMS and is not in its manifest.
