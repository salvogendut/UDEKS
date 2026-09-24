# UDEKS retained terminal API 0.1

The first terminal interface operates on the 64x21 retained root-console
model. It is a provisional resident 8502 C API; terminal handles and stream
requests will replace the implicit root-console target after task identities
and IPC exist.

Clients include `udeks/root_console.h`. Sequential output is accepted through:

```c
void udeks_root_console_write(unsigned char character);
void udeks_root_console_write_string(const unsigned char *text);
```

The model recognizes these control characters:

| Character | Behavior |
|---|---|
| `\r` | Move to column zero without changing row |
| `\n` | Move to column zero on the next row; scroll at the bottom |
| `\t` | Write spaces through the next eight-column tab stop |
| `\b` | Move left one column without erasing; stop at column zero |
| `\f` | Clear the grid and home the cursor |

Printable bytes replace the current cell and advance the cursor. Output at
column 63 wraps to the next row. Advancing below row 20 scrolls all retained
rows upward and clears the new bottom row.

The existing `write_at` operation remains available for boot diagnostics and
other positioned producers; it does not move the terminal cursor. `clear`
homes the cursor while preserving its visibility. `reset` also hides it.

Every text change and cursor movement marks the affected row as damaged.
The framebuffer owner calls `udeks_framebuffer_refresh_root_console()` while
holding its lease, then flushes or releases normally. Only damaged rows are
cleared and re-rendered into the canonical framebuffer; physical VDC transfer
remains the framebuffer service's responsibility.

This API does not yet include keyboard input, line editing, stream attachment,
terminal handles, or concurrency. Backspace is intentionally non-destructive;
the future line editor decides whether a key press should erase a character.
