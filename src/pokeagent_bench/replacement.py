"""Validate explicitly documented infrastructure replacement attempts."""
import hashlib
import json


def checksum(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()).hexdigest()


def validate_extended_batch(protocol, batch, registered_validator):
    records = batch.get('recovery_attempts', [])
    if not isinstance(records, list):
        raise ValueError('Invalid recovery authorization list')
    cells = batch.get('cells', [])
    count = len(cells) - len(records)
    if count < 0:
        raise ValueError('Invalid recovery cell count')
    registered = {k:v for k,v in batch.items() if k != 'recovery_attempts'}
    registered['cells'] = cells[:count]
    registered_validator(protocol, registered)
    original = {c['id']:c for c in registered['cells']}
    pairs = set()
    prior = []
    for actual, record in zip(cells[count:], records, strict=True):
        payload = {k:v for k,v in record.items() if k != 'sha256'}
        if checksum(payload) != record.get('sha256') or record.get('protocol_sha256') != protocol['sha256']:
            raise ValueError('Invalid recovery authorization checksum')
        source = original.get(record.get('source_cell'))
        if source is None or source['provider'] != 'claude':
            raise ValueError('Recovery must reference an original Claude attempt')
        pair = (source['model'], source['task'])
        kind = record.get('failure_kind')
        recovery_key = (pair, kind)
        if recovery_key in pairs:
            raise ValueError('Only one documented replacement per pair and repair')
        pairs.add(recovery_key)
        for previous in prior:
            if (previous['model'], previous['task']) == pair and (previous['status'] != 'error' or
                    previous.get('budget_hold_tokens', 0) < previous['token_limit'] + protocol['in_flight_reserve']):
                raise ValueError('Previous recovery must be a held error, never a gameplay result')
        group = [c for c in original.values() if (c['model'],c['task']) == pair]
        if any(c['status'] != 'error' or c.get('budget_hold_tokens', 0) < c['token_limit'] + protocol['in_flight_reserve'] for c in group):
            raise ValueError('Recovery requires exhausted, held errors and no gameplay result')
        if kind not in ('provider_timeout', 'response_truncation', 'response_budget_v3', 'interface_v4'):
            raise ValueError('Only reviewed provider timeouts and interface failures support replacement')
        if kind == 'interface_v4':
            allowed = {('claude-sonnet-5', 'league-hard'), ('claude-sonnet-5', 'league'),
                       ('claude-sonnet-5', 'lance'), ('claude-opus-4-7', 'league-hard'),
                       ('claude-opus-4-7', 'league'), ('claude-sonnet-5-5', 'league')}
            if pair not in allowed or record.get('adapter') != {
                    'id':'claude-interface-v4', 'max_output_tokens':4096,
                    'max_decision_seconds':180, 'max_consecutive_invalid_decisions':3}:
                raise ValueError('Interface repair is limited to six reviewed incomplete pairs')
            proof = record.get('adapter_source_sha256', '')
            if len(proof) != 64 or any(c not in '0123456789abcdef' for c in proof):
                raise ValueError('Interface repair requires a bound adapter')
        if kind in ('response_truncation', 'response_budget_v3'):
            adapter = ({'id':'claude-response-headroom-v3', 'max_output_tokens':32000, 'max_decision_seconds':600}
                       if kind == 'response_budget_v3' else {'id':'claude-response-headroom-v2', 'max_output_tokens':8192})
            if record.get('adapter') != adapter:
                raise ValueError('Unknown response headroom repair')
            proof = record.get('diagnostic_result_sha256', '')
            if not isinstance(proof, str) or len(proof) != 64 or any(c not in '0123456789abcdef' for c in proof):
                raise ValueError('Response repair requires a bound diagnostic')
            diagnostic = 'forest-headroom-v3-probe-01' if kind == 'response_budget_v3' else 'forest-headroom-v2-01'
            if record.get('diagnostic_id') != diagnostic or pair != ('claude-sonnet-4-6', 'viridian-forest'):
                raise ValueError('Response repair is limited to the validated Forest case')
        for key in ('original_error_sha256', 'original_result_sha256'):
            value = record.get(key)
            if not isinstance(value, str) or len(value) != 64 or any(c not in '0123456789abcdef' for c in value):
                raise ValueError('Recovery must bind the original failure')
        suffix = {'provider_timeout':'-recovery-01', 'response_truncation':'-headroom-v2-01', 'response_budget_v3':'-headroom-v3-01', 'interface_v4':'-interface-v4-01'}[kind]
        expected_id = source['id'] + suffix
        if actual.get('id') != expected_id or record.get('id') != expected_id:
            raise ValueError('Invalid recovery identity')
        fields = ('task', 'variant', 'model', 'provider', 'effort', 'effective_effort', 'token_limit')
        if any(actual.get(k) != source.get(k) for k in fields):
            raise ValueError('Recovery changed original trial conditions')
        if actual.get('status') not in ('pending', 'running', 'finished', 'error'):
            raise ValueError('Invalid recovery status')
        prior.append(actual)
    return records
