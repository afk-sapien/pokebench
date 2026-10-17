"""Preserve comparable Long results while extending a separate cumulative run."""
import json
from pathlib import Path
import shutil

from .core import digest, encoded, write_json
from .recovery import atomic, pack, unpack


BOUNDARY_FILES = (
    'recovery.json', 'manifest.json', 'result.json', 'campaign.json', 'final.state',
    'notes.txt', 'prompt.txt', 'loop_budget.json', 'latest.png',
    'actions.jsonl', 'decisions.jsonl', 'memory.jsonl',
)


def verified_boundary(root):
    root = Path(root)
    run = root / 'run'
    result = json.loads((run / 'result.json').read_text())
    wrapper = json.loads((run / 'recovery.json').read_text())
    if digest(encoded(wrapper['payload'])) != wrapper['sha256']:
        raise ValueError('Checkpoint checksum mismatch')
    saved = unpack(wrapper['payload'])
    calls = result['usage']['calls']
    if result['state'] != 'finished' or (run / 'pending.json').exists():
        raise ValueError('Archive or extend only a finished decision boundary')
    if saved['runner']['decision_index'] != calls or saved['session']['frame'] != result['frames']:
        raise ValueError('Result and checkpoint are at different boundaries')
    if saved['session']['usage'] != {k: v for k, v in result['usage'].items() if k != 'available'}:
        raise ValueError('Reconcile terminal usage before extending')
    if saved['manifest'] != json.loads((run / 'manifest.json').read_text()):
        raise ValueError('Manifest and checkpoint disagree')
    for name, expected in saved['logs'].items():
        path = run / name
        if (digest(path.read_bytes()) if path.exists() else None) != expected:
            raise ValueError('Changed checkpoint log: ' + name)
    return result, saved


def archive_boundary(root):
    root = Path(root).resolve()
    result, _ = verified_boundary(root)
    calls = result['usage']['calls']
    target = root / 'decision-checkpoints' / f'{calls:06d}'
    if target.exists():
        index = json.loads((target / 'checkpoint-index.json').read_text())
        if index['result_sha256'] != digest((root / 'run/result.json').read_bytes()):
            raise ValueError('Existing decision checkpoint is immutable')
        for name, expected in index['files'].items():
            if digest((target / name).read_bytes()) != expected:
                raise ValueError('Archived decision checkpoint changed: ' + name)
        return target
    target.mkdir(parents=True)
    files = {}
    for name in BOUNDARY_FILES:
        source = root / 'run' / name
        if source.exists():
            shutil.copy2(source, target / name)
            files[name] = digest((target / name).read_bytes())
    write_json(target / 'checkpoint-index.json', {
        'protocol': 'long-decision-boundaries-v1', 'decisions': calls,
        'result_sha256': files['result.json'], 'files': files,
        'run_root': str(root), 'runtime': str(root / 'runtime'),
        'note': 'Retain the run folder for screenshots, fixtures and the exact runtime.',
    })
    return target


def create_continuation(parent, destination, *, additional_decisions=2000):
    parent, destination = Path(parent).resolve(), Path(destination).resolve()
    if type(additional_decisions) is not int or additional_decisions <= 0:
        raise ValueError('Additional decisions must be positive')
    if destination.exists():
        raise ValueError('Continuation destination already exists')
    result, saved = verified_boundary(parent)
    if result['stop_reason'] != 'model_call_budget':
        raise ValueError('Decision extension requires a decision-limited parent run')
    used = result['usage']['input_tokens'] + result['usage']['output_tokens']
    if used >= saved['limits']['max_total_tokens']:
        raise ValueError('No token allowance remains under the existing ceiling')
    boundary = archive_boundary(parent)
    prior = json.loads((parent / 'continuation.json').read_text()) if (parent / 'continuation.json').exists() else {}
    destination.mkdir(parents=True)
    for folder in ('run', 'runtime', 'fixtures'):
        if (parent / folder).exists():
            shutil.copytree(parent / folder, destination / folder)
    for name in ('pilot.json', 'RESUME.md', 'subscription-access.json'):
        if (parent / name).exists():
            shutil.copy2(parent / name, destination / name)
    limit = result['usage']['calls'] + additional_decisions
    record = {
        'protocol': 'long-decision-boundaries-v1',
        'origin_run_id': prior.get('origin_run_id', parent.name),
        'parent_run_id': parent.name, 'parent_checkpoint': str(boundary),
        'parent_result_sha256': digest((parent / 'run/result.json').read_bytes()),
        'start_decisions': result['usage']['calls'], 'decision_limit': limit,
        'additional_decisions': additional_decisions,
        'reported_token_limit': saved['limits']['max_total_tokens'],
        'total_token_ceiling': saved['limits']['max_total_tokens'] + result['usage'].get('unreported_token_reserve', 0),
        'policy': 'Cumulative decisions, tokens, time and stuck tracking. Only the decision limit increases. Parent result is preserved.',
    }
    saved['limits']['max_model_calls'] = limit
    saved['manifest']['limits']['max_model_calls'] = limit
    saved['manifest']['continuation'] = record
    saved['session']['reason'] = None
    run = destination / 'run'
    atomic(run / 'manifest.json', saved['manifest'])
    payload = pack(saved)
    atomic(run / 'recovery.json', {'payload': payload, 'sha256': digest(encoded(payload))})
    initial = dict(result, state='paused', stop_reason='paused')
    atomic(run / 'result.json', initial)
    (run / 'final.state').unlink(missing_ok=True)
    write_json(destination / 'continuation.json', record)
    return record
