#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Private banked task mechanism bindings; never a user-supplied address."""
import sys
from pathlib import Path
from gen_capability_imports import map_exports

WAIT_FIELDS = ('state', 'operation', 'sequence', 'descriptor', 'count', 'flags',
               'selector', 'selector_high', 'child', 'status')


def render(gateway, scheduler, context):
    g, s, c = (map_exports(text) for text in (gateway, scheduler, context))
    def address(table, name, low, limit, size=1):
        value, kind = table[name]
        if kind != 'RLA' or not low <= value < value+size <= limit:
            raise ValueError('invalid banked binding: '+name)
        return value
    access = address(g, 'banked_access', 0xFE80, 0xFF00, 3)
    slots = address(s, '_udeks_lifecycle_slots_private', 0xC120, 0xC880, 64)
    current = address(s, '_udeks_lifecycle_current_private', 0xC120, 0xC880)
    event = address(s, '_udeks_lifecycle_last_event_private', 0xC120, 0xC880)
    contexts = address(c, '_udeks_task_contexts_private', 0xCDBD, 0xCF00, 88)
    waits = [address(s, '_udeks_task_wait_'+field+'_private', 0xC120, 0xC880, 8)
             for field in WAIT_FIELDS]
    if waits != list(range(waits[0], waits[0]+80, 8)):
        raise ValueError('wait snapshot arrays are not ten contiguous eight-byte arrays')
    values = dict(BANK0_ACCESS=access, BANK0_SLOTS=slots, BANK0_CURRENT=current, BANK0_EVENT=event,
                  BANK0_CONTEXTS=contexts, BANK0_WAITS=waits[0])
    return '; Generated private bindings.\n'+''.join(f'{n} = ${v:04x}\n' for n,v in values.items())


if __name__ == '__main__':
    Path(sys.argv[4]).write_text(render(*(Path(p).read_text() for p in sys.argv[1:4])))
