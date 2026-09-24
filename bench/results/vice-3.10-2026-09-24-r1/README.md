# VICE 3.10 qualification pass — original artifacts (r1)

This first independent-emulator pass used the immutable PRGs in
`bench/artifacts/2026-09-24/`. It is retained because it exposed two benchmark
harness defects, but its timings are superseded and must not be used for the
executive decision.

- The Z80 interrupt-service run stayed in state `$01` after both 20- and
  60-second host timeouts. Its diagnostic block recorded only 3 of 48 expected
  interrupts and two unexpected interrupt sources. The source had not
  explicitly selected IM1.
- The 1 MHz 8502 interrupt-service block reached complete state, but strict
  decoding rejected a non-monotonic sample (`24/416/292`). The `$0100`-scale
  discontinuity identified a torn low/high read of the running CIA timer.
- The 2 MHz interrupt-service block happened not to cross the same boundary;
  that does not make the read sequence safe.

The completed raw blocks and the incomplete Z80 diagnostic block are under
`raw/`; `raw/SHA256SUMS` protects them. Revision 2 corrects both preconditions
and is the first VICE result set suitable for architectural interpretation.
