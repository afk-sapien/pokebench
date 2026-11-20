import json
import shutil

import pytest

from pokeagent_bench.showcase import existing_link, export_public, long_row, short_snapshot, write_site
from pokeagent_bench.showcase_stats import score_interval


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


def test_preparation_is_unranked_and_retired_cells_stay_visible_but_unscored(tmp_path):
    def row(task, category, value):
        return {'id': task, 'task_id': task, 'category': category, 'score_group': task, 'model': 'old',
                'state': 'finished', 'value': value, 'tokens': 10, 'cost': {'low': 1.0, 'high': 2.0, 'partial': False}}
    rows = [row('b', 'battle', 0.5), row('p', 'preparation', 1.0), row('objectives-find-capture-species', 'objectives', 1.0)]
    tasks = [{'id': r['task_id'], 'title': r['task_id'], 'category': r['category']} for r in rows]
    source = {'cells': rows, 'tasks': tasks, 'categories': ['battle', 'preparation', 'objectives']}
    result = short_snapshot(source, tmp_path)
    model = result['models'][0]
    assert model['score'] == 0.5
    assert model['categories'] == {'battle': 0.5, 'preparation': 1.0}
    assert (model['finished'], model['planned'], model['complete']) == (2, 2, True)
    assert [c['retired'] for c in result['cells']] == [False, False, True]
    retired = result['tasks'][2]
    assert retired['retired'] and 'luck' in retired['retirement_reason']
    assert (result['finished'], result['planned']) == (2, 2)
    assert result['ranked_categories'] == ['battle', 'objectives']
    assert result['unranked_categories'] == ['preparation']
    from pokeagent_bench.showcase_costs import comparison
    priced = [dict(r, retired=r['task_id'] == 'objectives-find-capture-species') for r in rows]
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
    for relative, tag in (('focused-pass-v056/a', 'red-v0.10-newer'), ('focused-pass-v056/b/preparation', 'red-v0.9-older'),
                          ('batch/c', 'red-v0.10-newer')):
        (base / relative).mkdir(parents=True)
        (base / relative / 'manifest.json').write_text(json.dumps({'benchmark': tag}))
    rows = [{'id': 'a', 'task_id': 't', 'score_group': 't', 'category': 'battle', 'model': 'old',
             'mode': 'gameplay', 'state': 'finished', 'value': 1.0},
            {'id': 'b', 'task_id': 'p', 'score_group': 'p', 'category': 'battle', 'model': 'old',
             'mode': 'preparation', 'state': 'finished', 'value': 0.5}]
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


def test_cells_are_labeled_from_their_own_records(tmp_path):
    from pokeagent_bench.showcase import END_LINE, current_spec
    task = 'navigation-branching-cave'
    spec = current_spec(task)
    base = tmp_path / 'data'
    facts = {'cell-0001': ('fixed-battle-v4', END_LINE), 'cell-0002': (None, None),
             'cell-0003': ('fixed-battle-v3', 'An older prompt.'), 'cell-0223': (None, None)}
    for cell, (policy, prompt) in facts.items():
        (base / 'focused-pass-v056' / cell / 'assessment').mkdir(parents=True)
        if policy:
            (base / 'focused-pass-v056' / cell / 'assessment/assessment.json').write_text(json.dumps({'policy_version': policy}))
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
                      'cell-0003': ['earlier_policy', 'no_end_line'], 'cell-0223': ['harness_fault']}
    assert 'use_item' in result['cells'][3]['harness_fault']
    assert result['models'][0]['labels'] == {'earlier_spec': 1, 'earlier_start': 1, 'earlier_policy': 1,
                                             'no_end_line': 1, 'harness_fault': 1}
    assert set(result['label_text']) == {'earlier_spec', 'earlier_start', 'earlier_policy', 'no_end_line', 'harness_fault'}


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


def test_showcase_policy_matches_the_preparation_runtime():
    pytest.importorskip('pokecore')
    from pokeagent_bench.preparation_runtime import POLICY_VERSION
    from pokeagent_bench.showcase import CURRENT_POLICY
    assert CURRENT_POLICY == POLICY_VERSION


def test_community_rows_are_labeled_and_kept_out_of_the_cost_comparison(tmp_path):
    from pokeagent_bench.showcase import community_reports
    row = {'id': 'cell-0001', 'task_id': 't', 'score_group': 't', 'category': 'battle', 'model': 'official',
           'mode': 'gameplay', 'state': 'finished', 'value': 0.0, 'tokens': 100}
    suite = {'benchmark': 'red-v0.63-short-guard', 'tasks': [
        {'id': 't', 'category': 'battle', 'evaluation_spec_sha256': 'spec', 'variants': [{'variant': 'default', 'fixture_sha256': 'fx'}]}]}
    report = {'format': 'pokebench-verified-report-v1', 'verified': True, 'suite': 'short', 'model': 'local-model',
              'label': 'Community, replay verified, model unverified', 'handle': 'octocat', 'attempts_declared': 2,
              'harness': {'benchmark': 'red-v0.63-short-guard'}, 'bundle_sha256': 'abc',
              'cells': [dict(row, model='local-model', value=1.0, tokens=500, notes='private', variant='default',
                             evaluation_spec_sha256='spec', fixture_sha256='fx')]}
    (tmp_path / 'community').mkdir()
    for name, value in (('a', report), ('b', dict(report, verified=False)), ('c', dict(report, suite='smoke'))):
        (tmp_path / 'community' / f'{name}.json').write_text(json.dumps(value))
    assert community_reports(tmp_path) == [report]
    result = short_snapshot({'cells': [row], 'tasks': [], 'categories': ['battle']}, tmp_path, community=[report], suite=suite)
    added, official = result['models']
    assert added['id'] == 'community/octocat/local-model' and added['label'] == 'local-model'
    assert added['community'] == {'label': 'Community, replay verified, model unverified', 'handle': 'octocat',
                                  'model': 'local-model', 'attempts': 2, 'bundle_sha256': 'abc'}
    assert added['score'] == 1.0 and added['tokens'] == 500 and added['cost']['low'] is None
    assert added['suite'] == {'benchmark': 'red-v0.63-short-guard', 'tasks': 1, 'source': 'bundle abc'}
    assert 'community' not in official and 'suite' not in official
    cell = result['cells'][1]
    assert cell['revision'] == 'Community' and cell['replay'] is None and 'notes' not in cell
    assert [m['id'] for m in result['efficiency']['models']] == ['official']


def test_only_existing_local_replays_are_linked(tmp_path):
    (tmp_path / 'replay.html').write_text('replay')
    assert existing_link(tmp_path, 'replay.html') == 'replay.html'
    assert existing_link(tmp_path, 'missing.html') is None
    assert existing_link(tmp_path, '../outside.html') is None


def test_score_interval_resamples_tasks_within_categories():
    rows = [{'task_id': f'b{i}', 'category': 'battle', 'state': 'finished', 'value': i % 2} for i in range(10)]
    rows += [{'task_id': 'n', 'category': 'navigation', 'state': 'finished', 'value': 1},
             {'task_id': 'p', 'category': 'navigation', 'state': 'pending', 'value': None}]
    same = [dict(r, value=1) for r in rows if r['state'] == 'finished']
    ignored = rows + [{'task_id': 'q', 'category': 'preparation', 'state': 'finished', 'value': 0},
                      {'task_id': 'r', 'category': 'objectives', 'state': 'finished', 'value': 0, 'retired': True}]
    first, again, skipped = score_interval(rows), score_interval(rows), score_interval(ignored)
    counted = score_interval(ignored, 2000, 20261026, [])
    assert first == again == skipped
    assert 0.5 < first['low'] < 0.75 < first['high'] < 1.0
    perfect = score_interval(same)
    assert perfect['low'] == perfect['high'] == 1.0
    assert score_interval([]) is None
    assert counted['high'] < first['high']
    # The values the page's own scoreInterval gave for these rows before the interval moved to the build.
    method = {'draws': 2000, 'method': 'stratified-task-bootstrap-v1'}
    assert first == dict(method, low=0.6, high=0.9)
    assert counted == dict(method, low=0.39999999999999997, high=0.6)


def site_data():
    def cell(model, task, category, **extra):
        return {'model': model, 'task_id': task, 'category': category, 'variant': 'default', 'state': 'finished', 'value': 1,
                'token_limit': 100, **extra}
    # Two ids that clean to the same file name, a task in a score group, a retired task and a task no row ran.
    models = [{'id': 'org/model:7b', 'label': 'A', 'suite': {'tasks': 3}}, {'id': 'org-model-7b', 'label': 'B'}]
    tasks = [{'id': 'nav one', 'category': 'navigation'}, {'id': 'battle', 'category': 'battle'},
             {'id': 'old', 'category': 'objectives', 'retired': True}, {'id': 'unrun', 'category': 'navigation'}]
    cells = [cell('org-model-7b', 'battle', 'battle', score_group='fights', state='pending', value=None),
             cell('org/model:7b', 'nav one', 'navigation'), cell('org/model:7b', 'battle', 'battle', score_group='fights', value=0),
             cell('org/model:7b', 'old', 'objectives', retired=True, token_limit=50)]
    return {'short': {'models': models, 'tasks': tasks, 'cells': cells, 'unranked_categories': ['preparation']}, 'long': []}


def test_site_summary_holds_no_attempts_and_the_attempt_files_hold_each_once(tmp_path):
    import hashlib
    source = site_data()
    stale = tmp_path / 'showcase-cells' / 'model' / 'gone.json'
    stale.parent.mkdir(parents=True)
    stale.write_text('[]')
    data = write_site(source, tmp_path)
    assert json.loads((tmp_path / 'showcase-data.json').read_text()) == data
    assert data['short']['cells'] == source['short']['cells']
    summary = json.loads((tmp_path / 'showcase-summary.json').read_text())
    assert 'cells' not in summary['short'] and summary['long'] == []
    first, second = summary['short']['models']
    for row, full in zip(summary['short']['models'], data['short']['models']):
        assert row['ci'] == full['ci'] == score_interval([c for c in source['short']['cells'] if c['model'] == row['id']], unranked=['preparation'])
    assert (first['ran'], second['ran']) == ('1110', '0100')
    assert first['token_cap'] == 200 and 'token_cap' not in second
    nav, battle, old, unrun = summary['short']['tasks']
    assert battle['score_group'] == 'fights' and 'score_group' not in nav
    assert battle['coverage'] == {'finished': 1, 'attempts': 2} and unrun['coverage'] == {'finished': 0, 'attempts': 0}

    def load(url):
        path, version = url.split('?v=')
        text = (tmp_path / path).read_text()
        assert hashlib.sha256(text.encode()).hexdigest()[:12] == version
        return json.loads(text)
    # The two ids that clean to one name each get a file of their own.
    assert first['cells'].split('?')[0] != second['cells'].split('?')[0]
    assert all(m['cells'].startswith('showcase-cells/model/org-model-7b') for m in (first, second))
    key = lambda c: (c['model'], c['task_id'])
    for kind in ('models', 'tasks'):
        loaded = [c for row in summary['short'][kind] for c in load(row['cells'])]
        assert sorted(loaded, key=key) == sorted(source['short']['cells'], key=key)
    # A task's file lists its attempts in row order.
    assert [c['model'] for c in load(battle['cells'])] == ['org/model:7b', 'org-model-7b']
    assert not stale.exists()
    # A row that leaves the page takes its file with it, and a stored interval is kept.
    source['short']['models'] = [dict(source['short']['models'][0], ci={'low': 0, 'high': 1})]
    source['short']['cells'] = [c for c in source['short']['cells'] if c['model'] == 'org/model:7b']
    write_site(source, tmp_path)
    again = json.loads((tmp_path / 'showcase-summary.json').read_text())
    assert again['short']['models'][0]['ci'] == {'low': 0, 'high': 1}
    # With no other id to clash with, the name needs no hash.
    assert [p.name for p in (tmp_path / 'showcase-cells' / 'model').iterdir()] == ['org-model-7b.json']


def test_site_refuses_a_task_split_across_score_groups(tmp_path):
    source = site_data()
    source['short']['cells'][0]['score_group'] = 'other'
    with pytest.raises(ValueError, match='more than one score group'):
        write_site(source, tmp_path)
    assert not (tmp_path / 'showcase-summary.json').exists()


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
