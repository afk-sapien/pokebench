import base64
import hashlib
import io
import json

from PIL import Image, PngImagePlugin
import pytest

from pokeagent_bench.public_site import export_public, png, public_text, replay_payload, safe_metadata


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
    assert payload['steps'][0]['actions'] == [{'button': 'a', 'hold_frames': 8, 'release_frames': 0}]
    with pytest.raises(ValueError, match='does not match'):
        replay_payload(path, {**attempt, 'model': 'other'})


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
            attempt.update(status='finished', completed=True, replay_verified=True, tokens=100)
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
        attempt.update(status='finished', completed=attempt['model'] == 'gpt-6-astra', replay_verified=True)
    (root/'release-summary.json').write_text(json.dumps(summary))
    _, public = release_snapshot(root)
    assert public['headline_score_ready'] is True
    assert [m['score'] for m in public['models']] == [100.0, 0.0]


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
