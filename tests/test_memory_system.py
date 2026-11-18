import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


SKILL = Path(__file__).resolve().parents[1] / 'skills' / 'project-memory-dreaming'
INIT = SKILL / 'scripts' / 'init_project.py'


class InitTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='memory-中文 ')
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name) / '新项目 TideNotes'
        self.root.mkdir()

    def init(self, *args, ok=True):
        result = subprocess.run([sys.executable, str(INIT), str(self.root), *args],
                                capture_output=True, text=True, encoding='utf-8')
        if ok:
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        else:
            self.assertNotEqual(result.returncode, 0, result.stdout)
        return result

    def test_new_project_and_rerun_preserve_user_content(self):
        self.init('--name', 'TideNotes')
        for name in ['memory/README.md', 'memory/org/conventions.md',
                     'memory/org/red-lines.md', 'memory/team/decisions.md',
                     'memory/team/progress.md', 'memory/team/pitfalls.md',
                     'memory/agents/README.md', 'memory/skills/README.md',
                     'transcripts/README.md', 'dreaming/README.md',
                     'evals/memory/README.md', 'tools/agent_memory.py',
                     'AGENTS.md', 'CLAUDE.md', '.memory-system.json']:
            self.assertTrue((self.root / name).is_file(), name)
        target = self.root / 'memory/team/pitfalls.md'
        target.write_text('用户手写经验\n', encoding='utf-8')
        before = {p.relative_to(self.root): p.read_bytes()
                  for p in self.root.rglob('*') if p.is_file()}
        self.init()
        after = {p.relative_to(self.root): p.read_bytes()
                 for p in self.root.rglob('*') if p.is_file()}
        self.assertEqual(before, after)

    def test_initialized_memory_content_defaults_to_english(self):
        self.init('--name', 'TideNotes')
        generated_dirs = ['memory', 'transcripts', 'dreaming', 'evals']
        for directory in generated_dirs:
            for path in (self.root / directory).rglob('*.md'):
                content = path.read_text(encoding='utf-8')
                self.assertNotRegex(content, r'[\u3400-\u9fff]', str(path))
        for name in ['AGENTS.md', 'CLAUDE.md']:
            guidance = (self.root / name).read_text(encoding='utf-8')
            self.assertIn('Translate relevant non-English content into English before saving it in project memory', guidance)
            self.assertIn('user-facing replies in the language the user is currently using.', guidance)

    def test_existing_guidance_and_override_survive(self):
        for name in ['AGENTS.md', 'CLAUDE.md', 'AGENTS.override.md']:
            (self.root / name).write_bytes(b'# TideNotes\r\nUse pnpm.\r\n')
        self.init()
        for name in ['AGENTS.md', 'CLAUDE.md', 'AGENTS.override.md']:
            actual = (self.root / name).read_bytes()
            self.assertTrue(actual.startswith(b'# TideNotes\r\nUse pnpm.\r\n'))
            self.assertIn(b'memory/README.md', actual)
        before = (self.root / 'AGENTS.md').read_bytes()
        self.init()
        self.assertEqual((self.root / 'AGENTS.md').read_bytes(), before)

    def test_dry_run_has_no_side_effects(self):
        self.init('--dry-run')
        self.assertEqual(list(self.root.iterdir()), [])

    def test_colliding_directory_fails_before_any_files_are_added(self):
        (self.root / 'AGENTS.md').mkdir()
        self.init(ok=False)
        self.assertEqual([p.name for p in self.root.iterdir()], ['AGENTS.md'])

    def test_initializer_refuses_symlinked_memory(self):
        outside = Path(self.temp.name) / 'outside'
        outside.mkdir()
        try:
            (self.root / 'memory').symlink_to(outside, target_is_directory=True)
        except OSError as error:
            self.skipTest(f'OS does not allow creating test symlinks: {error}')
        self.init(ok=False)
        self.assertEqual(list(outside.iterdir()), [])


class RuntimeTests(unittest.TestCase):
    init = InitTests.init

    def setUp(self):
        InitTests.setUp(self)
        self.init('--name', 'TideNotes')
        self.tool_path = self.root / 'tools/agent_memory.py'

    def tool(self, *args, ok=True):
        result = subprocess.run([sys.executable, str(self.tool_path), '--root', str(self.root), *args],
                                capture_output=True, text=True, encoding='utf-8')
        if ok:
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            return json.loads(result.stdout)
        self.assertNotEqual(result.returncode, 0, result.stdout)
        return result

    def input(self, name, text):
        path = Path(self.temp.name) / name
        path.write_bytes(text.encode('utf-8'))
        return str(path)

    def record(self, text='npm test failed; pnpm test passed'):
        return self.tool('record', '--actor', 'codex', '--input', self.input('session.txt', text))['path']

    def batch(self):
        source = self.record()
        result = self.tool('prepare')
        run = result['run']
        directory = self.root / 'dreaming/runs' / run
        target = directory / 'candidate/memory/team/pitfalls.md'
        target.write_bytes(target.read_bytes() + b'\nUse pnpm test in this project.\n')
        proposal = [{'id': 'p1', 'type': 'add', 'target': 'memory/team/pitfalls.md',
                     'proposal': 'Use pnpm test in this project.', 'reason': 'observed recovery',
                     'confidence': 'medium', 'evidence': [
                         {'source': source, 'quote': 'npm test failed; pnpm test passed'}]}]
        (directory / 'proposals.json').write_text(json.dumps(proposal), encoding='utf-8')
        return source, run, directory

    def test_record_is_unique_and_prepare_isolated(self):
        a, b = self.record(), self.record()
        self.assertNotEqual(a, b)
        before = (self.root / 'memory/team/pitfalls.md').read_bytes()
        result = self.tool('prepare')
        directory = self.root / 'dreaming/runs' / result['run']
        self.assertEqual(set(result['transcripts']), {a, b})
        candidate = directory / 'candidate/memory/team/pitfalls.md'
        candidate.write_bytes(b'candidate only')
        self.assertEqual((self.root / 'memory/team/pitfalls.md').read_bytes(), before)
        self.assertEqual((directory / 'base/memory/team/pitfalls.md').read_bytes(), before)
        self.assertTrue((directory / 'transcripts' / Path(a).name).is_file())

    def test_write_requires_current_hash_and_actor_scope(self):
        path = 'memory/team/pitfalls.md'
        before = (self.root / path).read_bytes()
        expected = self.tool('hash', path)['sha256']
        content = self.input('entry.txt', 'verified lesson\n')
        self.tool('write', path, '--input', content, '--expected-hash', '0'*64, '--actor', 'codex', ok=False)
        self.assertEqual((self.root / path).read_bytes(), before)
        self.tool('write', path, '--input', content, '--expected-hash', expected, '--actor', 'codex')
        self.assertEqual((self.root / path).read_text(encoding='utf-8'), 'verified lesson\n')
        for forbidden in ['memory/org/red-lines.md', '../outside.md', 'memory/agents/other.md',
                          'memory/team/file.md:stream', 'memory/team/../../AGENTS.md']:
            self.tool('write', forbidden, '--input', content, '--expected-hash', 'missing', '--actor', 'codex', ok=False)

    def test_progress_append_and_lock(self):
        path = 'memory/team/progress.md'
        before = (self.root / path).read_bytes()
        expected = self.tool('hash', path)['sha256']
        entry = self.input('entry.txt', '\nreal result\n')
        self.tool('write', path, '--input', entry, '--expected-hash', expected, '--actor', 'codex', ok=False)
        self.tool('write', path, '--input', entry, '--expected-hash', expected, '--actor', 'codex', '--append')
        self.assertEqual((self.root / path).read_bytes(), before + b'\nreal result\n')
        (self.root / '.memory-system.lock').write_text('{}')
        self.tool('record', '--actor', 'codex', '--input', entry, ok=False)
        self.assertTrue((self.root / '.memory-system.lock').exists())

    @unittest.skipUnless(os.name == 'nt', 'Windows case-insensitive filesystem')
    def test_progress_case_alias_cannot_bypass_append_only(self):
        expected = self.tool('hash', 'memory/team/progress.md')['sha256']
        before = (self.root / 'memory/team/progress.md').read_bytes()
        self.tool('write', 'memory/team/Progress.md', '--input', self.input('entry.txt', 'erase history'),
                  '--expected-hash', expected, '--actor', 'codex', ok=False)
        self.assertEqual((self.root / 'memory/team/progress.md').read_bytes(), before)

    def test_overlapping_batch_cannot_reprocess_an_applied_source(self):
        source = self.record()
        a, b = self.tool('prepare')['run'], self.tool('prepare')['run']
        self.tool('review', a)
        self.tool('review', b)
        self.tool('apply', a, '--approved-by', 'owner')
        self.tool('apply', b, '--approved-by', 'owner', ok=False)

    def test_new_production_file_invalidates_reviewed_baseline(self):
        _, run, _ = self.batch()
        self.tool('review', run)
        extra = self.root / 'memory/team/new.md'
        extra.write_bytes(b'new knowledge after preparation\n')
        before = {p.relative_to(self.root): p.read_bytes()
                  for p in (self.root / 'memory').rglob('*') if p.is_file()}
        self.tool('apply', run, '--approved-by', 'owner', ok=False)
        after = {p.relative_to(self.root): p.read_bytes()
                 for p in (self.root / 'memory').rglob('*') if p.is_file()}
        self.assertEqual(before, after)
        self.assertFalse((self.root / f'dreaming/runs/{run}/receipt.json').exists())

    @unittest.skipUnless(os.name == 'nt', 'Windows case-insensitive filesystem')
    def test_processed_transcript_case_alias_is_not_new_evidence(self):
        source = self.record()
        run = self.tool('prepare')['run']
        self.tool('review', run)
        self.tool('apply', run, '--approved-by', 'owner')
        alias = 'transcripts/' + Path(source).name.upper()
        result = self.tool('prepare', '--transcript', alias)
        self.assertEqual(result['transcripts'], [])
        self.assertIsNone(result['run'])

    def test_review_apply_rollback_and_incremental_selection(self):
        source, run, directory = self.batch()
        path = 'memory/team/pitfalls.md'
        before = (self.root / path).read_bytes()
        self.tool('apply', run, '--approved-by', 'owner', ok=False)
        review = self.tool('review', run)
        self.assertEqual(review['changed_files'], [path])
        self.assertTrue((directory / 'REVIEW.md').is_file())
        self.tool('apply', run, '--approved-by', 'owner')
        self.assertIn(b'Use pnpm test', (self.root / path).read_bytes())
        self.assertEqual(self.tool('prepare')['transcripts'], [])
        self.tool('rollback', run, '--approved-by', 'owner')
        self.assertEqual((self.root / path).read_bytes(), before)
        self.assertEqual(self.tool('prepare')['transcripts'], [source])

    def test_review_requires_real_evidence_and_independent_recurrence(self):
        source, run, directory = self.batch()
        proposals = json.loads((directory / 'proposals.json').read_text())
        proposals[0]['evidence'][0]['quote'] = 'invented evidence'
        (directory / 'proposals.json').write_text(json.dumps(proposals))
        self.tool('review', run, ok=False)
        proposals[0]['evidence'][0]['quote'] = 'npm test failed; pnpm test passed'
        proposals[0]['type'] = 'promote_to_rule'
        proposals[0]['evidence'] *= 2
        (directory / 'proposals.json').write_text(json.dumps(proposals))
        self.tool('review', run, ok=False)
        proposals[0]['type'] = 'add'
        (directory / 'proposals.json').write_text(json.dumps(proposals))
        self.tool('review', run)

    def test_review_rejects_malformed_proposal_objects_without_traceback(self):
        _, run, directory = self.batch()
        path = directory / 'proposals.json'
        proposal = json.loads(path.read_text(encoding='utf-8'))[0]
        for malformed in [[None], [dict(proposal, target=42)],
                          [dict(proposal, evidence=['bad'])]]:
            with self.subTest(proposals=malformed):
                path.write_text(json.dumps(malformed), encoding='utf-8')
                result = self.tool('review', run, ok=False)
                self.assertTrue(result.stderr.startswith('Error: '), result.stderr)
                self.assertNotIn('Traceback', result.stderr)
                self.assertFalse((directory / 'review.json').exists())

    def test_apply_refuses_changed_candidate_or_baseline_without_writing(self):
        _, run, directory = self.batch()
        self.tool('review', run)
        target = self.root / 'memory/team/pitfalls.md'
        original = target.read_bytes()
        candidate = directory / 'candidate/memory/team/pitfalls.md'
        candidate.write_bytes(candidate.read_bytes() + b'not reviewed\n')
        self.tool('apply', run, '--approved-by', 'owner', ok=False)
        self.assertEqual(target.read_bytes(), original)
        self.tool('review', run)
        target.write_bytes(original + b'today lesson\n')
        before = target.read_bytes()
        self.tool('apply', run, '--approved-by', 'owner', ok=False)
        self.assertEqual(target.read_bytes(), before)

    def test_org_progress_and_unexplained_candidate_changes_are_rejected(self):
        _, run, directory = self.batch()
        org = directory / 'candidate/memory/org/conventions.md'
        original = org.read_bytes()
        org.write_bytes(b'overwrite org')
        self.tool('review', run, ok=False)
        org.write_bytes(original)
        progress = directory / 'candidate/memory/team/progress.md'
        previous = progress.read_bytes()
        progress.write_bytes(b'erase historical progress')
        self.tool('review', run, ok=False)
        progress.write_bytes(previous)
        (directory / 'candidate/memory/team/decisions.md').write_bytes(b'unexplained change')
        self.tool('review', run, ok=False)

    def test_foreign_project_transcript_rejected(self):
        source = self.record()
        path = self.root / source
        config = json.loads((self.root / '.memory-system.json').read_text(encoding='utf-8'))
        path.write_text(path.read_text(encoding='utf-8').replace(config['project_id'], 'foreign-project'), encoding='utf-8')
        self.tool('prepare', '--transcript', source, ok=False)
        result = self.tool('prepare')
        self.assertEqual(result['transcripts'], [])
        self.assertEqual(len(result['skipped']), 1)

    def test_rollback_preserves_post_apply_edits(self):
        _, run, _ = self.batch()
        self.tool('review', run)
        self.tool('apply', run, '--approved-by', 'owner')
        path = self.root / 'memory/team/pitfalls.md'
        path.write_bytes(path.read_bytes() + b'later edit\n')
        before = path.read_bytes()
        self.tool('rollback', run, '--approved-by', 'owner', ok=False)
        self.assertEqual(path.read_bytes(), before)

    def test_evaluation_uses_real_rows_and_reports_missing_citation_coverage(self):
        rows = [dict(case_id='a', first_pass=True, citation_correct=True, rework_count=0, duration_seconds=10),
                dict(case_id='b', first_pass=False, citation_correct=None, rework_count=2, duration_seconds=30)]
        path = self.input('results.jsonl', '\n'.join(json.dumps(row) for row in rows))
        result = self.tool('evaluate', '--results', path)
        self.assertEqual(result['cases'], 2)
        self.assertEqual(result['first_pass_rate'], 0.5)
        self.assertEqual(result['citation_correct_rate'], 1)
        self.assertEqual(result['citation_evaluated'], 1)
        self.assertEqual(result['total_rework'], 2)
        self.assertEqual(result['mean_duration_seconds'], 20)

    def test_evaluation_rejects_empty_duplicate_and_invalid_metrics(self):
        valid = dict(case_id='a', first_pass=True, citation_correct=None, rework_count=0, duration_seconds=10)
        for content in ['', json.dumps(valid) + '\n' + json.dumps(valid),
                        json.dumps(dict(valid, first_pass='true')),
                        json.dumps(dict(valid, duration_seconds=-1)),
                        json.dumps(dict(valid, duration_seconds=float('nan'))),
                        json.dumps(dict(valid, rework_count=True))]:
            path = self.input('bad-results.jsonl', content)
            self.tool('evaluate', '--results', path, ok=False)

    def test_evaluation_comparison_requires_matching_suite_environment_and_cases(self):
        base = dict(case_id='a', first_pass=False, citation_correct=False, rework_count=2,
                    duration_seconds=20, environment='same-model-tools', suite_id='v1')
        current = dict(base, first_pass=True, citation_correct=True, rework_count=0, duration_seconds=10)
        baseline = self.input('before.jsonl', json.dumps(base))
        results = self.input('after.jsonl', json.dumps(current))
        result = self.tool('evaluate', '--results', results, '--baseline', baseline)
        self.assertEqual(result['comparison']['first_pass_rate_delta'], 1)
        self.assertEqual(result['comparison']['mean_duration_seconds_delta'], -10)
        invalid = self.input('after.jsonl', json.dumps(dict(current, environment='other-model')))
        self.tool('evaluate', '--results', invalid, '--baseline', baseline, ok=False)

    def test_new_candidate_file_is_removed_by_rollback(self):
        source, run, directory = self.batch()
        target = 'memory/skills/testing.md'
        (directory / 'candidate' / target).write_text('pnpm test', encoding='utf-8')
        proposals = json.loads((directory / 'proposals.json').read_text())
        proposals.append(dict(proposals[0], id='p2', target=target))
        (directory / 'proposals.json').write_text(json.dumps(proposals))
        self.tool('review', run)
        self.tool('apply', run, '--approved-by', 'owner')
        self.assertTrue((self.root / target).exists())
        self.tool('rollback', run, '--approved-by', 'owner')
        self.assertFalse((self.root / target).exists())

    @unittest.skipUnless(os.name == 'nt', 'Windows junction test')
    def test_junction_target_cannot_escape_project(self):
        outside = Path(self.temp.name) / 'outside'
        outside.mkdir()
        junction = self.root / 'memory/team/linked'
        result = subprocess.run(['cmd', '/d', '/c', 'mklink', '/J', str(junction), str(outside)], capture_output=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.tool('write', 'memory/team/linked/escape.md', '--actor', 'codex',
                  '--input', self.input('entry.txt', 'outside'), '--expected-hash', 'missing', ok=False)
        self.assertEqual(list(outside.iterdir()), [])


if __name__ == '__main__':
    unittest.main()
