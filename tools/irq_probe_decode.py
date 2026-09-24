#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Decode and validate an UDEKS interrupt-qualification result block."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from statistics import median

from bench_decode import extract_memory


RESULT_BASE = 0xF180
RESULT_SIZE = 128
CPU_NAMES = {1: "8502", 2: "z80"}
MODE_NAMES = {1: "8502-native-vector", 2: "z80-im1"}


def parse_result(data: bytes) -> dict[str, object]:
    if len(data) < RESULT_SIZE:
        raise ValueError(f"result block is {len(data)} bytes; expected {RESULT_SIZE}")
    block = data[:RESULT_SIZE]
    if block[:4] != b"IRQP":
        raise ValueError("interrupt-probe magic is not IRQP")
    if block[4] != 1:
        raise ValueError(f"unsupported interrupt-probe format {block[4]}")
    if block[5] not in CPU_NAMES:
        raise ValueError(f"unknown CPU identifier {block[5]}")
    if block[6] not in MODE_NAMES:
        raise ValueError(f"unknown interrupt mode {block[6]}")
    if block[7] != 2:
        raise ValueError(f"probe state is {block[7]}, not complete")

    target = int.from_bytes(block[8:10], "little")
    count = int.from_bytes(block[10:12], "little")
    bad_sources = int.from_bytes(block[12:14], "little")
    first_icr = block[14]
    last_icr = block[15]
    timer_period = int.from_bytes(block[16:18], "little")
    sample_count = int.from_bytes(block[18:20], "little")
    if count != target:
        raise ValueError(f"interrupt count is {count}; expected {target}")
    if bad_sources:
        raise ValueError(f"unexpected interrupt-source count is {bad_sources}")
    if first_icr != 0x81 or last_icr != 0x81:
        raise ValueError(
            f"CIA1 ICR boundary values are {first_icr:#04x}/{last_icr:#04x}; "
            "expected 0x81/0x81"
        )
    if not timer_period:
        raise ValueError("timer period is zero")
    if sample_count != target:
        raise ValueError(f"latency sample count is {sample_count}; expected {target}")
    sample_end = 32 + (sample_count * 2)
    if sample_end > len(block):
        raise ValueError("latency samples exceed the result block")
    samples = [
        int.from_bytes(block[offset : offset + 2], "little")
        for offset in range(32, sample_end, 2)
    ]
    if any(sample > timer_period for sample in samples):
        raise ValueError(f"latency sample exceeds timer period {timer_period}")

    return {
        "format": block[4],
        "cpu": CPU_NAMES[block[5]],
        "mode": MODE_NAMES[block[6]],
        "target_interrupts": target,
        "interrupts_observed": count,
        "unexpected_sources": bad_sources,
        "first_icr": first_icr,
        "last_icr": last_icr,
        "timer_period_ticks": timer_period,
        "latency_samples_ticks": samples,
        "latency_min_ticks": min(samples),
        "latency_median_ticks": median(samples),
        "latency_max_ticks": max(samples),
    }


def parse_number(value: str) -> int:
    return int(value, 0)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path, help="result block, memory dump, or VSF")
    parser.add_argument("--offset", type=parse_number)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    try:
        block = extract_memory(
            args.input.read_bytes(), RESULT_BASE, RESULT_SIZE, args.offset
        )
        result = parse_result(block)
    except ValueError as error:
        raise SystemExit(f"invalid interrupt-probe result: {error}") from error

    if args.json:
        print(json.dumps(result, indent=2))
    else:
        print(f"CPU: {result['cpu']}")
        print(f"Mode: {result['mode']}")
        print(
            f"Interrupts: {result['interrupts_observed']}/"
            f"{result['target_interrupts']}"
        )
        print(f"Unexpected sources: {result['unexpected_sources']}")
        print(
            f"CIA1 ICR first/last: 0x{result['first_icr']:02x}/"
            f"0x{result['last_icr']:02x}"
        )
        print(f"Timer period: {result['timer_period_ticks']} system ticks")
        print(
            "Latency min/median/max: "
            f"{result['latency_min_ticks']}/"
            f"{result['latency_median_ticks']}/"
            f"{result['latency_max_ticks']} system ticks"
        )
        print(
            "Latency samples: "
            + ", ".join(str(sample) for sample in result["latency_samples_ticks"])
        )


if __name__ == "__main__":
    main()
