#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Decode and validate an UDEKS task-context benchmark result block."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from statistics import median

from bench_decode import extract_memory


RESULT_BASE = 0xF180
RESULT_SIZE = 128
HEADER_SIZE = 32
SAMPLES_PER_VARIANT = 8
VARIANT_NAMES = ("empty", "cpu_core", "compiler", "full")
CPU_NAMES = {1: "8502", 2: "z80"}
EXPECTED_CONTEXT_BYTES = {1: (7, 33, 33), 2: (16, 16, 24)}


def _distribution(samples: list[int | float]) -> dict[str, object]:
    return {
        "samples": samples,
        "minimum": min(samples),
        "median": median(samples),
        "maximum": max(samples),
    }


def parse_result(data: bytes) -> dict[str, object]:
    if len(data) < RESULT_SIZE:
        raise ValueError(f"result block is {len(data)} bytes; expected {RESULT_SIZE}")
    block = data[:RESULT_SIZE]
    if block[:4] != b"CTXB":
        raise ValueError("context-benchmark magic is not CTXB")
    if block[4] != 1:
        raise ValueError(f"unsupported context-benchmark format {block[4]}")
    cpu_id = block[5]
    if cpu_id not in CPU_NAMES:
        raise ValueError(f"unknown CPU identifier {cpu_id}")
    if block[6] != 2:
        raise ValueError(f"benchmark state is {block[6]}, not complete")
    if block[7] != len(VARIANT_NAMES):
        raise ValueError(f"variant count is {block[7]}, expected {len(VARIANT_NAMES)}")
    if block[8] != SAMPLES_PER_VARIANT:
        raise ValueError(
            f"samples per variant is {block[8]}, expected {SAMPLES_PER_VARIANT}"
        )
    iterations = int.from_bytes(block[10:12], "little")
    if not iterations:
        raise ValueError("iteration count is zero")
    context_bytes = tuple(block[12:15])
    if context_bytes != EXPECTED_CONTEXT_BYTES[cpu_id]:
        raise ValueError(
            f"context sizes are {context_bytes}; expected "
            f"{EXPECTED_CONTEXT_BYTES[cpu_id]}"
        )
    if block[15]:
        raise ValueError(f"qualification failure count is {block[15]}")

    raw_variants: list[list[int]] = []
    for variant_index, name in enumerate(VARIANT_NAMES):
        start = HEADER_SIZE + variant_index * SAMPLES_PER_VARIANT * 2
        samples = [
            int.from_bytes(block[offset : offset + 2], "little")
            for offset in range(start, start + SAMPLES_PER_VARIANT * 2, 2)
        ]
        if 0xFFFF in samples:
            raise ValueError(f"{name} overflowed the timer")
        raw_variants.append(samples)

    empty = raw_variants[0]
    variants = [
        {
            "name": "empty",
            "context_bytes": 0,
            "raw_total_ticks": _distribution(empty),
        }
    ]
    for variant_index, name in enumerate(VARIANT_NAMES[1:], start=1):
        raw = raw_variants[variant_index]
        adjusted = []
        for sample_index, (value, overhead) in enumerate(zip(raw, empty)):
            if value < overhead:
                raise ValueError(
                    f"{name} sample {sample_index} is below empty overhead"
                )
            adjusted.append(value - overhead)
        per_operation = [value / iterations for value in adjusted]
        variants.append(
            {
                "name": name,
                "context_bytes": context_bytes[variant_index - 1],
                "raw_total_ticks": _distribution(raw),
                "adjusted_total_ticks": _distribution(adjusted),
                "ticks_per_save_restore": _distribution(per_operation),
            }
        )

    return {
        "format": block[4],
        "cpu": CPU_NAMES[cpu_id],
        "iterations_per_sample": iterations,
        "samples_per_variant": block[8],
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
        raise SystemExit(f"invalid context-benchmark result: {error}") from error

    if args.json:
        print(json.dumps(result, indent=2))
        return

    print(f"CPU: {result['cpu']}")
    print(
        f"Samples: {result['samples_per_variant']} x "
        f"{result['iterations_per_sample']} save/restore operations"
    )
    print("variant       bytes  raw median  adjusted median  ticks/operation")
    for variant in result["variants"]:
        if variant["name"] == "empty":
            print(
                f"{variant['name']:<13} {0:>5} "
                f"{variant['raw_total_ticks']['median']:>11} {'-':>16} {'-':>16}"
            )
            continue
        print(
            f"{variant['name']:<13} {variant['context_bytes']:>5} "
            f"{variant['raw_total_ticks']['median']:>11} "
            f"{variant['adjusted_total_ticks']['median']:>16} "
            f"{variant['ticks_per_save_restore']['median']:>16.3f}"
        )


if __name__ == "__main__":
    main()
