# Private C cache runtime and row-blitter proof

Exact standalone PRGs, module/gateway binaries, maps and hashed source inputs.
Nothing in this archive is installed in the normal boot image.

The module contains the real C policy plus private cc65 helpers: 2,685 CODE
and 28 state bytes in bank 1. The private software stack is `$4D00-$4DEF`;
the bank-0 caller uses `$EFF0`, and the bank-1 shell stack is protected.
C/row resident bindings measure 83+194=277 bytes, excluding the diagnostic
uploader, embedded module, oracle, IRQ and guard code.

Three fault PRGs differ from `probe-0.prg` in exactly one live C gateway byte:
SEI removal, shifted ZP restoration, and shell-stack selection. Compiler
record sizes/runtime addresses, linked output hashes and PRG hashes are in
`build/build-report.json`. The matching results archive binds each record to
its exact program and emulator provenance.

See [the runtime notes](../../../docs/WINDOW-CACHE-C-RUNTIME.md) for layout,
reproduction and limits. This is not a production fit, NMI/input/task/Z80/HW
qualification or a GUI speed claim. `SHA256SUMS` covers the preserved evidence;
this explanatory README is outside the manifest. No ROMs are stored.
