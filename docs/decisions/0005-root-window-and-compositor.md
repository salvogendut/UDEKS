# ADR 0005: Retained root console and overlapping windows

- Status: accepted
- Date: 2026-09-24

## Context

The reference UDEKS boot screen established a bordered area containing boot
messages and a future-shell prompt. Treating that area as one-shot framebuffer
decoration would make it impossible to restore its contents after another
window overlaps it. It would also bind the future shell directly to VDC pixels
instead of the display-independent interfaces required by the microkernel
design.

The C128 has enough memory for a canonical framebuffer and compact retained
text state, but not for an unrestricted full-screen bitmap behind every
window. UDEKS must therefore retain content according to its type and compose
only the visible result.

## Decision

The bordered boot-message area is the persistent UDEKS root console window.
Boot diagnostics populate its retained text-cell model; after boot, the native
CLI continues in the same window. Text-bound standard input, output, and error
streams attach to terminal windows, with the root console as the default.

Other top-level windows may overlap and partially or completely obscure the
root console. Windows have geometry, visibility, z-order, damage, and focus.
They expose either retained text cells or graphical surfaces. Applications do
not write directly to VDC or VIC memory.

The full display retains desktop chrome, including the UDEKS logo rail, behind
the window stack. The compositor clips each window to its bounds and damaged
screen regions, draws back-to-front, and flushes the resulting canonical
surface through the display service. Obscured root-console output continues to
update its model and appears when the region is exposed again.

Memory policy depends on content:

- text windows retain compact character cells, cursor state, and later style
  attributes;
- bitmap windows use bounded owned surfaces, banked allocations, or repaint
  callbacks rather than an unconditional full-screen buffer;
- the existing 16,000-byte system-RAM framebuffer remains the final composed
  VDC image and recovery copy;
- a display backend owns physical video memory and register access.

Keyboard and pointer events go to the focused window. Window management and
focus policy remain separate from terminal editing and shell command policy.

## Consequences

- The boot console must become retained state before overlapping windows are
  introduced.
- The native CLI is a client of terminal, input, and service APIs rather than
  a privileged display owner.
- Text and graphics can coexist in one window stack and later target either
  video controller.
- Damage tracking and recomposition replace save-under buffers, avoiding memory
  proportional to every window's covered area.
- The first implementation may remain statically linked, but its boundaries
  must match future replaceable services.

## Related decisions

- [ADR 0004](0004-microkernel-modules.md): assembly microkernel and C services.
- [VDC framebuffer and compositor](../VDC-FRAMEBUFFER.md).
- [Window-system implementation plan](../WINDOW-SYSTEM.md).
