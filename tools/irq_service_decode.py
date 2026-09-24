#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Decode and validate an UDEKS interrupt-service benchmark result block."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from statistics import median

from bench_decode import extract_memory


RESULT_BASE = 0xF180
RESULT_SIZE = 320
HEADER_SIZE = 32
SAMPLE_ARRAY_BYTES = 96
CPU_NAMES = {1: "8502", 2: "z80"}
MODE_NAMES = {1: "8502-native-vector", 2: "z80-im1"}
VARIANT_NAMES = ("minimal", "kernel_tick", "jump_table_dispatch")


def _words(block: bytes, start: int, count: int) -> list[int]:
    return [
        int.from_bytes(block[offset : offset + 2], "little")
        for offset in range(start, start + count * 2, 2)
    ]


def _distribution(samples: list[int]) -> dict[str, object]:
    return {
        "samples_ticks": samples,
        "minimum_ticks": min(samples),
        "median_ticks": median(samples),
        "maximum_ticks": max(samples),
    }


def parse_result(data: bytes) -> dict[str, object]:
    if len(data) < RESULT_SIZE:
        raise ValueError(f"result block is {len(data)} bytes; expected {RESULT_SIZE}")
    block = data[:RESULT_SIZE]
    if block[:4] != b"IRQS":
        raise ValueError("interrupt-service magic is not IRQS")
    if block[4] != 1:
        raise ValueError(f"unsupported interrupt-service format {block[4]}")
    if block[5] not in CPU_NAMES:
        raise ValueError(f"unknown CPU identifier {block[5]}")
    if block[6] not in MODE_NAMES:
        raise ValueError(f"unknown interrupt mode {block[6]}")
    if block[7] != 2:
        raise ValueError(f"benchmark state is {block[7]}, not complete")

    variant_count = block[8]
    samples_per_variant = block[9]
    target = int.from_bytes(block[10:12], "little")
    observed = int.from_bytes(block[12:14], "little")
    bad_sources = int.from_bytes(block[14:16], "little")
    first_icr = block[16]
    last_icr = block[17]
    timer_period = int.from_bytes(block[18:20], "little")
    if variant_count != len(VARIANT_NAMES):
        raise ValueError(
            f"variant count is {variant_count}; expected {len(VARIANT_NAMES)}"
        )
    if samples_per_variant != 16:
        raise ValueError(f"samples per variant is {samples_per_variant}; expected 16")
    if target != variant_count * samples_per_variant:
        raise ValueError(f"target count {target} does not match the result shape")
    if observed != target:
        raise ValueError(f"interrupt count is {observed}; expected {target}")
    if bad_sources:
        raise ValueError(f"unexpected interrupt-source count is {bad_sources}")
    if first_icr != 0x81 or last_icr != 0x81:
        raise ValueError(
            f"CIA1 ICR boundary values are {first_icr:#04x}/{last_icr:#04x}; "
            "expected 0x81/0x81"
        )
    if not timer_period:
        raise ValueError("timer period is zero")
    if int.from_bytes(block[24:28], "little") != samples_per_variant:
        raise ValueError("kernel-tick counter does not match its sample count")
    if block[28] != 1:
        raise ValueError("kernel-tick event signal was not set")
    if block[29] != samples_per_variant:
        raise ValueError("dispatch target count does not match its sample count")

    total_samples = variant_count * samples_per_variant
    entries = _words(block, HEADER_SIZE, total_samples)
    preexits = _words(block, HEADER_SIZE + SAMPLE_ARRAY_BYTES, total_samples)
    resumes = _words(block, HEADER_SIZE + SAMPLE_ARRAY_BYTES * 2, total_samples)
    variants = []
    for variant_index, name in enumerate(VARIANT_NAMES):
        start = variant_index * samples_per_variant
        end = start + samples_per_variant
        entry = entries[start:end]
        preexit = preexits[start:end]
        resume = resumes[start:end]
        for sample_index, values in enumerate(zip(entry, preexit, resume)):
            entry_tick, preexit_tick, resume_tick = values
            if not (entry_tick <= preexit_tick <= resume_tick <= timer_period):
                raise ValueError(
                    f"{name} sample {sample_index} is not monotonic: "
                    f"{entry_tick}/{preexit_tick}/{resume_tick}"
                )
        handler = [end_tick - start_tick for start_tick, end_tick in zip(entry, preexit)]
        return_tail = [end_tick - start_tick for start_tick, end_tick in zip(preexit, resume)]
        service = [end_tick - start_tick for start_tick, end_tick in zip(entry, resume)]
        variants.append(
            {
                "name": name,
                "entry_latency": _distribution(entry),
                "instrumented_handler": _distribution(handler),
                "entry_to_resume": _distribution(service),
                "underflow_to_resume": _distribution(resume),
                "preexit_to_resume": _distribution(return_tail),
            }
        )

    return {
        "format": block[4],
        "cpu": CPU_NAMES[block[5]],
        "mode": MODE_NAMES[block[6]],
        "timer_period_ticks": timer_period,
        "interrupts_observed": observed,
        "unexpected_sources": bad_sources,
        "first_icr": first_icr,
        "last_icr": last_icr,
        "variants": variants,
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
        raise SystemExit(f"invalid interrupt-service result: {error}") from error

    if args.json:
        print(json.dumps(result, indent=2))
        return

    print(f"CPU: {result['cpu']}")
    print(f"Mode: {result['mode']}")
    print(f"Interrupts: {result['interrupts_observed']}")
    print(
        "variant                 entry min/med/max  handler min/med/max  "
        "service min/med/max  total min/med/max"
    )
    for variant in result["variants"]:
        entry = variant["entry_latency"]
        handler = variant["instrumented_handler"]
        service = variant["entry_to_resume"]
        resume = variant["underflow_to_resume"]
        print(
            f"{variant['name']:<23} "
            f"{entry['minimum_ticks']:>3}/{entry['median_ticks']:>5}/{entry['maximum_ticks']:<3}  "
            f"{handler['minimum_ticks']:>3}/{handler['median_ticks']:>5}/{handler['maximum_ticks']:<3}  "
            f"{service['minimum_ticks']:>3}/{service['median_ticks']:>5}/{service['maximum_ticks']:<3}  "
            f"{resume['minimum_ticks']:>3}/{resume['median_ticks']:>5}/{resume['maximum_ticks']:<3}"
        )


if __name__ == "__main__":
    main()
