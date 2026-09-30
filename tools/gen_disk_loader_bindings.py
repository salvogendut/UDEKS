#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Bind the compatibility loader's ownership check to this scheduler link."""
import sys
from pathlib import Path
from gen_task_yield_imports import map_exports


def render(text):
    address, kind = map_exports(text)['_udeks_lifecycle_slots_private']
    if kind != 'RLA' or not 0xC000 <= address < 0xC870:
        raise ValueError('unexpected lifecycle slot placement/type')
    # task_state.h: eight-byte records, task 2 is index 1, state offset 1.
    return f'; Generated; private binding, not a published ABI.\nDISK_LOADER_CHILD_STATE = ${address+9:04x}\n'


if __name__ == '__main__':
    Path(sys.argv[2]).write_text(render(Path(sys.argv[1]).read_text()))
