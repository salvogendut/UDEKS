# AGENTS.md — working notes for automated agents

## GitHub, toolchain and emulators

- On this Debian 12 machine, `gh`, cc65 and SDCC are **native**. Use `gh`
  directly; there is no `my-distrobox` container. Install missing development
  dependencies with `sudo apt install` when authorized.
- The older reference environment used `distrobox-enter my-distrobox` for
  toolchain/GitHub commands. Use it only on machines that actually provide it.
- VICE is the `net.sf.VICE` Flatpak, run from the host for the VICE probes.
  For new native emulator checks, use the available sibling `../1986` source
  and binary as requested by the user; record its actual revision and settings.
  The installed `1986` app is `io.github.salvogendut.Emulator1986`. IPC
  qualification also builds its pinned source in the feature worktree under
  `build/ipc-1986-source`, with a local static SDL3 build. See
  `docs/IPC-QUALIFICATION.md`; that older archive used a pinned download. ROMs are
  assembled from `../vice-roms` under the root repo's `build/1986-roms`.
  Keep ROM-bearing native checkpoints private under ignored `build/`.
- **Never run `make clean` at the repository root**: `build/` contains active
  git worktrees. Build each branch in its own `build/<name>` worktree.
- `make check` runs the host test suite. On this machine, placement/app gates
  and disk builds also run natively.
