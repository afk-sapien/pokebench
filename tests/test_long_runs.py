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
    limits = {'max_model_calls': 2000, 'max_total_tokens': 29680000, 'max_loop_tokens': 2000000,
              'max_milestone_tokens': 10000000, 'max_wall_seconds': 86400, 'max_frames': 10000000,
              'max_actions': 150000}
    manifest = {'limits': limits.copy()}
    result = {'state': 'finished', 'stop_reason': 'model_call_budget', 'frames': 50,
              'usage': dict(usage, available=True), 'score': 210, 'achievements': []}
    (run / 'actions.jsonl').write_text('recorded action\n')
    saved = {'manifest': manifest, 'limits': limits, 'elapsed': 100,
             'session': {'frame': 50, 'actions': 40, 'usage': usage, 'reason': None, 'notes': 'remember Cut'},
             'runner': {'decision_index': 2000, 'loop_state': {'tokens_without_progress': 12}},
             'engine': b'game state', 'logs': {'actions.jsonl': digest((run / 'actions.jsonl').read_bytes())}}
    payload = pack(saved)
    write_json(run / 'recovery.json', {'payload': payload, 'sha256': digest(encoded(payload))})
    write_json(run / 'manifest.json', manifest)
    write_json(run / 'result.json', result)
    (run / 'final.state').write_bytes(b'game state')
    return root


def test_extension_adds_one_chunk_with_its_own_allowance_and_keeps_memory_and_guards(tmp_path):
    parent = parent_run(tmp_path)
    original = {p.name: p.read_bytes() for p in (parent / 'run').iterdir()}
    destination = tmp_path / 'long-v068-astra-4k'
    record = create_continuation(parent, destination)
    assert {p.name: p.read_bytes() for p in (parent / 'run').iterdir()} == original
    saved = unpack(json.loads((destination / 'run/recovery.json').read_text())['payload'])
    # The chunk gets the first chunk's allowance on top of what was used: 21K tokens, 100 s, 50 frames, 40 actions.
    expected = {'max_model_calls': 4000, 'max_total_tokens': 21000 + 29680000, 'max_wall_seconds': 100 + 86400,
                'max_frames': 50 + 10000000, 'max_actions': 40 + 150000}
    assert {key: saved['limits'][key] for key in expected} == expected
    assert saved['manifest']['limits'] == saved['limits']
    # The guards keep their limits and their counts.
    assert (saved['limits']['max_loop_tokens'], saved['limits']['max_milestone_tokens']) == (2000000, 10000000)
    assert saved['runner']['loop_state']['tokens_without_progress'] == 12
    assert saved['session']['usage']['calls'] == 2000
    assert saved['session']['usage']['unreported_token_reserve'] == 320000
    assert saved['session']['notes'] == 'remember Cut'
    assert saved['engine'] == b'game state'
    assert record['chunk_allowance'] == {'max_total_tokens': 29680000, 'max_wall_seconds': 86400,
                                         'max_frames': 10000000, 'max_actions': 150000}
    assert record['total_token_ceiling'] == 21000 + 30000000
    assert record['additional_decisions'] == 2000
    assert (destination / 'runtime/frozen.py').read_text() == 'original runtime'
    assert Path(record['parent_checkpoint'], 'recovery.json').exists()
    with pytest.raises(ValueError, match='already exists'):
        create_continuation(parent, destination)


@pytest.mark.parametrize('reason', ['loop_token_budget', 'milestone_token_budget', 'token_budget', 'wall_budget'])
def test_only_a_decision_capped_run_gets_another_chunk(tmp_path, reason):
    root = parent_run(tmp_path)
    path = root / 'run/result.json'
    write_json(path, dict(json.loads(path.read_text()), stop_reason=reason))
    with pytest.raises(ValueError, match='decision cap'):
        create_continuation(root, tmp_path / 'new')
    assert not (tmp_path / 'new').exists()
    assert not (root / 'decision-checkpoints').exists()


def finish_chunk(root, calls, input_tokens):
    """Mark an extension as finished on its decision cap with the given cumulative usage."""
    run = root / 'run'
    saved = unpack(json.loads((run / 'recovery.json').read_text())['payload'])
    saved['session']['usage'].update(calls=calls, input_tokens=input_tokens)
    saved['runner']['decision_index'] = calls
    payload = pack(saved)
    write_json(run / 'recovery.json', {'payload': payload, 'sha256': digest(encoded(payload))})
    result = json.loads((run / 'result.json').read_text())
    result.update(state='finished', stop_reason='model_call_budget', usage=dict(saved['session']['usage'], available=True))
    write_json(run / 'result.json', result)


def test_later_chunks_reuse_the_first_chunk_allowance_even_after_an_older_record(tmp_path):
    origin = parent_run(tmp_path)
    second = tmp_path / 'long-v068-astra-4k'
    create_continuation(origin, second)
    # Published extensions have no chunk_allowance and much larger caps, so the chain leads back to the origin.
    record = json.loads((second / 'continuation.json').read_text())
    write_json(second / 'continuation.json', {k: v for k, v in record.items() if k != 'chunk_allowance'})
    wrapper = json.loads((second / 'run/recovery.json').read_text())
    saved = unpack(wrapper['payload'])
    for limits in (saved['limits'], saved['manifest']['limits']):
        limits['max_total_tokens'] = 10 ** 12
    payload = pack(saved)
    write_json(second / 'run/recovery.json', {'payload': payload, 'sha256': digest(encoded(payload))})
    write_json(second / 'run/manifest.json', saved['manifest'])
    finish_chunk(second, 4000, 25_000_000)
    third = tmp_path / 'long-v072-astra-6k'
    assert create_continuation(second, third)['reported_token_limit'] == 25_001_000 + 29680000
    finish_chunk(third, 6000, 50_000_000)
    record = create_continuation(third, tmp_path / 'long-v072-astra-8k')
    assert (record['decision_limit'], record['reported_token_limit']) == (8000, 50_001_000 + 29680000)
    assert record['chunk_allowance']['max_total_tokens'] == 29680000
    assert record['origin_run_id'] == 'long-v067-astra'


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
