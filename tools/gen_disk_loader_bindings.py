#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Bind the compatibility loader's ownership check to this scheduler link."""
import argparse
from pathlib import Path
from gen_task_yield_imports import map_exports
from service_image import TIME_BASE


def render(text, kernel_text=None):
    address, kind = map_exports(text)['_udeks_lifecycle_slots_private']
    if kind != 'RLA' or not 0xC000 <= address < 0xC870:
        raise ValueError('unexpected lifecycle slot placement/type')
    # task_state.h: eight-byte records, task 2 is index 1, state offset 1.
    current, current_kind = map_exports(text)['_udeks_lifecycle_current_private']
    if current_kind != 'RLA' or not 0xC000 <= current < 0xC880:
        raise ValueError('unexpected current-task placement/type')
    finish, finish_kind = map_exports(text)['_udeks_bootfs_finish_error']
    if finish_kind not in ('REA', 'RLA') or not 0xF3EF <= finish < 0xF68A:
        raise ValueError('unexpected bootfs error return placement/type')
    result = (f'; Generated; private binding, not a published ABI.\nDISK_LOADER_CHILD_STATE = ${address+9:04x}\n'
            f'STORAGE_CURRENT_TASK = ${current:04x}\nSTORAGE_FINISH_ERROR = ${finish:04x}\n')
    if kernel_text is not None:
        entry, kind = map_exports(kernel_text)['_udeks_time_slot_request']
        if kind != 'RLA' or not 0x2006 <= entry < TIME_BASE:
            raise ValueError('unexpected module request placement/type')
        result += f'TIME_MODULE_REQUEST = ${entry:04x}\n'
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('scheduler_map', type=Path)
    parser.add_argument('output', type=Path)
    parser.add_argument('--kernel-map', type=Path)
    args = parser.parse_args()
    args.output.write_text(render(args.scheduler_map.read_text(),
        args.kernel_map.read_text() if args.kernel_map else None))
