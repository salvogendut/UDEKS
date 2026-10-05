#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Private four-client allocation contract (all addresses in physical bank 1).

The final page of each allocation holds a 160-byte C stack between guards,
plus its private exit trampoline. File staging may use that page before
activation; image+BSS and request source ranges may not.
"""
ALLOCATIONS = (
    # task, base, limit, software stack, zero page, hardware stack
    (3, 0x2300, 0x3500, 0x3400, 0xD500, 0xD600),
    (4, 0x3500, 0x4000, 0x3F00, 0xD700, 0xD800),
    (5, 0x8000, 0x9000, 0x8F00, 0xD000, 0xE200),
    (6, 0xC600, 0xD000, 0xCF00, 0x0000, 0x0100),
)
ADMISSION_ORDER = (6, 4, 5, 3)  # smallest fitting allocation, not app names
RETAINED_BASE, RETAINED_LIMIT = 0x1300, 0x1C00  # physical bank 0


def check_assembly_layout(text):
    """Fail closed if the loader/initializer's shared tables drift."""
    import re
    if not re.search(r'^NATIVE_CLIENTS\s*=\s*4\s*$',text,re.M):
        raise ValueError('native client count changed')
    columns=('bases','limits','stacks','zero_pages','hardware_pages')
    for column,name in enumerate(columns,1):
        match=re.search(r'\.macro native_'+name+r'\s+\.byte ([^\n]+)\s+\.endmacro',text)
        if not match: raise ValueError('missing native table: '+name)
        values=tuple(int(value.strip().replace('$','0x'),0)*256 for value in match[1].split(','))
        if values!=tuple(row[column] for row in ALLOCATIONS):
            raise ValueError('native table differs: '+name)


def check_linked_tables(module,exports):
    for symbol,column in (('_udeks_native_base_pages',1),('_udeks_native_stack_pages',3)):
        address,kind=exports[symbol]
        if kind!='RLA' or not 0xe300<=address<=0xe640:
            raise ValueError('native runtime table outside module')
        if module[address-0xe300:address-0xe300+4]!=bytes(row[column]>>8 for row in ALLOCATIONS):
            raise ValueError('linked native table differs: '+symbol)


def fitting_allocations(executable):
    from o65_to_udex import relocate_executable
    candidates = []
    for task,base,limit,stack,_,_ in ALLOCATIONS:
        try:
            installed=relocate_executable(executable,base,limit-base)
        except ValueError:
            continue
        size=sum(int.from_bytes(installed[n:n+2],'little') for n in (10,12))
        if size<=stack-base:
            candidates.append(task)
    return candidates
