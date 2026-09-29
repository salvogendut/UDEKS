#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Measure private C window-manager savings against the frozen NMI checkpoint."""
import argparse
import hashlib
import json
import re
import shutil
import subprocess
from pathlib import Path
from graphics_span_bench import object_sizes
from gen_capability_imports import canonicalize
from graphics_raster_link_audit import link_command
from placement_audit import parse_map

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / 'bench/artifacts/2026-09-28-nmi-integration/src/services/window/window_manager.c'
WORK = ROOT / 'build/window-manager-budget'
NAME = '2026-09-28-window-manager-budget'
PRIVATE = ('increment_counter', 'window_by_handle', 'point_inside', 'damage_set',
    'damage_add', 'set_damage_intersection', 'draw_glyph', 'draw_title',
    'draw_chrome', 'paint_window_damage', 'compose_damage', 'raise_window',
    'top_window_at', 'close_hit', 'title_hit', 'resize_hit', 'begin_drag',
    'move_drag', 'resize_drag')
RESET = '''    for (index = 0; index < UDEKS_WINDOW_MAX; ++index) {
        windows[index].active = 0;
    }
    active_count = 0;
    focused_handle = UDEKS_WINDOW_NONE;
    dragging_handle = UDEKS_WINDOW_NONE;
    drag_mode = 0;
    previous_buttons = 0;
    publish_state();'''


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def variant(source, name):
    if name not in ('baseline', 'fastcall', 'reset', 'chrome', 'intersection', 'lean'):
        raise ValueError('unknown variant')
    if name == 'fastcall':
        for function in PRIVATE:
            pattern = r'(\bstatic\s+(?:unsigned char|void|struct udeks_window\s*\*)\s*)('+function+r'\s*\()'
            source, count = re.subn(pattern, r'\1__fastcall__ \2', source)
            if count != (2 if function == 'paint_window_damage' else 1):
                raise ValueError('private definition/prototype seam changed: '+function)
    if name in ('reset', 'lean'):
        head, body = source.split('unsigned char udeks_window_manager_start(void)\n{', 1)
        start, tail = body.split('\nvoid udeks_window_manager_reset(void)', 1)
        if start.count(RESET) != 1:
            raise ValueError('startup reset seam changed')
        source = head+'unsigned char udeks_window_manager_start(void)\n{'+start.replace(
            RESET, '    udeks_window_manager_reset();')+'\nvoid udeks_window_manager_reset(void)'+tail
    if name in ('chrome', 'lean'):
        head, rest = source.split('static void draw_chrome(const struct udeks_window *window)\n{', 1)
        body, tail = rest.split('\nstatic unsigned char paint_window_damage', 1)
        for field in ('x', 'y', 'width', 'height'):
            body = body.replace('window->'+field, field)
        before = '    int bottom;\n'
        if body.count(before) != 1:
            raise ValueError('chrome locals changed')
        body = body.replace(before, before+'''    int x = window->x;
    int y = window->y;
    int width = window->width;
    int height = window->height;
''')
        source = head+'static void draw_chrome(const struct udeks_window *window)\n{'+body+'\nstatic unsigned char paint_window_damage'+tail
    if name in ('intersection', 'lean'):
        before = '''    right = x + width < damage_right ? x + width : damage_right;
    bottom = (unsigned char)(y + height) < damage_bottom ?
        (unsigned char)(y + height) : damage_bottom;'''
        after = '''    right = x + width;
    if (right > damage_right) right = damage_right;
    bottom = (unsigned char)(y + height);
    if (bottom > damage_bottom) bottom = damage_bottom;'''
        if source.count(before) != 1:
            raise ValueError('intersection arithmetic seam changed')
        source = source.replace(before, after)
    return source


def build():
    WORK.mkdir(parents=True, exist_ok=True)
    baseline = BASE.read_text()
    results = {}
    for name in ('baseline', 'fastcall', 'reset', 'chrome', 'intersection', 'lean'):
        stem = WORK / name
        stem.with_suffix('.c').write_text(variant(baseline, name))
        subprocess.run(['cc65', '-t', 'none', '--cpu', '6502', '--standard', 'c99',
            '-Oirs', '-I', str(ROOT / 'include'), '-o', str(stem.with_suffix('.s')),
            str(stem.with_suffix('.c'))], check=True)
        subprocess.run(['ca65', '--cpu', '6502', '-l', str(stem.with_suffix('.lst')),
            '-o', str(stem.with_suffix('.o')), str(stem.with_suffix('.s'))], check=True)
        dump = subprocess.check_output(['od65', '--dump-imports', str(stem.with_suffix('.o'))], text=True)
        stem.with_suffix('.imports.txt').write_text(dump)
        records = re.findall(r'Address size:\s+0x([0-9A-Fa-f]+).*?Name:\s*"([^"]+)"', dump, re.S)
        imports = dict(canonicalize([(name, size.lower()) for size, name in records]))
        results[name] = {'segments': object_sizes(stem.with_suffix('.o')), 'imports': imports}
    if results['baseline']['segments']['CODE'] != 7900:
        raise ValueError('compiler does not reproduce qualified baseline')
    for name, result in results.items():
        if {n: s for n, s in result['segments'].items() if n != 'CODE'} != {
                n: s for n, s in results['baseline']['segments'].items() if n != 'CODE'}:
            raise ValueError('non-CODE allocation changed')
        result['code_saved'] = 7900-result['segments']['CODE']
        result['imports_added'] = sorted(set(result['imports'])-set(results['baseline']['imports']))
    flow = WORK / 'flow'
    flow.with_suffix('.c').write_text((ROOT / 'src/services/window/move_cache_flow.c').read_text())
    subprocess.run(['cc65','-t','none','--cpu','6502','--standard','c99','-Oirs','-I',str(ROOT / 'include'),
        '-o',str(flow.with_suffix('.s')),str(flow.with_suffix('.c'))],check=True)
    subprocess.run(['ca65','--cpu','6502','-l',str(flow.with_suffix('.lst')),
        '-o',str(flow.with_suffix('.o')),str(flow.with_suffix('.s'))],check=True)
    dump=subprocess.check_output(['od65','--dump-imports',str(flow.with_suffix('.o'))],text=True)
    flow.with_suffix('.imports.txt').write_text(dump)
    state=WORK / 'flow-state.c'
    state.write_text('#include "udeks/window_cache_flow.h"\n'
        'struct udeks_cache_flow flow_budget_state;\n')
    subprocess.run(['cl65','-t','none','--standard','c99','-Oirs','-I',str(ROOT / 'include'),
        '-c','-o',str(state.with_suffix('.o')),str(state)],check=True)
    if object_sizes(state.with_suffix('.o'))['BSS']!=4:
        raise ValueError('flow state layout changed')
    flow_sizes=object_sizes(flow.with_suffix('.o'))
    # Unbootable whole-link budget experiment: spend ALL available padding
    # and measure the actual shadow drift. Retarget EVERY split side output.
    transport_source=ROOT / 'bench/artifacts/2026-09-28-nmi-integration/src/8502/vic_graphics.s'
    transport=transport_source.read_text()
    for label,count in (('raster_scratch_placement_reserve',49),
            ('raster_primitives_placement_reserve',173),('raster_shared_placement_reserve',59)):
        before=f'{label}:\n        .res {count}, $ea'
        if transport.count(before)!=1:raise ValueError('frozen reserve changed')
        transport=transport.replace(before,f'{label}:\n        .res 0, $ea')
    (WORK / 'spent-transport.s').write_text(transport)
    subprocess.run(['ca65','--cpu','6502','-I',str(ROOT / 'src/8502'),'-o',str(WORK / 'spent-transport.o'),
        str(WORK / 'spent-transport.s')],check=True)
    binding_source=ROOT / 'bench/window-cache-command/binding.s'
    gateway=ROOT / 'bench/artifacts/2026-09-28-window-cache-command/build/gateway.bin'
    binding=binding_source.read_text().replace('build/bench/window-cache-command/gateway.bin',str(gateway))
    (WORK / 'binding.s').write_text(binding)
    subprocess.run(['ca65','--cpu','6502','-I',str(ROOT / 'bench/window-cache-command'),
        '-o',str(WORK / 'binding.o'),str(WORK / 'binding.s')],check=True)
    if object_sizes(WORK / 'binding.o')['CODE']!=241:
        raise ValueError('qualified binding drift')
    config=(ROOT / 'cfg/8502-bootstrap.cfg').read_text()
    config=re.sub(r'file = "(build/[^"\n]+)"',lambda m:'file = "'+str(WORK / Path(m[1]).name)+'"',config)
    (WORK / 'experimental.cfg').write_text(config)
    command=link_command(subprocess.check_output(['make','-Bn','build/8502/udeks-8502.bin'],cwd=ROOT,text=True))
    # Snapshot all real normal providers. The two replacements are private
    # to this experiment; none of its images is packaged or executed.
    objects=[ROOT / value for value in command if value.endswith('.o')]
    command[command.index('build/8502/window_manager.o')]=str(WORK / 'lean.o')
    command[command.index('build/8502/vic_graphics_transport.o')]=str(WORK / 'spent-transport.o')
    command[command.index('-C')+1]=str(WORK / 'experimental.cfg')
    command[command.index('-m')+1]=str(WORK / 'experimental.map')
    command[command.index('-o')+1]=str(WORK / 'experimental.bin')
    command.extend(str(WORK / name) for name in ('flow.o','flow-state.o','binding.o'))
    subprocess.run(command,cwd=ROOT,check=True)
    old_modules,old_segments=parse_map((ROOT / 'build/8502/udeks-8502.map').read_text())
    new_modules,new_segments=parse_map((WORK / 'experimental.map').read_text())
    old_regions={name:(start,end) for name,start,end in old_segments}
    new_regions={name:(start,end) for name,start,end in new_segments}
    shortfall=new_regions['VICSHADOW'][0]-0xa1e0
    helpers_added={name:size for name,size in new_modules.items() if name.startswith('none.lib(') and name not in old_modules}
    if old_regions['VICSHADOW']!=(0xa1e0,0xc11f) or shortfall<=0:
        raise ValueError('placement premise changed: review experiment')
    paths = [BASE, Path(__file__), ROOT / 'include/udeks/window.h',
        ROOT / 'include/udeks/vic_graphics.h', ROOT / 'include/udeks/pointer.h',
        ROOT / 'include/udeks/window_cache_flow.h', ROOT / 'include/udeks/window_cache_command.h',
        ROOT / 'include/udeks/window_cache_state.h',ROOT / 'src/services/window/move_cache_flow.c',
        ROOT / 'tools/gen_capability_imports.py', ROOT / 'tools/graphics_span_bench.py',
        ROOT / 'tools/graphics_raster_link_audit.py',ROOT / 'tools/placement_audit.py',
        ROOT / 'bench/window-cache-command/layout.inc',binding_source,gateway,transport_source,
        ROOT / 'cfg/8502-bootstrap.cfg',ROOT / 'build/8502/udeks-8502.map',ROOT / 'Makefile',*objects]
    names={name+'.'+suffix for name in results for suffix in ('c','s','o','lst','imports.txt')}
    names|={'flow.'+suffix for suffix in ('c','s','o','lst','imports.txt')}
    names|={'spent-transport.s','spent-transport.o','binding.s','binding.o','flow-state.c','flow-state.o',
        'experimental.cfg','experimental.map','experimental.bin'}
    names|={Path(value).name for value in re.findall(r'file = "([^"]+)"',config) if value}
    report = {'qualification': 'private C sizing and isolated UNBOOTABLE budget link; not installed cache',
        'baseline_code': 7900, 'results': results,
        'flow_segments':flow_sizes,'flow_state_bytes':4,'resident_binding_bytes':241,
        'available_after_savings':281+results['lean']['code_saved'],
        'experimental_bank0_shortfall':shortfall,'helpers_added':helpers_added,'experimental_link_command':command,
        'experimental_qualification':'UNBOOTABLE budget link: shadow moves; manager hooks/locks/delivery still absent',
        'cc65': subprocess.check_output(['cc65', '--version'], stderr=subprocess.STDOUT, text=True).strip(),
        'source_sha256': {str(p.relative_to(ROOT)): digest(p) for p in paths},
        'output_sha256': {name:digest(WORK / name) for name in sorted(names)}}
    (WORK / 'report.json').write_text(json.dumps(report, indent=2)+'\n')
    print(json.dumps({name: {k: v for k, v in r.items() if k != 'imports'} for name, r in results.items()}, indent=2))
    print(json.dumps({k:report[k] for k in ('flow_segments','available_after_savings',
        'experimental_bank0_shortfall','helpers_added')},indent=2))


def preserve():
    report = json.loads((WORK / 'report.json').read_text())
    for key, root in (('source_sha256', ROOT), ('output_sha256', WORK)):
        for name, sha in report[key].items():
            if digest(root / name) != sha:
                raise ValueError('input/output drift '+name)
    destination = ROOT / 'bench/artifacts' / NAME
    if destination.exists():
        raise ValueError('refusing to overwrite evidence')
    destination.mkdir(parents=True)
    for name in report['source_sha256']:
        path = destination / name; path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(ROOT / name, path)
    for name in set(report['output_sha256']) | {'report.json'}:
        path = destination / 'build' / name; path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(WORK / name, path)
    paths = sorted(p for p in destination.rglob('*') if p.is_file())
    (destination / 'SHA256SUMS').write_text(''.join(f'{digest(p)}  {p.relative_to(destination)}\n' for p in paths))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=('build', 'preserve'))
    args = parser.parse_args()
    {'build': build, 'preserve': preserve}[args.action]()
