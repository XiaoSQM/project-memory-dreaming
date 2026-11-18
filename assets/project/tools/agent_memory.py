#!/usr/bin/env python3
"""Local file memory operations. Python 3.10+, standard library only."""

import argparse
from contextlib import contextmanager
from datetime import datetime, timezone
import difflib
import hashlib
import json
import math
import os
from pathlib import Path, PurePosixPath
import re
import stat
import sys
import tempfile
import uuid


class MemoryError(ValueError):
    pass


def now():
    return datetime.now(timezone.utc).isoformat(timespec='seconds')


def linked(path):
    info = path.lstat()
    return stat.S_ISLNK(info.st_mode) or bool(
        getattr(info, 'st_file_attributes', 0) & 0x400)


def safe_path(root, relative):
    text = str(relative).replace('\\', '/')
    parts = PurePosixPath(text).parts
    if not parts or text.startswith('/') or ':' in text or '\x00' in text or '..' in parts:
        raise MemoryError(f'Unsafe project-relative path: {relative}')
    path = root
    for part in parts:
        path = path / part
        if path.exists() or path.is_symlink():
            if linked(path):
                raise MemoryError(f'Links/reparse points are not supported: {path}')
    return path


def digest(data):
    return hashlib.sha256(data).hexdigest()


def current_hash(root, relative):
    path = safe_path(root, relative)
    if path.exists() and not path.is_file():
        raise MemoryError(f'Expected a regular file: {relative}')
    return digest(path.read_bytes()) if path.exists() else 'missing'


def put(root, relative, data, expected='missing'):
    path = safe_path(root, relative)
    if current_hash(root, relative) != expected:
        raise MemoryError(f'Content changed; reread and redraft: {relative}')
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(dir=path.parent, prefix='.memory-write-', delete=False) as handle:
            temporary = Path(handle.name)
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        if current_hash(root, relative) != expected:
            raise MemoryError(f'Content changed before replace: {relative}')
        os.replace(temporary, path)
    finally:
        if temporary is not None and temporary.exists():
            temporary.unlink()


def json_bytes(value):
    return (json.dumps(value, ensure_ascii=False, indent=2) + '\n').encode('utf-8')


def read_json(root, relative):
    return json.loads(safe_path(root, relative).read_text(encoding='utf-8-sig'))


@contextmanager
def lock(root):
    path = safe_path(root, '.memory-system.lock')
    try:
        descriptor = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    except FileExistsError:
        raise MemoryError('Memory writer is locked. Confirm the owning process finished before removing .memory-system.lock.') from None
    try:
        with os.fdopen(descriptor, 'w', encoding='utf-8') as handle:
            json.dump({'pid': os.getpid(), 'created_at': now()}, handle)
        yield
    finally:
        path.unlink()


def project(root):
    value = read_json(root, '.memory-system.json')
    if value.get('schema_version') != 1 or not value.get('project_id'):
        raise MemoryError('Unsupported project configuration; use the matching skill version.')
    return value


def actor_id(value):
    if not re.fullmatch(r'[a-z0-9][a-z0-9_-]{0,63}', value):
        raise MemoryError('Actor must use 1-64 lowercase letters, digits, hyphens or underscores.')
    return value


def files_under(root, relative):
    directory = safe_path(root, relative)
    found = {}
    if not directory.exists():
        return found
    for parent, directories, names in os.walk(directory, followlinks=False):
        for name in sorted(directories + names):
            path = Path(parent) / name
            rel = path.relative_to(root).as_posix()
            safe_path(root, rel)
            if path.is_file():
                found[path.relative_to(directory).as_posix()] = path.read_bytes()
            elif not path.is_dir():
                raise MemoryError(f'Unsupported file type: {rel}')
    return found


def writable(relative, actor=None):
    path = PurePosixPath(str(relative).replace('\\', '/'))
    if len(path.parts) < 3 or path.parts[0] != 'memory' or path.suffix != '.md':
        raise MemoryError('Only Markdown files below memory/team, memory/agents or memory/skills are writable.')
    area = path.parts[1]
    if area not in ('team', 'agents', 'skills'):
        raise MemoryError(f'Protected memory area: {relative}')
    if area == 'agents' and actor is not None and path != PurePosixPath('memory', 'agents', actor + '.md'):
        raise MemoryError('An actor can only write its own scratchpad.')


def write_memory(root, relative, data, expected, actor, append=False):
    actor_id(actor)
    safe_path(root, relative)
    writable(relative, actor)
    with lock(root):
        path = safe_path(root, relative)
        old = path.read_bytes() if path.exists() else b''
        if PurePosixPath(relative.replace('\\', '/')).as_posix().casefold() == 'memory/team/progress.md' and not append:
            raise MemoryError('Progress is append-only; use --append.')
        data.decode('utf-8-sig')
        put(root, relative, old + data if append else data, expected)
    return {'path': relative, 'sha256': current_hash(root, relative), 'actor': actor}


def record(root, actor, body, kind):
    actor_id(actor)
    if not body.strip():
        raise MemoryError('Cannot record an empty session.')
    identity = project(root)
    session = uuid.uuid4().hex
    metadata = {'schema_version': 1, 'project_id': identity['project_id'],
                'session_id': session, 'actor': actor, 'kind': kind,
                'visibility': 'project', 'created_at': now(),
                'summary': body.strip().splitlines()[0][:160]}
    text = '---\n' + ''.join(f'{key}: {json.dumps(value, ensure_ascii=False)}\n'
                              for key, value in metadata.items()) + '---\n\n' + body + '\n'
    relative = f'transcripts/{datetime.now(timezone.utc):%Y%m%dT%H%M%SZ}-{actor}-{session[:12]}.md'
    with lock(root):
        put(root, relative, text.encode('utf-8'))
    return {'path': relative, 'session_id': session, 'kind': kind}


def transcript_meta(data):
    text = data.decode('utf-8-sig')
    if not text.startswith('---\n') or '\n---\n' not in text[4:]:
        raise MemoryError('Transcript needs tool-generated JSON-valued frontmatter; import via record.')
    header = text[4:].split('\n---\n', 1)[0]
    return {key: json.loads(value.strip()) for key, value in
            (line.split(':', 1) for line in header.splitlines())}


def state(root):
    path = safe_path(root, 'dreaming/state.json')
    return read_json(root, 'dreaming/state.json') if path.exists() else {'processed': {}}


def prepare(root, requested):
    identity = project(root)
    with lock(root):
        processed = state(root)['processed']
        selected, skipped = [], []
        paths = requested or ['transcripts/' + name for name in sorted(files_under(root, 'transcripts'))
                              if name.endswith('.md') and name != 'README.md']
        sessions = set()
        for relative in dict.fromkeys(paths):
            try:
                path = safe_path(root, relative)
                path = path.resolve(strict=True)
                relative = path.relative_to(root).as_posix()
                if path.parent != safe_path(root, 'transcripts') or path.suffix != '.md':
                    raise MemoryError('Transcripts must be direct Markdown children of transcripts/.')
                data = path.read_bytes()
                meta = transcript_meta(data)
                if meta.get('project_id') != identity['project_id'] or meta.get('visibility') != 'project':
                    raise MemoryError('Transcript project or visibility does not match.')
                session = meta.get('session_id')
                if not isinstance(session, str) or not session or meta.get('kind') not in ('summary', 'full'):
                    raise MemoryError('Transcript identity or kind is invalid.')
                if session in sessions:
                    raise MemoryError('Duplicate session identity; not an independent session.')
                if processed.get(relative) == digest(data):
                    continue
                sessions.add(session)
                selected.append({'path': relative, 'sha256': digest(data),
                                 'session_id': session, 'kind': meta['kind'], 'data': data})
            except (MemoryError, OSError, ValueError, KeyError, TypeError) as error:
                if requested:
                    raise MemoryError(f'{relative}: {error}') from error
                skipped.append({'path': relative, 'reason': str(error)})
        if not selected:
            return {'run': None, 'transcripts': [], 'skipped': skipped, 'message': 'No new authorized transcripts.'}
        run = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ-') + uuid.uuid4().hex[:10]
        prefix = f'dreaming/runs/{run}'
        memories = {'memory/' + name: data for name, data in files_under(root, 'memory').items()}
        for relative, data in memories.items():
            put(root, f'{prefix}/base/{relative}', data)
            put(root, f'{prefix}/candidate/{relative}', data)
        for item in selected:
            put(root, f"{prefix}/transcripts/{Path(item['path']).name}", item.pop('data'))
        manifest = {'schema_version': 1, 'project_id': identity['project_id'], 'run': run,
                    'created_at': now(), 'status': 'prepared', 'transcripts': selected,
                    'processed_at_prepare': {item['path']: processed.get(item['path']) for item in selected},
                    'base_hashes': {path: digest(data) for path, data in memories.items()}}
        put(root, prefix + '/manifest.json', json_bytes(manifest))
        put(root, prefix + '/proposals.json', b'[]\n')
    return {'run': run, 'directory': prefix, 'transcripts': [s['path'] for s in selected], 'skipped': skipped}


def batch(root, run):
    if not re.fullmatch(r'[A-Za-z0-9_-]{1,80}', run):
        raise MemoryError('Invalid run ID.')
    prefix = f'dreaming/runs/{run}'
    manifest = read_json(root, prefix + '/manifest.json')
    if manifest.get('project_id') != project(root)['project_id'] or manifest.get('run') != run:
        raise MemoryError('Batch does not belong to this project.')
    return prefix, manifest


def candidate_changes(root, prefix, manifest):
    base = files_under(root, prefix + '/base')
    if {name: digest(data) for name, data in base.items()} != manifest['base_hashes']:
        raise MemoryError('Batch baseline snapshot was changed.')
    candidate = files_under(root, prefix + '/candidate')
    if set(base) - set(candidate):
        raise MemoryError('Keep historical files; mark obsolete entries instead of deleting files.')
    changes = {}
    for relative, data in candidate.items():
        safe_path(root, relative)
        if base.get(relative) == data:
            continue
        writable(relative)
        data.decode('utf-8-sig')
        if relative.casefold() == 'memory/team/progress.md' and not data.startswith(base.get(relative, b'')):
            raise MemoryError('Candidate rewrites historical progress.')
        changes[relative] = data
    return base, candidate, changes


def checked_proposals(root, prefix, manifest, changes):
    proposals = read_json(root, prefix + '/proposals.json')
    if not isinstance(proposals, list):
        raise MemoryError('proposals.json must be an array.')
    sources = {}
    for item in manifest['transcripts']:
        data = safe_path(root, prefix + '/transcripts/' + Path(item['path']).name).read_bytes()
        if digest(data) != item['sha256']:
            raise MemoryError('Transcript snapshot changed.')
        meta = transcript_meta(data)
        if meta['session_id'] != item['session_id'] or meta['project_id'] != manifest['project_id']:
            raise MemoryError('Transcript identity changed.')
        sources[item['path']] = (data.decode('utf-8-sig'), item['session_id'])
    ids, covered = set(), set()
    statistics = []
    for proposal in proposals:
        if not isinstance(proposal, dict):
            raise MemoryError('Each proposal must be an object.')
        for field in ('id', 'type', 'target', 'proposal', 'reason', 'confidence', 'evidence'):
            if field not in proposal:
                raise MemoryError(f'Proposal missing field: {field}')
        if not isinstance(proposal['id'], str) or not proposal['id'].strip() or proposal['id'] in ids:
            raise MemoryError('Proposal IDs must be unique nonempty strings.')
        ids.add(proposal['id'])
        if proposal['type'] not in ('add', 'update', 'deprecate', 'promote_to_rule') or proposal['confidence'] not in ('high', 'medium', 'low'):
            raise MemoryError('Invalid proposal type or confidence.')
        target = proposal['target']
        if not isinstance(target, str):
            raise MemoryError('Proposal target must be a project-relative path string.')
        safe_path(root, target)
        if not (target.startswith('memory/org/') and target.endswith('.md')):
            writable(target)
        if not all(isinstance(proposal[field], str) and proposal[field].strip() for field in ('proposal', 'reason')):
            raise MemoryError('Proposals need nonempty content and reasoning.')
        evidence = proposal['evidence']
        if not isinstance(evidence, list) or not evidence:
            raise MemoryError('Every proposal requires transcript evidence.')
        sessions = set()
        for item in evidence:
            if not isinstance(item, dict):
                raise MemoryError('Each evidence item must be an object with source and quote.')
            source, quote = item.get('source'), item.get('quote')
            if source not in sources or not isinstance(quote, str) or not quote.strip() or quote not in sources[source][0]:
                raise MemoryError('Evidence must quote the selected transcript verbatim.')
            sessions.add(sources[source][1])
        if proposal['type'] == 'promote_to_rule' and len(sessions) < 2:
            raise MemoryError('Rule promotion needs at least two independent sessions.')
        covered.add(target)
        statistics.append({'id': proposal['id'], 'sessions': len(sessions), 'out_of': len(sources)})
    if set(changes) - covered:
        raise MemoryError('Every candidate change needs a proposal with evidence: ' + ', '.join(sorted(set(changes) - covered)))
    return proposals, statistics


def review_data(root, prefix, manifest):
    base, candidate, changes = candidate_changes(root, prefix, manifest)
    proposals, statistics = checked_proposals(root, prefix, manifest, changes)
    frozen = {'candidate_hashes': {name: digest(data) for name, data in candidate.items()},
              'proposals_sha256': current_hash(root, prefix + '/proposals.json'),
              'manifest_sha256': current_hash(root, prefix + '/manifest.json')}
    return base, changes, proposals, statistics, frozen


def review(root, run):
    with lock(root):
        prefix, manifest = batch(root, run)
        if manifest['status'] != 'prepared':
            raise MemoryError('Only a prepared batch can be reviewed.')
        base, changes, proposals, statistics, frozen = review_data(root, prefix, manifest)
        report = [f'# Dreaming review: {run}', '', 'Status: proposed; awaiting explicit owner approval.',
                  'Evaluation: not performed by this review.', '', '## Evidence and prevalence', '']
        for proposal, stat in zip(proposals, statistics):
            report.extend([f"### {proposal['id']} — {proposal['target']}",
                           f"Type: {proposal['type']}; confidence: {proposal['confidence']}; independent sessions: {stat['sessions']}/{stat['out_of']}",
                           proposal['reason'], proposal['proposal']])
            for item in proposal['evidence']:
                report.append(f"- Source: {item['source']}; quote: {item['quote']}")
            if proposal.get('uncertainties'):
                report.append('Uncertainties: ' + str(proposal['uncertainties']))
            report.append('')
        report.extend(['## Candidate differences', ''])
        for relative, data in sorted(changes.items()):
            difference = ''.join(difflib.unified_diff(
                base.get(relative, b'').decode('utf-8-sig').splitlines(keepends=True),
                data.decode('utf-8-sig').splitlines(keepends=True),
                fromfile='base/' + relative, tofile='candidate/' + relative))
            report.extend(['```diff', difference, '```', ''])
        report.append('No candidate changes.' if not changes else 'Review all changes and supporting evidence before approval.')
        put(root, prefix + '/review.json', json_bytes(frozen), current_hash(root, prefix + '/review.json'))
        put(root, prefix + '/REVIEW.md', '\n'.join(report).encode('utf-8'), current_hash(root, prefix + '/REVIEW.md'))
    return {'run': run, 'changed_files': sorted(changes), 'report': prefix + '/REVIEW.md', 'statistics': statistics}


def ensure_baseline(root, manifest):
    live = {'memory/' + name: digest(data) for name, data in files_under(root, 'memory').items()}
    expected = manifest['base_hashes']
    for relative in sorted(set(live) | set(expected)):
        if live.get(relative) != expected.get(relative):
            raise MemoryError(f'Production memory changed; prepare and review a new batch: {relative}')


def apply(root, run, approved_by):
    if not approved_by.strip():
        raise MemoryError('Record the actual reviewer after obtaining explicit approval.')
    with lock(root):
        prefix, manifest = batch(root, run)
        if manifest['status'] != 'prepared':
            raise MemoryError('Batch is not awaiting application.')
        base, changes, _, _, frozen = review_data(root, prefix, manifest)
        if read_json(root, prefix + '/review.json') != frozen:
            raise MemoryError('Candidate or evidence changed after review; review again and obtain new approval.')
        ensure_baseline(root, manifest)
        previous_state = state(root)
        for item in manifest['transcripts']:
            current = previous_state['processed'].get(item['path'])
            if current == item['sha256'] or current != manifest['processed_at_prepare'][item['path']]:
                raise MemoryError('A source was processed after batch preparation; prepare a fresh batch.')
        receipt = {'status': 'applying', 'approved_by': approved_by, 'started_at': now(),
                   'before': {rel: digest(base[rel]) if rel in base else 'missing' for rel in changes},
                   'after': {rel: digest(data) for rel, data in changes.items()},
                   'processed_before': {item['path']: previous_state['processed'].get(item['path']) for item in manifest['transcripts']}}
        put(root, prefix + '/receipt.json', json_bytes(receipt))
        for relative, data in changes.items():
            put(root, relative, data, receipt['before'][relative])
        for item in manifest['transcripts']:
            previous_state['processed'][item['path']] = item['sha256']
        put(root, 'dreaming/state.json', json_bytes(previous_state), current_hash(root, 'dreaming/state.json'))
        receipt.update(status='applied', finished_at=now())
        put(root, prefix + '/receipt.json', json_bytes(receipt), current_hash(root, prefix + '/receipt.json'))
        manifest['status'] = 'applied'
        put(root, prefix + '/manifest.json', json_bytes(manifest), current_hash(root, prefix + '/manifest.json'))
    return {'run': run, 'status': 'applied', 'changed_files': sorted(changes), 'evaluation': 'not performed'}


def rollback(root, run, approved_by):
    if not approved_by.strip():
        raise MemoryError('Rollback requires the actual reviewer identity after approval.')
    with lock(root):
        prefix, manifest = batch(root, run)
        receipt = read_json(root, prefix + '/receipt.json')
        if receipt['status'] != 'applied':
            raise MemoryError('Automatic rollback supports completed batches only; inspect partial operations using receipt.json.')
        for relative, expected in receipt['after'].items():
            if current_hash(root, relative) != expected:
                raise MemoryError(f'Later edit detected; do not overwrite it: {relative}')
        previous_state = state(root)
        for item in manifest['transcripts']:
            if previous_state['processed'].get(item['path']) != item['sha256']:
                raise MemoryError('Transcript processing state changed in a later run.')
        before_data = {}
        for relative, expected in receipt['before'].items():
            writable(relative)
            if expected != 'missing':
                data = safe_path(root, prefix + '/base/' + relative).read_bytes()
                if digest(data) != expected:
                    raise MemoryError('Rollback snapshot changed.')
                before_data[relative] = data
        receipt['status'] = 'rolling_back'
        put(root, prefix + '/receipt.json', json_bytes(receipt), current_hash(root, prefix + '/receipt.json'))
        for relative, expected in receipt['before'].items():
            if expected == 'missing':
                safe_path(root, relative).unlink()
            else:
                put(root, relative, before_data[relative], receipt['after'][relative])
        for relative, previous in receipt['processed_before'].items():
            if previous is None:
                previous_state['processed'].pop(relative, None)
            else:
                previous_state['processed'][relative] = previous
        put(root, 'dreaming/state.json', json_bytes(previous_state), current_hash(root, 'dreaming/state.json'))
        receipt.update(status='rolled_back', rollback_by=approved_by, rolled_back_at=now())
        put(root, prefix + '/receipt.json', json_bytes(receipt), current_hash(root, prefix + '/receipt.json'))
        manifest['status'] = 'rolled_back'
        put(root, prefix + '/manifest.json', json_bytes(manifest), current_hash(root, prefix + '/manifest.json'))
    return {'run': run, 'status': 'rolled_back', 'restored_files': sorted(receipt['before'])}


def evaluation_rows(path):
    rows = []
    identities = set()
    for number, line in enumerate(path.read_text(encoding='utf-8-sig').splitlines(), 1):
        if not line.strip():
            continue
        row = json.loads(line)
        if not isinstance(row, dict) or not isinstance(row.get('case_id'), str) or not row['case_id'].strip():
            raise MemoryError(f'Invalid case_id on line {number}.')
        if row['case_id'] in identities:
            raise MemoryError(f'Duplicate case_id: {row["case_id"]}')
        identities.add(row['case_id'])
        if type(row.get('first_pass')) is not bool or (row.get('citation_correct') is not None and type(row['citation_correct']) is not bool):
            raise MemoryError('first_pass must be Boolean; citation_correct must be Boolean or null.')
        if type(row.get('rework_count')) is not int or row['rework_count'] < 0:
            raise MemoryError('rework_count must be a nonnegative integer.')
        duration = row.get('duration_seconds')
        if type(duration) not in (int, float) or not math.isfinite(duration) or duration < 0:
            raise MemoryError('duration_seconds must be a finite nonnegative number.')
        rows.append(row)
    if not rows:
        raise MemoryError('No real evaluation rows supplied; no metrics can be reported.')
    return rows


def metrics(rows):
    citations = [row['citation_correct'] for row in rows if row.get('citation_correct') is not None]
    return {'cases': len(rows), 'case_ids': sorted(row['case_id'] for row in rows),
            'first_pass_rate': sum(row['first_pass'] for row in rows) / len(rows),
            'citation_correct_rate': sum(citations) / len(citations) if citations else None,
            'citation_evaluated': len(citations),
            'total_rework': sum(row['rework_count'] for row in rows),
            'mean_duration_seconds': sum(row['duration_seconds'] for row in rows) / len(rows)}


def evaluate(results, baseline=None):
    rows = evaluation_rows(results)
    result = metrics(rows)
    result['source'] = str(results.resolve())
    if baseline:
        before_rows = evaluation_rows(baseline)
        before = {row['case_id']: row for row in before_rows}
        if set(before) != {row['case_id'] for row in rows}:
            raise MemoryError('Comparison needs identical case IDs.')
        for row in rows:
            previous = before[row['case_id']]
            for field in ('environment', 'suite_id'):
                if not row.get(field) or row[field] != previous.get(field):
                    raise MemoryError(f'Comparison needs the same explicit {field} for each case.')
            if (row.get('citation_correct') is None) != (previous.get('citation_correct') is None):
                raise MemoryError('Comparison needs the same citation evaluation coverage.')
        old = metrics(before_rows)
        comparison = {key + '_delta': result[key] - old[key]
                      for key in ('first_pass_rate', 'total_rework', 'mean_duration_seconds')}
        comparison['citation_correct_rate_delta'] = (
            result['citation_correct_rate'] - old['citation_correct_rate']
            if result['citation_correct_rate'] is not None else None)
        comparison['baseline'] = str(baseline.resolve())
        comparison['attribution'] = 'Observed differences only; causality is not established.'
        result['comparison'] = comparison
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=Path.cwd())
    commands = parser.add_subparsers(dest='command', required=True)
    commands.add_parser('status')
    hash_command = commands.add_parser('hash')
    hash_command.add_argument('path')
    write_command = commands.add_parser('write')
    write_command.add_argument('path')
    write_command.add_argument('--input', required=True, type=Path)
    write_command.add_argument('--expected-hash', required=True)
    write_command.add_argument('--actor', required=True)
    write_command.add_argument('--append', action='store_true')
    record_command = commands.add_parser('record')
    record_command.add_argument('--input', required=True, type=Path)
    record_command.add_argument('--actor', required=True)
    record_command.add_argument('--kind', choices=['summary', 'full'], default='summary')
    prepare_command = commands.add_parser('prepare')
    prepare_command.add_argument('--transcript', action='append')
    for name in ('review', 'apply', 'rollback'):
        command = commands.add_parser(name)
        command.add_argument('run')
        if name != 'review':
            command.add_argument('--approved-by', required=True)
    evaluation = commands.add_parser('evaluate')
    evaluation.add_argument('--results', type=Path, required=True)
    evaluation.add_argument('--baseline', type=Path)
    args = parser.parse_args()
    root = args.root.resolve(strict=True)
    project(root)
    if args.command == 'status':
        result = {'project': project(root), 'processed_transcripts': len(state(root)['processed']),
                  'background_scheduler': 'not configured by this tool'}
    elif args.command == 'hash':
        result = {'path': args.path, 'sha256': current_hash(root, args.path)}
    elif args.command == 'write':
        result = write_memory(root, args.path, args.input.read_bytes(), args.expected_hash, args.actor, args.append)
    elif args.command == 'record':
        result = record(root, args.actor, args.input.read_text(encoding='utf-8-sig'), args.kind)
    elif args.command == 'prepare':
        result = prepare(root, args.transcript)
    elif args.command == 'review':
        result = review(root, args.run)
    elif args.command == 'apply':
        result = apply(root, args.run, args.approved_by)
    elif args.command == 'rollback':
        result = rollback(root, args.run, args.approved_by)
    else:
        result = evaluate(args.results, args.baseline)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8')
        sys.stderr.reconfigure(encoding='utf-8')
    try:
        main()
    except (MemoryError, OSError, ValueError, KeyError, TypeError) as error:
        print(f'Error: {error}', file=sys.stderr)
        sys.exit(1)
