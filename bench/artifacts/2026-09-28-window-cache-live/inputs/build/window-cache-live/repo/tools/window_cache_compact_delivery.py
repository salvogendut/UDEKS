#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Qualify cold-boot delivery of the compact controller, without invoking it."""
import argparse
import json
from pathlib import Path
import window_cache_controller_delivery as delivery

ROOT = delivery.ROOT
WORK = ROOT / 'build/window-cache-compact-delivery'
NAME = '2026-09-28-window-cache-compact-delivery'
PROOF = ROOT / 'bench/artifacts/2026-09-28-window-cache-compact'
MODULE = PROOF / 'build/bench/window-cache-compact/module.bin'
MODULE_MAP = MODULE.with_suffix('.map')
GATEWAY = PROOF / 'build/gateway.bin'


def qualified_module():
    report = json.loads((PROOF / 'build/build-report.json').read_text())
    module = MODULE.read_bytes()
    gateway = GATEWAY.read_bytes()
    if (report['module_bytes'], report['gateway_source'], report['gateway_bytes']) != (4106, 0x5146, 196):
        raise ValueError('compact module placement changed')
    if len(module) != 4106 or len(gateway) != 196 or module[0x5146-0x4200:] != gateway:
        raise ValueError('compact module does not include the exact qualified gateway')
    for path in (MODULE, MODULE_MAP):
        key = str(path.relative_to(PROOF))
        # The proof's original generated paths were rooted at the repository.
        if delivery.digest(path) != report['source_sha256'][key]:
            raise ValueError('compact module input drift '+key)
    if delivery.digest(GATEWAY) != report['linked_sha256']['gateway.bin']:
        raise ValueError('compact gateway drift')
    return module


def configure():
    delivery.WORK = WORK
    delivery.NAME = NAME
    delivery.PROOF = PROOF
    delivery.configure()


def build():
    qualified_module()
    configure()
    delivery.build(module_path=MODULE, extra_inputs=(Path(__file__), MODULE_MAP, GATEWAY,
        ROOT / 'tests/test_window_cache_compact_delivery.py'))
    path = WORK / 'build-report.json'
    report = json.loads(path.read_text())
    report.update(qualification='compact controller cold-boot delivery only; uninvoked; GUI moves disabled',
        gateway_source=0x5146, gateway_bytes=196,
        remaining_before_hooks=131, resident_transport_bytes=371)
    path.write_text(json.dumps(report, indent=2)+'\n')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=('build', 'vice', '1986', 'preserve'))
    action = parser.parse_args().action
    if action == 'build':
        build()
    else:
        configure()
        if action == 'vice':
            delivery.base.probe_vice(); delivery.bind_run('vice')
        elif action == '1986':
            delivery.base.probe_1986(); delivery.bind_run('1986')
        else:
            delivery.preserve()


if __name__ == '__main__':
    main()
