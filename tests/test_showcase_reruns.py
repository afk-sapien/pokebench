"""A model's new v0.37 source replaces its old Short cells or Long run only when complete, and moves no other row."""
import copy
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess

import pytest

from pokeagent_bench import showcase
from pokeagent_bench.showcase import (MAINTAINER_FORMAT, MAINTAINER_REVISION, RERUN_FORMAT, SOURCES, SUITE_FILE, build,
                                     community_reports, freeze, long_snapshot, maintainer_sources, short_snapshot)
from pokeagent_bench.showcase_costs import PRICING, comparison

OPUS, SOL = 'claude-opus-5-5', 'gpt-5.6-sol'
NEW = 'red-v0.63-short-guard'
ADDED = 'red-v0.62-milestone-short'
CATEGORIES = ['navigation', 'battle', 'operations', 'preparation', 'objectives']
OLD_STARTS = [('navigation-one', 'navigation', 'default'), ('battle-one', 'battle', 'default'),
              ('battle-one', 'battle', 'variant-b'), ('preparation-one', 'preparation', 'default')]
# The same number of tasks as the old set, so only the suite field, not a count, can mark the new row.
NEW_STARTS = [('navigation-one', 'navigation', 'default'), ('navigation-new', 'navigation', 'default'),
              ('battle-one', 'battle', 'default'), ('battle-one', 'battle', 'variant-b')]
ASSETS = Path(__file__).parents[1] / 'src/pokeagent_bench/showcase_assets'


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(value if isinstance(value, str) else json.dumps(value))


def attempt(folder, harness, tokens, model):
    """A finished attempt folder whose recorded usage prices it."""
    usage = {'input_tokens': tokens - 100, 'output_tokens': 100}
    write(folder / 'manifest.json', {'benchmark': harness, 'agent': {'model': model}, 'scenario': {'task_id': 't'}})
    write(folder / 'result.json', {'state': 'finished', 'usage': dict(usage, accounting_complete=True)})
    write(folder / 'decisions.jsonl', json.dumps({'usage': usage}) + '\n')


def task(task_id, category, **extra):
    return {'id': task_id, 'title': task_id.replace('-', ' ').capitalize(), 'category': category, 'goal': 'Goal.',
            'start': 'Start.', 'action_policy': 'assisted-gameplay-v1',
            'mode': 'preparation' if category == 'preparation' else 'gameplay', **extra}


def new_cells(model, first=101):
    rows = []
    for n, (task_id, category, variant) in enumerate(NEW_STARTS, first):
        value = 2 / 3 if task_id == 'navigation-new' else float(n % 2)
        rows.append({'id': f'cell-{n:04d}', 'task_id': task_id, 'category': category, 'score_group': task_id,
                     'model': model, 'provider': 'claude', 'variant': variant, 'mode': 'gameplay', 'repeat': 1,
                     'state': 'finished', 'value': value, 'tokens': 5000 + n, 'decisions': 9,
                     'stop_reason': 'completed', 'decision_limit': 200, 'token_limit': 6000000,
                     'evaluation_spec_sha256': f'spec-{task_id}', 'fixture_sha256': f'fx-{task_id}-{variant}-new'})
    return rows


def batch(base, folder, rows):
    """A v0.37 catalog batch folder as catalog-pass leaves it: progress.json plus one folder per attempt."""
    for row in rows:
        if row['state'] == 'finished' and not (base / folder / row['id']).exists():
            attempt(base / folder / row['id'], NEW, row['tokens'], row['model'])
    write(base / folder / 'progress.json', {'protocol': 'p', 'benchmark': None, 'status': 'running', 'cells': rows})


def long_run(base, run_id, model, *, state='finished', package='0.35.0', score=100):
    write(base / run_id / 'run/manifest.json', {'agent': {'model': model}, 'benchmark': f'red-v0.x-{run_id}',
                                                'package_version': package,
                                                'limits': {'max_model_calls': 2000, 'max_total_tokens': 30000000}})
    write(base / run_id / 'run/result.json', {'state': state, 'score': score, 'stop_reason': 'model_call_budget',
                                              'usage': {'calls': 2000, 'input_tokens': 900, 'output_tokens': 100}})


@pytest.fixture
def site(tmp_path):
    base, web = tmp_path / 'data', tmp_path / 'data/reviews/web'
    cells, n = [], 0
    for model in (SOL, OPUS):
        for task_id, category, variant in OLD_STARTS:
            n += 1
            cells.append({'id': f'cell-{n:04d}', 'task_id': task_id, 'category': category, 'score_group': task_id,
                          'model': model, 'variant': variant, 'mode': 'preparation' if category == 'preparation' else 'gameplay',
                          'state': 'finished', 'value': 0.5 if category == 'preparation' else float(n % 2),
                          'tokens': 1000 + n, 'decisions': 5, 'stop_reason': 'completed', 'decision_limit': 200,
                          'token_limit': 6000000, 'fixture_sha256': f'fx-{task_id}-{variant}-old',
                          'replay': f'replays/focused-v056-cell-{n:04d}.html'})
            attempt(base / 'focused-pass-v056' / cells[-1]['id'], 'red-v0.59-old', cells[-1]['tokens'], model)
            write(web / cells[-1]['replay'], 'replay')
    tasks = [task('navigation-one', 'navigation'), task('battle-one', 'battle'), task('preparation-one', 'preparation')]
    write(web / 'focused-analysis.json', {'cells': cells, 'tasks': tasks, 'categories': CATEGORIES})
    # One kept copy of an attempt per model, so the attempts log has an entry for each.
    for cell, model in (('cell-0001', SOL), ('cell-0005', OPUS)):
        write(base / f'focused-pass-v056/{cell}-quota-error-01/manifest.json',
              {'agent': {'model': model}, 'scenario': {'task_id': 'navigation-one'}})
    for name, model in (('opus', OPUS), ('sol', SOL), ('sonnet', 'claude-sonnet-5-5'), ('terra', 'gpt-5.6-terra')):
        long_run(base, f'long-v065-{name}', model)
    suite = {'format': 'pokebench-short-suite-v1', 'benchmark': NEW, 'package': '0.37.1', 'tag': 'v0.37.1', 'added_in': ADDED, 'tasks': [
        task('navigation-one', 'navigation', score_group='navigation-one', evaluation_spec_sha256='spec-navigation-one',
             variants=[{'variant': 'default', 'fixture_sha256': 'fx-navigation-one-default-new'}]),
        task('navigation-new', 'navigation', score_group='navigation-new', evaluation_spec_sha256='spec-navigation-new',
             milestones=3, variants=[{'variant': 'default', 'fixture_sha256': 'fx-navigation-new-default-new'}]),
        task('battle-one', 'battle', score_group='battle-one', evaluation_spec_sha256='spec-battle-one',
             variants=[{'variant': 'default', 'fixture_sha256': 'fx-battle-one-default-new'},
                       {'variant': 'variant-b', 'fixture_sha256': 'fx-battle-one-variant-b-new'}])]}
    write(tmp_path / 'suite.json', suite)
    # Opus finished every start. Sol is still running in the same batch and has no entry.
    batch(base, 'v037-pass', new_cells(OPUS) + [dict(r, state='running', value=None) for r in new_cells(SOL, 201)])
    write(web / 'v037-pass/replays/focused-v056-cell-0101.html', 'replay')
    write(base / 'v037-pass/cell-0102-quota-error-01/manifest.json', {'agent': {'model': OPUS}, 'scenario': {'task_id': 'navigation-new'}})
    write(base / 'v037-pass/cell-0201-quota-error-01/manifest.json', {'agent': {'model': SOL}, 'scenario': {'task_id': 'navigation-new'}})

    def current():
        """What the site builder produced before the swap: no rerun map, no stored sets."""
        source = showcase.load(web / 'focused-analysis.json')
        return {'schema': 'pokebench-showcase-v1', 'short': short_snapshot(source, web, [], base, community_reports(web)),
                'long': long_snapshot(base, web), 'pricing': PRICING, 'report': None}

    write(tmp_path / 'frozen.json', dict(format='pokebench-showcase-frozen-v1', **freeze(current()['short'])))

    def built(models, maintainer=()):
        write(tmp_path / 'sources.json', {'format': RERUN_FORMAT, 'models': models})
        write(tmp_path / 'maintainer.json', {'format': MAINTAINER_FORMAT, 'rows': list(maintainer)})
        data = plain(build(base, web, sources=tmp_path / 'sources.json', frozen=tmp_path / 'frozen.json',
                           suite=tmp_path / 'suite.json', maintainer=tmp_path / 'maintainer.json'))
        data.pop('updated_at')
        return data

    return type('Site', (), {'base': base, 'web': web, 'current': staticmethod(current), 'built': staticmethod(built)})


def plain(data):
    return json.loads(json.dumps(data, allow_nan=False))


def by(rows, model, keep=False):
    return [r for r in rows if (r.get('model', r.get('id')) == model) == keep]


def test_no_entries_build_exactly_what_the_site_showed(site, capsys):
    assert site.built({}) == plain(site.current())
    assert capsys.readouterr().err == ''


def test_a_complete_source_replaces_only_its_own_row_cells_and_the_task_table(site, capsys):
    before, after = site.built({}), site.built({OPUS: {'short': 'v037-pass'}})
    assert capsys.readouterr().err == ''
    b, a = before['short'], after['short']
    # No number on another row moves.
    assert by(a['models'], OPUS) == by(b['models'], OPUS) and len(by(a['models'], OPUS)) == 1
    assert by(a['cells'], OPUS) == by(b['cells'], OPUS)
    assert by(a['efficiency']['models'], OPUS) == by(b['efficiency']['models'], OPUS)
    assert by(a['attempts']['log'], OPUS) == by(b['attempts']['log'], OPUS)
    assert after['long'] == before['long']
    for key in set(b) - {'models', 'cells', 'tasks', 'efficiency', 'attempts', 'finished', 'planned'}:
        assert a[key] == b[key], key
    # The new batch replaces every old Opus cell and is never merged with them.
    new = by(a['cells'], OPUS, keep=True)
    assert [c['id'] for c in new] == ['cell-0101', 'cell-0102', 'cell-0103', 'cell-0104']
    assert {(c['source'], c['revision'], c['harness']) for c in new} == {('v037-pass', 'v0.37 rerun', NEW)}
    assert all(c['labels'] == [] and c['cost']['low'] > 0 for c in new)
    assert new[0]['replay'] == 'v037-pass/replays/focused-v056-cell-0101.html' and new[1]['replay'] is None
    row = by(a['models'], OPUS, keep=True)[0]
    assert row['suite'] == {'benchmark': NEW, 'tasks': 3, 'source': 'v037-pass'}
    assert (row['finished'], row['planned'], row['complete'], row['harness']['label']) == (4, 4, True, 'red-v0.63')
    assert row['categories'] == {'navigation': pytest.approx((1 + 2 / 3) / 2), 'battle': 0.5}
    assert 'suite' not in by(a['models'], OPUS)[0]
    # Trials count kept and adopted attempts only, never the unadopted Sol attempts still running in the batch.
    assert (a['finished'], a['planned']) == (b['finished'], b['planned']) == (8, 8)
    assert [e['cell'] for e in by(a['attempts']['log'], OPUS, keep=True)] == ['cell-0102']
    # The task table is the union of both sets, and the added task names the release that added it.
    assert [t['id'] for t in a['tasks']] == ['navigation-one', 'navigation-new', 'battle-one', 'preparation-one']
    assert [t for t in a['tasks'] if t['id'] != 'navigation-new'] == b['tasks']
    added = a['tasks'][1]
    assert (added['title'], added['suite'], added['milestones'], added['retired']) == ('Navigation new', ADDED, 3, False)
    # The cost comparison keeps its stored starts. The new row is priced on its own attempts at those starts.
    assert a['efficiency']['starts'] == b['efficiency']['starts'] == 3
    cost = by(a['efficiency']['models'], OPUS, keep=True)[0]
    assert cost['starts'] == 3 and cost['cost'] != by(b['efficiency']['models'], OPUS, keep=True)[0]['cost']


WHY = {'running': '3 of 4 cells finished (1 running).', 'paused': '3 of 4 cells finished (1 paused).',
       'evaluation_error': '3 of 4 cells finished (1 evaluation_error).', 'pending': '3 of 4 cells finished (1 pending).',
       'missing start': 'with 1 missing, 0 not in the suite and 0 repeated.', 'repeated start': 'and 1 repeated.',
       'unknown start': 'with 1 missing, 1 not in the suite', 'other spec': 'Regenerate it from the tag the batch ran.',
       'other start': 'Regenerate it from the tag the batch ran.', 'other harness': f'recorded harness red-v0.61-older, not {NEW}.',
       'no progress': 'has no progress.json yet.', 'no cells': 'has no cells for this model.',
       'outside': 'is not a folder under the data folder.'}


@pytest.mark.parametrize('break_it', WHY)
def test_an_incomplete_source_changes_nothing_and_says_why(site, capsys, break_it):
    before = site.built({})
    rows = new_cells(OPUS)
    folder = 'v037-broken'
    if break_it in ('running', 'paused', 'evaluation_error', 'pending'):
        rows[2].update(state=break_it, value=None)
    elif break_it == 'missing start':
        rows.pop()
    elif break_it == 'repeated start':
        rows.append(dict(rows[0], id='cell-0199'))
    elif break_it == 'unknown start':
        rows[0]['variant'] = 'variant-z'
    elif break_it == 'other spec':
        rows[0]['evaluation_spec_sha256'] = 'spec-older'
    elif break_it == 'other start':
        rows[0]['fixture_sha256'] = 'fx-older'
    elif break_it == 'no cells':
        rows = new_cells(SOL)
    elif break_it == 'outside':
        folder = '../outside'
    if break_it != 'no progress':
        batch(site.base, folder, rows)
    if break_it == 'other harness':
        write(site.base / folder / 'cell-0103/manifest.json', {'benchmark': 'red-v0.61-older'})
    if break_it == 'no progress':
        (site.base / folder).mkdir()
    after = site.built({OPUS: {'short': folder}})
    assert after == before
    error = capsys.readouterr().err
    assert error.startswith(f'{OPUS} Short: kept the old row. ') and error.count('\n') == 1
    assert WHY[break_it] in error


def test_a_finished_long_run_replaces_only_that_models_run(site, capsys):
    before = site.built({})
    long_run(site.base, 'long-v037-sol', SOL, package='0.37.1', score=300)
    after = site.built({SOL: {'long': 'long-v037-sol'}})
    assert capsys.readouterr().err == ''
    assert after['short'] == before['short']
    assert by(after['long'], SOL) == by(before['long'], SOL) and len(by(after['long'], SOL)) == 3
    row = by(after['long'], SOL, keep=True)[0]
    assert (row['run_id'], row['score'], row['harness'], row['decision_limit']) == ('long-v037-sol', 300, 'red-v0.x-long-v037-sol', 2000)


@pytest.mark.parametrize('state, model, package, why', [
    ('running', SOL, '0.37.1', 'is running, not finished.'), ('paused', SOL, '0.37.1', 'is paused, not finished.'),
    ('finished', OPUS, '0.37.1', f'ran {OPUS}, not this model.'), ('finished', SOL, '0.36.0', 'ran package 0.36.0, not 0.37.x.')])
def test_an_unfinished_or_mismatched_long_run_changes_nothing(site, capsys, state, model, package, why):
    before = site.built({})
    long_run(site.base, 'long-v037-sol', model, state=state, package=package)
    assert site.built({SOL: {'long': 'long-v037-sol'}}) == before
    error = capsys.readouterr().err
    assert error.startswith(f'{SOL} Long: kept the old row. ') and why in error


def test_a_stored_comparison_set_keeps_other_rows_fixed():
    def cell(model, task_id, value, low):
        return {'model': model, 'task_id': task_id, 'variant': 'default', 'category': 'battle', 'score_group': task_id,
                'state': 'finished', 'value': value, 'cost': {'low': low, 'high': low, 'partial': False}}
    cells = [cell(m, t, 1.0, 2.0) for m in ('a', 'b') for t in ('one', 'two')]
    models = [{'id': m, 'label': m} for m in ('a', 'b', 'c')]
    stored = {('one', 'default'), ('two', 'default')}
    alone = comparison(cells, models[:2], stored)
    joined = comparison(cells + [cell('c', 'one', 0.0, 1.0)], models, stored)
    assert joined['models'][:2] == alone['models'] and joined['starts'] == alone['starts'] == 2
    assert joined['models'][2]['starts'] == 1
    # Without the stored set, a new row that lacks a start would shrink every other row's comparison.
    assert comparison(cells + [cell('c', 'one', 0.0, 1.0)], models)['models'][0]['starts'] == 1


def test_stored_suite_lists_the_v037_short_tasks():
    from pokeagent_bench.evaluation_catalog import load_catalog
    suite = showcase.load(SOURCES / SUITE_FILE)
    assert (suite['benchmark'], suite['package'], suite['tag'], suite['added_in']) == (NEW, '0.37.1', 'v0.37.1', ADDED)
    assert len(suite['tasks']) == 44 and sum(len(t['variants']) for t in suite['tasks']) == 46
    added = {t['id'] for t in suite['tasks'] if t.get('milestones')}
    assert added == {'battle-elite-four-no-items', 'battle-mt-moon-underleveled', 'navigation-pewter-to-lavender',
                     'navigation-seafoam-islands', 'navigation-silph-co', 'navigation-victory-road', 'objectives-cinnabar-gym'}
    catalog = {t['id']: group['category'] for group in load_catalog(include_retired=True) for t in group['evals']}
    assert added.isdisjoint(catalog)
    assert all(catalog[t['id']] == t['category'] for t in suite['tasks'] if t['id'] not in added)
    assert all(t['title'] and t['goal'] and t['category'] in CATEGORIES for t in suite['tasks'])
    assert isinstance(showcase.rerun_sources(SOURCES / 'rerun-sources.json'), dict)


RENDER = r'''
const fs = require('fs')
const [stats, app, dataPath] = process.argv.slice(2)
const els = {}
const el = id => els[id] ||= {innerHTML: '', textContent: '', value: '', hidden: false, tabIndex: 0, children: [], dataset: {},
  setAttribute() {}, addEventListener() {}, scrollIntoView() {}, focus() {}}
global.document = {getElementById: el, querySelectorAll: () => []}
global.location = {hash: ''}
global.history = {replaceState() {}}
global.window = {addEventListener() {}}
global.setInterval = () => 0
const data = JSON.parse(fs.readFileSync(dataPath, 'utf8'))
global.fetch = async () => ({ok: true, json: async () => data})
global.scoreInterval = require(stats).scoreInterval
eval(fs.readFileSync(app, 'utf8'))
setTimeout(() => console.log(JSON.stringify(Object.fromEntries(Object.entries(els).map(([k, v]) => [k, {html: v.innerHTML, text: v.textContent, hidden: v.hidden}])))), 0)
'''


def render(tmp_path, data):
    write(tmp_path / 'render.js', RENDER)
    write(tmp_path / 'render-data.json', dict(data, updated_at='2026-11-15T00:00:00+00:00'))
    output = subprocess.run(['node', str(tmp_path / 'render.js'), str(ASSETS / 'showcase-stats.js'), str(ASSETS / 'showcase.js'),
                             str(tmp_path / 'render-data.json')], check=True, capture_output=True, text=True).stdout
    page = json.loads(output)
    assert page['snapshot']['text'] == 'All trials finished'
    return page


@pytest.mark.skipif(not shutil.which('node'), reason='node is not installed')
def test_page_labels_task_sets_only_when_rows_differ(site, tmp_path):
    same = render(tmp_path, site.built({}))
    assert 'task' not in same['ranking']['html'].split('set</span>')[0][-40:] and ' set</span>' not in same['ranking']['html']
    assert same['suite-note']['hidden'] and 'Not run' not in same['tasks']['html']
    # One set is one group with no title, ranked as before.
    assert 'set-row' not in same['ranking']['html'] and re.findall(r'<span class="rank">([^<]*)</span>', same['ranking']['html']) == ['01', '02']
    mixed = render(tmp_path, site.built({OPUS: {'short': 'v037-pass'}}))
    found = groups(mixed['ranking']['html'])
    assert [(title, [rank for rank, _ in rows]) for title, rows in found] == [
        ('Current set, red-v0.63, 3 tasks', ['01']), ('Earlier set, 3 tasks', ['01'])]
    assert 'Opus' in found[0][1][0][1] and 'Opus' not in found[1][1][0][1]
    assert '3-task red-v0.63 set</span>' in mixed['ranking']['html'] and '3-task earlier set</span>' in mixed['ranking']['html']
    assert not mixed['suite-note']['hidden'] and 'The sets share 2 tasks.' in mixed['suite-note']['text']
    assert 'the 3-task red-v0.63 set: Navigation 2 tasks, 12.5 points each' in mixed['weight-note']['text']
    assert 'the 3-task earlier set: Navigation 1 tasks, 25.0 points each' in mixed['weight-note']['text']
    assert mixed['tasks']['html'].count('Not run.') == 2
    assert 'Added in red-v0.62' in mixed['tasks']['html'] and 'its 3 ordered milestones' in mixed['tasks']['html']
    assert '66.7%' in mixed['tasks']['html'] and 'fixed before the reruns' in mixed['short-cost']['html']


HAIKU = 'claude-haiku-5-5'
EXTRA = f'{HAIKU}@red-v0.63'
RUNS = 'release-runs/short-haiku'
BACKUP = 'release-runs/backup/cell-0302-v0371-provider-error'


def report_cells():
    return [dict(c, replay_verified=True) for c in new_cells(HAIKU, 301)]


def maintainer_entry(base, cells=None, **change):
    """A verified report, the run folder it came from and one kept copy, as a maintainer-rows.json entry."""
    cells = report_cells() if cells is None else cells
    for c in report_cells():
        if not (base / RUNS / c['id']).exists():
            attempt(base / RUNS / c['id'], NEW, c['tokens'], HAIKU)
            write(base / RUNS / c['id'] / 'manifest.json', {'benchmark': NEW, 'agent': {'model': HAIKU}, 'package_version': '0.37.2',
                                                           'scenario': {'task_id': c['task_id']}})
    write(base / BACKUP / 'manifest.json', {'agent': {'model': HAIKU}, 'scenario': {'task_id': 'navigation-new'}})
    write(base / BACKUP / 'result.json', {'state': 'evaluation_error', 'stop_reason': 'provider_error', 'usage': {'calls': 40}})
    write(base / 'release-rows/haiku.json', {'format': 'pokebench-verified-report-v1', 'verified': True, 'problems': [],
                                             'suite': 'short', 'model': HAIKU, 'bundle_sha256': 'bundle',
                                             'harness': {'benchmark': NEW, 'package_version': '0.37.4'}, 'cells': cells})
    entry = {'id': EXTRA, 'model': HAIKU, 'suite': 'short', 'report': 'release-rows/haiku.json',
             'report_sha256': hashlib.sha256((base / 'release-rows/haiku.json').read_bytes()).hexdigest(), 'runs': RUNS,
             'replaced': {BACKUP: 'Stopped by a provider error.'}, 'release': 'v0.37.4',
             'label': 'Maintainer run, replay verified', 'detail': 'Ranked with the rows on the current set.'}
    return dict(entry, **change)


def test_a_maintainer_row_sits_beside_the_ranked_rows_and_moves_none_of_them(site, capsys):
    before, after = site.built({}), site.built({}, [maintainer_entry(site.base)])
    assert capsys.readouterr().err == ''
    b, a = before['short'], after['short']
    assert by(a['models'], EXTRA) == b['models'] and by(a['cells'], EXTRA) == b['cells']
    assert by(a['attempts']['log'], EXTRA) == b['attempts']['log'] and after['long'] == before['long']
    # It takes no part in the cost comparison or the frozen starts.
    assert a['efficiency'] == b['efficiency'] and freeze(copy.deepcopy(a)) == freeze(copy.deepcopy(b))
    row = by(a['models'], EXTRA, keep=True)[0]
    assert (row['label'], row['complete'], row['harness']['label']) == ('Haiku (red-v0.63)', True, 'red-v0.63')
    assert row['suite'] == {'benchmark': NEW, 'tasks': 3, 'source': RUNS}
    assert row['maintainer'] == {'label': 'Maintainer run, replay verified', 'detail': 'Ranked with the rows on the current set.', 'model': HAIKU,
                                 'release': 'v0.37.4', 'packages': ['0.37.2'], 'verified_on': '0.37.4',
                                 'report_sha256': maintainer_entry(site.base)['report_sha256'], 'bundle_sha256': 'bundle',
                                 'wall_seconds': None}
    cells = by(a['cells'], EXTRA, keep=True)
    assert [c['id'] for c in cells] == ['cell-0301', 'cell-0302', 'cell-0303', 'cell-0304']
    assert {(c['source'], c['revision'], c['harness'], c['replay']) for c in cells} == {(RUNS, MAINTAINER_REVISION, NEW, None)}
    assert all(c['cost']['low'] > 0 for c in cells) and (a['finished'], a['planned']) == (12, 12)
    assert by(a['attempts']['log'], EXTRA, keep=True) == [
        {'batch': RUNS, 'cell': 'cell-0302', 'kind': 'replaced', 'reason': 'Stopped by a provider error.', 'model': EXTRA,
         'task_id': 'navigation-new', 'stop_reason': 'provider_error', 'decisions': 40}]
    assert [t for t in a['tasks'] if t['id'] != 'navigation-new'] == b['tasks']


OFF = {'sha': 'does not match its listed sha256.', 'tokens': 'used a different token count than the report.',
       'unverified': 'is finished and not replay verified.', 'missing': 'with 1 missing, 0 not in the suite and 0 repeated.',
       'harness': f'recorded harness red-v0.61-older, not {NEW}.', 'model': 'ran a different model or task than the report.',
       'outside': 'is not a folder under the data folder.', 'other spec': f'that {SUITE_FILE} does not list.'}


@pytest.mark.parametrize('break_it', OFF)
def test_a_maintainer_row_its_runs_do_not_back_stays_off_the_site(site, capsys, break_it):
    before = site.built({})
    cells = report_cells()
    if break_it == 'unverified':
        cells[1]['replay_verified'] = False
    elif break_it == 'missing':
        cells.pop()
    elif break_it == 'other spec':
        cells[0]['evaluation_spec_sha256'] = 'spec-older'
    entry = maintainer_entry(site.base, cells)
    if break_it == 'sha':
        entry['report_sha256'] = '0' * 64
    elif break_it == 'tokens':
        write(site.base / RUNS / 'cell-0303/result.json', {'state': 'finished', 'usage': {'input_tokens': 1, 'output_tokens': 1}})
    elif break_it in ('harness', 'model'):
        manifest = json.loads((site.base / RUNS / 'cell-0303/manifest.json').read_text())
        if break_it == 'harness':
            manifest['benchmark'] = 'red-v0.61-older'
        else:
            manifest['agent']['model'] = OPUS
        write(site.base / RUNS / 'cell-0303/manifest.json', manifest)
    elif break_it == 'outside':
        entry['runs'] = '../outside'
    assert site.built({}, [entry]) == before
    error = capsys.readouterr().err
    assert error.startswith(f'{EXTRA}: left off the site. ') and error.count('\n') == 1 and OFF[break_it] in error


@pytest.mark.parametrize('change, why', [({'format': 'other'}, 'is not a'), ({'rows': [{'id': 'x'}]}, 'each row names exactly'),
                                         ({'rows': [dict.fromkeys(showcase.MAINTAINER_KEYS, 'x')]}, 'only Short rows')])
def test_the_maintainer_list_names_every_field_and_only_short_rows(tmp_path, change, why):
    write(tmp_path / 'rows.json', {'format': MAINTAINER_FORMAT, 'rows': [], **change})
    with pytest.raises(ValueError, match=why):
        maintainer_sources(tmp_path / 'rows.json')


def test_the_checked_in_maintainer_list_holds_the_haiku_row():
    rows = maintainer_sources(SOURCES / 'maintainer-rows.json')
    assert [(r['id'], r['model'], r['release'], r['label']) for r in rows] == [
        (EXTRA, HAIKU, 'v0.37.4', 'Maintainer run, replay verified')]


@pytest.mark.skipif(not shutil.which('node'), reason='node is not installed')
def groups(html):
    """The ranking table as [(group title, [(rank, row html)])], in page order."""
    found = []
    for row in html.split('<tr ')[1:]:
        title = re.search(r'scope="colgroup"><span>([^<]*)</span>', row)
        if title:
            found.append((title[1], []))
        else:
            found[-1][1].append((re.search(r'<span class="rank"[^>]*>([^<]*)</span>', row)[1], row))
    return found


@pytest.mark.skipif(not shutil.which('node'), reason='node is not installed')
def test_page_ranks_each_task_set_as_its_own_group_with_the_current_set_first(site, tmp_path):
    page = render(tmp_path, site.built({}, [maintainer_entry(site.base)]))
    found = groups(page['ranking']['html'])
    assert [title for title, _ in found] == ['Current set, red-v0.63, 3 tasks', 'Earlier set, 3 tasks']
    assert [[rank for rank, _ in rows] for _, rows in found] == [['01'], ['01', '02']]
    extra = found[0][1][0][1]
    assert 'Haiku (red-v0.63)' in extra and 'maintainer-note' in extra and 'Maintainer run, replay verified' in extra
    assert 'Ran on package 0.37.2. Replay verified on v0.37.4.' in extra and 'Ranked with the rows on the current set.' in extra
    assert not any('Haiku' in row for _, row in found[1][1]) and '—</span>' not in page['ranking']['html']
    assert f'colspan="{len(CATEGORIES) + 5}"' in page['ranking']['html']
    note = page['suite-note']['text']
    assert note.startswith('Task sets differ between rows, so each set is ranked as its own group, the current set first.')
    assert ('Haiku (red-v0.63) is a maintainer run on the red-v0.63 Short suite, ranked in the current set. '
            "That model's earlier row keeps its place in the earlier set.") in note
    assert 'The rows in the earlier set keep their earlier results.' in note and 'scores in different groups are not' in note
    assert 'not given a rank' not in note and ';' not in note and '—' not in note
    assert 'is a maintainer run on a newer harness and stays out of this comparison.' in page['short-cost']['html']
    assert 'fixed before the reruns' not in page['short-cost']['html'] and 'Verified, not published' in page['tasks']['html']
    # Models are counted once each. Haiku has no earlier row here, so it is the third.
    assert '<strong>3</strong><span>models</span>' in page['short-stats']['html']
    # Each task set shows its own size, the current set first, and the union no row ran is not shown.
    stats = re.findall(r'<strong>([^<]*)</strong><span>([^<]*)</span>', page['short-stats']['html'])
    assert stats[:2] == [('3', 'red-v0.63 set tasks'), ('3', 'earlier set tasks')] and all(label != 'tasks' for _, label in stats)
    assert '<strong>3</strong><span>tasks</span>' in render(tmp_path, site.built({}))['short-stats']['html']
    # A maintainer row of a model that already has a ranked row adds no model.
    data = site.built({}, [maintainer_entry(site.base)])
    for row in data['short']['models']:
        row.get('maintainer', {}).update(model=OPUS)
    assert '<strong>2</strong><span>models</span>' in render(tmp_path, data)['short-stats']['html']


LOCAL = 'community/octocat/local-model'


def community_report(site, **change):
    """A verified community report of the stored suite, as community-add leaves it in the web folder."""
    report = {'format': 'pokebench-verified-report-v1', 'verified': True, 'suite': 'short', 'model': 'local-model',
              'label': 'Community, replay verified, model unverified', 'handle': 'octocat', 'attempts_declared': 2,
              'harness': {'benchmark': NEW}, 'bundle_sha256': 'abcdef0123456789', 'problems': [],
              'cells': [dict(c, replay_verified=True, value=1.0) for c in new_cells('local-model', 401)]}
    report.update(change)
    write(site.web / 'community/octocat.json', report)
    return report


@pytest.mark.skipif(not shutil.which('node'), reason='node is not installed')
def test_a_community_row_on_the_stored_suite_ranks_in_the_current_set_with_its_own_label(site, tmp_path, capsys):
    before = site.built({}, [maintainer_entry(site.base)])
    community_report(site)
    data = site.built({}, [maintainer_entry(site.base)])
    assert capsys.readouterr().err == ''
    a, b = data['short'], before['short']
    # It moves no other row and stays out of the cost comparison.
    assert by(a['models'], LOCAL) == b['models'] and by(a['cells'], LOCAL) == b['cells'] and a['efficiency'] == b['efficiency']
    row = by(a['models'], LOCAL, keep=True)[0]
    assert row['suite'] == {'benchmark': NEW, 'tasks': 3, 'source': 'bundle abcdef012345'} and row['cost']['low'] is None
    # Its cells are checked against the stored suite, so they carry no earlier start label.
    assert all(c['labels'] == [] and c['harness'] == NEW for c in by(a['cells'], LOCAL, keep=True))
    found = groups(render(tmp_path, data)['ranking']['html'])
    assert [title for title, _ in found] == ['Current set, red-v0.63, 3 tasks', 'Earlier set, 3 tasks']
    # Every task passed, so the community row outscores Haiku and takes 01 of the current set.
    current = [(rank, 'Haiku (red-v0.63)' in html, 'Community, replay verified, model unverified' in html) for rank, html in found[0][1]]
    assert current == [('01', False, True), ('02', True, False)]
    assert not any('local-model' in html for _, html in found[1][1])
    note = render(tmp_path, data)['suite-note']['text']
    assert 'local-model is a community run on the red-v0.63 Short suite, ranked in the current set with its own label.' in note


@pytest.mark.parametrize('change, why', [
    ({'harness': {'benchmark': 'red-v0.61-fair-harness'}}, f'It ran red-v0.61-fair-harness, not the stored {NEW} suite.'),
    ({'cells': [dict(c, replay_verified=True) for c in new_cells('local-model', 401)][:-1]},
     'with 1 missing, 0 not in the suite and 0 repeated.'),
    ({'cells': [dict(c, replay_verified=True, fixture_sha256='fx-older') for c in new_cells('local-model', 401)]},
     f'cell-0401 ran a task definition or start that {SUITE_FILE} does not list.')])
def test_a_community_row_off_the_stored_suite_stays_off_the_board_with_the_reason(site, capsys, change, why):
    before = site.built({})
    community_report(site, **change)
    assert site.built({}) == before
    error = capsys.readouterr().err
    assert error.startswith(f'{LOCAL}: left off the site. ') and error.count('\n') == 1 and why in error


def test_short_snapshot_shows_community_rows_only_against_a_stored_suite(site):
    report = community_report(site)
    with pytest.raises(ValueError, match='only on the stored suite'):
        short_snapshot({'cells': [], 'tasks': [], 'categories': []}, site.web, community=[report])


def test_submit_section_pins_one_release_and_links_the_guide_on_main():
    page = (ASSETS / 'index.html').read_text()
    section = page.split('<section id="submit"', 1)[1].split('</section>', 1)[0]
    assert '<a href="#submit">Submit</a>' in page
    commands = re.findall(r'<code>(uvx [^<]*)</code>', section)
    tags = {re.search(r'pokebench@(v[\d.]+) pokebench ', c)[1] for c in commands}
    assert len(commands) == 4 and len(tags) == 1 and f'from release {tags.pop()}, installed unchanged' in section
    assert [c.split(' pokebench ', 1)[1].split()[:3] for c in commands] == [
        ['setup', '--rom', '/path/to/red.gb'], ['enter', '--suite', 'smoke'], ['enter', '--suite', 'short'], ['enter', '--suite', 'short']]
    assert 'href="https://github.com/afk-sapien/pokebench/blob/main/SUBMITTING.md"' in section
    assert '—' not in section and ';' not in section.replace('&amp;', '')


@pytest.mark.skipif(not shutil.which('node'), reason='node is not installed')
def test_submit_cost_reads_the_current_set_caps_and_its_priced_runs(site, tmp_path):
    data = site.built({}, [maintainer_entry(site.base)])
    row = next(m for m in data['short']['models'] if m.get('maintainer'))
    worst = sum(c['token_limit'] for c in data['short']['cells'] if c['model'] == row['id'] and not c.get('retired'))
    html = render(tmp_path, data)['submit-cost']['html']
    assert f'up to {worst / 1e6:.1f}M tokens, input plus output' in html
    assert f'{HAIKU} used {row["tokens"] / 1e6:.1f}M, an estimated ${row["cost"]["low"]:.2f}' in html
    assert '<strong>Local model:</strong> free.' in html and '—' not in html.replace('–', '')
    # The test runs record no play time, so no time line is shown.
    assert row['maintainer']['wall_seconds'] is None and 'Time:' not in html
    # With no priced row on a stored set the page keeps its static text.
    assert 'submit-cost' not in render(tmp_path, site.built({}))


@pytest.mark.skipif(not shutil.which('node'), reason='node is not installed')
def test_submit_time_is_one_example_from_the_kept_attempts_play_time(site, tmp_path):
    entry = maintainer_entry(site.base)
    for number, seconds in zip(range(301, 305), (20000, 21000, 20000, 1000)):
        path = site.base / RUNS / f'cell-{number:04d}/result.json'
        write(path, dict(json.loads(path.read_text()), wall_seconds=seconds + 0.4))
    data = site.built({}, [entry])
    row = next(m for m in data['short']['models'] if m.get('maintainer'))
    # The replaced attempt is not counted, only the four kept ones.
    assert row['maintainer']['wall_seconds'] == 62002
    html = render(tmp_path, data)['submit-cost']['html']
    assert ('<p><strong>Time:</strong> one example, not a promise. The published claude-haiku-5-5 run played the whole Short suite, '
            'one task at a time, in about 17 hours. Yours depends on the model, its provider and your machine.</p>') in html
    for row in data['short']['models']:
        row.get('maintainer', {}).update(wall_seconds=600)
    assert 'in about 10 minutes.' in render(tmp_path, data)['submit-cost']['html']


REAL = os.environ.get('POKEBENCH_SITE_DATA')


@pytest.mark.skipif(not REAL, reason='set POKEBENCH_SITE_DATA to the data folder to compare with the stored site data')
def test_real_site_data_is_unchanged_with_no_entries(tmp_path):
    base = Path(REAL)
    web = base / 'reviews/all-results-preview'
    stored = json.loads((web / 'showcase-data.json').read_text())
    write(tmp_path / 'sources.json', {'format': RERUN_FORMAT, 'models': {}})
    write(tmp_path / 'maintainer.json', {'format': MAINTAINER_FORMAT, 'rows': []})
    data = plain(build(base, web, sources=tmp_path / 'sources.json', maintainer=tmp_path / 'maintainer.json'))
    for value in (stored, data):
        value.pop('updated_at')
    assert data == stored
    frozen = showcase.load(SOURCES / 'frozen.json')
    assert freeze(copy.deepcopy(data['short'])) == {k: frozen[k] for k in ('comparison_starts', 'current_starts')}


@pytest.mark.skipif(not REAL, reason='set POKEBENCH_SITE_DATA to the data folder to check the checked-in maintainer rows')
def test_real_maintainer_rows_are_adopted_and_move_no_other_row(tmp_path, capsys):
    base = Path(REAL)
    web = base / 'reviews/all-results-preview'
    write(tmp_path / 'sources.json', {'format': RERUN_FORMAT, 'models': {}})
    write(tmp_path / 'maintainer.json', {'format': MAINTAINER_FORMAT, 'rows': []})
    before = plain(build(base, web, sources=tmp_path / 'sources.json', maintainer=tmp_path / 'maintainer.json'))['short']
    after = plain(build(base, web, sources=tmp_path / 'sources.json'))['short']
    assert capsys.readouterr().err == ''
    assert by(after['models'], EXTRA) == before['models'] and by(after['cells'], EXTRA) == before['cells']
    assert after['efficiency'] == before['efficiency']
    row = by(after['models'], EXTRA, keep=True)[0]
    assert (row['label'], row['finished'], row['planned'], round(row['score'], 3)) == ('Haiku (red-v0.63)', 46, 46, 0.628)
    assert row['maintainer']['packages'] == ['0.37.1', '0.37.2'] and row['maintainer']['release'] == 'v0.37.4'
    # 46 kept attempts, summed: about 17.2 hours of play.
    assert row['maintainer']['wall_seconds'] == 61934
