# UDEKS window system and native console plan

## Product model

The black-bordered boot area is the UDEKS root console window. It begins with
boot diagnostics and becomes the default interactive console. New text or
graphics windows can be created above it, moved through z-order, and hidden or
closed without destroying the console content underneath.

The logo rail and desktop background sit behind the root console. The VDC
framebuffer is a composed output surface, not the authoritative copy of any
window's content.

## Implementation stages

### 1. Retained root-console model

- [x] Define the initial 64-column by 21-row text grid matching the bordered
  viewport.
- [x] Retain characters and cursor position independently of VDC pixels.
- [x] Move boot-message construction out of the VDC renderer.
- [x] Render the retained rows through the owned framebuffer API.
- [x] Advertise retained text in framebuffer diagnostic format 8; format 7
  remains readable as preserved historical evidence.
- [x] Qualify an unchanged visual result on 16 KiB and 64 KiB VDC tiers in
  VICE and `1986`, within a 1,800-frame cold-boot window.

### 2. Terminal behavior

- [x] Add sequential character output, carriage return, newline, tab, backspace,
  clear, cursor movement, wrapping, and scrolling.
- [x] Track dirty text rows and render only changed rows.
- [x] Preserve output while the root console is obscured.
- [ ] Define stream endpoints so standard output can target a terminal handle.

The provisional resident API and exact control-character behavior are defined
in the [retained terminal API](../abi/terminal.md). It targets the implicit
root console until scheduler identities and IPC make terminal handles
meaningful.

### 3. Window registry and compositor

- Define bounded window descriptors with handles, geometry, visibility,
  surface type, z-order, owner, and damage.
- Add create, destroy, move, resize, show, hide, raise, and lower operations.
- Clip every client operation to its window and screen bounds.
- Recompose damaged regions back-to-front without save-under buffers.

### 4. Text and graphics clients

- Generalize the root text grid into reusable terminal-window storage.
- Add bounded one-bit bitmap windows and repaint callbacks.
- Add window chrome and optional title/border policy outside client surfaces.
- Keep display-controller details behind VDC and VIC backends.

### 5. Input and focus

- [x] Implement a complete polled C128 keyboard event source and bounded FIFO.
- [ ] Route normalized key events to the focused window.
- Add focus traversal and explicit focus changes through the window manager.
- Add joystick, pointer, and light-pen sources without changing client input
  semantics.

### 6. Native UDEKS CLI

- Build line editing, insertion/deletion, history, and completion as a terminal
  client.
- Use registry-based command dispatch rather than a monolithic command chain.
- Begin with `help`, `clear`, `echo`, `version`, `sysinfo`, `services`,
  `devices`, `memory`, and `reboot`.
- Add filesystem, process, and module commands only when their service APIs
  exist.

### 7. Dual-display composition

- Allow workspaces or windows to target VDC, VIC-IIe, or mirrored outputs.
- Preserve focus and stream bindings when a window changes display.
- Demonstrate concurrent root-console and graphical application activity on
  separate monitors.

## Constraints

- Clients never access `$D600/$D601`, VIC registers, or video RAM directly.
- The 8502 owns interactive display and input policy; Z80 work is admitted only
  for measured bounded operations.
- A 16 KiB VDC configuration remains a supported baseline.
- No window may allocate an implicit full-screen bitmap merely for overlap
  restoration.
- All waits and transfers remain bounded and diagnosable.
