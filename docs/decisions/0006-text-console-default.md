# ADR 0006: Text-mode root console and 1 MHz boot default

- Status: accepted
- Date: 2026-09-24

## Context

The first root-console implementation composed software-font text into a
640x200 bitmap. Atomic cold-boot upload removed the visible top-to-bottom
paint, and dirty spans reduced later transfers, but physical-hardware testing
showed that interactive text still arrived too slowly to be a usable system
console. A bitmap makes every glyph a multi-byte software-rendering operation
and provides no hardware cursor.

The C128 VDC already provides an 80x25 text display, programmable character
RAM, per-cell attributes, a hardware cursor, and block fill. UDEKS needs only a
small set of non-stock shapes for its identity and window chrome. Text mode
also removes the display-performance reason for selecting VDC-only 2 MHz mode
during every boot.

## Decision

The default UDEKS root console uses the VDC's native 80x25 attribute text mode.
Its screen lives at `$0000`, attributes at `$0800`, and the retained 64x21 root
terminal occupies the bordered area at character coordinate `(14,2)`. Normal
text uses the stock C128 character generator.

Build tooling converts the 64-pixel pipe and Japanese wordmark XPM files into
8x8 tiles, deduplicates identical tiles, and appends six line-drawing glyphs.
Only screen codes `$80` and above are redefined; codes `$00-$7F` remain the
stock console set. The current assets require 63 custom glyphs. The upload is
performed once into the upper half of the active character-generator region,
rather than replacing the whole set.

The root-terminal model remains display independent. Dirty character spans are
translated to VDC screen codes and transferred directly, and the VDC hardware
cursor represents the insertion point. Screen and attribute clears use the
VDC block-fill engine. A typical keypress therefore changes one or a few text
cells instead of repainting bitmap glyphs or uploading a 16,000-byte surface.

The framebuffer service and its public graphics API remain available, but it
is not a default boot service and does not own the root console. A graphical
client must explicitly acquire a display mode. Since the VDC cannot overlay
hardware text on bitmap graphics, later policy must either switch the VDC as a
whole, use character graphics, or place graphical work on the VIC-IIe.

The VIC-IIe is the preferred initial candidate for interactive pixel graphics:
its display RAM is directly addressable by the 8502, unlike the VDC's indirect
port. This is a hypothesis to qualify with equivalent drawing benchmarks, not
a claim that it wins every workload; the VIC has lower resolution and consumes
memory cycles while displaying. The VDC remains valuable for 640-pixel output
and an independent second monitor.

The production boot remains at the stock 1 MHz 8502 clock. The already
qualified VDC-only 2 MHz transition is retained as an optional machine-policy
mechanism for a workload that explicitly permits the VIC-IIe display to be
blanked. Applications and drivers may not write `$D030` privately.

"Reuse the C128 console" means reuse its VDC text-display architecture and
character generator, not call the BASIC/KERNAL screen editor after UDEKS has
taken control. UDEKS retains its own terminal state, bounded VDC transport,
input service, and line editor, avoiding a permanent dependency on ROM editor
workspace and MMU assumptions.

## Consequences

- The root terminal remains responsive at 1 MHz and preserves the VIC-IIe for
  future second-monitor use.
- Boot transfers scale with cells and one-time custom glyph data, not with a
  full-screen bitmap.
- The logo and window borders retain their intended appearance without a
  software font renderer.
- Text windows are the natural first window type. Mixed pixel graphics on the
  same VDC require an explicit mode/ownership transition rather than implicit
  overlap.
- ADR 0005 still defines retained window content and focus, but its assumption
  that a full-screen bitmap is always the final VDC composition target is
  superseded.

## Related decisions

- [ADR 0004](0004-microkernel-modules.md): assembly-oriented microkernel and C
  services.
- [ADR 0005](0005-root-window-and-compositor.md): retained root console and
  overlapping-window model.
- [VDC console service](../VDC-CONSOLE.md).
- [VDC framebuffer service](../VDC-FRAMEBUFFER.md).
