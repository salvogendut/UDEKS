# Sprite-file UI prototype — NOT installed or qualified

**Superseded:** production Save/Load now lives in `user/bin/xsprdef.c` and
`user/bin/xspr_file.c`, using the generic joined allocation. See
[the current guide](../../docs/XSPRDEF.md). This directory preserves the
original compile-only experiment; the notes below describe that checkpoint,
not the current shipped worktree build.

The user accepted the pixel-click fix and requested S confirmation, an L load
control, and `SPRITES.SPR` as the default filename. This directory preserves
the first implementation while the accepted editor remains built unchanged.

The draft has Yes/No Save/Load dialogs, simple result/error messages and native
UTRQ OPEN/READ/WRITE/CLOSE through `$FF16` (not the transient console gate).
The proposed file is `/SPRITES.SPR`: all eight definitions, each 63 bytes in
MSB-first row order, exactly 504 bytes, with no PRG load address or header.
This format is **proposed**, not published. LOAD stages into a union with the
app-private drawing buffer and commits only after exact length, EOF and CLOSE
succeed; the compositor retains its independent image while I/O is active.
The proposed B behavior keeps edits in the session bank before returning to
the list, so several sprites can be edited before a single disk save.

Status after the generic-capacity follow-up:

1. Size: measured 5,373 file bytes and 5,290 image+BSS bytes; the
   ordinary largest native allocation permits 4,352 image+BSS and 4,608 file
   bytes. The user chose the generic capacity feature first. Its joined
   allocation permits 7,168 image+BSS / 7,424 file bytes, enough for this
   prototype, with a three-client concurrency limit while joined. This does
   not itself install or qualify the Save/Load code.
2. Writes currently support create-exclusive only. Repeated save of an
   existing filename gives EEXIST, not overwrite. The user has been asked
   whether to deliver that limitation first or add overwrite support first.
   Never silently delete/overwrite the file or make the boot mount writable.

Measure in the reference container:

```sh
distrobox-enter my-distrobox -- python3 experiments/xsprdef-files/measure.py
```

This intentionally produces objects/map only under `build/sprite-files`;
there is no launchable image or production dependency. It has **not** passed
behavioral/emulator qualification. Before integration: codec tests covering
short/error reads and writes, wrong lengths, every CLOSE error, unchanged
editor state on failed load, UI hitboxes/cancel, native owner isolation,
save-close-reboot-load on copied media, read-only/existing-file errors and
all slot/stack/retained limits. Preserve the accepted pixel-click regression.
