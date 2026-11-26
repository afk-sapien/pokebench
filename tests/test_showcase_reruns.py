"""A model's new v0.37 source replaces its old Short cells or Long run only when complete, and moves no other row."""
import copy
import hashlib
from html import unescape
import json
import os
from pathlib import Path
import re
import shutil
import subprocess

import pytest

from pokeagent_bench import showcase
from pokeagent_bench.showcase import (MAINTAINER_FORMAT, MAINTAINER_REVISION, RERUN_FORMAT, SOURCES, SUITE_FILE, VERSIONS_FILE,
                                     VERSIONS_FORMAT, build, community_reports, freeze, long_snapshot, maintainer_sources,
                                     root_map, short_snapshot, short_versions, write_site)
from pokeagent_bench.showcase_costs import PRICING, comparison

OPUS, SOL = 'claude-opus-5-5', 'gpt-5.6-sol'
NEW = 'red-v0.63-short-guard'
ADDED = 'red-v0.62-milestone-short'
# A newer version no row has run, then the stored suite: one start per variant of each task the fixture suite lists.
NEXT = 'red-v0.64-harder-short'
VERSIONS = {'format': VERSIONS_FORMAT, 'versions': [
    {'benchmark': NEXT, 'runs': 5, 'tasks': 4, 'released': False, 'note': 'This version is not released yet.'},
    {'benchmark': NEW, 'runs': 4, 'tasks': 3, 'released': True}]}
# No row has run the newer version, so it has no table, only its note between the two tables.
TITLES = [f'{NEW}, 4 runs over 3 tasks', 'Earlier set, 4 runs over 3 tasks']
NEXT_NOTE = '<p class="version-note small">This version is not released yet.</p>'
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

    def built(models, maintainer=(), roots=None):
        write(tmp_path / 'sources.json', {'format': RERUN_FORMAT, 'models': models})
        write(tmp_path / 'maintainer.json', {'format': MAINTAINER_FORMAT, 'rows': list(maintainer)})
        write(tmp_path / 'versions.json', VERSIONS)
        data = plain(build(base, web, sources=tmp_path / 'sources.json', frozen=tmp_path / 'frozen.json',
                           suite=tmp_path / 'suite.json', maintainer=tmp_path / 'maintainer.json', roots=roots,
                           versions=tmp_path / 'versions.json'))
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
const path = require('path')
const [app, folder, opened, actions] = process.argv.slice(2)
const els = {}
const el = id => els[id] ||= {innerHTML: '', textContent: '', value: '', hidden: false, tabIndex: 0, children: [], dataset: {},
  listeners: {}, setAttribute() {}, addEventListener(type, fn) { this.listeners[type] = fn }, scrollIntoView() {}, focus() {}}
// The tasks open in the page. Each action then opens a task or picks a row, as a visitor would.
let open = JSON.parse(opened)
global.document = {getElementById: el, querySelectorAll: selector => selector === '.task[open]' ? open.map(task => ({dataset: {task}})) : []}
global.location = {hash: ''}
global.history = {replaceState() {}}
global.window = {addEventListener() {}}
global.setInterval = () => 0
const fetched = []
global.fetch = async url => {
  fetched.push(url)
  const file = path.join(folder, url.split('?')[0])
  return {ok: fs.existsSync(file), json: async () => JSON.parse(fs.readFileSync(file, 'utf8'))}
}
eval(fs.readFileSync(app, 'utf8'))
const settle = () => new Promise(done => setTimeout(done, 0))
;(async () => {
  await settle()
  for (const action of JSON.parse(actions)) {
    if (action.toggle) {
      open = [...open, action.toggle]
      els.tasks.listeners.toggle({target: {open: true, dataset: {task: action.toggle}}})
    }
    if (action.close) {
      open = open.filter(task => task !== action.close)
      els.tasks.listeners.toggle({target: {open: false, dataset: {task: action.close}}})
    }
    if (action.pick) els.ranking.listeners.click({target: {closest: () => ({dataset: {model: action.pick}})}})
    await settle()
  }
  const page = Object.fromEntries(Object.entries(els).map(([k, v]) => [k, {html: v.innerHTML, text: v.textContent, hidden: v.hidden}]))
  console.log(JSON.stringify({...page, fetched}))
})()
'''


def render(tmp_path, data, opened=None, actions=()):
    """Render the page from the files the site writes. With no list given, every task is open."""
    folder = tmp_path / 'render-site'
    folder.mkdir(exist_ok=True)
    write_site(dict(data, updated_at='2026-11-15T00:00:00+00:00'), folder)
    opened = [t['id'] for t in data['short']['tasks']] if opened is None else opened
    write(tmp_path / 'render.js', RENDER)
    output = subprocess.run(['node', str(tmp_path / 'render.js'), str(ASSETS / 'showcase.js'), str(folder), json.dumps(opened),
                             json.dumps(list(actions))], check=True, capture_output=True, text=True).stdout
    page = json.loads(output)
    assert page['snapshot']['text'] == 'All trials finished'
    return page


@pytest.mark.skipif(not shutil.which('node'), reason='node is not installed')
def test_page_labels_task_sets_only_when_rows_differ(site, tmp_path):
    same = render(tmp_path, site.built({}))
    assert 'task' not in same['ranking']['html'].split('set</span>')[0][-40:] and ' set</span>' not in same['ranking']['html']
    assert same['suite-note']['hidden'] and 'Not run' not in same['tasks']['html']
    # One set is one table with no title, ranked as before.
    assert 'set-title' not in same['ranking']['html'] and same['ranking']['html'].count('<table') == 1
    assert re.findall(r'<span class="rank">([^<]*)</span>', same['ranking']['html']) == ['01', '02']
    assert groups(same['ranking']['html'])[0][0] == ''
    mixed = render(tmp_path, site.built({OPUS: {'short': 'v037-pass'}}))
    found = groups(mixed['ranking']['html'])
    # The newer version no row has run has no table and lists no row, only its note.
    assert [(title, [rank for rank, _ in rows]) for title, rows in found] == list(zip(TITLES, [['01'], ['01']]))
    assert 'Opus' in found[0][1][0][1] and 'Opus' not in found[1][1][0][1] and NEXT not in mixed['ranking']['html']
    assert mixed['ranking']['html'].count(NEXT_NOTE) == 1
    assert '3-task red-v0.63 set</span>' in mixed['ranking']['html'] and '3-task earlier set</span>' in mixed['ranking']['html']
    assert not mixed['suite-note']['hidden'] and 'The sets share 2 tasks.' in mixed['suite-note']['text']
    assert 'the 3-task red-v0.63 set: Navigation 2 tasks, 12.5 points each' in mixed['weight-note']['text']
    assert 'the 3-task earlier set: Navigation 1 tasks, 25.0 points each' in mixed['weight-note']['text']
    assert mixed['tasks']['html'].count('Not run.') == 2
    assert 'Added in red-v0.62' in mixed['tasks']['html'] and 'its 3 ordered milestones' in mixed['tasks']['html']
    assert '66.7%' in mixed['tasks']['html'] and 'fixed before the reruns' in mixed['short-cost']['html']


@pytest.mark.skipif(not shutil.which('node'), reason='node is not installed')
def test_page_loads_attempts_only_for_the_task_or_row_a_visitor_opens(site, tmp_path):
    data = site.built({OPUS: {'short': 'v037-pass'}})
    tasks = [t['id'] for t in data['short']['tasks']]
    coverage = lambda page: re.findall(r'<span class="task-coverage">([^<]*)</span>', page['tasks']['html'])
    every = render(tmp_path, data)
    closed = render(tmp_path, data, opened=[])
    # The summary alone fills the ranking, the counts and each task's coverage line.
    assert closed['fetched'] == ['showcase-summary.json'] and 'Watch ↗' not in closed['tasks']['html']
    assert closed['tasks']['html'].count('Loading attempts…') == len(tasks) and coverage(closed) == coverage(every)
    assert closed['tasks']['html'].count('Not run.') == 2 and closed['ranking'] == every['ranking']
    opened = render(tmp_path, data, opened=[], actions=[{'toggle': tasks[0]}])
    assert [url.split('?')[0] for url in opened['fetched'][1:]] == [f'showcase-cells/task/{tasks[0]}.json']
    body = opened['tasks']['html'].split('</details>')
    assert 'Loading attempts…' not in body[0] and all('Loading attempts…' in part for part in body[1:-1])
    # Picking a row loads that row's file alone and fills every task from it.
    picked = render(tmp_path, data, opened=[], actions=[{'pick': SOL}])
    assert [url.split('?')[0] for url in picked['fetched'][1:]] == ['showcase-cells/model/gpt-5.6-sol.json']
    assert 'Loading' not in picked['tasks']['html'] and 'Opus' not in picked['tasks']['html']


@pytest.mark.skipif(not shutil.which('node'), reason='node is not installed')
def test_page_says_when_attempts_fail_and_loads_them_again_when_reopened(site, tmp_path):
    data = site.built({})
    task = data['short']['tasks'][0]['id']
    render(tmp_path, data, opened=[])
    missing = tmp_path / 'render-site' / 'showcase-cells' / 'task' / f'{task}.json'
    write(tmp_path / 'render.js', RENDER.replace("fs.existsSync(file)", f"fs.existsSync(file) && !file.endsWith({json.dumps(missing.name)})"))
    asked = lambda page: [url.split('?')[0] for url in page['fetched']].count(f'showcase-cells/task/{task}.json')

    def run(actions):
        output = subprocess.run(['node', str(tmp_path / 'render.js'), str(ASSETS / 'showcase.js'), str(tmp_path / 'render-site'),
                                 json.dumps([task]), json.dumps(actions)], check=True, capture_output=True, text=True).stdout
        return json.loads(output)
    # A browser fires toggle again for a task a render draws open. That is not a visitor opening it, so nothing is asked again.
    page = run([{'toggle': task}])
    assert page['tasks']['html'].count('Attempts could not be loaded.') == 1 and asked(page) == 1
    page = run([{'toggle': task}, {'close': task}, {'toggle': task}])
    assert page['tasks']['html'].count('Attempts could not be loaded.') == 1 and asked(page) == 2


HAIKU = 'claude-haiku-5-5'
EXTRA = f'{HAIKU}@red-v0.63'
RUNS = 'release-runs/short-haiku'
BACKUP = 'release-runs/backup/cell-0302-v0371-provider-error'


def report_cells():
    return [dict(c, replay_verified=True) for c in new_cells(HAIKU, 301)]


def maintainer_entry(base, cells=None, model=HAIKU, first=301, **change):
    """A verified report, the run folder it came from and, for Haiku, one kept copy, as a maintainer-rows.json entry."""
    haiku = model == HAIKU
    runs, report = (RUNS, 'release-rows/haiku.json') if haiku else (f'release-runs/short-{model}', f'release-rows/{model}.json')
    made = [dict(c, replay_verified=True) for c in new_cells(model, first)]
    cells = made if cells is None else cells
    for c in made:
        if not (base / runs / c['id']).exists():
            attempt(base / runs / c['id'], NEW, c['tokens'], model)
            write(base / runs / c['id'] / 'manifest.json', {'benchmark': NEW, 'agent': {'model': model}, 'package_version': '0.37.2',
                                                           'scenario': {'task_id': c['task_id']}})
    if haiku:
        write(base / BACKUP / 'manifest.json', {'agent': {'model': HAIKU}, 'scenario': {'task_id': 'navigation-new'}})
        write(base / BACKUP / 'result.json', {'state': 'evaluation_error', 'stop_reason': 'provider_error', 'usage': {'calls': 40}})
    write(base / report, {'format': 'pokebench-verified-report-v1', 'verified': True, 'problems': [],
                          'suite': 'short', 'model': model, 'bundle_sha256': 'bundle',
                          'harness': {'benchmark': NEW, 'package_version': '0.37.4'}, 'cells': cells})
    entry = {'id': f'{model}@red-v0.63', 'model': model, 'suite': 'short', 'report': report,
             'report_sha256': hashlib.sha256((base / report).read_bytes()).hexdigest(), 'runs': runs,
             'replaced': {BACKUP: 'Stopped by a provider error.'} if haiku else {}, 'release': 'v0.37.4',
             'label': 'Maintainer run, replay verified', 'detail': 'Ranked in the table of its suite version.'}
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
    assert row['maintainer'] == {'label': 'Maintainer run, replay verified', 'detail': 'Ranked in the table of its suite version.', 'model': HAIKU,
                                 'release': 'v0.37.4', 'packages': ['0.37.2'], 'verified_on': '0.37.4',
                                 'report_sha256': maintainer_entry(site.base)['report_sha256'], 'bundle_sha256': 'bundle',
                                 'effort': None, 'wall_seconds': None}
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


ROW = dict(dict.fromkeys(showcase.MAINTAINER_KEYS, 'x'), suite='short', replaced={})


@pytest.mark.parametrize('change, why', [({'format': 'other'}, 'is not a'), ({'rows': [{'id': 'x'}]}, 'each row names exactly'),
                                         ({'rows': [dict.fromkeys(showcase.MAINTAINER_KEYS, 'x')]}, 'only Short rows'),
                                         ({'rows': [dict(ROW, other='x')]}, 'each row names exactly'),
                                         ({'rows': [dict(ROW, root='../runs')]}, 'is not a plain name'),
                                         ({'rows': [dict(ROW, runs='/home/someone/runs')]}, 'is not relative'),
                                         ({'rows': [dict(ROW, report='~/report.json')]}, 'is not relative'),
                                         ({'rows': [dict(ROW, replaced={'/data/backup/cell-0001': 'x'})]}, 'is not relative')])
def test_the_maintainer_list_names_every_field_and_only_short_rows(tmp_path, change, why):
    write(tmp_path / 'rows.json', {'format': MAINTAINER_FORMAT, 'rows': [], **change})
    with pytest.raises(ValueError, match=why):
        maintainer_sources(tmp_path / 'rows.json')


TERRA, SONNET = 'gpt-5.6-terra', 'claude-sonnet-5-5'
SECOND = 'runs-20261123'


def test_the_checked_in_maintainer_list_holds_the_haiku_terra_and_sonnet_rows():
    rows = maintainer_sources(SOURCES / 'maintainer-rows.json')
    assert [(r['id'], r['model'], r['release'], r.get('root')) for r in rows] == [
        (EXTRA, HAIKU, 'v0.37.4', None), (f'{TERRA}@red-v0.63', TERRA, 'v0.37.4', SECOND),
        (f'{SONNET}@red-v0.63', SONNET, 'v0.37.4', SECOND)]
    # Terra and Sonnet take Haiku's label and rules, and neither ran an attempt again.
    assert {(r['label'], r['detail'], r['suite']) for r in rows} == {(rows[0]['label'], rows[0]['detail'], 'short')}
    assert rows[1]['replaced'] == rows[2]['replaced'] == {} and all(re.fullmatch('[0-9a-f]{64}', r['report_sha256']) for r in rows)
    assert [(r['report'], r['runs']) for r in rows[1:]] == [(f'runs/short-{m}.pokebench.verified.json', f'runs/short-{m}') for m in (TERRA, SONNET)]


def test_the_checked_in_sources_hold_no_absolute_path():
    for path in SOURCES.glob('*.json'):
        text = path.read_text()
        assert not re.search(r'"(/|~)|/home/|/Users/|/tmp/', text), path.name


def test_a_maintainer_row_under_a_root_is_read_there_and_shows_only_the_root_name(site, tmp_path, capsys):
    before = site.built({})
    second = tmp_path / 'second'
    entry = maintainer_entry(second, model=TERRA, first=502, root='runs-x')
    terra = f'{TERRA}@red-v0.63'
    assert site.built({}, [entry]) == before
    assert capsys.readouterr().err == f'{terra}: left off the site. Its root runs-x was not given. Pass --root runs-x=FOLDER.\n'
    # The same paths under the data folder are not the row's.
    assert site.built({}, [entry], roots={'runs-x': site.base}) == before
    assert capsys.readouterr().err == f'{terra}: left off the site. {entry["report"]} is not a file under the runs-x root.\n'
    data = site.built({}, [entry], roots={'runs-x': second})
    assert capsys.readouterr().err == ''
    b, a = before['short'], data['short']
    assert by(a['models'], terra) == b['models'] and by(a['cells'], terra) == b['cells'] and a['efficiency'] == b['efficiency']
    row = by(a['models'], terra, keep=True)[0]
    assert (row['label'], row['complete'], row['suite']['source']) == ('Terra (red-v0.63)', True, f'runs-x/release-runs/short-{TERRA}')
    assert all(c['source'] == row['suite']['source'] and c['cost']['low'] > 0 for c in by(a['cells'], terra, keep=True))
    assert str(tmp_path) not in json.dumps(data)


@pytest.mark.parametrize('items, why', [(['runs-x'], 'is not NAME=FOLDER'), (['../x=/data'], 'is not NAME=FOLDER'),
                                        (['runs-x='], 'is not NAME=FOLDER'), (['a=/one', 'a=/two'], 'given twice')])
def test_a_root_is_given_once_as_a_plain_name_and_a_folder(items, why):
    assert root_map(['runs-x=/data/second', 'b=rel']) == {'runs-x': Path('/data/second'), 'b': Path('rel')}
    with pytest.raises(ValueError, match=why):
        root_map(items)


@pytest.mark.parametrize('change, why', [
    (lambda v: v['versions'][1].update(runs=5), f'{NEW} must be listed with 4 runs over 3 tasks'),
    (lambda v: v['versions'].reverse(), 'newest first'), (lambda v: v['versions'].pop(), f'{NEW} must be listed'),
    (lambda v: v['versions'][0].pop('released'), 'each version names'), (lambda v: v.update(format='x'), 'is not a')])
def test_the_versions_list_runs_newest_first_and_agrees_with_the_stored_suite(site, tmp_path, change, why):
    suite = json.loads((tmp_path / 'suite.json').read_text())
    write(tmp_path / 'listed.json', VERSIONS)
    assert [(v['name'], v['runs'], v['tasks'], v['released']) for v in short_versions(tmp_path / 'listed.json', suite)] == [
        (NEXT, 5, 4, False), (NEW, 4, 3, True)]
    listed = copy.deepcopy(VERSIONS)
    change(listed)
    write(tmp_path / 'listed.json', listed)
    with pytest.raises(ValueError, match=why):
        short_versions(tmp_path / 'listed.json', suite)


def test_the_checked_in_versions_list_puts_the_unreleased_harder_suite_first():
    suite = showcase.load(SOURCES / SUITE_FILE)
    versions = short_versions(SOURCES / VERSIONS_FILE, suite)
    assert [(v['name'], v['runs'], v['tasks'], v['released']) for v in versions] == [
        (NEXT, 51, 49, False), (NEW, 46, 44, True)]
    assert versions[0]['note'] == ('The next Short suite version, red-v0.64-harder-short, adds five harder tasks. '
                                   'It is not released yet, and no model has run it.') and 'note' not in versions[1]
    # The harder suite is the stored suite and five more tasks, one start each.
    added = showcase.load(SOURCES / VERSIONS_FILE)['versions'][0]['added']
    assert len(set(added)) == 5 and set(added).isdisjoint(t['id'] for t in suite['tasks'])


def groups(html):
    """The ranking as [(table title, [(rank, row html)])], in page order. A table alone has the empty title."""
    tables = re.findall(r'(?:<h3 class="set-title">([^<]*)</h3>)?<div class="table-scroll"><table class="leaderboard">(.*?)</table></div>', html)
    return [(unescape(title), [(re.search(r'<span class="rank"[^>]*>([^<]*)</span>', row)[1], row) for row in body.split('<tr ')[1:]])
            for title, body in tables]


@pytest.mark.skipif(not shutil.which('node'), reason='node is not installed')
def test_page_ranks_each_suite_version_in_its_own_table_newest_first(site, tmp_path):
    page = render(tmp_path, site.built({}, [maintainer_entry(site.base)]))
    html = page['ranking']['html']
    found = groups(html)
    assert [title for title, _ in found] == TITLES
    assert [[rank for rank, _ in rows] for _, rows in found] == [['01'], ['01', '02']]
    # The board leads with the stored suite's ranked table. The version no row has run is its note alone, directly
    # below that table and above the earlier set, with no table and no rows.
    assert html.startswith(f'<section class="rank-set"><h3 class="set-title">{TITLES[0]}</h3>') and html.count(NEXT_NOTE) == 1
    assert f'</table></div></section>{NEXT_NOTE}<section class="rank-set"><h3 class="set-title">{TITLES[1]}</h3>' in html
    assert NEXT not in html and 'Not yet run' not in html and 'not-run-row' not in html
    # Each table has the full head, so every column keeps its title.
    assert html.count('<th>Model</th>') == 2 and html.count('<th>') == 2 * (len(CATEGORIES) + 5)
    extra = found[0][1][0][1]
    assert 'Haiku (red-v0.63)' in extra and 'maintainer-note' in extra and 'Maintainer run, replay verified' in extra
    assert 'Ran on package 0.37.2. Replay verified on v0.37.4.' in extra and 'Ranked in the table of its suite version.' in extra
    assert not any('Haiku' in row for _, row in found[1][1]) and '—</span>' not in html
    # These attempts record no effort, so no row shows one.
    assert 'harness-effort' not in html
    note = page['suite-note']['text']
    assert note.startswith('Task sets differ between rows, so each Short suite version a row has run is ranked in a table of its own, '
                           'newest first, and the earlier set is ranked last.')
    assert ('Haiku (red-v0.63) is a maintainer run on the red-v0.63 Short suite, ranked in the table of that version. '
            "That model's earlier row keeps its place in the earlier set.") in note
    assert 'The rows in the earlier set keep their earlier results.' in note and 'scores in different tables are not' in note
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


@pytest.mark.skipif(not shutil.which('node'), reason='node is not installed')
def test_a_version_gets_its_table_once_a_row_has_run_it(site, tmp_path):
    data = site.built({}, [maintainer_entry(site.base)])
    for row in data['short']['models']:
        if row.get('suite'):
            row['suite']['benchmark'] = NEXT
    html = render(tmp_path, data)['ranking']['html']
    # The newer version now has a row, so it leads with its own table and its note is gone.
    # The stored suite has no row left and no note, so it shows nothing.
    assert [(title, [rank for rank, _ in rows]) for title, rows in groups(html)] == [
        (f'{NEXT}, 5 runs over 4 tasks', ['01']), (TITLES[1], ['01', '02'])]
    assert 'version-note' not in html and html.count('<h3 class="set-title">') == 2


def set_efforts(base, efforts):
    """Record each kept Haiku attempt's reasoning effort in its manifest, as agent.reasoning_effort. None leaves it out."""
    for number, effort in zip(range(301, 305), efforts):
        path = base / RUNS / f'cell-{number:04d}/manifest.json'
        manifest = json.loads(path.read_text())
        manifest['agent'].pop('reasoning_effort', None)
        if effort is not None:
            manifest['agent']['reasoning_effort'] = effort
        write(path, manifest)


def effort_row(site):
    return next(m for m in site.built({}, [maintainer_entry(site.base)])['short']['models'] if m.get('maintainer'))


@pytest.mark.skipif(not shutil.which('node'), reason='node is not installed')
def test_a_maintainer_row_shows_the_one_effort_every_attempt_recorded(site, tmp_path):
    maintainer_entry(site.base)
    set_efforts(site.base, ['low'] * 4)
    data = site.built({}, [maintainer_entry(site.base)])
    row = next(m for m in data['short']['models'] if m.get('maintainer'))
    assert row['maintainer']['effort'] == 'low effort'
    found = groups(render(tmp_path, data)['ranking']['html'])
    # It sits in the Harness column under the harness version. The earlier rows show no effort.
    assert ('<span class="harness-version" title="red-v0.63-short-guard">red-v0.63</span>'
            '<span class="harness-effort">low effort</span></td>') in found[0][1][0][1]
    assert not any('harness-effort' in html for _, html in found[1][1])


def test_a_maintainer_row_gives_counts_when_its_attempts_record_mixed_efforts(site):
    maintainer_entry(site.base)
    set_efforts(site.base, ['low', 'medium', 'low', 'low'])
    assert effort_row(site)['maintainer']['effort'] == 'Effort: low in 3 runs, medium in 1'
    # An attempt that records no effort is counted too, after the recorded values.
    set_efforts(site.base, ['medium', 'low', 'low', None])
    assert effort_row(site)['maintainer']['effort'] == 'Effort: low in 2 runs, medium in 1, not recorded in 1'
    assert showcase.effort_text(['high', 'low']) == 'Effort: high in 1 run, low in 1'
    assert showcase.effort_text([None, '']) is None and showcase.effort_text([]) is None


LOCAL ='community/octocat/local-model'


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
    assert [title for title, _ in found] == TITLES
    # Every task passed, so the community row outscores Haiku and takes 01 of the stored suite's table.
    current = [(rank, 'Haiku (red-v0.63)' in html, 'Community, replay verified, model unverified' in html) for rank, html in found[0][1]]
    assert current == [('01', False, True), ('02', True, False)]
    assert not any('local-model' in html for _, html in found[1][1])
    note = render(tmp_path, data)['suite-note']['text']
    assert 'local-model is a community run on the red-v0.63 Short suite, ranked in the table of that version with its own label.' in note


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


GUIDE = re.compile(r'href="https://github\.com/afk-sapien/pokebench/blob/([0-9a-f]{40})/SUBMITTING\.md"')


def submit_section():
    page =(ASSETS / 'index.html').read_text()
    return page, page.split('<section id="submit"', 1)[1].split('</section>', 1)[0]


def test_submit_section_pins_one_release_and_one_guide_commit():
    page, section = submit_section()
    assert '<a href="#submit">Submit</a>' in page
    commands = re.findall(r'<code>(uvx [^<]*)</code>', section)
    tags = {re.search(r'pokebench@(v[\d.]+) pokebench ', c)[1] for c in commands}
    assert len(commands) == 4 and len(tags) == 1 and f'from release {tags.pop()}, installed unchanged' in section
    assert [c.split(' pokebench ', 1)[1].split()[:3] for c in commands] == [
        ['setup', '--rom', '/path/to/red.gb'], ['enter', '--suite', 'smoke'], ['enter', '--suite', 'short'], ['enter', '--suite', 'short']]
    # The guide link names one commit, so a later change on a branch cannot change the guide under these commands.
    assert len(GUIDE.findall(section)) == 1 and section.count('/SUBMITTING.md"') == 1
    assert '—' not in section and ';' not in section.replace('&amp;', '')


def test_submit_guide_commit_holds_every_command_on_the_page():
    _, section = submit_section()
    commit = GUIDE.search(section)[1]
    shown = subprocess.run(['git', 'show', f'{commit}:SUBMITTING.md'], cwd=ASSETS, capture_output=True, text=True) \
        if shutil.which('git') else None
    if not shown or shown.returncode:
        pytest.skip(f'commit {commit} is not in this clone')
    commands = [unescape(c) for c in re.findall(r'<code>([^<]*)</code>', section)]
    tag = re.search(r'pokebench@(v[\d.]+) ', section)[1]
    assert len(commands) == 5 and [c for c in commands if c not in shown.stdout] == []
    assert f'Run release `{tag}`, installed unchanged.' in shown.stdout


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
    # The written file adds each row's score interval, which the build leaves to the writer.
    for row in stored['short']['models']:
        row.pop('ci', None)
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
    # The rows under a root are left off when it is not given, each with its reason.
    assert capsys.readouterr().err == ''.join(f'{m}@red-v0.63: left off the site. Its root {SECOND} was not given. '
                                              f'Pass --root {SECOND}=FOLDER.\n' for m in (TERRA, SONNET))
    assert by(after['models'], EXTRA) == before['models'] and by(after['cells'], EXTRA) == before['cells']
    assert after['efficiency'] == before['efficiency']
    row = by(after['models'], EXTRA, keep=True)[0]
    assert (row['label'], row['finished'], row['planned'], round(row['score'], 3)) == ('Haiku (red-v0.63)', 46, 46, 0.628)
    assert row['maintainer']['packages'] == ['0.37.1', '0.37.2'] and row['maintainer']['release'] == 'v0.37.4'
    # 46 kept attempts, summed: about 17.2 hours of play.
    assert row['maintainer']['wall_seconds'] == 61934
    # Every row is ranked now, so the note sets the row apart from the earlier rows, not from the ranked ones.
    # Each suite version has its own table, so the note names that table rather than a current set.
    assert row['maintainer']['detail'] == ('Run by the maintainers on a newer harness than the earlier rows. '
                                           'Ranked in the table of its suite version.')


ROOTS = os.environ.get('POKEBENCH_SITE_ROOTS')
# The scores the runs' own logs print, 62.9 and 63.1.
TERRA_SCORE, SONNET_SCORE = 0.629, 0.631


@pytest.mark.skipif(not (REAL and ROOTS), reason='set POKEBENCH_SITE_DATA and POKEBENCH_SITE_ROOTS=NAME=FOLDER to check the rows under a root')
def test_real_rows_under_a_root_rank_beside_haiku_and_move_no_earlier_row(tmp_path, capsys):
    base = Path(REAL)
    web = base / 'reviews/all-results-preview'
    roots = root_map(ROOTS.split(','))
    write(tmp_path / 'sources.json', {'format': RERUN_FORMAT, 'models': {}})
    write(tmp_path / 'maintainer.json', {'format': MAINTAINER_FORMAT, 'rows': []})
    before = plain(build(base, web, sources=tmp_path / 'sources.json', maintainer=tmp_path / 'maintainer.json'))['short']
    after = plain(build(base, web, sources=tmp_path / 'sources.json', roots=roots))['short']
    assert capsys.readouterr().err == ''
    ids = [EXTRA, f'{TERRA}@red-v0.63', f'{SONNET}@red-v0.63']
    assert [m for m in after['models'] if m['id'] not in ids] == before['models']
    assert [c for c in after['cells'] if c['model'] not in ids] == before['cells'] and after['efficiency'] == before['efficiency']
    rows = {m['id']: m for m in after['models'] if m['id'] in ids}
    assert {k: (r['label'], r['finished'], r['planned'], round(r['score'], 3)) for k, r in rows.items()} == {
        EXTRA: ('Haiku (red-v0.63)', 46, 46, 0.628), ids[1]: ('Terra (red-v0.63)', 46, 46, TERRA_SCORE),
        ids[2]: ('Sonnet (red-v0.63)', 46, 46, SONNET_SCORE)}
    assert [rows[k]['suite']['source'] for k in ids[1:]] == [f'{SECOND}/runs/short-{m}' for m in (TERRA, SONNET)]
    assert all(rows[k]['maintainer']['packages'] == ['0.37.4'] for k in ids[1:])
    # Every kept attempt of all three rows recorded low effort.
    assert {k: r['maintainer']['effort'] for k, r in rows.items()} == dict.fromkeys(ids, 'low effort')
    assert [e for e in after['attempts']['log'] if e['model'] in ids[1:]] == []
    assert [(v['name'], v['runs'], v['tasks']) for v in after['versions']] == [
        (NEXT, 51, 49), (NEW, 46, 44), ('Earlier set', 49, 47)]
    # The page names each root, never its folder.
    assert not any(str(folder) in json.dumps(after) for folder in roots.values())
