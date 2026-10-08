# SPDX-License-Identifier: GPL-3.0-or-later
"""Keep downloadable snapshots reproducible and separate from local builds."""
import hashlib
import json
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import unittest
from urllib.parse import unquote, urlsplit

ROOT = Path(__file__).resolve().parents[1]
ACCEPTED = ROOT/'bench/results/2026-10-09-default-time'


class PublishedBoot(unittest.TestCase):
    def test_published_images_match_checksums_and_accepted_build(self):
        rows = (ROOT/'build/SHA256SUMS').read_text().splitlines()
        self.assertEqual(len(rows), 3)
        seen = set()
        for row in rows:
            expected, name = row.split()
            self.assertIn(name, ('udeks.d64', 'udeks.d71', 'udeks.d81'))
            self.assertNotIn(name, seen)
            seen.add(name)
            disk = (ROOT/'build'/name).read_bytes()
            self.assertEqual(hashlib.sha256(disk).hexdigest(), expected)
            accepted = json.loads((ACCEPTED/'build.json').read_text())
            self.assertEqual(expected,accepted['disks'][name.rsplit('.',1)[1]]['sha256'])
            self.assertEqual(len(disk), {'udeks.d64': 174848, 'udeks.d71': 349696,
                                         'udeks.d81': 819200}[name])

    def test_current_readme_index_and_image_links_resolve(self):
        for relative in ('README.md', 'docs/README.md', 'build/README.md'):
            path = ROOT/relative
            text = path.read_text()
            links = re.findall(r'\[[^\]\n]*\]\(([^)\n]+)\)', text)
            links += re.findall(r'<img[^>]*src="([^"]+)"', text)
            for target in links:
                parsed = urlsplit(target)
                if parsed.scheme or not parsed.path: continue
                with self.subTest(document=relative, target=target):
                    self.assertTrue((path.parent/unquote(parsed.path)).exists())
        documents = (ROOT/'README.md').read_text().split('## Documents\n', 1)[1]
        self.assertLessEqual(len(re.findall(r'^- ', documents, re.M)), 6)

    def test_only_publication_files_escape_build_ignore(self):
        names = ('build/udeks.d64', 'build/udeks.d71', 'build/udeks.d81', 'build/SHA256SUMS',
                 'build/README.md', 'build/boot/udeks.d64',
                 'build/root-filesystem/README.md', 'build/new-object.o')
        with tempfile.TemporaryDirectory() as temporary:
            temp = Path(temporary)
            shutil.copyfile(ROOT/'.gitignore', temp/'.gitignore')
            subprocess.run(['git', 'init', '-q'], cwd=temp, check=True)
            (temp/'build').mkdir()
            result = subprocess.run(['git', 'check-ignore', '--stdin'], cwd=temp,
                input='\n'.join(names)+'\n', text=True, capture_output=True, check=True)
            self.assertEqual(set(result.stdout.splitlines()), set(names[5:]))

    def test_clean_preserves_published_images_worktrees_and_test_runs(self):
        makefile = (ROOT/'Makefile').read_text()
        clean = 'BUILD_DIR := build\nclean:\n'+makefile.split('\nclean:\n', 1)[1].split('\nhelp:', 1)[0]
        with tempfile.TemporaryDirectory() as temporary:
            temp = Path(temporary)
            keep = ('build/udeks.d64', 'build/udeks.d71', 'build/udeks.d81', 'build/README.md',
                    'build/SHA256SUMS', 'build/root-filesystem/.git',
                    'build/root-namespace/result.json')
            remove = tuple('build/'+name+'/output.o' for name in
                ('8502', 'z80', 'boot', 'assets', 'user', 'storage', 'window-cache', 'bench'))
            for name in keep+remove:
                path = temp/name
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(b'test fixture')
            refused = subprocess.run(['make', '-f', '-', 'clean', 'BUILD_DIR=/'],
                cwd=temp, input=clean, text=True, capture_output=True)
            self.assertNotEqual(refused.returncode, 0)
            for name in remove: self.assertTrue((temp/name).exists())
            subprocess.run(['make', '-f', '-', 'clean'], cwd=temp, input=clean,
                           text=True, capture_output=True, check=True)
            for name in keep: self.assertEqual((temp/name).read_bytes(), b'test fixture')
            for name in remove: self.assertFalse((temp/name).exists())

    def test_publication_is_explicit_and_updates_three_checksums(self):
        makefile = (ROOT/'Makefile').read_text()
        recipe = makefile.split('\npublish-boot: boot\n', 1)[1].split('\n\n', 1)[0]
        rules = ('BUILD_DIR := build\nBOOT_D64 := build/boot/udeks.d64\n'
                 'BOOT_D71 := build/boot/udeks.d71\nBOOT_D81 := build/boot/udeks.d81\n.PHONY: boot publish-boot\n'
                 'boot:\n\npublish-boot: boot\n'+recipe+'\n')
        with tempfile.TemporaryDirectory() as temporary:
            temp = Path(temporary)
            (temp/'build/boot').mkdir(parents=True)
            for suffix in ('d64', 'd71', 'd81'):
                (temp/('build/boot/udeks.'+suffix)).write_bytes(suffix.encode())
                (temp/('build/udeks.'+suffix)).write_bytes(b'published')
            subprocess.run(['make', '-f', '-', 'boot'], cwd=temp, input=rules,
                           text=True, capture_output=True, check=True)
            self.assertEqual((temp/'build/udeks.d64').read_bytes(), b'published')
            subprocess.run(['make', '-f', '-', 'publish-boot'], cwd=temp, input=rules,
                           text=True, capture_output=True, check=True)
            for row in (temp/'build/SHA256SUMS').read_text().splitlines():
                expected, name = row.split()
                content = (temp/'build'/name).read_bytes()
                self.assertEqual(content, (temp/'build/boot'/name).read_bytes())
                self.assertEqual(hashlib.sha256(content).hexdigest(), expected)
