from copy import deepcopy

import pytest

from pokeagent_bench import release
from pokeagent_bench.replacement import checksum, validate_extended_batch
from test_release import register


def replacement(tmp_path, monkeypatch):
    root, _, _ = register(tmp_path, monkeypatch)
    protocol = release.read(root / 'protocol.json')
    batch = release.read(root / 'batch.json')
    group = [c for c in batch['cells'] if c['provider'] == 'claude' and c['task'] == 'starter']
    for cell in group:
        cell.update(status='error', budget_hold_tokens=cell['token_limit'] + protocol['in_flight_reserve'])
    source = group[0]
    child = {k:v for k,v in source.items() if k != 'budget_hold_tokens'}
    child.update(id=source['id'] + '-recovery-01', status='pending')
    record = {'id':child['id'], 'source_cell':source['id'], 'protocol_sha256':protocol['sha256'],
              'failure_kind':'provider_timeout', 'original_error_sha256':'a'*64, 'original_result_sha256':'b'*64}
    record['sha256'] = checksum(record)
    batch['recovery_attempts'] = [record]
    batch['cells'].append(child)
    return protocol, batch, source, child


def test_timeout_replacement_preserves_original_registration_and_allows_finished_loss(tmp_path, monkeypatch):
    protocol, batch, source, child = replacement(tmp_path, monkeypatch)
    release.validate_batch(protocol, batch)
    assert source['status'] == 'error'
    child['status'] = 'finished'
    release.validate_batch(protocol, batch)


@pytest.mark.parametrize('change', ['model', 'task', 'variant', 'token_limit', 'effort', 'id'])
def test_replacement_cannot_change_conditions(tmp_path, monkeypatch, change):
    protocol, batch, source, child = replacement(tmp_path, monkeypatch)
    child[change] = 99 if isinstance(child[change], int) else 'changed'
    with pytest.raises(ValueError):
        release.validate_batch(protocol, batch)


@pytest.mark.parametrize('status', ['finished', 'pending', 'running'])
def test_replacement_cannot_repeat_gameplay_or_bypass_unused_attempts(tmp_path, monkeypatch, status):
    protocol, batch, source, child = replacement(tmp_path, monkeypatch)
    source['status'] = status
    with pytest.raises(ValueError, match='exhausted'):
        release.validate_batch(protocol, batch)


def test_replacement_requires_full_failure_hold_and_integrity(tmp_path, monkeypatch):
    protocol, batch, source, child = replacement(tmp_path, monkeypatch)
    source['budget_hold_tokens'] = 1
    with pytest.raises(ValueError, match='held errors'):
        release.validate_batch(protocol, batch)
    source['budget_hold_tokens'] = source['token_limit'] + protocol['in_flight_reserve']
    batch['recovery_attempts'][0]['original_result_sha256'] = 'c'*64
    with pytest.raises(ValueError, match='checksum'):
        release.validate_batch(protocol, batch)


def test_replacement_refuses_interface_errors_and_second_replacement(tmp_path, monkeypatch):
    protocol, batch, source, child = replacement(tmp_path, monkeypatch)
    record = batch['recovery_attempts'][0]
    record['failure_kind'] = 'outside_tool'
    record['sha256'] = checksum({k:v for k,v in record.items() if k != 'sha256'})
    with pytest.raises(ValueError, match='timeouts'):
        release.validate_batch(protocol, batch)
    record['failure_kind'] = 'provider_timeout'
    record['sha256'] = checksum({k:v for k,v in record.items() if k != 'sha256'})
    batch['recovery_attempts'].append(deepcopy(record))
    batch['cells'].append(deepcopy(child))
    with pytest.raises(ValueError, match='one documented'):
        release.validate_batch(protocol, batch)


def test_frozen_validator_adapter_validates_original_prefix(tmp_path, monkeypatch):
    protocol, batch, source, child = replacement(tmp_path, monkeypatch)
    validate_extended_batch(protocol, batch, release._validate_registered_batch)
    batch['cells'][0]['token_limit'] += 1
    with pytest.raises(ValueError, match='configuration changed'):
        validate_extended_batch(protocol, batch, release._validate_registered_batch)


def test_public_snapshot_keeps_original_errors_and_counts_replacement(tmp_path):
    from test_public_site import release_files
    from test_release import outcome
    from pokeagent_bench.core import digest, encoded, write_json
    from pokeagent_bench.public_site import release_snapshot
    root = tmp_path / 'release'
    protocol, summary = release_files(root)
    protocol.pop('sha256')
    protocol['in_flight_reserve'] = 100000
    protocol['sha256'] = digest(encoded(protocol))
    cells = release.plan(protocol['tasks'], protocol['models'], protocol['variants'])
    group = [c for c in cells if c['provider'] == 'claude' and c['task'] == 'first']
    for cell in group:
        cell.update(status='error', budget_hold_tokens=1100000)
    source = group[0]
    path = root / 'runs' / source['id']
    path.mkdir(parents=True)
    write_json(path / 'result.json', outcome(complete_accounting=False, reason='provider_error'))
    write_json(path / 'error.json', {'message':'Claude decision timed out'})
    child = {k:v for k,v in source.items() if k != 'budget_hold_tokens'}
    child.update(id=source['id']+'-recovery-01', status='finished', replay={'verified':True})
    result = root / 'runs' / child['id'] / 'result.json'
    result.parent.mkdir()
    write_json(result, outcome(completed=True, reason='completed'))
    child['result_sha256'] = digest(result.read_bytes())
    record = {'id':child['id'], 'source_cell':source['id'], 'protocol_sha256':protocol['sha256'],
              'failure_kind':'provider_timeout', 'original_error_sha256':digest((path/'error.json').read_bytes()),
              'original_result_sha256':digest((path/'result.json').read_bytes())}
    record['sha256'] = checksum(record)
    cells.append(child)
    write_json(root/'protocol.json', protocol)
    write_json(root/'batch.json', {'protocol_sha256':protocol['sha256'], 'cells':cells, 'recovery_attempts':[record]})
    summary.update(protocol_sha256=protocol['sha256'], planned=len(cells), attempts=[
        {**c, 'tokens':40, 'completed':True if c is child else None, 'replay_verified':c is child,
         'accounting_complete':c is child} for c in cells])
    write_json(root/'release-summary.json', summary)
    _, public = release_snapshot(root)
    assert public['finished'] == 1
    assert public['errors'] == 2
    assert public['attempts'][-1]['recovery_of'] == source['id']
    summary['attempts'][-1]['variant'] = 2
    write_json(root/'release-summary.json', summary)
    with pytest.raises(ValueError, match='differs from batch'):
        release_snapshot(root)


def test_headroom_repair_is_limited_to_validated_case_and_never_repeats_a_result(tmp_path, monkeypatch):
    protocol, batch, source, child = replacement(tmp_path, monkeypatch)
    record = batch['recovery_attempts'][0]
    record.update(failure_kind='response_truncation', id=source['id']+'-headroom-v2-01',
                  adapter={'id':'claude-response-headroom-v2','max_output_tokens':8192},
                  diagnostic_id='forest-headroom-v2-01', diagnostic_result_sha256='a'*64)
    child['id'] = record['id']
    record['sha256'] = checksum({k:v for k,v in record.items() if k != 'sha256'})
    with pytest.raises(ValueError, match='validated Forest case'):
        release.validate_batch(protocol, batch)
    record['adapter']['max_output_tokens'] = 16000
    record['sha256'] = checksum({k:v for k,v in record.items() if k != 'sha256'})
    with pytest.raises(ValueError, match='Unknown response'):
        release.validate_batch(protocol, batch)


@pytest.mark.parametrize('version', [2, 3])
def test_validated_headroom_trial_requires_all_earlier_recoveries_to_be_held_errors(tmp_path, monkeypatch, version):
    protocol, batch, source, child = replacement(tmp_path, monkeypatch)
    old_model = source['model']
    for model in protocol['models']:
        if model['model'] == old_model:
            model['model'] = 'claude-sonnet-4-6'
    for task in protocol['tasks']:
        if task['id'] == 'starter':
            task['id'] = 'viridian-forest'
    protocol['sha256'] = checksum({k:v for k,v in protocol.items() if k != 'sha256'})
    batch['protocol_sha256'] = protocol['sha256']
    for cell in batch['cells']:
        if cell['model'] == old_model:
            cell['model'] = 'claude-sonnet-4-6'
            cell['effective_effort'] = 'medium'
        if cell['task'] == 'starter':
            cell['task'] = 'viridian-forest'
    record = batch['recovery_attempts'][0]
    record['protocol_sha256'] = protocol['sha256']
    record['sha256'] = checksum({k:v for k,v in record.items() if k != 'sha256'})
    child.update(status='error', budget_hold_tokens=child['token_limit']+protocol['in_flight_reserve'])
    second = {k:v for k,v in child.items() if k != 'budget_hold_tokens'}
    second.update(id=source['id']+'-headroom-v2-01', status='pending')
    repair = {**record, 'id':second['id'], 'failure_kind':'response_truncation',
              'adapter':{'id':'claude-response-headroom-v2','max_output_tokens':8192},
              'diagnostic_id':'forest-headroom-v2-01', 'diagnostic_result_sha256':'a'*64}
    if version == 3:
        second['id'] = source['id']+'-headroom-v3-01'
        repair.update(id=second['id'], failure_kind='response_budget_v3',
                      adapter={'id':'claude-response-headroom-v3','max_output_tokens':32000,'max_decision_seconds':600},
                      diagnostic_id='forest-headroom-v3-probe-01')
    repair['sha256'] = checksum({k:v for k,v in repair.items() if k != 'sha256'})
    batch['cells'].append(second)
    batch['recovery_attempts'].append(repair)
    release.validate_batch(protocol, batch)
    child['status'] = 'finished'
    with pytest.raises(ValueError, match='never a gameplay result'):
        release.validate_batch(protocol, batch)


def test_interface_repair_only_allows_missing_reviewed_pairs(tmp_path, monkeypatch):
    protocol, batch, source, child = replacement(tmp_path, monkeypatch)
    old_model = source['model']
    for model in protocol['models']:
        if model['model'] == old_model:
            model['model'] = 'claude-sonnet-5'
    for task in protocol['tasks']:
        if task['id'] == 'starter':
            task['id'] = 'lance'
    for cell in batch['cells']:
        if cell['model'] == old_model:
            cell.update(model='claude-sonnet-5', effective_effort='medium')
        if cell['task'] == 'starter':
            cell['task'] = 'lance'
    protocol['sha256'] = checksum({k:v for k,v in protocol.items() if k != 'sha256'})
    batch['protocol_sha256'] = protocol['sha256']
    record = batch['recovery_attempts'][0]
    child['id'] = source['id']+'-interface-v4-01'
    record.update(id=child['id'], protocol_sha256=protocol['sha256'], failure_kind='interface_v4',
                  adapter={'id':'claude-interface-v4', 'max_output_tokens':4096,
                           'max_decision_seconds':180, 'max_consecutive_invalid_decisions':3},
                  adapter_source_sha256='c'*64)
    record['sha256'] = checksum({k:v for k,v in record.items() if k != 'sha256'})
    release.validate_batch(protocol, batch)
    source['status'] = 'finished'
    with pytest.raises(ValueError, match='exhausted'):
        release.validate_batch(protocol, batch)
    source['status'] = 'error'
    record['adapter']['max_output_tokens'] = 32000
    record['sha256'] = checksum({k:v for k,v in record.items() if k != 'sha256'})
    with pytest.raises(ValueError, match='six reviewed'):
        release.validate_batch(protocol, batch)
