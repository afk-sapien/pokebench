from pokeagent_bench.showcase import existing_link, short_snapshot


def test_partial_scores_keep_failures_and_exclude_pending(tmp_path):
    rows = [
        {'id': 'a', 'task_id': 'battle-one', 'category': 'battle', 'score_group': 'battle-one',
         'model': 'old', 'state': 'finished', 'value': 0.0, 'tokens': 100},
        {'id': 'b', 'task_id': 'battle-two', 'category': 'battle', 'score_group': 'battle-two',
         'model': 'old', 'state': 'finished', 'value': 1.0, 'tokens': 200},
    ]
    extra = {'cells': [
        dict(rows[0], model='gpt-6-astra', value=1.0),
        dict(rows[1], model='gpt-6-astra', value=None, state='pending', tokens=0),
    ]}
    source = {'cells': rows, 'tasks': [], 'categories': ['battle']}
    result = short_snapshot(source, tmp_path, extra)
    old, astra = result['models']
    assert old['score'] == 0.5
    assert old['complete']
    assert astra['score'] == 1.0
    assert astra['finished'] == 1
    assert not astra['complete']
    assert result['finished'] == 3
    assert result['planned'] == 4


def test_snapshot_does_not_export_provider_context(tmp_path):
    source = {'cells': [{'id': 'a', 'task_id': 't', 'score_group': 't', 'category': 'battle',
                        'model': 'model', 'state': 'finished', 'value': 1.0,
                        'provider': {'secret': 'private'}, 'notes': 'private',
                        'replay': '../outside.html'}], 'tasks': [], 'categories': ['battle']}
    row = short_snapshot(source, tmp_path)['cells'][0]
    assert 'notes' not in row
    assert 'provider' not in row
    assert row['replay'] is None


def test_only_existing_local_replays_are_linked(tmp_path):
    (tmp_path / 'replay.html').write_text('replay')
    assert existing_link(tmp_path, 'replay.html') == 'replay.html'
    assert existing_link(tmp_path, 'missing.html') is None
    assert existing_link(tmp_path, '../outside.html') is None
