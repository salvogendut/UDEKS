#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Wrap the linked scheduler page and tail in one boot-load envelope."""

from __future__ import annotations

import argparse
import re
from pathlib import Path

LOAD_ADDRESS = 0x5000
PAGE_ADDRESS = 0x1C00
TAIL_ADDRESS = 0xC120
TAIL_LIMIT = 0xCE00
HANDLER_ADDRESS = 0xC900
CONTEXT_ADDRESS = 0xCDBD
MAGIC = b"USOV"
ABI_MAJOR = 0
ABI_MINOR = 3
HEADER_SIZE = 20

SEGMENT = re.compile(
    r"^([A-Z][A-Z0-9]*)\s+([0-9A-Fa-f]{6})\s+"
    r"([0-9A-Fa-f]{6})\s+([0-9A-Fa-f]{6})\s+",
    re.MULTILINE,
)


def map_segments(text: str) -> dict[str, tuple[int, int, int]]:
    return {
        name: (int(start, 16), int(end, 16), int(size, 16))
        for name, start, end, size in SEGMENT.findall(text)
    }


def build_overlay(
    page: bytes,
    tail: bytes,
    map_text: str,
    context: bytes = b"",
    context_map_text: str = "",
    switch_tail: bytes = b"",
    yield_handler: bytes = b"",
    vectors: bytes = b"",
) -> tuple[bytes, str]:
    segments = map_segments(map_text)
    if "SCHEDULER" not in segments or "CODE" not in segments or "BSS" not in segments:
        raise ValueError("scheduler overlay map lacks SCHEDULER, CODE, or BSS")
    page_start, _page_end, page_size = segments["SCHEDULER"]
    code_start = segments["CODE"][0]
    bss_start, bss_end, bss_size = segments["BSS"]
    if page_start != PAGE_ADDRESS:
        raise ValueError(f"scheduler page starts at ${page_start:04X}, expected $1C00")
    if code_start != TAIL_ADDRESS:
        raise ValueError(f"scheduler tail starts at ${code_start:04X}, expected $C120")
    if len(page) < page_size:
        raise ValueError(
            f"scheduler page image is {len(page)} bytes; map requires at least {page_size}"
        )
    if len(page) > 0x0400:
        raise ValueError("scheduler page exceeds $1C00-$1FFF")
    if any(page[page_size:]):
        raise ValueError("scheduler page padding is not zero")
    if len(tail) != bss_start - code_start:
        raise ValueError(
            f"scheduler tail image is {len(tail)} bytes; map requires "
            f"{bss_start - code_start}"
        )
    if bss_size == 0 or bss_size > 0xFF or bss_end + 1 > TAIL_LIMIT:
        raise ValueError("scheduler BSS is empty, exceeds 255 bytes, or reaches $CE00")
    if vectors:
        if len(vectors) != 6:
            raise ValueError("task-context vector image is not six bytes")
        if len(page) != 0x0400 or any(page[-len(vectors):]):
            raise ValueError("scheduler page does not retain six zero vector bytes")
        page = page[:-len(vectors)] + vectors
    installed_tail = tail
    if yield_handler:
        handler_offset = HANDLER_ADDRESS - code_start
        if len(installed_tail) > handler_offset:
            raise ValueError("scheduler core reaches the lifecycle handler")
        if HANDLER_ADDRESS + len(yield_handler) > CONTEXT_ADDRESS:
            raise ValueError("lifecycle handler reaches the context binding")
        installed_tail += bytes(handler_offset - len(installed_tail))
        installed_tail += yield_handler
    checksum = (sum(page) + sum(installed_tail)) & 0xFFFF
    header = bytearray(MAGIC)
    header += bytes((ABI_MAJOR, ABI_MINOR))
    header += page_start.to_bytes(2, "little")
    header += len(page).to_bytes(2, "little")
    header += code_start.to_bytes(2, "little")
    header += len(installed_tail).to_bytes(2, "little")
    header += bss_start.to_bytes(2, "little")
    header += bss_size.to_bytes(2, "little")
    header += checksum.to_bytes(2, "little")
    if len(header) != HEADER_SIZE:
        raise AssertionError("scheduler overlay header size drifted")
    extension = b""
    activation_constants = ""
    if context or context_map_text or switch_tail or yield_handler:
        if not context or not context_map_text or not switch_tail or not yield_handler:
            raise ValueError(
                "task activation requires context, map, switch tail, and lifecycle handler"
            )
        context_segments = map_segments(context_map_text)
        if "CODE" not in context_segments or "BSS" not in context_segments:
            raise ValueError("task-context map lacks CODE or BSS")
        context_start = context_segments["CODE"][0]
        context_bss, context_bss_end, context_bss_size = context_segments["BSS"]
        if context_start != CONTEXT_ADDRESS or context_bss_end != 0xCEFF:
            raise ValueError("task-context placement is not $CDBD-$CEFF")
        if len(context) != context_bss - context_start:
            raise ValueError("task-context emitted image does not reach its BSS")
        if len(context) > 0xFF or context_bss_size > 0x80:
            raise ValueError("task-context activation exceeds the bounded copier")
        if len(switch_tail) != 0xC0:
            raise ValueError("task-switch tail is not the 192-byte gate image")
        if len(yield_handler) == 0:
            raise ValueError("lifecycle handler is empty")
        context_source = LOAD_ADDRESS + HEADER_SIZE + len(page) + len(installed_tail)
        switch_source = context_source + len(context)
        extension = context + switch_tail
        activation_constants = (
            f"TASK_ACTIVATION_CONTEXT_SOURCE = ${context_source:04x}\n"
            f"TASK_ACTIVATION_CONTEXT_DESTINATION = ${context_start:04x}\n"
            f"TASK_ACTIVATION_CONTEXT_IMAGE_SIZE = ${len(context):02x}\n"
            f"TASK_ACTIVATION_CONTEXT_BSS = ${context_bss:04x}\n"
            f"TASK_ACTIVATION_CONTEXT_BSS_SIZE = ${context_bss_size:02x}\n"
            f"TASK_ACTIVATION_TAIL_SOURCE = ${switch_source:04x}\n"
            "TASK_ACTIVATION_TAIL_DESTINATION = $ff05\n"
            f"TASK_ACTIVATION_TAIL_SIZE = ${len(switch_tail):02x}\n"
            f"TASK_ACTIVATION_EXTENSION_CHECKSUM = ${sum(extension) & 0xffff:04x}\n"
        )
    payload = (
        LOAD_ADDRESS.to_bytes(2, "little") + header + page + installed_tail + extension
    )
    page_source = LOAD_ADDRESS + HEADER_SIZE
    tail_source = page_source + len(page)
    constants = (
        "; generated by tools/build_scheduler_overlay.py\n"
        f"SCHEDULER_OVERLAY_LOAD = ${LOAD_ADDRESS:04x}\n"
        f"SCHEDULER_OVERLAY_END = ${LOAD_ADDRESS + HEADER_SIZE + len(page) + len(installed_tail) + len(extension):04x}\n"
        f"SCHEDULER_OVERLAY_HEADER_SIZE = ${HEADER_SIZE:02x}\n"
        f"SCHEDULER_OVERLAY_ABI_MAJOR = ${ABI_MAJOR:02x}\n"
        f"SCHEDULER_OVERLAY_ABI_MINOR = ${ABI_MINOR:02x}\n"
        f"SCHEDULER_OVERLAY_PAGE_SOURCE = ${page_source:04x}\n"
        f"SCHEDULER_OVERLAY_PAGE_SIZE = ${len(page):04x}\n"
        f"SCHEDULER_OVERLAY_TAIL_SOURCE = ${tail_source:04x}\n"
        f"SCHEDULER_OVERLAY_TAIL_DESTINATION = ${code_start:04x}\n"
        f"SCHEDULER_OVERLAY_TAIL_SIZE = ${len(installed_tail):04x}\n"
        f"SCHEDULER_OVERLAY_BSS = ${bss_start:04x}\n"
        f"SCHEDULER_OVERLAY_BSS_SIZE = ${bss_size:02x}\n"
        f"SCHEDULER_OVERLAY_CHECKSUM = ${checksum:04x}\n"
        f"{activation_constants}"
    )
    return payload, constants


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("page", type=Path)
    parser.add_argument("tail", type=Path)
    parser.add_argument("map", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("constants", type=Path)
    parser.add_argument("--activation-context", type=Path)
    parser.add_argument("--activation-context-map", type=Path)
    parser.add_argument("--activation-tail", type=Path)
    parser.add_argument("--activation-yield-handler", type=Path)
    parser.add_argument("--activation-vectors", type=Path)
    args = parser.parse_args()
    try:
        payload, constants = build_overlay(
            args.page.read_bytes(), args.tail.read_bytes(),
            args.map.read_text(encoding="utf-8"),
            b"" if args.activation_context is None else args.activation_context.read_bytes(),
            "" if args.activation_context_map is None else args.activation_context_map.read_text(encoding="utf-8"),
            b"" if args.activation_tail is None else args.activation_tail.read_bytes(),
            b"" if args.activation_yield_handler is None else args.activation_yield_handler.read_bytes(),
            b"" if args.activation_vectors is None else args.activation_vectors.read_bytes(),
        )
    except ValueError as error:
        raise SystemExit(f"cannot build scheduler overlay: {error}") from error
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_bytes(payload)
    args.constants.parent.mkdir(parents=True, exist_ok=True)
    args.constants.write_text(constants, encoding="utf-8")


if __name__ == "__main__":
    main()
