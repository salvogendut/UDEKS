#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Decode and strictly validate the context-switch spike result block."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from bench_decode import extract_memory, parse_number


RESULT_BASE = 0xF180
RESULT_SIZE = 32
STRATEGY_RELOCATE = 2
FLAG_COPY = 0x01
FLAG_RELOCATE = 0x02
STRATEGY_NAMES = {1: "copy", 2: "relocate"}


def parse_result(data: bytes) -> dict[str, int]:
    if len(data) < RESULT_SIZE:
        raise ValueError(f"result block is {len(data)} bytes; expected {RESULT_SIZE}")
    block = data[:RESULT_SIZE]
    if block[:4] != b"CXSW":
        raise ValueError("context-switch magic is not CXSW")
    if block[4] != 1:
        raise ValueError(f"unsupported context-switch format {block[4]}")
    if block[5] != 1:
        raise ValueError(f"unknown CPU identifier {block[5]}")
    state = block[6]
    if state != 2:
        if state & 0x80:
            raise ValueError(
                f"context-switch spike failed with code {block[6] & 0x7F} "
                f"(failure {block[7]}, switches "
                f"{block[9] | (block[10] << 8)})"
            )
        raise ValueError(f"context-switch state is {state}, not complete")
    if block[7] != 0:
        raise ValueError(f"complete spike reports failure code {block[7]}")
    rounds = block[8]
    if rounds == 0:
        raise ValueError("round count is zero")
    switches = block[9] | (block[10] << 8)
    if switches != rounds * 2:
        raise ValueError(
            f"switch count {switches} does not match {rounds} rounds"
        )
    interrupts = block[11]
    boundary = block[22] | (block[24] << 8)
    body = block[23] | (block[25] << 8)
    if boundary == 0:
        raise ValueError("no interrupt arrived in a switch-boundary window")
    if body == 0:
        raise ValueError("no interrupt arrived during task execution")
    if interrupts != (boundary + body) & 0xFF:
        raise ValueError(
            f"recorded interrupt total {interrupts} does not match "
            f"boundary {boundary} plus body {body} modulo 256"
        )
    if block[12] != switches:
        raise ValueError(
            f"only {block[12]} of {switches} switches recorded a successful check"
        )
    if block[13] != 0:
        raise ValueError(f"switch check failures: {block[13]}")
    if block[14] != 0:
        raise ValueError(f"canary failures: {block[14]}")
    flags = block[15]
    if flags & ~(FLAG_COPY | FLAG_RELOCATE):
        raise ValueError(f"unknown strategy flag bits: {flags:#04x}")
    strategy = block[16]
    if strategy != STRATEGY_RELOCATE:
        raise ValueError(f"strategy {strategy} is not relocation")
    if flags != FLAG_RELOCATE:
        raise ValueError(
            f"relocation strategy flags are {flags:#04x}; expected "
            f"{FLAG_RELOCATE:#04x}"
        )
    if block[18] != rounds or block[19] != rounds:
        raise ValueError(
            f"step counts {block[18]}/{block[19]} do not match {rounds} rounds"
        )
    xfers = block[20] | (block[21] << 8)
    if xfers != 0:
        raise ValueError(f"relocation moved {xfers} page bytes per switch")
    if any(block[26:32]):
        raise ValueError("unused result bytes 26-31 are nonzero")
    return {
        "format": block[4],
        "cpu": block[5],
        "state": state,
        "failure": block[7],
        "rounds": rounds,
        "switches": switches,
        "interrupts": boundary + body,
        "boundary_interrupts": boundary,
        "body_interrupts": body,
        "checks_ok": block[12],
        "checks_failed": block[13],
        "canary_failed": block[14],
        "flags": flags,
        "strategy": strategy,
        "last_current": block[17],
        "step_a": block[18],
        "step_b": block[19],
        "page_bytes_per_switch": xfers,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path, help="result record, memory dump, or VSF")
    parser.add_argument("--offset", type=parse_number)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    try:
        block = extract_memory(
            args.input.read_bytes(), RESULT_BASE, RESULT_SIZE, args.offset
        )
        result = parse_result(block)
    except ValueError as error:
        raise SystemExit(f"invalid context-switch record: {error}") from error

    if args.json:
        print(json.dumps(result, indent=2))
        return
    print(
        "Context switch: "
        f"{STRATEGY_NAMES.get(result['strategy'], 'unknown')} complete "
        f"({result['switches']} switches, {result['interrupts']} interrupts: "
        f"{result['boundary_interrupts']} boundary, "
        f"{result['body_interrupts']} body)"
    )
    print(
        f"Checks: {result['checks_ok']} passed, "
        f"{result['checks_failed']} failed, "
        f"{result['canary_failed']} canary failures, "
        f"{result['page_bytes_per_switch']} page bytes per switch"
    )


if __name__ == "__main__":
    main()
