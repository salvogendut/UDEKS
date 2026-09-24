# UDEKS root-terminal line editor API 0.1

The initial input consumer is a resident 8502 terminal service with a fixed
focus on the retained root console. It follows the keyboard service in the
static registry, removes queued events, ignores releases, and sends normalized
press events to a bounded editor. A later window registry will replace fixed
focus with a terminal handle without changing the keyboard event source.

The editor stores at most 54 printable ASCII bytes, reserving the final screen
cell for its visible cursor. It supports insertion at the cursor, destructive
Backspace to the left, Home, the standard shifted/unshifted horizontal cursor
key, the C128 dedicated left/right keys, and Return. Unsupported non-text keys
are ignored. There is no history, completion, typematic repeat, layout policy,
or command dispatch yet.

Return retains a NUL-terminated submitted line for the next command consumer,
clears the active edit buffer, advances the retained console, and emits a new
`UDEKS:~> ` prompt. `udeks_line_editor_get_line()` consumes that submission.
Until command dispatch is installed, a later Return explicitly overwrites an
unconsumed submission and advances the diagnostic overwrite counter.

Text changes first update the retained console. The terminal then acquires the
framebuffer, renders only the damaged cell span, flushes the bounded dirty-row
range, and releases ownership. Ordinary appended characters therefore repaint
one character and the old/new cursor cells instead of scanning or redrawing the
whole framebuffer.

## Diagnostic record

The service publishes a 32-byte `RCLI` record at `$F150`:

| Offset | Size | Meaning |
|---:|---:|---|
| 0 | 4 | ASCII magic `RCLI` |
| 4 | 1 | Format (`1`) |
| 5 | 1 | Starting (`1`), ready (`2`), or error |
| 6 | 1 | Failure code |
| 7 | 1 | Maximum editable bytes (`54`) |
| 8–9 | 2 | Current line length and cursor offset |
| 10 | 1 | Framebuffer refresh pending |
| 11 | 1 | Focused terminal (`0`, the root console) |
| 12–19 | 8 | Poll, press, edit, and submission counters, little-endian |
| 20 | 1 | Last submitted length |
| 21–22 | 2 | Last submitted unsigned byte sum, little-endian |
| 23 | 1 | Unconsumed submissions overwritten |
| 24–25 | 2 | Completed framebuffer refreshes, little-endian |
| 26–31 | 6 | Reserved |
