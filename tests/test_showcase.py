import json
from pathlib import Path
import shutil
import subprocess

import pytest

from pokeagent_bench.showcase import existing_link, export_public, long_row, short_snapshot


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


def test_stored_preparation_is_dropped_and_retired_cells_stay_visible_but_unscored(tmp_path):
    def row(task, category, value):
        return {'id': task, 'task_id': task, 'category': category, 'score_group': task, 'model': 'old',
                'state': 'finished', 'value': value, 'tokens': 10, 'cost': {'low': 1.0, 'high': 2.0, 'partial': False}}
    rows = [row('b', 'battle', 0.5), row('p', 'preparation', 1.0), row('objectives-find-capture-species', 'objectives', 1.0)]
    tasks = [{'id': r['task_id'], 'title': r['task_id'], 'category': r['category']} for r in rows]
    source = {'cells': rows, 'tasks': tasks, 'categories': ['battle', 'preparation', 'objectives']}
    extra = {'web_prefix': 'batch', 'cells': [dict(rows[1], id='q')]}
    result = short_snapshot(source, tmp_path, extra)
    model = result['models'][0]
    assert model['score'] == 0.5
    assert model['categories'] == {'battle': 0.5}
    assert (model['finished'], model['planned'], model['complete'], model['tokens']) == (1, 1, True, 20)
    assert [c['id'] for c in result['cells']] == ['b', 'objectives-find-capture-species']
    assert [c['retired'] for c in result['cells']] == [False, True]
    assert [t['id'] for t in result['tasks']] == ['b', 'objectives-find-capture-species']
    retired = result['tasks'][1]
    assert retired['retired'] and 'luck' in retired['retirement_reason']
    assert (result['finished'], result['planned']) == (1, 1)
    assert result['categories'] == ['battle', 'objectives']
    assert 'ranked_categories' not in result and 'unranked_categories' not in result
    from pokeagent_bench.showcase_costs import comparison
    priced = [dict(r, retired=r['task_id'] == 'objectives-find-capture-species') for r in (rows[0], rows[2])]
    value = comparison(priced, [{'id': 'old', 'label': 'Old'}])
    assert value['starts'] == 1
    assert value['models'][0]['score'] == 0.5 and value['models'][0]['cost'] == {'low': 1.0, 'high': 2.0}


def test_snapshot_does_not_export_provider_context(tmp_path):
    source = {'cells': [{'id': 'a', 'task_id': 't', 'score_group': 't', 'category': 'battle',
                        'model': 'model', 'state': 'finished', 'value': 1.0,
                        'provider': {'secret': 'private'}, 'notes': 'private',
                        'replay': '../outside.html'}], 'tasks': [], 'categories': ['battle']}
    row = short_snapshot(source, tmp_path)['cells'][0]
    assert 'notes' not in row
    assert 'provider' not in row
    assert row['replay'] is None


def test_harness_labels_come_from_each_run_manifest(tmp_path):
    base = tmp_path / 'data'
    for relative, tag in (('focused-pass-v056/a', 'red-v0.10-newer'), ('focused-pass-v056/b', 'red-v0.9-older'),
                          ('batch/c', 'red-v0.10-newer')):
        (base / relative).mkdir(parents=True)
        (base / relative / 'manifest.json').write_text(json.dumps({'benchmark': tag}))
    rows = [{'id': 'a', 'task_id': 't', 'score_group': 't', 'category': 'battle', 'model': 'old',
             'mode': 'gameplay', 'state': 'finished', 'value': 1.0},
            {'id': 'b', 'task_id': 'p', 'score_group': 'p', 'category': 'battle', 'model': 'old',
             'mode': 'gameplay', 'state': 'finished', 'value': 0.5}]
    extra = {'web_prefix': 'batch', 'cells': [dict(rows[0], id='c', model='new')]}
    result = short_snapshot({'cells': rows, 'tasks': [], 'categories': ['battle']}, tmp_path, extra, base)
    assert [c['harness'] for c in result['cells']] == ['red-v0.10-newer', 'red-v0.9-older', 'red-v0.10-newer']
    harness = {m['id']: m['harness'] for m in result['models']}
    assert harness['old'] == {'revisions': ['Original pass'], 'versions': ['red-v0.9-older', 'red-v0.10-newer'],
                              'label': 'red-v0.9 to v0.10'}
    assert harness['new'] == {'revisions': ['Current interface'], 'versions': ['red-v0.10-newer'], 'label': 'red-v0.10'}
    assert short_snapshot({'cells': rows, 'tasks': [], 'categories': ['battle']}, tmp_path)['models'][0]['harness']['label'] is None


def test_long_rows_carry_their_harness_version(tmp_path):
    run = tmp_path / 'long-run' / 'run'
    run.mkdir(parents=True)
    (run / 'manifest.json').write_text(json.dumps({'agent': {'model': 'unpriced'}, 'benchmark': 'red-v0.59-lossless-inspection'}))
    (run / 'result.json').write_text(json.dumps({'state': 'finished', 'score': 5, 'usage': {'calls': 3}}))
    row = long_row(tmp_path / 'long-run', tmp_path, 'opus')
    assert row['harness'] == 'red-v0.59-lossless-inspection'
    assert row['model'] == 'unpriced'
    assert row['pair_blocks'] is None
    shutil.copytree(tmp_path / 'long-run', tmp_path / 'long-v065-sonnet')
    assert long_row(tmp_path / 'long-v065-sonnet', tmp_path, 'sonnet')['pair_blocks'] == {'pair': 246, 'blocked': 434}


def test_long_rows_show_the_stored_v2_rescore(tmp_path):
    root = tmp_path / 'long-run'
    (root / 'run').mkdir(parents=True)
    badge = {'id': 'badge:boulder', 'label': 'Earn the Boulder Badge from Brock', 'decision': 40, 'points': 50}
    (root / 'run/result.json').write_text(json.dumps({'state': 'finished', 'score': 50, 'achievements': [badge]}))
    events = [{'kind': 'milestone', 'id': 'area:viridian-forest', 'label': 'Enter Viridian Forest', 'decision': 12,
               'points': 8, 'tokens': 9},
              {'kind': 'profile', 'id': 'start'},
              {'kind': 'milestone', 'id': 'badge:boulder', 'label': 'Earn the Boulder Badge from Brock', 'decision': 40,
               'points': 40, 'tokens': 30}]
    rescore = {'run': 'long-run', 'recorded_score': 50, 'score': 48, 'campaign': {'events': events}}
    (root / 'campaign-progress-v2.json').write_text(json.dumps(rescore))
    row = long_row(root, tmp_path, 'opus')
    assert row['score'] == 48 and row['badges'] == 1
    assert row['milestones'] == [{'label': 'Enter Viridian Forest', 'decision': 12, 'points': 8, 'id': 'area:viridian-forest'},
                                 {'label': 'Earn the Boulder Badge from Brock', 'decision': 40, 'points': 40,
                                  'id': 'badge:boulder'}]
    # A rescore of a different recording must not replace this run's numbers.
    (root / 'campaign-progress-v2.json').write_text(json.dumps({**rescore, 'recorded_score': 45}))
    with pytest.raises(ValueError, match='does not match'):
        long_row(root, tmp_path, 'opus')


def test_cells_are_labeled_from_their_own_records(tmp_path):
    from pokeagent_bench.showcase import END_LINE, current_spec
    task = 'navigation-branching-cave'
    spec = current_spec(task)
    base = tmp_path / 'data'
    facts = {'cell-0001': END_LINE, 'cell-0002': None, 'cell-0003': 'An older prompt.', 'cell-0223': None}
    for cell, prompt in facts.items():
        (base / 'focused-pass-v056' / cell).mkdir(parents=True)
        if prompt:
            (base / 'focused-pass-v056' / cell / 'prompt.txt').write_text(prompt)
    def row(cell, spec_hash, fixture):
        return {'id': cell, 'task_id': task, 'category': 'navigation', 'score_group': task, 'model': 'old', 'variant': 'default',
                'state': 'finished', 'value': 0.0, 'evaluation_spec_sha256': spec_hash, 'fixture_sha256': fixture}
    rows = [row('cell-0001', spec, 'new'), row('cell-0002', 'old-spec', 'old'), row('cell-0003', spec, 'new'),
            row('cell-0223', spec, 'new')]
    result = short_snapshot({'cells': rows, 'tasks': [], 'categories': ['navigation']}, tmp_path, None, base)
    labels = {c['id']: c['labels'] for c in result['cells']}
    assert labels == {'cell-0001': [], 'cell-0002': ['earlier_spec', 'earlier_start'],
                      'cell-0003': ['no_end_line'], 'cell-0223': ['harness_fault']}
    assert 'use_item' in result['cells'][3]['harness_fault']
    assert result['models'][0]['labels'] == {'earlier_spec': 1, 'earlier_start': 1, 'no_end_line': 1, 'harness_fault': 1}
    assert set(result['label_text']) == {'earlier_spec', 'earlier_start', 'no_end_line', 'harness_fault'}


def test_attempts_log_lists_replaced_and_resumed_copies(tmp_path):
    base = tmp_path / 'data'
    replaced = base / 'focused-pass-v056/original-errors-v058/cell-0018'
    resumed = base / 'main-v067-fable/cell-0002-quota-error-01'
    for folder, stop in ((replaced, 'invalid_model_response'), (resumed, 'usage_unavailable')):
        folder.mkdir(parents=True)
        (folder / 'manifest.json').write_text(json.dumps({'agent': {'model': 'm'}, 'scenario': {'task_id': 't'}}))
        (folder / 'result.json').write_text(json.dumps({'stop_reason': stop, 'usage': {'calls': 7}}))
    (base / 'main-v067-fable/cell-0002').mkdir()
    extra = {'web_prefix': 'main-v067-fable', 'cells': []}
    attempts = short_snapshot({'cells': [], 'tasks': [], 'categories': []}, tmp_path, extra, base)['attempts']
    assert 'No gameplay retries' in attempts['rule']
    assert [(e['batch'], e['cell'], e['kind'], e['stop_reason'], e['decisions']) for e in attempts['log']] == [
        ('focused-pass-v056', 'cell-0018', 'replaced', 'invalid_model_response', 7),
        ('main-v067-fable', 'cell-0002', 'resumed', 'usage_unavailable', 7)]
    assert attempts['log'][1]['reason'].startswith('Quota error stopped the attempt')
    assert short_snapshot({'cells': [], 'tasks': [], 'categories': []}, tmp_path)['attempts']['log'] == []


def test_community_rows_are_labeled_and_kept_out_of_the_cost_comparison(tmp_path):
    from pokeagent_bench.showcase import community_reports
    row = {'id': 'cell-0001', 'task_id': 't', 'score_group': 't', 'category': 'battle', 'model': 'official',
           'mode': 'gameplay', 'state': 'finished', 'value': 0.0, 'tokens': 100}
    report = {'format': 'pokebench-verified-report-v1', 'verified': True, 'suite': 'short', 'model': 'local-model',
              'label': 'Community, replay verified, model unverified', 'handle': 'octocat', 'attempts_declared': 2,
              'harness': {'benchmark': 'red-v0.61-fair-harness'}, 'bundle_sha256': 'abc',
              'cells': [dict(row, model='local-model', value=1.0, tokens=500, notes='private')]}
    (tmp_path / 'community').mkdir()
    for name, value in (('a', report), ('b', dict(report, verified=False)), ('c', dict(report, suite='smoke'))):
        (tmp_path / 'community' / f'{name}.json').write_text(json.dumps(value))
    assert community_reports(tmp_path) == [report]
    result = short_snapshot({'cells': [row], 'tasks': [], 'categories': ['battle']}, tmp_path, community=[report])
    added, official = result['models']
    assert added['id'] == 'community/octocat/local-model' and added['label'] == 'local-model'
    assert added['community'] == {'label': 'Community, replay verified, model unverified', 'handle': 'octocat',
                                  'model': 'local-model', 'attempts': 2, 'bundle_sha256': 'abc'}
    assert added['score'] == 1.0 and added['tokens'] == 500 and added['cost']['low'] is None
    assert 'community' not in official
    cell = result['cells'][1]
    assert cell['revision'] == 'Community' and cell['replay'] is None and 'notes' not in cell
    assert [m['id'] for m in result['efficiency']['models']] == ['official']


def test_a_community_long_run_joins_the_long_panel_unpriced(tmp_path):
    from pokeagent_bench.showcase import community_long_row, community_reports
    badge = {'id': 'badge:boulder', 'label': 'Earn the Boulder Badge from Brock', 'points': 40, 'decision': 40}
    cell = {'id': 'cell-0001', 'task_id': 'campaign-full-game', 'state': 'finished', 'decision_limit': 2000,
            'token_limit': 30_000_000, 'tokens': 9_000_000, 'decisions': 2000, 'stop_reason': 'model_call_budget',
            'campaign': {'points': 48, 'maximum_points': 1000}, 'milestones': [badge], 'notes': 'private'}
    report = {'format': 'pokebench-verified-report-v1', 'verified': True, 'suite': 'long', 'model': 'local-model',
              'label': 'Community, replay verified, model unverified', 'handle': 'octocat', 'attempts_declared': 1,
              'harness': {'benchmark': 'red-v0.62-next', 'package_version': '0.37.0'}, 'bundle_sha256': 'abc',
              'cells': [cell]}
    (tmp_path / 'community').mkdir()
    (tmp_path / 'community' / 'long.json').write_text(json.dumps(report))
    (tmp_path / 'community' / 'short.json').write_text(json.dumps(dict(report, suite='short')))
    assert community_reports(tmp_path, 'long') == [report]
    assert [r['suite'] for r in community_reports(tmp_path)] == ['short']
    row = community_long_row(report)
    assert row['id'] == 'community/octocat/local-model' and row['label'] == 'local-model'
    assert row['community'] == {'label': 'Community, replay verified, model unverified', 'handle': 'octocat',
                                'model': 'local-model', 'attempts': 1, 'bundle_sha256': 'abc'}
    assert (row['score'], row['maximum'], row['badges'], row['decision_limit']) == (48, 1000, 1, 2000)
    assert row['milestones'] == [badge] and row['tokens'] == 9_000_000 and row['cost']['low'] is None
    assert row['harness'] == 'red-v0.62-next' and row['versions']['package'] == '0.37.0'
    assert row['replay'] is None and row['report'] is None and row['extensions'] == []
    assert 'private' not in json.dumps(row)


def test_only_existing_local_replays_are_linked(tmp_path):
    (tmp_path / 'replay.html').write_text('replay')
    assert existing_link(tmp_path, 'replay.html') == 'replay.html'
    assert existing_link(tmp_path, 'missing.html') is None
    assert existing_link(tmp_path, '../outside.html') is None


@pytest.mark.skipif(not shutil.which('node'), reason='node is not installed')
def test_score_interval_resamples_tasks_within_categories():
    stats = Path(__file__).parents[1] / 'src/pokeagent_bench/showcase_assets/showcase-stats.js'
    rows = [{'task_id': f'b{i}', 'category': 'battle', 'state': 'finished', 'value': i % 2} for i in range(10)]
    rows += [{'task_id': 'n', 'category': 'navigation', 'state': 'finished', 'value': 1},
             {'task_id': 'p', 'category': 'navigation', 'state': 'pending', 'value': None}]
    same = [dict(r, value=1) for r in rows if r['state'] == 'finished']
    ignored = rows + [{'task_id': 'r', 'category': 'objectives', 'state': 'finished', 'value': 0, 'retired': True}]
    script = (f'const {{scoreInterval}} = require({json.dumps(str(stats))})\n'
              f'console.log(JSON.stringify([scoreInterval({json.dumps(rows)}), scoreInterval({json.dumps(rows)}), '
              f'scoreInterval({json.dumps(same)}), scoreInterval([]), scoreInterval({json.dumps(ignored)})]))')
    first, again, perfect, empty, skipped = json.loads(
        subprocess.run(['node', '-e', script], check=True, capture_output=True, text=True).stdout)
    assert first == again == skipped
    assert 0.5 < first['low'] < 0.75 < first['high'] < 1.0
    assert perfect['low'] == perfect['high'] == 1.0
    assert empty is None


def test_public_page_omits_report_link_without_report(tmp_path):
    web = tmp_path / 'web'
    web.mkdir()
    (web / 'showcase-data.json').write_text(json.dumps({'short': {'cells': []}, 'long': [], 'report': 'technical-report.pdf'}))
    data = export_public(web, tmp_path / 'public')
    page = (tmp_path / 'public' / 'index.html').read_text()
    assert data['report'] is None
    assert 'technical-report.pdf' not in page
    assert 'technical report' not in page.lower()
    assert 'analysis-v060.html' not in page


def test_public_page_states_the_scoring_change(tmp_path):
    web = tmp_path / 'web'
    web.mkdir()
    (web / 'showcase-data.json').write_text(json.dumps({'short': {'cells': []}, 'long': [], 'report': None}))
    export_public(web, tmp_path / 'public')
    page = (tmp_path / 'public' / 'index.html').read_text()
    note = page.split('<p id="scoring-change" class="small">')[1].split('</p>')[0]
    assert note.count('.') == 1 and note.endswith('.')
    assert '14 November 2026' in note
    assert all(name in note for name in ('navigation', 'battles', 'menus', 'quests', 'preparation', 'Pikachu'))
    assert 'four categories equally' in page and 'Preparation' not in page
    long_note = page.split('<p id="long-scoring-change" class="small">')[1].split('</p>')[0]
    assert long_note.count('.') == 1 and long_note.endswith('.')
    assert all(part in long_note for part in ('14 November 2026', '75 milestones', 'same recorded runs', 'no new model calls'))
