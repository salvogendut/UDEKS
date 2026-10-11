# AGENTS.md — working notes for automated agents

## GitHub, toolchain and emulators

- On this Debian 12 machine, `gh`, cc65 and SDCC are **native**. Use `gh`
  directly; there is no `my-distrobox` container. Install missing development
  dependencies with `sudo apt install` when authorized.
- The older reference environment used `distrobox-enter my-distrobox` for
  toolchain/GitHub commands. Use it only on machines that actually provide it.
- VICE is the `net.sf.VICE` Flatpak, run from the host for the VICE probes.
  The native `1986` harness needs sibling emulator source, absent here.
  Use the installed `io.github.salvogendut.Emulator1986` Flatpak here; ROMs
  are assembled from `../vice-roms` under `build/1986-roms`.
- **Never run `make clean` at the repository root**: `build/` contains active
  git worktrees. Build each branch in its own `build/<name>` worktree.
- `make check` runs the host test suite. On this machine, placement/app gates
  and disk builds also run natively.
