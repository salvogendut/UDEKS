# SPDX-License-Identifier: GPL-3.0-or-later
from collections import Counter
import hashlib
import json
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'tools'))
from add_disk_apps import add_apps
from build_scheduler_overlay import map_segments
from storage_owner_probe import with_spawn_child
from gen_capability_imports import map_exports

EVIDENCE = '2026-10-07-storage-ownership'
ARTIFACTS = ROOT/'bench/artifacts'/EVIDENCE
RESULTS = ROOT/'bench/results'/EVIDENCE


class StorageOwner(unittest.TestCase):
    def test_exact_production_images_fit_without_borrowing_stacks(self):
        segments = map_segments((ARTIFACTS/'module.map').read_text())
        expected = dict(STARTUP=(0x1200,0x1214,21), CODE=(0x1215,0x1870,1628),
                        STORAGECODE=(0xb000,0xc5a1,5538), BSS=(0xe000,0xe17f,384),
                        IECCODE=(0xe300,0xe85c,1373), RODATA=(0xf000,0xf064,101),
                        STORAGEHIGH=(0xf065,0xfefd,3737))
        for name, bounds in expected.items(): self.assertEqual(segments[name], bounds)
        for name, size in dict(module=1649,policy=5538,driver=1373,hidden=3838).items():
            self.assertEqual(len((ARTIFACTS/(name+'.bin')).read_bytes()), size)
        module = (ARTIFACTS/'module.bin').read_bytes()
        self.assertEqual(module[3:9], b'UIEC\0\3')
        for offset in (0,9,12,15,18): self.assertEqual(module[offset],0x4c)

    def test_context_generations_are_private_initialized_driver_state(self):
        symbols = map_exports((ARTIFACTS/'module.map').read_text())
        driver = (ARTIFACTS/'driver.bin').read_bytes()
        address,kind = symbols['_udeks_storage_generations']
        self.assertEqual(kind,'RLA')
        self.assertTrue(0xe300 <= address < 0xe900-11)
        self.assertEqual(driver[address-0xe300:address-0xe300+11],b'\1'*11)
        self.assertEqual(symbols['_udeks_storage_cleanup_error'][0], address+11)

    def test_permanent_transport_does_not_share_live_loader_or_vic_stack(self):
        segments = map_segments((ARTIFACTS/'stage1-gateway.map').read_text())
        self.assertEqual(segments['STORAGEGATE'], (0xfe20,0xfe51,50))
        self.assertLess(segments['TASKLOADER'][1],0xfe20)
        self.assertEqual(segments['BOOTINIT'][0],0xfe80)
        blob = (ARTIFACTS/'task-loader.bin').read_bytes()
        gate = blob[0xfe20-0xf910:0xfe52-0xf910]
        self.assertEqual(len(gate),50)
        self.assertIn(bytes.fromhex('200f12'),gate)
        self.assertIn(bytes.fromhex('8503'),gate)  # service stack high

    def test_hooks_precede_lifecycle_or_foreground_memory_reuse(self):
        source = (ROOT/'src/scheduler/task_yield_handler.s').read_text()
        exit_body = source.split('request_exit:',1)[1].split('current_slot:',1)[0]
        self.assertLess(exit_body.index('jsr current_slot'),exit_body.index('jsr $c883'))
        self.assertLess(exit_body.index('jsr $c883'),exit_body.index('lda #TASK_STATE_ZOMBIE'))
        source = (ROOT/'src/scheduler/task_wait_state.s').read_text()
        cancel = source.split('_udeks_task_cancel_request:',1)[1].split('cancel_missing:',1)[0]
        self.assertLess(cancel.index('bne cancel_missing'),cancel.index('jsr $c883'))
        self.assertLess(cancel.index('jsr $c883'),cancel.index('sta _udeks_lifecycle_slots_private+TASK_SLOT_EXIT'))
        source = (ROOT/'src/boot/stage1-gateway.s').read_text()
        self.assertIn('jsr TASK_SLOT\n        sta TASK_EXIT\n        lda #9\n        jsr $c883',source)
        self.assertIn('jsr $3200\n        cmp #0',source)  # initializer preserves P

    def test_retirement_closes_before_generation_advance(self):
        source = (ROOT/'src/services/filesystem/iec_context.s').read_text()
        body = source.split('_udeks_storage_context_retire:',1)[1].split('identify:',1)[0]
        self.assertLess(body.index('jsr $1209'),body.index('inc _udeks_storage_generations,x'))
        router = (ROOT/'src/services/filesystem/iec_router.s').read_text()
        self.assertIn('lda STORAGE_CURRENT_TASK\n        bne selected',router)
        self.assertNotIn('TREQ_PAYLOAD',router)
        self.assertNotIn('$f68a',router.lower())

    def test_all_formats_exercised_real_return_exit_cancel_and_reuse(self):
        for drive,suffix in (('1541','d64'),('1571','d71'),('1581','d81')):
            result=json.loads((RESULTS/(drive+'.json')).read_text())
            image=(ARTIFACTS/('udeks.'+suffix)).read_bytes()
            self.assertEqual(hashlib.sha256(image).hexdigest(),result['disk_sha256'])
            fixture=with_spawn_child(image,(ARTIFACTS/'CHILD.BIN').read_bytes())
            fixture=add_apps(fixture,[(name,(ARTIFACTS/name).read_bytes())
                                     for name in ('LEAK.BIN','HOLD.BIN','PARENT.BIN')])
            self.assertEqual(hashlib.sha256(fixture).hexdigest(),result['fixture_sha256'])
            retirements=[r for r in result['checks'] if 'retired' in r]
            self.assertEqual(Counter(r['retired'] for r in retirements),Counter({9:2,6:3,2:1}))
            for r in retirements:
                self.assertEqual(r['generation_after'],(r['generation_before']+1)&255)
            commands=[r['command'] for r in result['checks'] if 'command' in r]
            self.assertEqual(commands.count('leak'),2)
            self.assertEqual(commands.count('hold &'),2)
            self.assertIn('parent &',commands)
            self.assertIn('xclock &',commands)
            self.assertEqual(commands[-1],'echo ownership-ok')

    def test_recovery_and_four_app_regression_are_preserved(self):
        recovery=json.loads((RESULTS/'recovery-1541.json').read_text())
        self.assertTrue(recovery['recovery'])
        self.assertIn('/mnt/COWSAY.BIN recovery-alive',[c['command'] for c in recovery['checks']])
        result=json.loads((RESULTS/'four-native-1571.json').read_text())
        self.assertEqual(hashlib.sha256((ARTIFACTS/'udeks.d71').read_bytes()).hexdigest(),result['disk_sha256'])
        commands=[c['command'] for c in result['checks'] if 'command' in c]
        for command in ('xclock &','xwave &','xcalc &','xdraw &','canvas -q','extra &'):
            self.assertIn(command,commands)
        self.assertTrue(any(c.get('check')=='four-resized-pixels' for c in result['checks']))

    def test_current_boundary_rejects_future_versions_and_legacy_create(self):
        header=(ROOT/'include/udeks/task_request.h').read_text()
        self.assertIn('UDEKS_TASK_REQUEST_ABI_MINOR     14u',header)
        fixture=(ROOT/'bench/storage-owner/foreground.c').read_text()
        self.assertIn('R[5]=15',fixture)
        self.assertIn('if(R[12]!=71)',fixture)
        self.assertIn('if(R[12]!=22)',fixture)

    def test_preserved_checksums(self):
        for line in (RESULTS/'SHA256SUMS').read_text().splitlines():
            digest,relative=line.split(maxsplit=1)
            self.assertEqual(hashlib.sha256((ROOT/relative).read_bytes()).hexdigest(),digest,relative)
