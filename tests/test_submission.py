import json
import zipfile

import pytest

from conftest import FakeEngine
from pokeagent_bench import submission
from pokeagent_bench.cli import main
from pokeagent_bench.core import Limits, digest, encoded, write_json
from pokeagent_bench.session import Session

# No ROM and no model. Runs are recorded and replayed with the fake engine, through the real replay code.
TASKS = ('battle-one', 'battle-two')


def plan(provider='openai-compatible', model='local-model'):
    cells = [{'id': f'cell-{index:04d}', 'task_id': task, 'category': 'battle', 'mode': 'gameplay',
              'benchmark': 'pokebench', 'score_group': task, 'provider': provider, 'model': model,
              'variant': 'default', 'repeat': 1, 'token_limit': 1000, 'decision_limit': 5,
              'fixture_sha256': digest(b'fake-state-0'), 'evaluation_spec_sha256': 'spec-' + task}
             for index, task in enumerate(TASKS, 1)]
    return {'protocol': 'catalog-batch-v3-decisions', 'benchmark': 'pokebench', 'suite': 'short',
            'cells': cells, 'cell_count': len(cells), 'held_tasks': []}


@pytest.fixture
def world(tmp_path, monkeypatch):
    """A setup folder, a finished two task suite run and a fake emulator for replay."""
    rom = tmp_path / 'red.gb'
    rom.write_bytes(b'rom')
    fixtures = tmp_path / 'data' / 'fixtures'
    run = tmp_path / 'run'
    run.mkdir()
    write_json(run / 'plan.json', plan())
    for cell in plan()['cells']:
        scenario = {'rom_sha256': digest(b'rom'), 'state_sha256': digest(b'fake-state-0'), 'task_id': cell['task_id']}
        (fixtures / cell['task_id']).mkdir(parents=True)
        write_json(fixtures / cell['task_id'] / 'scenario.json', scenario)
        (fixtures / cell['task_id'] / 'initial.state').write_bytes(b'fake-state-0')
        session = Session(FakeEngine(), run / cell['id'], scenario, limits=Limits(max_total_tokens=1000, max_model_calls=5),
                          agent={'provider': 'openai-compatible', 'model': 'local-model',
                                 'configuration': {'endpoint': 'http://gpu-box.corp.example:8000/v1'}})
        session.act('decision-1-1.1', 'a', 3, 2)
        session.act('decision-2-1.1', 'b', 3, 2)
        session.usage.update(calls=2, input_tokens=400, output_tokens=50)
        session.finish('action_budget')
        session.close()
        result = json.loads((run / cell['id'] / 'result.json').read_text())
        write_json(run / cell['id'] / 'result.json', {**result, 'state': 'finished'})
    monkeypatch.setattr('pokeagent_bench.session.RedEngine', lambda *_: FakeEngine())
    monkeypatch.setattr(submission, 'new_plan', lambda suite, fixtures, provider, model: plan(provider, model))
    monkeypatch.setattr(submission, 'select_scenario', lambda fixtures, task, variant: fixtures / task)
    monkeypatch.setattr(submission, 'scoring', lambda task: {'goal': 'first-gym', 'track': 'structured', 'score_max': 75})
    monkeypatch.setattr(submission, 'local_names', lambda: [])
    monkeypatch.setattr(submission, 'accepted_harness', lambda: [submission.this_harness()])
    monkeypatch.chdir(tmp_path)
    return {'rom': rom, 'fixtures': fixtures, 'run': run, 'bundle': tmp_path / 'bundle.zip'}


@pytest.fixture
def bundle(world):
    submission.submit(world['run'], world['bundle'], handle='octocat')
    return world['bundle']


def check(world, path=None):
    return submission.verify(path or world['bundle'], world['rom'], world['fixtures'])


def repack(path, change, *, rehash=True):
    """Rewrite a bundle the way a dishonest submitter could, keeping submit.json consistent."""
    with zipfile.ZipFile(path) as archive:
        files = {name: archive.read(name) for name in archive.namelist()}
    change(files)
    if rehash:
        summary = json.loads(files['submit.json'])
        summary['files'] = {name: digest(data) for name, data in files.items() if name != 'submit.json'}
        files['submit.json'] = encoded(summary)
    with zipfile.ZipFile(path, 'w', zipfile.ZIP_DEFLATED) as archive:
        for name, data in files.items():
            archive.writestr(name, data)


def edit(name, change):
    def apply(files):
        value = json.loads(files[name])
        change(value)
        files[name] = encoded(value)
    return apply


def test_bundle_holds_only_logs_and_results_and_verifies(world, capsys):
    submission.submit(world['run'], world['bundle'], handle='octocat')
    with zipfile.ZipFile(world['bundle']) as archive:
        names = set(archive.namelist())
        text = b''.join(archive.read(name) for name in names).decode()
    assert names == {'plan.json', 'submit.json'} | {
        f'cell-000{n}/{name}' for n in (1, 2) for name in ('manifest.json', 'actions.jsonl', 'result.json')}
    assert 'corp.example' not in text and 'platform' not in text
    printed = capsys.readouterr().out
    assert '2 x actions.jsonl' in printed and 'Endpoint host: not included' in printed
    result = check(world)
    assert result['verified'] and result['problems'] == []
    assert result['label'] == 'Community, replay verified, model unverified'
    assert result['handle'] == 'octocat' and result['summary']['completed'] == 2
    assert all(cell['replay_verified'] for cell in result['cells'])
    assert 'token counts' in result['self_reported']
    assert json.loads((world['bundle'].with_name('bundle.verified.json')).read_text())['verified']


def test_endpoint_host_needs_the_flag(world):
    submission.submit(world['run'], world['bundle'], endpoint_host=True)
    with zipfile.ZipFile(world['bundle']) as archive:
        assert json.loads(archive.read('submit.json'))['endpoint_host'] == 'gpu-box.corp.example'
        assert b':8000' not in archive.read('cell-0001/manifest.json')


def test_edited_score_fails(world, bundle):
    repack(bundle, edit('cell-0001/result.json', lambda result: result.update(score=75, completed=True)))
    result = check(world)
    assert not result['verified'] and 'differs from replay' in result['problems'][0]
    assert 'summary' not in result


def test_broken_hash_chain_fails(world, bundle):
    def change(files):
        rows = files['cell-0002/actions.jsonl'].decode().splitlines()
        row = json.loads(rows[0])
        row['action']['button'] = 'start'
        files['cell-0002/actions.jsonl'] = ('\n'.join([json.dumps(row)] + rows[1:]) + '\n').encode()
    repack(bundle, change)
    result = check(world)
    assert not result['verified'] and 'cell-0002' in result['problems'][0] and 'Broken action log' in result['problems'][0]


def test_swapped_start_state_fails(world, bundle):
    other = digest(b'easier-state')
    repack(bundle, edit('cell-0001/manifest.json', lambda manifest: (
        manifest.update(initial_sha256=other), manifest['scenario'].update(state_sha256=other))))
    assert 'Start state is not the benchmark start' in check(world)['problems'][0]
    repack(bundle, edit('plan.json', lambda plan: plan['cells'][0].update(fixture_sha256=other)))
    with pytest.raises(ValueError, match='differ from the suite: battle-one'):
        check(world)


def test_changed_scenario_fails(world, bundle):
    repack(bundle, edit('cell-0001/manifest.json', lambda manifest: manifest['scenario'].update(objective={'kind': 'easy'})))
    assert 'Scenario differs' in check(world)['problems'][0]


def test_missing_task_is_refused(world, bundle):
    def change(files):
        value = json.loads(files['plan.json'])
        value['cells'] = value['cells'][:1]
        files['plan.json'] = encoded(value)
        for name in [name for name in files if name.startswith('cell-0002/')]:
            del files[name]
    repack(bundle, change)
    with pytest.raises(ValueError, match='missing tasks of the suite: battle-two'):
        check(world)


def test_over_budget_run_fails(world, bundle):
    repack(bundle, edit('cell-0001/result.json', lambda result: result['usage'].update(calls=6)))
    assert 'more than 5 decisions' in check(world)['problems'][0]
    repack(bundle, edit('cell-0001/result.json', lambda result: result['usage'].update(calls=2, input_tokens=5000)))
    assert 'more than 1000 tokens' in check(world)['problems'][0]
    repack(bundle, edit('cell-0001/result.json', lambda result: result['usage'].update(input_tokens=400)))
    repack(bundle, edit('cell-0001/manifest.json', lambda manifest: manifest['limits'].update(max_model_calls=500)))
    assert 'more than 5 decisions' in check(world)['problems'][0]


@pytest.mark.parametrize('name', ['../evil.json', '/etc/passwd', 'cell-0001/../../x', 'cell-0001/initial.state', 'notes.txt'])
def test_archive_entries_outside_the_known_names_are_refused(world, bundle, name, tmp_path):
    repack(bundle, lambda files: files.update({name: b'{}'}))
    with pytest.raises(ValueError, match='not allowed'):
        check(world)
    assert not (tmp_path.parent / 'evil.json').exists()


def test_files_must_match_their_recorded_hashes(world, bundle):
    repack(bundle, edit('cell-0001/result.json', lambda result: result.update(score=1)), rehash=False)
    with pytest.raises(ValueError, match='do not match the hashes'):
        check(world)


def test_large_or_broken_archives_are_refused(world, bundle, monkeypatch):
    world['bundle'].with_name('junk.zip').write_bytes(b'not a zip')
    with pytest.raises(ValueError, match='not a zip'):
        check(world, world['bundle'].with_name('junk.zip'))
    monkeypatch.setattr(submission, 'UNPACKED_LIMIT', 100)
    with pytest.raises(ValueError, match='size limit'):
        check(world)
    monkeypatch.setattr(submission, 'ATTACHMENT_LIMIT', 100)
    with pytest.raises(ValueError, match='larger than'):
        check(world)


def test_only_the_accepted_harness_version_passes(world, bundle, monkeypatch):
    other = {'benchmark': 'red-v9', 'package_version': '9.0.0', 'source_sha256': 'f' * 64}
    monkeypatch.setattr(submission, 'accepted_harness', lambda: [other])
    with pytest.raises(ValueError, match=r'battle-one ran on .* Accepted: red-v9 \(package 9.0.0, source ffffffffffff\) only'):
        submission.submit(world['run'], world['bundle'].with_name('other.zip'))
    with pytest.raises(ValueError, match='This checkout is .* Accepted: red-v9'):
        check(world)
    assert not world['bundle'].with_name('other.zip').exists()


def test_a_dev_build_with_the_same_version_name_is_refused(world, bundle, monkeypatch):
    released = {**submission.this_harness(), 'source_sha256': 'e' * 64}
    monkeypatch.setattr(submission, 'accepted_harness', lambda: [released])
    with pytest.raises(ValueError, match='source eeeeeeeeeeee'):
        submission.submit(world['run'], world['bundle'].with_name('other.zip'))
    with pytest.raises(ValueError, match='Check out that release unchanged'):
        check(world)
    repack(bundle, edit('cell-0001/manifest.json', lambda manifest: manifest.update(source_sha256='e' * 64)))
    monkeypatch.setattr(submission, 'accepted_harness', lambda: [submission.this_harness()])
    result = check(world)
    assert not result['verified'] and 'cell-0001' in result['problems'][0] and 'Ran on' in result['problems'][0]


def test_an_empty_accepted_list_closes_submissions(world, bundle, monkeypatch, capsys):
    monkeypatch.setattr(submission, 'accepted_harness', lambda: [])
    message = 'They open with the frozen v0.61 release'
    with pytest.raises(ValueError, match=message):
        submission.submit(world['run'], world['bundle'].with_name('other.zip'))
    with pytest.raises(ValueError, match=message):
        check(world)
    monkeypatch.setattr('pokeagent_bench.quick_run.locate', lambda data, rom: (world['fixtures'], None, world['rom']))
    for command in (['submit', 'run'], ['verify', 'bundle.zip']):
        monkeypatch.setattr('sys.argv', ['pokebench', *command])
        assert main() == 2
        assert message in capsys.readouterr().err
    assert not world['bundle'].with_name('other.zip').exists()


def test_every_accepted_entry_needs_its_source_hash(tmp_path):
    assert all(set(entry) == set(submission.ENTRY_KEYS) for entry in submission.accepted_harness())
    path = tmp_path / 'accepted.json'
    entry = submission.this_harness()
    write_json(path, {'accepted': [entry]})
    assert submission.accepted_harness(path) == [entry]
    for bad in ({key: entry[key] for key in ('benchmark', 'package_version')}, {**entry, 'source_sha256': ''},
                {**entry, 'extra': 'x'}):
        write_json(path, {'accepted': [bad]})
        with pytest.raises(ValueError, match='source_sha256'):
            submission.accepted_harness(path)


@pytest.mark.parametrize('leak, finding', [
    ('/home/someone/runs', 'path or key shaped'), ('sk-abcdefghijklmnop1234', 'path or key shaped'),
    ('value-of-my-secret-variable', 'secret environment variable'), ('seen on Workstation7 today', 'local user or host name')])
def test_privacy_scan_stops_the_bundle(world, monkeypatch, leak, finding):
    monkeypatch.setenv('MY_PROVIDER_API_KEY', 'value-of-my-secret-variable')
    monkeypatch.setattr(submission, 'local_names', lambda: ['workstation7'])
    path = world['run'] / 'cell-0001' / 'result.json'
    write_json(path, {**json.loads(path.read_text()), 'note': leak})
    with pytest.raises(ValueError, match='Privacy scan stopped the bundle') as error:
        submission.submit(world['run'], world['bundle'])
    assert finding in str(error.value) and 'my-secret' not in str(error.value)
    assert not world['bundle'].exists()


def test_unfinished_or_foreign_folders_are_not_packed(world, tmp_path):
    path = world['run'] / 'cell-0002' / 'result.json'
    write_json(path, {**json.loads(path.read_text()), 'state': 'paused'})
    with pytest.raises(ValueError, match='1 of 2 runs are not finished: battle-two'):
        submission.submit(world['run'], world['bundle'])
    with pytest.raises(ValueError, match='not a suite run folder'):
        submission.submit(tmp_path, world['bundle'])
    with pytest.raises(ValueError, match='GitHub user name'):
        submission.collect(world['run'], handle='../x')


def test_commands_exit_nonzero_on_a_failed_bundle(world, monkeypatch, capsys):
    monkeypatch.setattr('pokeagent_bench.quick_run.locate', lambda data, rom: (world['fixtures'], None, world['rom']))
    monkeypatch.setattr('sys.argv', ['pokebench', 'submit', 'run', '--output', 'bundle.zip', '--handle', 'octocat'])
    assert main() == 0
    monkeypatch.setattr('sys.argv', ['pokebench', 'verify', 'bundle.zip'])
    assert main() == 0
    assert 'VERIFIED. 2 runs replayed' in capsys.readouterr().out
    repack(world['bundle'], edit('cell-0001/result.json', lambda result: result.update(score=75)))
    with pytest.raises(SystemExit) as stop:
        main()
    assert stop.value.code == 1 and 'NOT VERIFIED' in capsys.readouterr().out


def test_only_verified_short_reports_join_the_site_data(world, bundle, tmp_path, capsys):
    from pokeagent_bench.showcase import community_reports
    web = tmp_path / 'web'
    web.mkdir()
    report = world['bundle'].with_name('bundle.verified.json')
    result = check(world)
    submission.community_add(report, web)
    assert community_reports(web) == [result]
    assert "needs the owner's yes" in capsys.readouterr().out
    with pytest.raises(ValueError, match='already exists'):
        submission.community_add(report, web)
    for change, message in (({'suite': 'smoke'}, 'Only Short'), ({'suite': 'long'}, 'Only Short'),
                            ({'verified': False}, 'not verified'), ({'problems': ['x']}, 'not verified'),
                            ({'format': 'other'}, 'not a report'), ({'harness': {'benchmark': 'red-v9'}}, 'verified on red-v9'),
                            ({'handle': 'someone-else'}, None)):
        write_json(report, {**result, **change})
        if message is None:
            submission.community_add(report, web)
            continue
        with pytest.raises(ValueError, match=message):
            submission.community_add(report, web)
    assert sorted(path.name for path in (web / 'community').iterdir()) == [
        'octocat-local-model.json', 'someone-else-local-model.json']
