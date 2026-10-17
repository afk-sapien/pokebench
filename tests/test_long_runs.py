import json
from pathlib import Path

import pytest

from pokeagent_bench.core import digest, encoded, write_json
from pokeagent_bench.long_runs import archive_boundary, create_continuation
from pokeagent_bench.recovery import pack, unpack
from pokeagent_bench.showcase import long_snapshot


def parent_run(tmp_path):
    root = tmp_path / 'long-v067-astra'
    run = root / 'run'
    run.mkdir(parents=True)
    (root / 'runtime').mkdir()
    (root / 'runtime/frozen.py').write_text('original runtime')
    write_json(root / 'pilot.json', {})
    usage = {'calls': 2000, 'input_tokens': 20000, 'output_tokens': 1000,
             'accounting_complete': False, 'unreported_token_reserve': 320000}
    limits = {'max_model_calls': 2000, 'max_total_tokens': 29680000,
              'max_loop_tokens': 2000000, 'max_wall_seconds': 86400}
    manifest = {'limits': limits.copy()}
    result = {'state': 'finished', 'stop_reason': 'model_call_budget', 'frames': 50,
              'usage': dict(usage, available=True), 'score': 210, 'achievements': []}
    (run / 'actions.jsonl').write_text('recorded action\n')
    saved = {'manifest': manifest, 'limits': limits, 'elapsed': 100,
             'session': {'frame': 50, 'usage': usage, 'reason': None, 'notes': 'remember Cut'},
             'runner': {'decision_index': 2000, 'loop_state': {'tokens_without_progress': 12}},
             'engine': b'game state', 'logs': {'actions.jsonl': digest((run / 'actions.jsonl').read_bytes())}}
    payload = pack(saved)
    write_json(run / 'recovery.json', {'payload': payload, 'sha256': digest(encoded(payload))})
    write_json(run / 'manifest.json', manifest)
    write_json(run / 'result.json', result)
    (run / 'final.state').write_bytes(b'game state')
    return root


def test_extension_preserves_parent_memory_usage_and_other_limits(tmp_path):
    parent = parent_run(tmp_path)
    original = {p.name: p.read_bytes() for p in (parent / 'run').iterdir()}
    destination = tmp_path / 'long-v068-astra-4k'
    record = create_continuation(parent, destination)
    assert {p.name: p.read_bytes() for p in (parent / 'run').iterdir()} == original
    saved = unpack(json.loads((destination / 'run/recovery.json').read_text())['payload'])
    assert saved['limits']['max_model_calls'] == 4000
    assert saved['limits']['max_total_tokens'] == 29680000
    assert saved['limits']['max_loop_tokens'] == 2000000
    assert saved['session']['usage']['calls'] == 2000
    assert saved['session']['usage']['unreported_token_reserve'] == 320000
    assert saved['session']['notes'] == 'remember Cut'
    assert saved['runner']['loop_state']['tokens_without_progress'] == 12
    assert saved['engine'] == b'game state'
    assert record['total_token_ceiling'] == 30000000
    assert (destination / 'runtime/frozen.py').read_text() == 'original runtime'
    assert Path(record['parent_checkpoint'], 'recovery.json').exists()
    with pytest.raises(ValueError, match='already exists'):
        create_continuation(parent, destination)


@pytest.mark.parametrize('failure', ['pending', 'changed_log', 'usage'])
def test_extension_rejects_uncertain_boundary(tmp_path, failure):
    root = parent_run(tmp_path)
    if failure == 'pending':
        (root / 'run/pending.json').write_text('{}')
    elif failure == 'changed_log':
        (root / 'run/actions.jsonl').write_text('uncommitted action')
    else:
        p = root / 'run/result.json'
        result = json.loads(p.read_text())
        result['usage']['input_tokens'] += 1
        write_json(p, result)
    with pytest.raises(ValueError):
        create_continuation(root, tmp_path / 'new')
    assert not (tmp_path / 'new').exists()


def test_boundary_archive_rejects_overwrite_or_tampering(tmp_path):
    root = parent_run(tmp_path)
    boundary = archive_boundary(root)
    assert archive_boundary(root) == boundary
    (boundary / 'final.state').write_bytes(b'changed')
    with pytest.raises(ValueError, match='changed'):
        archive_boundary(root)


def test_extended_score_never_replaces_common_allowance(tmp_path):
    parent = parent_run(tmp_path)
    destination = tmp_path / 'long-v068-astra-4k'
    create_continuation(parent, destination)
    p = destination / 'run/result.json'
    result = json.loads(p.read_text())
    result.update(score=400, state='running')
    result['usage']['calls'] = 2800
    write_json(p, result)
    web = tmp_path / 'web'
    web.mkdir()
    (web / (destination.name + '.html')).write_text('live')
    row = next(r for r in long_snapshot(tmp_path, web) if r['id'] == 'astra')
    assert row['score'] == 210
    assert row['decisions'] == 2000
    assert row['decision_limit'] == 2000
    assert row['extensions'][0]['score'] == 400
    assert row['extensions'][0]['decisions'] == 2800
    assert row['extensions'][0]['decision_limit'] == 4000
    assert row['extensions'][0]['state'] == 'running'
