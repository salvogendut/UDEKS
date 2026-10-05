# AGENTS.md — working notes for automated agents

## GitHub, toolchain and emulators

- `gh` and the cc65/SDCC toolchain live in the **`my-distrobox`** container, not
  on the bare host. Run them through `distrobox-enter`:
  - `distrobox-enter my-distrobox -- gh issue create ...`
  - `distrobox-enter my-distrobox -- make -j8 boot graphics-apps-check ...`
- `gh` authenticates from the container's **keyring only under
  `distrobox-enter`**. `podman exec` (and the bare host) report an invalid or
  missing token, so always use `distrobox-enter my-distrobox -- gh ...` for
  GitHub operations.
- If `distrobox` is not on `PATH`, invoke it from the active deployment, e.g.
  `PATH=/run/host/sysroot/ostree/deploy/fedora/deploy/<hash>.0/usr/bin:$PATH \
   LD_LIBRARY_PATH=/run/host/sysroot/ostree/deploy/fedora/deploy/<hash>.0/usr/lib64 \
   CONMON=<hash>/usr/bin/conmon distrobox-enter my-distrobox -- <command>`.
- VICE is the `net.sf.VICE` Flatpak, run from the host for the VICE probes.
  The native `1986` harness builds against the sibling emulator source.
- **Never run `make clean` at the repository root**: `build/` contains active
  git worktrees. Build each branch in its own `build/<name>` worktree.
- `make check` runs the host test suite; container-only gates
  (`placement-check`, `graphics-apps-check`, disk builds) run under
  `distrobox-enter`.
