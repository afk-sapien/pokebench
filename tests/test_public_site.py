import base64
import hashlib
import io
import json
import shutil
import subprocess

from PIL import Image, PngImagePlugin
import pytest

from pokeagent_bench.public_site import REPLAY, export_public, png, public_text, replay_payload, safe_metadata


def screenshot():
    stream = io.BytesIO()
    metadata = PngImagePlugin.PngInfo()
    metadata.add_text('private', '/home/person/private-token')
    Image.new('RGB', (160, 144), 'green').save(stream, format='PNG', pnginfo=metadata)
    return 'data:image/png' + chr(59) + 'base64,' + base64.b64encode(stream.getvalue()).decode()


def test_png_reencoding_drops_metadata():
    value = png(screenshot())
    raw = base64.b64decode(value.split(',')[1])
    assert b'/home/' not in raw
    assert Image.open(io.BytesIO(raw)).info == {}
    with pytest.raises(ValueError):
        png('data:image/svg+xml,unsafe')


@pytest.mark.parametrize('value', ['/home/user/private', 'file:///tmp/x', '127.0.0.1:8942', 'api_key=oops', 'session_id=secret'])
def test_private_strings_fail_closed(value):
    with pytest.raises(ValueError):
        public_text(value)


def replay(path, model='gpt-6-astra'):
    run = {'id': 'cell-1', 'model': model, 'completed': True, 'plan': '/home/private',
           'images': {'image': screenshot()}, 'steps': [{'decision': 1, 'before_frame': 0,
               'after_frame': 8, 'tokens': 40, 'cumulative_tokens': 40, 'before': 'image', 'after': 'image',
               'plan': 'api_key=private', 'gameplay_input': {'secret': 'do not publish'},
               'actions': [{'button': 'a', 'hold_frames': 8, 'release_frames': 0, 'private': 'secret'}]}]}
    path.write_text('<script id="data" type="application/json">'+json.dumps({'runs': [run]})+'</script><script>private executable</script>')


def test_replay_is_allowlisted_and_bound_to_attempt(tmp_path):
    path = tmp_path/'replay.html'
    replay(path)
    attempt = {'id': 'cell-1', 'model': 'gpt-6-astra', 'completed': True}
    payload = replay_payload(path, attempt)
    encoded = json.dumps(payload)
    assert 'private' not in encoded
    assert 'gameplay_input' not in encoded
    assert payload['steps']['actions'] == [[['a', 8, 0, 1]]]
    with pytest.raises(ValueError, match='does not match'):
        replay_payload(path, {**attempt, 'model': 'other'})


def shot(colour, size=(160, 144)):
    stream = io.BytesIO()
    image = Image.new('RGB', size, 'white')
    image.paste(colour, (0, 0, size[0] // 2, size[1] // 2))
    image.save(stream, format='PNG')
    return 'data:image/png' + chr(59) + 'base64,' + base64.b64encode(stream.getvalue()).decode()


def rich_replay(path, frames=3, **changes):
    """A local review page with a jump between steps, repeated input and private model text."""
    colours = [(n % 256, n // 256, 99) for n in range(frames)]
    images = {f'k{n}': shot(colour) for n, colour in enumerate(colours)}
    images['same-as-k0'] = shot(colours[0])
    press = {'button': 'a', 'hold_frames': 8, 'release_frames': 4, 'private': 'secret'}
    steps = []
    for n in range(frames - 1):
        steps.append({'decision': n + 1, 'before_frame': n * 10, 'after_frame': n * 10 + 8, 'tokens': 40,
                      'cumulative_tokens': 40 * (n + 1), 'before': f'k{n}', 'after': f'k{n + 1}',
                      'plan': {'goal': 'model plan text'}, 'notes': 'model note text',
                      'requested_commands': [{'command': 'model_command'}],
                      'gameplay_input': {'location': {'map_name': 'Pallet Town', 'secret': 'hidden'},
                                         'last_command': {'outcome': f'Moved {n} tiles.'}, 'party': [{'name': 'RIVALMON'}]},
                      'actions': [press, press, {'button': None, 'hold_frames': 0, 'release_frames': 30}]})
    steps[1].update(before='same-as-k0', actions=[])
    run = {'id': 'cell-1', 'model': 'gpt-6-astra', 'completed': False, 'objective': 'Earn the Boulder Badge.',
           'stop_reason': 'model_call_budget', 'images': images, 'steps': steps, **changes}
    path.write_text('<script id="data" type="application/json">' + json.dumps({'runs': [run]}) + '</script>')
    return colours


ATTEMPT = {'id': 'cell-1', 'model': 'gpt-6-astra', 'completed': False}


def frame(frames, number):
    """Cut one screen back out of the published sprite sheets."""
    sheet, slot = divmod(number, frames['per_sheet'])
    raw = base64.b64decode(frames['sheets'][sheet].split(',')[1])
    left = slot % frames['columns'] * frames['width']
    top = slot // frames['columns'] * frames['height']
    return Image.open(io.BytesIO(raw)), (left, top, left + frames['width'], top + frames['height'])


def test_replay_sheets_keep_every_pixel_and_store_each_screen_once(tmp_path):
    colours = rich_replay(tmp_path/'replay.html', frames=300)
    payload = replay_payload(tmp_path/'replay.html', ATTEMPT)
    frames = payload['frames']
    assert payload['format'] == 2
    assert frames['count'] == 300
    assert (frames['columns'], frames['per_sheet'], len(frames['sheets'])) == (16, 256, 2)
    for number in (0, 17, 255, 256, 299):
        sheet, box = frame(frames, number)
        assert sheet.mode == 'RGB' or sheet.mode == 'P'
        assert sheet.info == {} or set(sheet.info) <= {'transparency'}
        expected = Image.open(io.BytesIO(base64.b64decode(shot(colours[number]).split(',')[1]))).convert('RGB')
        assert sheet.convert('RGB').crop(box).tobytes() == expected.tobytes()
    steps = payload['steps']
    assert steps['start'] == 0
    assert steps['screen'][:3] == [1, 2, 3]
    assert steps['breaks'] == {'1': 0}
    assert 'before' not in steps
    assert 'cumulative' not in steps


def test_replay_uses_a_small_palette_for_game_boy_screens(tmp_path):
    rich_replay(tmp_path/'replay.html')
    frames = replay_payload(tmp_path/'replay.html', ATTEMPT)['frames']
    sheet, _ = frame(frames, 0)
    assert sheet.mode == 'P'
    assert len(sheet.getcolors()) == 4


def test_replay_packs_actions_and_harness_text_but_no_model_text(tmp_path):
    rich_replay(tmp_path/'replay.html', frames=4)
    details = {'label': 'Astra', 'score': 85, 'maximum': 1000, 'badges': 1, 'decisions': 3,
               'milestones': [{'label': 'Reach Viridian City', 'decision': 2, 'points': 5, 'id': 'event:viridian'}],
               'harness': 'red-v0.59', 'versions': {'package': '0.7.3', 'core': 'unrecorded', 'private': '/home/x'}}
    payload = replay_payload(tmp_path/'replay.html', ATTEMPT, details)
    steps = payload['steps']
    assert steps['actions'] == [[['a', 8, 4, 2], [None, 0, 30, 1]], [], [['a', 8, 4, 2], [None, 0, 30, 1]]]
    assert payload['places'] == ['Pallet Town']
    assert steps['place'] == [0, 0, 0]
    assert payload['outcomes'] == ['Moved 1 tiles.', 'Moved 2 tiles.']
    assert steps['outcome'] == [0, 1, -1]
    assert payload['meta'] == {'goal': 'Earn the Boulder Badge.', 'label': 'Astra', 'score': 85, 'maximum': 1000,
                               'badges': 1, 'decisions': 3, 'stop_reason': 'model_call_budget',
                               'milestones': details['milestones'], 'harness': {'name': 'red-v0.59', 'package': '0.7.3'}}
    encoded = json.dumps(payload)
    for private in ('model plan', 'model note', 'model_command', 'RIVALMON', 'hidden', 'secret', '/home/', 'plans', 'notes'):
        assert private not in encoded


def test_replay_drops_unsafe_optional_text_and_rejects_unsafe_details(tmp_path):
    rich_replay(tmp_path/'replay.html', objective='Read /home/user/private first.', stop_reason='api_key=oops')
    payload = replay_payload(tmp_path/'replay.html', ATTEMPT)
    assert payload['meta'] == {}
    with pytest.raises(ValueError):
        replay_payload(tmp_path/'replay.html', ATTEMPT, {'label': '/home/user/name'})
    with pytest.raises(ValueError):
        replay_payload(tmp_path/'replay.html', ATTEMPT, {'score': 'high'})


def test_replay_keeps_recorded_totals_when_steps_do_not_add_up(tmp_path):
    rich_replay(tmp_path/'replay.html')
    source = (tmp_path/'replay.html').read_text().replace('"cumulative_tokens": 80', '"cumulative_tokens": 500')
    (tmp_path/'replay.html').write_text(source)
    assert replay_payload(tmp_path/'replay.html', ATTEMPT)['steps']['cumulative'] == [40, 500]


def test_replay_rejects_mixed_screen_sizes(tmp_path):
    rich_replay(tmp_path/'replay.html')
    data = json.loads((tmp_path/'replay.html').read_text().split('>', 1)[1].rsplit('<', 1)[0])
    data['runs'][0]['images']['k1'] = shot((1, 2, 3), (80, 72))
    (tmp_path/'replay.html').write_text('<script id="data">' + json.dumps(data) + '</script>')
    with pytest.raises(ValueError, match='differ in size'):
        replay_payload(tmp_path/'replay.html', ATTEMPT)


def test_replay_page_is_self_contained_and_follows_the_house_style():
    assert chr(59) not in REPLAY
    assert '__FACE__' not in REPLAY
    assert REPLAY.count('__DATA__') == 1
    assert 'data.format !== 2' in REPLAY
    for remote in ('http://', 'https://', 'src="//'):
        assert remote not in REPLAY


def unpacked(payload):
    """Run the page's own reader on a payload."""
    node = shutil.which('node')
    if not node:
        pytest.skip('Node is not installed')
    reader = REPLAY[REPLAY.index('function unpack() {'):REPLAY.index('const steps = unpack()')]
    script = 'const data = ' + json.dumps(payload) + '\n' + reader + '\nconsole.log(JSON.stringify(unpack()))'
    return json.loads(subprocess.run([node, '-e', script], capture_output=True, text=True, check=True).stdout)


def test_replay_page_reads_the_new_format_and_the_published_old_one(tmp_path):
    rich_replay(tmp_path/'replay.html', frames=4)
    payload = replay_payload(tmp_path/'replay.html', ATTEMPT)
    steps = unpacked(payload)
    assert [step['decision'] for step in steps] == [1, 2, 3]
    assert [step['cumulative_tokens'] for step in steps] == [40, 80, 120]
    assert [(step['before']['x'], step['after']['x']) for step in steps] == [(0, 160), (0, 320), (320, 480)]
    assert steps[0]['before']['src'] == payload['frames']['sheets'][0]
    assert steps[0]['actions'] == [{'button': 'a', 'hold_frames': 8, 'release_frames': 4}] * 2 + [
        {'button': None, 'hold_frames': 0, 'release_frames': 30}]
    assert steps[0]['location'] == 'Pallet Town'
    assert [step.get('outcome') for step in steps] == ['Moved 1 tiles.', 'Moved 2 tiles.', None]
    assert not any(step['same'] for step in steps)

    old = {'model': 'gpt-6-astra', 'completed': True, 'action_policy': 'assisted-gameplay-v1', 'benchmark': 'unrecorded',
           'images': {'one': 'data:one', 'two': 'data:two'},
           'steps': [{'decision': 1, 'before_frame': 0, 'after_frame': 8, 'tokens': 40, 'cumulative_tokens': 40,
                      'before': 'one', 'after': 'two', 'actions': [{'button': 'a', 'hold_frames': 8, 'release_frames': 0}]},
                     {'decision': 2, 'before_frame': 8, 'after_frame': 16, 'tokens': 5, 'cumulative_tokens': 45,
                      'before': 'two', 'after': 'two', 'actions': []}]}
    steps = unpacked(old)
    assert [(step['before']['src'], step['after']['src'], step['same']) for step in steps] == [
        ('data:one', 'data:two', False), ('data:two', 'data:two', True)]
    assert steps[1]['cumulative_tokens'] == 45
    assert steps[0]['actions'] == old['steps'][0]['actions']


def test_metadata_does_not_copy_configuration_paths_or_credentials():
    metadata = safe_metadata({'agent': {'model': 'gpt-6-astra', 'provider': 'codex',
        'session_id': 'private', 'configuration': {'secret': '/home/user', 'context_turns': 8}},
        'platform': '/home/user/private', 'core': {'version': '0.1.4', 'direct_url': {'url': 'private'}}})
    assert metadata['context'] == {'context_turns': 8}
    assert 'private' not in json.dumps(metadata)


def test_complete_static_export_contains_only_public_data(tmp_path):
    root = tmp_path/'repo'
    reviews = root/'data'/'reviews'
    reviews.mkdir(parents=True)
    run = root/'data'/'batch'/'cell-1'
    run.mkdir(parents=True)
    (run/'manifest.json').write_text(json.dumps({'agent': {'provider': 'codex', 'model': 'gpt-6-astra', 'harness': 'test-v1', 'session_id': 'SECRET'}, 'created_at': '2026-10-05T00:00:00Z'}))
    replay(reviews/'replay.html')
    task = {'id': 'task', 'name': 'Task', 'category': 'Battles', 'difficulty': 'medium',
        'description': 'Win the battle', 'tokens': 1000, 'state_hash': 'a'*64, 'preview': screenshot()}
    attempt = {'id': 'cohort/cell-1', 'source_cohort': 'cohort', 'source_run_id': 'cell-1',
        'task': 'task', 'model': 'gpt-6-astra', 'status': 'finished', 'completed': True,
        'repeat': 1, 'tokens': 40, 'replay_verified': True, 'replay': 'replay.html',
        'retained_from': {'private': '/home/user'}, 'secret': 'SECRET'}
    cohort = {'id': 'combined', 'label': 'Development', 'analysis': 'exploratory', 'tasks': [task],
        'attempts': [attempt], 'models': [{'model': 'gpt-6-astra'}], 'configuration': {'secret': 'SECRET'}}
    feed = reviews/'feed.json'
    feed.write_text(json.dumps({'updated_at': '2026-10-05T00:00:00Z', 'cohorts': [cohort]}))
    config = root/'data'/'config.json'
    config.write_text(json.dumps([{'id': 'cohort', 'batch': 'data/batch'}]))
    out = tmp_path/'public'
    manifest = export_public(feed, config, out)
    assert manifest['tasks'] == manifest['attempts'] == manifest['replays'] == 1
    assert (out/'benchmarks'/'task.html').exists()
    for item in manifest['files']:
        raw = (out/item['path']).read_bytes()
        assert hashlib.sha256(raw).hexdigest() == item['sha256']
        assert b'SECRET' not in raw
        assert b'/home/' not in raw
    index = (out/'index.html').read_text()
    assert 'Development preview' in index
    assert 'id="suite"' not in index
    assert 'setInterval(refresh' not in index
    assert 'benchmarks/${esc(t.id)}.html' in index
    assert 'test-v1' in (out/'results.json').read_text()
    assert json.loads((out/'results.json').read_text())['cohorts'][0]['attempts'][0]['outcome_category'] == 'success'
    assert '<small>Completed</small>' in (out/'benchmarks'/'task.html').read_text()
    with pytest.raises(ValueError, match='new public export'):
        export_public(feed, config, out)


def test_export_rejects_path_traversal(tmp_path):
    from pokeagent_bench.public_site import clean_task
    task = {'id': '../escape', 'name': 'Task', 'category': 'Battles', 'difficulty': 'medium',
            'description': 'Win', 'tokens': 1000, 'state_hash': 'a'*64, 'preview': screenshot()}
    with pytest.raises(ValueError):
        clean_task(task)


def test_failed_export_leaves_no_publishable_partial_directory(tmp_path):
    feed = tmp_path/'broken.json'
    feed.write_text('{bad json')
    out = tmp_path/'public'
    with pytest.raises(ValueError):
        export_public(feed, tmp_path/'config.json', out)
    assert not out.exists()
    assert not list(tmp_path.glob('.pokebench-export-*'))


def release_files(root):
    from pokeagent_bench.core import digest, encoded
    root.mkdir()
    protocol = {'id': 'pokebench-v1-beta', 'frozen_at': '2026-10-05T00:00:00Z', 'track': 'gameplay',
                'scoring': 'Equal task weights', 'uncertainty': 'Descriptive only',
                'budget_policy': 'Stop at boundaries', 'retry_policy': 'No gameplay retries',
                'history_policy': 'No imported development runs', 'variants': 2,
                'total_token_budget': 50000000, 'maximum_planned_tokens': 100000000,
                'planned_attempts': 8, 'context_turns': 8, 'compact_at': 12000, 'paid_summaries': 0,
                'source_sha256': 'a'*64, 'fixture_registration_sha256': 'b'*64,
                'rom_sha256': 'c'*64, 'catalog_sha256': 'd'*64,
                'core': {'version': '0.1.4', 'private_path': '/home/owner'},
                'models': [{'model': model, 'provider': provider, 'effort': 'medium'}
                           for model, provider in [('gpt-6-astra', 'codex'), ('claude-sonnet-4-6', 'claude')]],
                'tasks': [{'id': task, 'name': task, 'difficulty': 'medium', 'tokens': 1000000,
                           'validation_status': 'development-qualified', 'score_eligible': True,
                           'starting_state_sha256': ['e'*64, 'f'*64]}
                          for task in ['first', 'second']]}
    protocol['sha256'] = digest(encoded(protocol))
    attempts = [{'id': f'cell-{index}', 'model': model['model'], 'provider': model['provider'],
                 'effort': 'medium', 'task': task, 'variant': variant, 'status': 'pending',
                 'tokens': 0, 'token_limit': 1000000, 'completed': None, 'replay_verified': False}
                for index, (model, task, variant) in enumerate(
                    (m, t, v) for m in protocol['models'] for t in ['first', 'second'] for v in [1, 2])]
    summary = {'id': protocol['id'], 'protocol_sha256': protocol['sha256'], 'planned': 8,
               'status': 'paused at total token budget', 'attempts': attempts,
               'models': [{'model': 'gpt-6-astra', 'score': 100}], 'private': '/home/private'}
    (root/'protocol.json').write_text(json.dumps(protocol))
    (root/'release-summary.json').write_text(json.dumps(summary))
    return protocol, summary


def test_controlled_results_require_full_registered_matched_coverage(tmp_path):
    from pokeagent_bench.public_site import release_section, release_snapshot
    root = tmp_path/'release'
    _, summary = release_files(root)
    for attempt in summary['attempts']:
        if attempt['task'] == 'first':
            attempt.update(status='finished', completed=True, replay_verified=True, accounting_complete=True, tokens=100)
    (root/'release-summary.json').write_text(json.dumps(summary))
    protocol, public = release_snapshot(root)
    assert public['matched_task_ids'] == ['first']
    assert public['headline_score_ready'] is False
    assert all(model['score'] is None for model in public['models'])
    assert public['pending'] == 4
    assert public['finished'] == 4
    assert '/home/' not in json.dumps([protocol, public])
    page = release_section(protocol, public)
    assert 'Paused at the shared token ceiling' in page
    assert '50,000,000 shared execution ceiling' in page
    assert 'Pending' in page
    for attempt in summary['attempts']:
        attempt.update(status='finished', completed=attempt['model'] == 'gpt-6-astra', replay_verified=True, accounting_complete=True)
    (root/'release-summary.json').write_text(json.dumps(summary))
    _, public = release_snapshot(root)
    assert public['headline_score_ready'] is True
    assert [m['score'] for m in public['models']] == [100.0, 0.0]


def test_provisional_ranking_shares_starts_and_weights_tasks_equally(tmp_path):
    from pokeagent_bench.public_site import release_snapshot
    root = tmp_path/'release'
    _, summary = release_files(root)
    for a in summary['attempts']:
        # Two starts on the first task and only one on the second are shared.
        if a['task'] == 'first' or a['variant'] == 1:
            a.update(status='finished', replay_verified=True, accounting_complete=True,
                     completed=(a['task'] == 'first') == (a['model'] == 'gpt-6-astra'))
        elif a['model'] == 'gpt-6-astra':
            a.update(status='finished', replay_verified=True, accounting_complete=True, completed=True)
    (root/'release-summary.json').write_text(json.dumps(summary))
    _, result = release_snapshot(root)
    assert result['headline_score_ready'] is False
    assert all(m['score'] is None for m in result['models'])
    provisional = result['provisional']
    assert [t['variants'] for t in provisional['tasks']] == [[1, 2], [1]]
    assert [m['score'] for m in provisional['models']] == [50, 50]
    assert [m['rank'] for m in provisional['models']] == [1, 1]
    assert [m['starts'] for m in provisional['models']] == [3, 3]
    assert sorted(m['wins'] for m in provisional['models']) == [1, 2]


@pytest.mark.parametrize('invalid', [
    {'status': 'pending'}, {'status': 'error'}, {'status': 'running'},
    {'replay_verified': False}, {'accounting_complete': False}, {'completed': None},
])
def test_provisional_ranking_excludes_unusable_start_for_every_model(tmp_path, invalid):
    from pokeagent_bench.public_site import release_snapshot
    root = tmp_path/'release'
    _, summary = release_files(root)
    for a in summary['attempts']:
        if a['task'] == 'first' and a['variant'] == 1:
            a.update(status='finished', completed=True, replay_verified=True, accounting_complete=True)
    summary['attempts'][0].update(invalid)
    (root/'release-summary.json').write_text(json.dumps(summary))
    _, result = release_snapshot(root)
    assert result['provisional']['tasks'] == []
    assert all(m['score'] is None and m['rank'] is None for m in result['provisional']['models'])


def test_provisional_ranking_ignores_experiments_and_counts_losses(tmp_path):
    from pokeagent_bench.core import digest, encoded
    from pokeagent_bench.public_site import release_snapshot, release_section
    root = tmp_path/'release'
    protocol, summary = release_files(root)
    protocol['tasks'][1]['score_eligible'] = False
    protocol['sha256'] = digest(encoded({k:v for k,v in protocol.items() if k != 'sha256'}))
    summary['protocol_sha256'] = protocol['sha256']
    for a in summary['attempts']:
        a.update(status='finished', completed=a['model'] == 'claude-sonnet-4-6',
                 replay_verified=True, accounting_complete=True)
    (root/'protocol.json').write_text(json.dumps(protocol))
    (root/'release-summary.json').write_text(json.dumps(summary))
    public_protocol, result = release_snapshot(root)
    assert [t['task'] for t in result['provisional']['tasks']] == ['first']
    assert [m['score'] for m in result['provisional']['models']] == [100, 0]
    assert [m['rank'] for m in result['provisional']['models']] == [1, 2]
    page = release_section(public_protocol, result)
    assert 'OpenAI' in page and 'Anthropic' in page
    assert 'Provisional' in page and 'starts 1, 2' in page


def test_controlled_export_rejects_duplicate_or_mismatched_registration(tmp_path):
    from pokeagent_bench.public_site import release_snapshot
    root = tmp_path/'release'
    _, summary = release_files(root)
    summary['attempts'][-1] = summary['attempts'][0]
    (root/'release-summary.json').write_text(json.dumps(summary))
    with pytest.raises(ValueError, match='matrix'):
        release_snapshot(root)
    summary['protocol_sha256'] = '0'*64
    (root/'release-summary.json').write_text(json.dumps(summary))
    with pytest.raises(ValueError, match='frozen protocol'):
        release_snapshot(root)



def test_release_snapshot_derives_outcome_category_from_original_stop(tmp_path):
    from pokeagent_bench.public_site import release_snapshot

    root = tmp_path / "release"
    _, summary = release_files(root)
    summary["attempts"][0].update(status="finished", completed=False, stop_reason="invalid_model_response",
                                  replay_verified=True, accounting_complete=True)
    summary["attempts"][1].update(status="error", stop_reason="provider_error")
    (root / "release-summary.json").write_text(json.dumps(summary))
    _, public = release_snapshot(root)
    assert public["attempts"][0]["outcome_category"] == "interface_failure"
    assert public["attempts"][1]["outcome_category"] == "infrastructure_failure"
    assert public["attempts"][2]["outcome_category"] == "pending"
    assert public["attempts"][0]["completed"] is False
