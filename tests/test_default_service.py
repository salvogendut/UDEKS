# SPDX-License-Identifier: GPL-3.0-or-later
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tools'))
import default_service_layout as default
from check_service_migration import overlay_changed


class DefaultServiceTests(unittest.TestCase):
    def test_both_binaries_are_required(self):
        for binaries in ([],[b''],[b'']*3):
            with self.assertRaisesRegex(ValueError,'both normal and panic'):
                default.layouts('','',binaries)

    def test_no_resident_fallback_or_missing_manager_can_pass(self):
        complete = {'time-slot.o':{},'time-resident.o':{},'service_registry.o':{}}
        for modules in (dict(complete,**{'time.o':{}}),
                        *({k:v for k,v in complete.items() if k!=missing} for missing in complete)):
            with patch.object(default,'layout_maps',return_value={'SERVICEBOOT':(0x93d0,0x95d5,518)}), \
                 patch.object(default,'parse_map',return_value=(modules,{})), \
                 patch.object(default,'qualify') as qualification:
                with self.assertRaises(ValueError):
                    default.layouts('normal','panic',[b'',b''])
                qualification.assert_not_called()

    def test_missing_startup_overlay_rejected(self):
        with patch.object(default,'layout_maps',return_value={}):
            with self.assertRaisesRegex(ValueError,'startup overlay'):
                default.layouts('','',[b'',b''])

    def test_actual_binary_and_each_map_reach_vector_qualification(self):
        modules = {'time-slot.o':{},'time-resident.o':{},'service_registry.o':{}}
        segments = {'SERVICEBOOT':(0x93d0,0x95d5,518)}
        with patch.object(default,'layout_maps',return_value=segments), \
             patch.object(default,'parse_map',return_value=(modules,{})), \
             patch.object(default,'map_exports',side_effect=[{'normal':1},{'panic':2}]), \
             patch.object(default,'qualify',side_effect=['ok','panic-ok']) as check:
            self.assertEqual(default.layouts('normal','panic',[b'N',b'P']),
                             {'normal':'ok','panic':'panic-ok'})
            self.assertEqual(check.call_args_list[0].args,({},segments,{'normal':1},b'N'))
            self.assertEqual(check.call_args_list[1].args,({},segments,{'panic':2},b'P'))

    def test_upgrade_changes_inputs_not_existing_objects_or_unchanged_timestamps(self):
        with tempfile.TemporaryDirectory() as temp:
            root,target = Path(temp)/'new',Path(temp)/'old'
            for directory in (root,target):
                (directory/'src').mkdir(parents=True)
                (directory/'src/unchanged.c').write_text('same')
                (directory/'Makefile').write_text(str(directory))
            (target/'build').mkdir()
            (target/'build/stale.o').write_bytes(b'old object')
            unchanged = (target/'src/unchanged.c').stat().st_mtime_ns
            changed = overlay_changed(root,target)
            self.assertEqual(changed,['Makefile'])
            self.assertEqual((target/'src/unchanged.c').stat().st_mtime_ns,unchanged)
            self.assertEqual((target/'build/stale.o').read_bytes(),b'old object')
            self.assertEqual((target/'Makefile').read_text(),str(root))

    def test_flag_sensitive_recipes_track_the_default_policy(self):
        makefile = (ROOT/'Makefile').read_text()
        storage = (ROOT/'mk/storage.mk').read_text()
        for name,text in (('service_registry.s',makefile),('syscall_gate.o',makefile),('router.o',storage)):
            recipes = [line for line in text.replace('\\\n',' ').splitlines() if '/'+name+':' in line]
            self.assertTrue(any('mk/services.mk' in line for line in recipes),name)


if __name__ == '__main__':
    unittest.main()
