"""Preserve comparable Long results while extending a separate cumulative run."""
import json
from pathlib import Path
import shutil

from .core import digest, encoded, write_json
from .recovery import atomic, pack, unpack


BOUNDARY_FILES = (
    'recovery.json', 'manifest.json', 'result.json', 'campaign.json', 'final.state',
    'notes.txt', 'prompt.txt', 'loop_budget.json', 'milestone_budget.json', 'latest.png',
    'actions.jsonl', 'decisions.jsonl', 'memory.jsonl',
)
# Every extension adds exactly one chunk of decisions.
CHUNK_DECISIONS = 2000
# Each chunk gets the first chunk's allowance of these, on top of what the run has used.
CHUNK_ALLOWANCES = ('max_total_tokens', 'max_wall_seconds', 'max_frames', 'max_actions')


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


def first_chunk_allowance(parent):
    """Follow the extension chain back to the first chunk and return its spending allowance."""
    manifest = json.loads((parent / 'run/manifest.json').read_text())
    while (parent / 'continuation.json').exists():
        record = json.loads((parent / 'continuation.json').read_text())
        if 'chunk_allowance' in record:
            return record['chunk_allowance']
        checkpoint = Path(record['parent_checkpoint'])
        manifest = json.loads((checkpoint / 'manifest.json').read_text())
        parent = Path(json.loads((checkpoint / 'checkpoint-index.json').read_text())['run_root'])
    return {key: manifest['limits'][key] for key in CHUNK_ALLOWANCES}


def create_continuation(parent, destination):
    """Add one 2000-decision chunk to a run that stopped on its decision cap.

    The chunk gets the first chunk's allowance of tokens, active time, frames and actions on top of what
    the run has used. The no-progress and no-milestone guards count across chunks, so a run that a guard
    stopped never gets another chunk.
    """
    parent, destination = Path(parent).resolve(), Path(destination).resolve()
    if destination.exists():
        raise ValueError('Continuation destination already exists')
    result, saved = verified_boundary(parent)
    if result['stop_reason'] != 'model_call_budget' or result['usage']['calls'] != saved['limits']['max_model_calls']:
        raise ValueError('Only a run that stopped on its decision cap gets another chunk, '
                         f"not one that stopped on {result['stop_reason']}")
    allowance = first_chunk_allowance(parent)
    boundary = archive_boundary(parent)
    prior = json.loads((parent / 'continuation.json').read_text()) if (parent / 'continuation.json').exists() else {}
    destination.mkdir(parents=True)
    for folder in ('run', 'runtime', 'fixtures'):
        if (parent / folder).exists():
            shutil.copytree(parent / folder, destination / folder)
    for name in ('pilot.json', 'RESUME.md', 'subscription-access.json'):
        if (parent / name).exists():
            shutil.copy2(parent / name, destination / name)
    used = {'max_total_tokens': result['usage']['input_tokens'] + result['usage']['output_tokens'],
            'max_wall_seconds': saved['elapsed'], 'max_frames': saved['session']['frame'],
            'max_actions': saved['session']['actions']}
    limits = {key: used[key] + allowance[key] for key in CHUNK_ALLOWANCES}
    limits['max_model_calls'] = result['usage']['calls'] + CHUNK_DECISIONS
    record = {
        'protocol': 'long-decision-boundaries-v1',
        'origin_run_id': prior.get('origin_run_id', parent.name),
        'parent_run_id': parent.name, 'parent_checkpoint': str(boundary),
        'parent_result_sha256': digest((parent / 'run/result.json').read_bytes()),
        'start_decisions': result['usage']['calls'], 'decision_limit': limits['max_model_calls'],
        'additional_decisions': CHUNK_DECISIONS, 'chunk_allowance': allowance,
        'reported_token_limit': limits['max_total_tokens'],
        'total_token_ceiling': limits['max_total_tokens'] + result['usage'].get('unreported_token_reserve', 0),
        'policy': 'One more 2000-decision chunk for a run that stopped on its decision cap. The chunk gets the '
                  'first chunk\'s token, time, frame and action allowance on top of what was used. '
                  'The no-progress and no-milestone guards count across chunks. Parent result is preserved.',
    }
    saved['limits'].update(limits)
    saved['manifest']['limits'].update(limits)
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
