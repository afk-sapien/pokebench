from copy import deepcopy
import json

import pytest

from pokeagent_bench import suite
from pokeagent_bench.core import digest, encoded, write_json
from pokeagent_bench.suite_report import export_report


@pytest.fixture
def archived_suite(tmp_path):
    root = tmp_path / 'old-suite'
    fixture = root / 'fixtures/league'
    fixture.mkdir(parents=True)
    (fixture / 'initial.state').write_bytes(b'old-state')
    (fixture / 'preview.png').write_bytes(b'old-preview')
    write_json(fixture / 'scenario.json', {
        'preview_sha256': digest(b'old-preview'), 'objective': {'description': 'Become Champion'}})
    write_json(fixture / 'reference-commands.json', [])
    original = {'definition': suite.LEAGUE_DEFINITION,
                'definition_sha256': digest(encoded(suite.LEAGUE_DEFINITION)),
                'status': 'verified', 'rom_sha256': digest(b'rom'),
                'core': {'version': 'old-core', 'source_sha256': 'old-hash'},
                'fixtures': {'league': {
                    'scenario': 'fixtures/league', 'state_sha256': digest(b'old-state'),
                    'manifest_sha256': digest((fixture / 'scenario.json').read_bytes()),
                    'reference_commands_sha256': digest(encoded([])),
                    'limits': suite.limits(suite.LEAGUE_TASK),
                    'reference': {'verified': True, 'score': 1},
                    'negative': {'verified': True, 'score': 0}}}}
    write_json(root / 'suite.json', original)
    return root


def test_core_upgrade_keeps_reports_readable_but_blocks_new_runs(archived_suite, tmp_path):
    with pytest.raises(ValueError, match='Core runtime changed'):
        suite.plan(archived_suite, ['model'], 1)
    output = tmp_path / 'report.html'
    export_report(archived_suite, None, output)
    assert 'Become Champion' in output.read_text()
    fixture = archived_suite / 'fixtures/league/initial.state'
    fixture.write_bytes(b'tampered')
    with pytest.raises(ValueError, match='Fixture or budget changed'):
        export_report(archived_suite, None, output)


def test_artifact_only_validation_cannot_run_emulation(archived_suite, tmp_path):
    for kwargs in [{'rom': tmp_path / 'rom'}, {'replay_references': True}]:
        with pytest.raises(ValueError, match='requires the matching Core'):
            suite.validate(archived_suite, require_runtime=False, **kwargs)


def test_revalidation_uses_same_sources_and_preserves_original(archived_suite, tmp_path, monkeypatch):
    before = (archived_suite / 'suite.json').read_bytes()
    rom = tmp_path / 'rom'
    rom.write_bytes(b'rom')
    output = tmp_path / 'new-suite'
    calls = []
    def prepare(rom_arg, bindings, destination, suite_id):
        calls.append((rom_arg, json.loads(bindings.read_text()), destination, suite_id))
        destination.mkdir()
        result = deepcopy(json.loads(before))
        result['core'] = {'version': 'new-core'}
        return result
    monkeypatch.setattr(suite, 'prepare', prepare)
    result = suite.revalidate(archived_suite, rom, output)
    assert len(calls) == 1
    assert calls[0][1] == {'league': {
        'scenario': str(archived_suite / 'fixtures/league'),
        'reference': str(archived_suite / 'fixtures/league/reference')}}
    assert calls[0][3] == 'red-league-v1'
    assert result['revalidated_from']['suite_sha256'] == digest(before)
    assert result['core']['version'] == 'new-core'
    assert (archived_suite / 'suite.json').read_bytes() == before
    rom.write_bytes(b'wrong-rom')
    with pytest.raises(ValueError, match='Suite ROM mismatch'):
        suite.revalidate(archived_suite, rom, tmp_path / 'wrong')
    assert len(calls) == 1


def test_revalidation_cli_contract():
    from pokeagent_bench.cli import parser
    args = parser().parse_args(['suite', 'revalidate', '--suite', 'old', '--rom', 'red.gb', '--output', 'new'])
    assert args.suite_command == 'revalidate'
    assert str(args.output) == 'new'
