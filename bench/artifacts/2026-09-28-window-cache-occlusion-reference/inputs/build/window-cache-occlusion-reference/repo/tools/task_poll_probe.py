#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Qualify resident POLL with a compiled C task and live software-stack locals."""
from __future__ import annotations

import argparse
import os
import re
import time
from pathlib import Path

import shadow_boot_probe as sp
from task_cancel_probe import wait_symbols
from task_waitpid_probe import scheduler_symbols
from vice_capture import choose_port, monitor_command

ROOT = Path(__file__).resolve().parents[1]
PHASE = 0xF044


def validate_completion(record: bytes) -> None:
    if len(record) != 8 or record != b"UPOL\xa5\x00\xa1\x00":
        raise ValueError(f"compiled POLL task failed: {record.hex()}")


def paused_writes(port: int, writes: list[tuple[int, bytes]]) -> None:
    """Keep the CPU paused for the whole mutation, preserving its live map."""
    sp.write_kernel_blocks(port, writes)


def run(disk: Path, timeout: float, flatpak_id: str) -> None:
    overlay = ROOT / "build/8502/udeks-scheduler-overlay.map"
    slots = scheduler_symbols(overlay)["_udeks_lifecycle_slots_private"]
    waits = wait_symbols(overlay)
    tick = int(re.search(r"_udeks_monotonic_ticks_low\s+([0-9A-F]{6})\s+RLA",
                         overlay.read_text()).group(1), 16)
    editor = sp.symbol_addresses(ROOT / "build/8502/udeks-8502.map")
    port = choose_port()
    process, master = sp.launch_vice(disk.resolve(), port, flatpak_id)
    work = ROOT / "build/vice"
    work.mkdir(parents=True, exist_ok=True)
    deadline = time.monotonic() + timeout

    def capture(label: str, start: int, size: int) -> bytes:
        return sp.capture_blocks(port, [(work / f"poll-{disk.suffix[1:]}-{label}.bin",
                                        start, start + size - 1, "kernel")])[0]

    def blocked() -> None:
        sp.wait_for_byte(port, slots + 1, 4, deadline)
        if capture("blocked", slots, 8)[1:3] != bytes((4, 2)):
            raise RuntimeError("POLL did not own WAITING/INPUT")

    def inject(text: str) -> None:
        start = editor[sp.LINE_EDITOR_TEXT_SYMBOL]
        length = editor[sp.LINE_EDITOR_LENGTH_SYMBOL]
        record = bytearray(length - start + 3)
        record[:len(text)] = text.encode("ascii")
        record[length - start] = len(text)
        record[length - start + 1] = 1
        paused_writes(port, [(start, bytes(record))])

    try:
        print(f"{disk.name}: booting compiled C POLL task", flush=True)
        sp.wait_for_byte(port, PHASE, 1, deadline)
        if any(capture("validation", waits["state"], 8)):
            raise RuntimeError("rejected/immediate requests left wait ownership")
        print("  immediate and invalid requests OK", flush=True)
        # Force a wrap while retaining the raster-owned counter progression.
        paused_writes(port, [(tick, b"\xfe\xff"), (0xF046, b"\xa1")])
        sp.wait_for_byte(port, PHASE, 2, deadline)
        end = int.from_bytes(capture("wrapped-clock", tick, 2), "little")
        if not 8 <= end < 0x8000:
            raise RuntimeError(f"finite wait did not cross the clock wrap: {end}")
        blocked()
        print("  finite wrap OK; infinite wait blocked", flush=True)
        # Two extra STOPPED subscriptions exercise the bounded eight-slot
        # scan without claiming to allocate/run extra CPU contexts. One is
        # infinite; one is already at its finite deadline when input arrives.
        writes = [(slots + 8, bytes((1, 5, 2, 1, 0, 0, 4, 0))),
                  (slots + 16, bytes((1, 5, 2, 1, 0, 0, 4, 0))),
                  (tick, b"\x00\x00")]
        for index in (1, 2):
            pending = {"state": 1, "operation": 16, "sequence": 0x40 + index,
                       "descriptor": 0, "count": 4, "flags": 0,
                       "selector": 0, "selector_high": 0,
                       "child": 0xFF if index == 1 else 1,
                       "status": 0xFF if index == 1 else 0}
            writes.extend((waits[name] + index, bytes((value,)))
                          for name, value in pending.items())
        # Commit the submission in the same paused session as the deadline.
        start = editor[sp.LINE_EDITOR_TEXT_SYMBOL]
        length = editor[sp.LINE_EDITOR_LENGTH_SYMBOL]
        text = bytearray(length - start + 3)
        text[:5] = b"hello"
        text[length - start:length - start + 2] = b"\x05\x01"
        writes.append((start, bytes(text)))
        paused_writes(port, writes)
        sp.wait_for_byte(port, PHASE, 3, deadline)
        blocked()
        extra_slots = capture("extra-slots", slots + 8, 16)
        states = capture("extra-waits", waits["state"] + 1, 2)
        ready = capture("extra-ready", waits["flags"] + 1, 2)
        if (states != b"\x02\x02" or ready != b"\x01\x01" or
                any(extra_slots[offset + 1] != 5 or extra_slots[offset + 2] != 0
                    or extra_slots[offset + 6] != 2 for offset in (0, 8))):
            raise RuntimeError("multiple waiters or ready/expired precedence failed")
        cleanup = [(slots + 8, bytes(16))]
        cleanup.extend((address + 1, bytes(2)) for address in waits.values())
        paused_writes(port, cleanup)
        print("  partial reads OK; testing stopped wake", flush=True)
        # STOP has no public syscall yet; inject the equivalent lifecycle
        # state, without changing the compiled task's saved CPU/C context.
        paused_writes(port, [(slots + 1, b"\x05"), (slots + 6, b"\x04")])
        inject("")
        sp.wait_for_byte(port, waits["state"], 2, deadline)
        time.sleep(0.25)  # repeated wake scans must leave it stopped
        stopped = capture("stopped", slots, 8)
        if stopped[1] != 5 or stopped[2] != 0 or stopped[6] != 2:
            raise RuntimeError(f"ready STOPPED task changed unexpectedly: {stopped.hex()}")
        # Simulate another user of the released record; resume must restore
        # the original sequence, payload and flags from private ownership.
        paused_writes(port, [(0xF361, b"\xaa"), (0xF366, b"\xff"),
                            (slots + 1, b"\x02"), (slots + 6, b"\x00")])
        sp.wait_for_byte(port, PHASE, 0xA5, deadline)
        record = capture("complete", 0xF040, 8)
        validate_completion(record)
        if any(capture("cleared-waits", waits["state"], 8)):
            raise RuntimeError("completed input waits retain a subscription")
        print(f"{disk.name}: validation, finite wrap, infinite wake, chunked/empty "
              "reads, multiple waiters, ready/expired precedence, stopped wake, "
              "sequence restoration and live C locals OK", flush=True)
    except (RuntimeError, TimeoutError, ValueError):
        print(f"POLL diagnostic: {capture('failure', 0xF040, 8).hex()}", flush=True)
        print("Lifecycle: " + capture("failure-lifecycle", slots, 71).hex(), flush=True)
        print("RODATA: " + capture("failure-rodata", slots - 31, 31).hex(), flush=True)
        print("Kernel ZP: " + capture("failure-zp", 0, 32).hex(), flush=True)
        print(monitor_command(port, "r").decode("ascii", errors="replace"), flush=True)
        raise
    finally:
        sp.terminate(process, port)
        os.close(master)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--disk", type=Path,
                        default=ROOT / "build/boot/udeks-task-poll-probe.d71")
    parser.add_argument("--timeout", type=float, default=60)
    parser.add_argument("--flatpak-id", default="net.sf.VICE")
    args = parser.parse_args()
    run(args.disk, args.timeout, args.flatpak_id)


if __name__ == "__main__":
    main()
