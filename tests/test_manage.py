"""CLI contract tests. Only disposable local repositories are modified."""
from __future__ import annotations
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

SOURCE = Path(__file__).resolve().parents[1]
CLI = SOURCE / 'scripts' / 'manage.py'

class ManageTests(unittest.TestCase):
    def setUp(self):
        self.assertTrue(CLI.is_file(), 'manage.py must implement the template command interface')
        self.temp = tempfile.TemporaryDirectory(prefix='paper-template-test-')
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name) / 'paper'
        # Test the tool against a minimal synthetic repository, never copy the
        # live paper's initialized metadata, gitlinks, real data, or edited text.
        self.root.mkdir()
        fixture = {
            'AGENTS.md': '# Fixture policy\n',
            'README.md': '# Fixture paper\n',
            'src/main.typ': '= Fixture\n',
            '.typst-version': '0.15.1\n',
            '.gitmodules': '# No fixture submodules yet.\n',
            '.gitignore': '/build/\n__pycache__/\n',
            'project.json': json.dumps({'initialized':False, 'name':'fixture',
                                        'title':'Fixture', 'authors':[], 'abstract':''})+'\n',
            'config/hooks.json': json.dumps({'code-test':['make','test'], 'figures':None})+'\n',
            'docs/ASSETS.md': '# Fixture asset notes\n',
            'docs/REPRODUCE.md': '# Fixture provenance\n\n<!-- pins:start -->\n```json\n[]\n```\n<!-- pins:end -->\n',
        }
        for name, text in fixture.items():
            destination = self.root / name
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_text(text, encoding='utf-8')
        self.git('init', '-b', 'main')
        self.git('config', 'user.name', 'Template Test')
        self.git('config', 'user.email', 'template-test@example.invalid')
        self.git('add', '.')

    def git(self, *args, root=None, check=True):
        return subprocess.run(['git', '-C', str(root or self.root), *args],
                              text=True, capture_output=True, check=check)

    def cli(self, *args):
        return subprocess.run([sys.executable, str(CLI), '--root', str(self.root), *args],
                              text=True, capture_output=True)

    def expect(self, code, *args):
        out = self.cli(*args)
        self.assertEqual(out.returncode, code, out.stdout + out.stderr)
        return out

    def commit(self, msg='meta: test fixture'):
        self.git('commit', '-m', msg)
        return self.git('rev-parse', 'HEAD').stdout.strip()

    def add_pin(self, *, sha='a'*40, path='submodules/code', url='https://github.com/example/paper-code.git'):
        (self.root / '.gitmodules').write_text(f'[submodule "code"]\n\tpath = {path}\n\turl = {url}\n')
        self.git('add', '.gitmodules')
        self.git('update-index', '--add', '--cacheinfo', f'160000,{sha},{path}')
        return self.expect(0, 'record-pins', '--reason', 'test pin inventory')

    def test_unborn_head_can_validate_staged_template(self):
        self.expect(0, 'check')

    def test_check_does_not_mutate_index_or_document(self):
        before = self.git('write-tree').stdout
        data = (self.root / 'docs/REPRODUCE.md').read_bytes()
        self.expect(0, 'check')
        self.assertEqual(before, self.git('write-tree').stdout)
        self.assertEqual(data, (self.root / 'docs/REPRODUCE.md').read_bytes())

    def test_unstaged_source_changes_are_not_certified(self):
        with (self.root / 'README.md').open('a') as f:
            f.write('\nunstaged change\n')
        out = self.expect(1, 'check')
        self.assertIn('unstaged', out.stdout + out.stderr)

    def test_staged_oversized_blob_is_rejected(self):
        (self.root / 'too large.bin').write_bytes(b'x' * 10_000_001)
        self.git('add', 'too large.bin')
        self.expect(1, 'check')

    def test_exact_blob_limit_is_permitted(self):
        (self.root / 'boundary.bin').write_bytes(b'x' * 10_000_000)
        self.git('add', 'boundary.bin')
        self.expect(0, 'check')

    def test_deleted_historical_oversized_blob_is_rejected(self):
        base = self.commit()
        (self.root / 'old.bin').write_bytes(b'x' * 10_000_001)
        self.git('add', 'old.bin')
        self.commit('meta: add oversized historical blob')
        self.git('rm', 'old.bin')
        self.commit('meta: delete oversized historical blob')
        self.expect(1, 'check', '--history', '--base', base)

    def test_prohibited_weights_are_rejected(self):
        (self.root / 'weights.pth').write_bytes(b'not a real model')
        self.git('add', 'weights.pth')
        self.expect(1, 'check')

    def test_copied_submodule_source_is_rejected(self):
        p = self.root / 'submodules/code/main.py'
        p.parent.mkdir(parents=True)
        p.write_text('print(1)\n')
        self.git('add', 'submodules')
        self.expect(1, 'check')

    def test_gitmodules_without_gitlink_is_rejected(self):
        (self.root / '.gitmodules').write_text('[submodule "code"]\npath = submodules/code\nurl = https://github.com/example/code.git\n')
        self.git('add', '.gitmodules')
        self.expect(1, 'check')

    def test_gitlink_outside_submodules_is_rejected(self):
        self.git('update-index', '--add', '--cacheinfo', f'160000,{"a"*40},code')
        self.expect(1, 'check')

    def test_record_pins_uses_index_full_hash_and_requires_staging(self):
        self.add_pin()
        self.assertIn('a'*40, (self.root / 'docs/REPRODUCE.md').read_text())
        self.expect(1, 'check')  # record is not staged yet
        self.git('add', 'docs/REPRODUCE.md')
        self.expect(0, 'check')
        self.expect(2, 'check', '--require-submodules')

    def test_wrong_recorded_pin_is_rejected(self):
        self.add_pin()
        p = self.root / 'docs/REPRODUCE.md'
        p.write_text(p.read_text().replace('a'*40, 'b'*40))
        self.git('add', 'docs/REPRODUCE.md')
        self.expect(1, 'check')

    def test_remote_url_with_password_is_rejected(self):
        (self.root / '.gitmodules').write_text('[submodule "code"]\npath = submodules/code\nurl = https://name:password@github.com/example/code.git\n')
        self.git('add', '.gitmodules')
        self.git('update-index', '--add', '--cacheinfo', f'160000,{"a"*40},submodules/code')
        self.expect(1, 'check')

    def test_record_pins_preserves_narrative(self):
        p = self.root / 'docs/REPRODUCE.md'
        p.write_text(p.read_text() + '\nResearcher-owned narrative.\n')
        self.expect(0, 'record-pins', '--reason', 'template inventory')
        self.assertIn('Researcher-owned narrative.', p.read_text())

    def test_record_pins_requires_reason(self):
        env = os.environ.copy()
        env.pop('REASON', None)
        r = subprocess.run([sys.executable, str(CLI), '--root', str(self.root), 'record-pins'],
                           env=env, text=True, capture_output=True)
        self.assertEqual(r.returncode, 2)

    def test_metadata_initialization_is_one_time(self):
        self.expect(0, 'init', '--name', 'test-paper', '--title', 'A title: "quoted"', '--author', 'Test Author')
        d = json.loads((self.root / 'project.json').read_text())
        self.assertEqual(d['title'], 'A title: "quoted"')
        self.assertEqual(d['authors'], ['Test Author'])
        self.expect(1, 'init', '--name', 'other', '--title', 'Other', '--author', 'Other')
        self.assertEqual(d, json.loads((self.root / 'project.json').read_text()))

    def test_unconfigured_figures_are_blocked_not_passed(self):
        self.expect(2, 'figures')

    def test_manifest_requires_committed_revision(self):
        self.expect(2, 'manifest')

    def test_manifest_records_real_commit_without_modifying_tracked_files(self):
        sha = self.commit()
        self.expect(0, 'manifest')
        result = json.loads((self.root / 'build/provenance.json').read_text())
        self.assertEqual(result['paper_commit'], sha)
        self.assertFalse(result['dirty'])
        self.assertEqual(result['pins'], [])
        self.assertEqual('', self.git('status', '--porcelain').stdout)

    def test_release_manifest_rejects_dirty_checkout(self):
        self.commit()
        (self.root / 'untracked.txt').write_text('unpublished work\n')
        self.expect(1, 'manifest', '--release')

    def test_submodule_restore_refuses_dirty_dependency(self):
        dep = Path(self.temp.name) / 'dep'
        dep.mkdir()
        self.git('init', '-b', 'main', root=dep)
        self.git('config', 'user.name', 'Fixture', root=dep)
        self.git('config', 'user.email', 'fixture@example.invalid', root=dep)
        (dep / 'README.md').write_text('dependency\n')
        self.git('add', '.', root=dep)
        self.git('commit', '-m', 'feat: fixture', root=dep)
        self.git('-c', 'protocol.file.allow=always', 'submodule', 'add', '--name', 'code', str(dep), 'submodules/code')
        # Replace only the published URL; no network is accessed by this guard test.
        self.git('config', '-f', '.gitmodules', 'submodule.code.url', 'https://github.com/example/code.git')
        self.git('add', '.gitmodules', 'submodules/code')
        self.expect(0, 'record-pins', '--reason', 'fixture')
        self.git('add', 'docs/REPRODUCE.md')
        p = self.root / 'submodules/code/README.md'
        p.write_text('local unpublished edit\n')
        self.expect(1, 'submodules')
        self.assertEqual(p.read_text(), 'local unpublished edit\n')

    def test_failing_code_hook_is_fail_not_blocked(self):
        dep = Path(self.temp.name) / 'failing-dep'
        dep.mkdir()
        self.git('init', '-b', 'main', root=dep)
        self.git('config', 'user.name', 'Fixture', root=dep)
        self.git('config', 'user.email', 'fixture@example.invalid', root=dep)
        (dep / 'Makefile').write_text('test:\n\t@exit 1\n')
        self.git('add', '.', root=dep)
        self.git('commit', '-m', 'feat: deliberately failing test command', root=dep)
        self.git('-c', 'protocol.file.allow=always', 'submodule', 'add', '--name', 'code', str(dep), 'submodules/code')
        self.git('config', '-f', '.gitmodules', 'submodule.code.url', 'https://github.com/example/code.git')
        self.git('add', '.gitmodules', 'submodules/code')
        self.expect(0, 'record-pins', '--reason', 'failing hook fixture')
        (self.root / 'config/hooks.json').write_text(json.dumps({'code-test':['make','test'], 'figures':None}))
        self.git('add', 'docs/REPRODUCE.md', 'config/hooks.json')
        self.expect(1, 'code-test')

    def test_missing_typst_reports_blocked(self):
        env = os.environ.copy()
        env['PATH'] = str(Path(self.temp.name) / 'no-executables')
        r = subprocess.run([sys.executable, str(CLI), '--root', str(self.root), 'compile'],
                           env=env, text=True, capture_output=True)
        self.assertEqual(r.returncode, 2, r.stdout + r.stderr)
        self.assertIn('BLOCKED', r.stderr)

    def test_asset_at_two_mb_requires_a_recorded_justification(self):
        p = self.root / 'assets/boundary.svg'
        p.parent.mkdir()
        p.write_bytes(b'x' * 2_000_000)
        self.git('add', 'assets/boundary.svg')
        self.expect(1, 'check')
        notes = self.root / 'docs/ASSETS.md'
        notes.write_text(notes.read_text() + '\nassets/boundary.svg: synthetic threshold-test justification.\n')
        self.git('add', 'docs/ASSETS.md')
        self.expect(0, 'check')

if __name__ == '__main__':
    unittest.main()
