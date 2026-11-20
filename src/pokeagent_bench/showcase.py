"""Build the compact local showcase from existing benchmark evidence."""
from collections import Counter, defaultdict
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import shutil
import sys

from .benchmark_tracks import UNRANKED_CATEGORIES
from .core import digest, encoded
from .evaluation_catalog import retired_tasks, task_definition
from .focused_analysis import grouped_scores
from .reporting_labels import ARCHIVES, HARNESS_FAULTS, LONG_PAIR_BLOCKS, NOTES, RETRY_RULE
from .showcase_costs import PRICING, comparison, run_cost, sum_cost
from .showcase_stats import score_interval

LABELS = {'claude-fable-5-1': 'Fable 5.1', 'gpt-6-astra': 'Astra', 'gpt-5.6-sol': 'Sol', 'gpt-5.6-terra': 'Terra',
          'gpt-5.6-luna': 'Luna', 'claude-opus-5-5': 'Opus',
          'claude-sonnet-5-5': 'Sonnet', 'claude-haiku-5-5': 'Haiku'}
ASSETS = ('showcase.css', 'showcase.js')
# The page loads the summary. Attempts sit in one file per row and one per task, fetched when opened.
SUMMARY = 'showcase-summary.json'
ATTEMPTS = 'showcase-cells'
CELL_FIELDS = ('id', 'task_id', 'category', 'score_group', 'model', 'variant', 'mode',
               'state', 'value', 'tokens', 'decisions', 'stop_reason', 'decision_limit',
               'token_limit', 'evaluation_spec_sha256', 'fixture_sha256')
# Checked-in inputs: which models have a new v0.37 source, the v0.37 Short task list, and the sets frozen before any swap.
SOURCES = Path(__file__).with_name('showcase_sources')
RERUN_FORMAT = 'pokebench-rerun-sources-v1'
RERUN_REVISION = 'v0.37 rerun'
MAINTAINER_REVISION = 'Maintainer run'
LONG_NAMES = {'claude-opus-5-5': 'opus', 'gpt-5.6-sol': 'sol', 'claude-sonnet-5-5': 'sonnet', 'gpt-5.6-terra': 'terra',
              'gpt-6-astra': 'astra', 'claude-fable-5-1': 'fable', 'gpt-5.6-luna': 'luna', 'claude-haiku-5-5': 'haiku'}


def load(path):
    return json.loads(Path(path).read_text())


def existing_link(web, relative):
    if not relative:
        return None
    path = (web / relative).resolve()
    if not path.is_relative_to(web.resolve()):
        return None
    return relative if path.is_file() else None


def harness_tag(run):
    """Return the benchmark version a run recorded, from its gameplay or preparation manifest."""
    for name in ('manifest.json', 'preparation/manifest.json'):
        path = Path(run) / name
        if path.exists():
            return load(path).get('benchmark')
    return None


TAG = re.compile(r'([a-z]+)-v(\d+(?:\.\d+)*)')


def tag_key(tag):
    match = TAG.match(tag)
    return (tuple(int(part) for part in match[2].split('.')) if match else (), tag)


def short_tag(tag):
    match = TAG.match(tag)
    return match[0] if match else tag


def harness_summary(rows):
    """Describe which harness revision and versions a group of attempts ran under."""
    tags = sorted({r['harness'] for r in rows if r.get('harness')}, key=tag_key)
    short = list(dict.fromkeys(short_tag(t) for t in tags))
    if not short:
        label = None
    elif len(short) == 1:
        label = short[0]
    else:
        label = short[0] + ' to ' + short[-1].split('-', 1)[-1]
    return {'revisions': sorted({r['revision'] for r in rows if r.get('revision')}),
            'versions': tags, 'label': label}


END_LINE = 'ends automatically when the benchmark confirms success'
# Same as preparation_runtime.POLICY_VERSION, which imports the emulator core. A test keeps them equal.
CURRENT_POLICY = 'fixed-battle-v4'


def cell_facts(run):
    """Battle policy and prompt facts that a cell folder records but its batch summary does not."""
    run, facts = Path(run), {}
    if (run / 'assessment/assessment.json').exists():
        facts['policy_version'] = load(run / 'assessment/assessment.json').get('policy_version')
    if (run / 'prompt.txt').exists():
        facts['end_line'] = END_LINE in (run / 'prompt.txt').read_text()
    return facts


def current_spec(task_id):
    try:
        return digest(encoded(task_definition(task_id)))
    except ValueError:
        return None


def label_cells(cells, specs=None, starts=None):
    """Note each attempt that ran under conditions the current version no longer uses. Scores are unchanged.

    specs maps a task to its current definition hash and starts maps (task, variant) to its current start hashes.
    Without them, specs come from the catalog and starts from the cells that ran the current definition.
    """
    if specs is None:
        specs = {task: current_spec(task) for task in {c['task_id'] for c in cells}}
    if starts is None:
        starts = defaultdict(set)
        for c in cells:
            if c.get('fixture_sha256') and c.get('evaluation_spec_sha256') == specs[c['task_id']]:
                starts[c['task_id'], c.get('variant')].add(c['fixture_sha256'])
    for c in cells:
        spec, start = specs.get(c['task_id']), starts.get((c['task_id'], c.get('variant')), set())
        c['labels'] = [code for code, applies in (
            ('earlier_spec', not c['retired'] and spec is not None and c.get('evaluation_spec_sha256') not in (None, spec)),
            ('earlier_start', len(start) == 1 and c.get('fixture_sha256') not in (None, *start)),
            ('earlier_policy', c.get('policy_version') not in (None, CURRENT_POLICY)),
            ('no_end_line', c.get('end_line') is False),
            ('harness_fault', bool(c.get('harness_fault')))) if applies]


RESUMED = re.compile(r'(cell-\d+)-([a-z-]+?)-\d+')


def attempts_log(base, batches):
    """List every replaced, resumed or continued copy of a published attempt that its batch keeps."""
    log = []
    for batch in batches:
        root = Path(base) / batch
        found = [(folder, folder.name, kind, why) for name, (kind, why) in ARCHIVES.items()
                 for folder in sorted((root / name).glob('cell-*')) if folder.is_dir()]
        for folder in sorted(root.glob('cell-*-*')):
            match = RESUMED.fullmatch(folder.name)
            if match and folder.is_dir():
                why = match[2].replace('-', ' ').capitalize() + ' stopped the attempt. It resumed from its last completed decision.'
                found.append((folder, match[1], 'resumed', why))
        for folder, cell, kind, why in found:
            manifest = load(folder / 'manifest.json') if (folder / 'manifest.json').exists() else {}
            result = load(folder / 'result.json') if (folder / 'result.json').exists() else {}
            log.append({'batch': batch, 'cell': cell, 'kind': kind, 'reason': why,
                        'model': manifest.get('agent', {}).get('model'),
                        'task_id': manifest.get('scenario', {}).get('task_id'),
                        'stop_reason': result.get('stop_reason'), 'decisions': result.get('usage', {}).get('calls')})
    return log


def community_reports(web):
    """Verified Short reports that a maintainer added with community-add."""
    from .submission import REPORT_FORMAT
    reports = [load(path) for path in sorted((Path(web) / 'community').glob('*.json'))]
    return [r for r in reports if r.get('format') == REPORT_FORMAT and r.get('verified') is True and r.get('suite') == 'short']


def suite_hashes(suite):
    """The definition hash per task and the start hash per (task, variant) of a stored Short suite."""
    specs = {t['id']: t['evaluation_spec_sha256'] for t in suite['tasks']}
    starts = {(t['id'], v['variant']): {v['fixture_sha256']} for t in suite['tasks'] for v in t['variants']}
    return specs, starts


def suite_mismatch(rows, suite):
    """Why report cells are not exactly the starts of a stored Short suite, or None when they are."""
    specs, starts = suite_hashes(suite)
    keys = Counter((c.get('task_id'), c.get('variant')) for c in rows)
    missing = sorted(set(starts) - set(keys), key=str)
    unknown = sorted(set(keys) - set(starts), key=str)
    repeated = sorted((k for k, n in keys.items() if n > 1), key=str)
    if missing or unknown or repeated:
        return (f'{len(keys)} of {len(starts)} {suite["benchmark"]} starts, with {len(missing)} missing, '
                f'{len(unknown)} not in the suite and {len(repeated)} repeated.')
    for c in rows:
        if c.get('evaluation_spec_sha256') != specs[c['task_id']] or c.get('fixture_sha256') not in starts[c['task_id'], c['variant']]:
            return f'{c.get("id")} ran a task definition or start that {SUITE_FILE} does not list.'
    return None


def community_id(report):
    return f'community/{report.get("handle") or "unnamed"}/{report["model"]}'


def community_mismatch(report, suite):
    """Why a community report did not run the stored Short suite, or None when it did. Only such a report is shown."""
    benchmark = report.get('harness', {}).get('benchmark')
    if benchmark != suite['benchmark']:
        return f'It ran {benchmark}, not the stored {suite["benchmark"]} suite.'
    return suite_mismatch(report.get('cells', []), suite)


def frozen_sets(frozen):
    """The stored cost comparison starts and the stored start hashes for the earlier start label."""
    return ({tuple(key) for key in frozen['comparison_starts']},
            {(task, variant): set(hashes) for task, variant, hashes in frozen['current_starts']})


def freeze(short):
    """The comparison starts and start hashes of a built Short panel with no rerun, as frozen.json stores them."""
    official = {m['id'] for m in short['models'] if 'community' not in m and 'maintainer' not in m}
    grouped = {m: set() for m in official}
    for c in short['cells']:
        if (c['model'] in official and not c['retired'] and c['category'] not in UNRANKED_CATEGORIES
                and c['state'] == 'finished' and c.get('value') is not None and c.get('cost', {}).get('low') is not None):
            grouped[c['model']].add((c['task_id'], c.get('variant')))
    shared = set.intersection(*grouped.values()) if grouped else set()
    specs = {task: current_spec(task) for task in {c['task_id'] for c in short['cells']}}
    starts = defaultdict(set)
    for c in short['cells']:
        if c.get('fixture_sha256') and c.get('evaluation_spec_sha256') == specs[c['task_id']]:
            starts[c['task_id'], c.get('variant')].add(c['fixture_sha256'])
    def order(key):
        return key[0], key[1] or ''
    return {'comparison_starts': [list(k) for k in sorted(shared, key=order)],
            'current_starts': [[t, v, sorted(h)] for (t, v), h in sorted(starts.items(), key=lambda kv: order(kv[0]))]}


def short_snapshot(source, web, extra=None, base=None, community=(), reruns=None, frozen=None, suite=None, maintained=()):
    """Build the Short panel.

    reruns maps a model to an adopted v0.37 batch, as {'folder', 'web', 'cells'}. Its cells replace every
    earlier cell of that model and are never merged with them. frozen holds the stored comparison starts and
    start hashes, so a swap moves no other row. suite is the stored v0.37 Short suite that adopted rows ran.
    maintained lists rows from adopt_maintainer. Each is a row of its own beside the model's earlier row, and it
    stays out of the cost comparison. community lists verified reports that ran the stored suite, as build keeps
    them with community_mismatch. They are labeled against that suite and also stay out of the cost comparison.
    """
    reruns = reruns or {}
    shared, frozen_starts = frozen_sets(frozen) if frozen else (None, None)
    cells = []
    for row in source['cells']:
        if row['model'] in reruns:
            continue
        clean = {k: row.get(k) for k in CELL_FIELDS}
        clean['replay'] = existing_link(web, row.get('replay'))
        clean['revision'] = 'Original pass'
        clean['harness_fault'] = HARNESS_FAULTS.get(f"focused-pass-v056/{row['id']}")
        if base is not None:
            clean['cost'] = run_cost(base / 'focused-pass-v056' / row['id'], row['model'], row.get('tokens'))
            clean['harness'] = harness_tag(base / 'focused-pass-v056' / row['id'])
            clean.update(cell_facts(base / 'focused-pass-v056' / row['id']))
        cells.append(clean)
    extras = extra if isinstance(extra, list) else [extra] if extra else []
    for batch in extras:
        for row in batch['cells']:
            if row['model'] in reruns:
                continue
            clean = {k: row.get(k) for k in CELL_FIELDS}
            revision = row.get('attempt_revision', 'v066-astra')
            clean['replay'] = existing_link(web, f"{batch.get('web_prefix', 'main-v066-astra')}/replays/focused-{revision}-{row['id']}.html")
            clean['revision'] = 'Current interface'
            clean['harness_fault'] = HARNESS_FAULTS.get(f"{batch.get('web_prefix')}/{row['id']}")
            if base is not None:
                clean['cost'] = run_cost(base / batch['web_prefix'] / row['id'], row['model'], row.get('tokens'))
                clean['harness'] = harness_tag(base / batch['web_prefix'] / row['id'])
                clean.update(cell_facts(base / batch['web_prefix'] / row['id']))
            cells.append(clean)
    fresh = []
    for model, swap in reruns.items():
        for row in swap['cells']:
            clean = {k: row.get(k) for k in CELL_FIELDS}
            # The same replay name the catalog pass writes under its web folder.
            revision = row.get('attempt_revision') or ('v057' if row.get('replacement_condition') else 'v056')
            clean['replay'] = existing_link(web, f"{swap['web']}/replays/focused-{revision}-{row['id']}.html")
            clean['revision'] = RERUN_REVISION
            clean['source'] = swap['folder']
            clean['harness_fault'] = HARNESS_FAULTS.get(f"{swap['folder']}/{row['id']}")
            if base is not None:
                run = base / swap['folder'] / row['id']
                clean['cost'] = run_cost(run, model, row.get('tokens'))
                clean['harness'] = harness_tag(run)
                clean.update(cell_facts(run))
            fresh.append(clean)
    beside = {}
    for row_set in maintained:
        beside[row_set['id']] = row_set
        for row in row_set['cells']:
            clean = {k: row.get(k) for k in CELL_FIELDS}
            run = base / row_set['runs'] / row['id']
            # The verified report gives the cell. The run folder it came from gives the cost and the harness.
            clean.update(model=row_set['id'], replay=None, revision=MAINTAINER_REVISION, source=row_set['runs'],
                         harness_fault=None, cost=run_cost(run, row_set['model'], row.get('tokens')),
                         harness=harness_tag(run), **cell_facts(run))
            fresh.append(clean)
    submitted = {}
    if community and suite is None:
        raise ValueError('Community rows are shown only on the stored suite, so short_snapshot needs it.')
    for entry in community:
        name = community_id(entry)
        submitted[name] = {'label': entry['label'], 'handle': entry.get('handle'), 'model': entry['model'],
                           'attempts': entry.get('attempts_declared'), 'bundle_sha256': entry['bundle_sha256']}
        for row in entry['cells']:
            clean = {k: row.get(k) for k in CELL_FIELDS}
            # Community token counts are self reported, so no cost is estimated from them.
            clean.update(model=name, replay=None, revision='Community', harness=entry['harness']['benchmark'],
                         cost={'low': None, 'high': None, 'partial': False, 'note': 'Community run, not priced'})
            fresh.append(clean)
    cells += fresh
    retired = retired_tasks()
    # Retired attempts stay visible for history, but they are not scored or counted as planned.
    for cell in cells:
        cell['retired'] = cell['task_id'] in retired
    adopted = {id(c) for c in fresh}
    label_cells([c for c in cells if id(c) not in adopted], starts=frozen_starts)
    if fresh:
        label_cells(fresh, *suite_hashes(suite))
    scored = [c for c in cells if not c['retired']]
    by_model = defaultdict(list)
    for cell in cells:
        by_model[cell['model']].append(cell)
    models = []
    for name, rows in by_model.items():
        categories, score = grouped_scores(rows)
        counted = [r for r in rows if not r['retired']]
        finished = sum(r['state'] == 'finished' for r in counted)
        note, kept = submitted.get(name), beside.get(name)
        # A maintainer row names its suite, so it reads apart from the same model's earlier row.
        label = (note['model'] if note else f'{LABELS.get(kept["model"], kept["model"])} ({short_tag(suite["benchmark"])})'
                 if kept else LABELS.get(name, name))
        models.append({'id': name, 'label': label, 'score': score,
                       **({'community': note} if note else {}), **({'maintainer': kept['note']} if kept else {}),
                       'categories': categories, 'finished': finished, 'planned': len(counted),
                       'complete': finished == len(counted), 'tokens': sum(r.get('tokens') or 0 for r in rows),
                       'cost': sum_cost(rows), 'harness': harness_summary(rows),
                       'errors': sum(r['state'] == 'evaluation_error' for r in counted),
                       'labels': dict(Counter(code for r in counted for code in r['labels']))})
        if name in reruns or kept or note:
            origin = reruns[name]['folder'] if name in reruns else kept['runs'] if kept else f'bundle {note["bundle_sha256"][:12]}'
            models[-1]['suite'] = {'benchmark': suite['benchmark'], 'tasks': len(suite['tasks']), 'source': origin}
    models.sort(key=lambda m: (not m['complete'], -(m['score'] if m['score'] is not None else -1)))
    tasks = []
    for t in source['tasks']:
        task = {k: t.get(k) for k in ('id', 'title', 'category', 'goal', 'start', 'action_policy', 'mode')}
        task['retired'] = t['id'] in retired
        if task['retired']:
            task['retirement_reason'] = task_definition(t['id']).get('retirement_reason')
        tasks.append(task)
    if reruns or beside or submitted:
        # Union of both task sets. Tasks only the stored suite has come from it, since this catalog lacks them.
        # added_in names the release that first ran them, which can be older than the suite's own release.
        known = {t['id'] for t in tasks}
        for t in suite['tasks']:
            if t['id'] not in known:
                task = {k: t.get(k) for k in ('id', 'title', 'category', 'goal', 'start', 'action_policy', 'mode')}
                task.update(retired=t['id'] in retired, suite=suite.get('added_in', suite['benchmark']))
                if t.get('milestones'):
                    task['milestones'] = t['milestones']
                tasks.append(task)
        order = list(source['categories'])
        tasks.sort(key=lambda t: order.index(t['category']) if t['category'] in order else len(order))
    log = []
    if base is not None:
        batches = ['focused-pass-v056'] + [b['web_prefix'] for b in extras]
        log = [e for e in attempts_log(base, batches) if e['model'] not in reruns]
        for model, swap in reruns.items():
            log += [e for e in attempts_log(base, [swap['folder']]) if e['model'] == model]
        for row_set in maintained:
            for folder, why in row_set['replaced'].items():
                manifest, result = load(base / folder / 'manifest.json'), load(base / folder / 'result.json')
                log.append({'batch': row_set['runs'], 'cell': re.match(r'cell-\d+', Path(folder).name)[0], 'kind': 'replaced',
                            'reason': why, 'model': row_set['id'], 'task_id': manifest.get('scenario', {}).get('task_id'),
                            'stop_reason': result.get('stop_reason'), 'decisions': result.get('usage', {}).get('calls')})
    return {'models': models, 'tasks': tasks, 'cells': cells, 'categories': source['categories'],
            'ranked_categories': [c for c in source['categories'] if c not in UNRANKED_CATEGORIES],
            'unranked_categories': [c for c in source['categories'] if c in UNRANKED_CATEGORIES],
            'finished': sum(c['state'] == 'finished' for c in scored), 'planned': len(scored),
            'label_text': {code: {'label': label, 'detail': detail} for code, (label, detail) in NOTES.items()},
            'attempts': {'rule': RETRY_RULE, 'log': log},
            'efficiency': comparison([c for c in scored if c['model'] not in submitted and c['model'] not in beside],
                                     [m for m in models if m['id'] not in submitted and m['id'] not in beside], shared)}


def rescored(root, result):
    """The score and milestones under the current Long protocol, from the stored exact replay of the run."""
    path = root / 'campaign-progress-v2.json'
    if not path.exists():
        return result.get('score', 0), result.get('achievements', [])
    rescore = load(path)
    if rescore['run'] != root.name or rescore['recorded_score'] != result.get('score'):
        raise ValueError(f'{path} does not match the recorded run')
    return rescore['score'], [e for e in rescore['campaign']['events'] if e['kind'] == 'milestone']


def long_row(root, web, name, decision_limit=2000):
    result = load(root / 'run/result.json') if (root / 'run/result.json').exists() else {'state': 'queued'}
    pilot = load(root / 'pilot.json') if (root / 'pilot.json').exists() else {}
    usage = result.get('usage', {})
    score, achievements = rescored(root, result)
    manifest = load(root / 'run/manifest.json') if (root / 'run/manifest.json').exists() else {}
    cost = run_cost(root / 'run', manifest.get('agent', {}).get('model'))
    replay = existing_link(web, f'{root.name}-replay.html')
    loop = load(root / 'run/loop_budget.json') if (root / 'run/loop_budget.json').exists() else {}
    stop_detail = ({'last_progress_decision': loop.get('last_progress_decision'), 'limit': loop.get('limit')}
                   if result.get('stop_reason') == 'loop_token_budget' else None)
    return {'id': name, 'label': 'Fable 5.1' if name == 'fable' else name.title(),
            'model': manifest.get('agent', {}).get('model'), 'stop_detail': stop_detail,
            'harness': manifest.get('benchmark'),
            'run_id': root.name, 'decision_limit': decision_limit,
            'token_limit': pilot.get('token_limit', 30000000), 'cost': cost,
            'report': existing_link(web, f'{root.name}.html'), 'score': score,
            'maximum': 1000, 'badges': sum(a['id'].startswith('badge:') for a in achievements),
            'state': result['state'], 'stop_reason': result.get('stop_reason'),
            'decisions': usage.get('calls', 0),
            'tokens': usage.get('input_tokens', 0) + usage.get('output_tokens', 0),
            'milestones': [{k: a.get(k) for k in ('label', 'decision', 'points', 'id')} for a in achievements],
            'versions': {'package': manifest.get('package_version'),
                         'core': manifest.get('core', {}).get('version'),
                         'emulator': ' '.join(str(manifest.get('emulator', {}).get(k) or '') for k in ('backend', 'version')).strip()},
            'image': existing_link(web, f'{root.name}.png'), 'replay': replay,
            'replay_mb': round((web / replay).stat().st_size / 1e6) if replay else None,
            'pair_blocks': dict(zip(('pair', 'blocked'), LONG_PAIR_BLOCKS[root.name])) if root.name in LONG_PAIR_BLOCKS else None}


def long_snapshot(base, web, reruns=None):
    """Build the Long panel. reruns maps a row name to an adopted run folder that replaces that row's run."""
    reruns = reruns or {}
    rows = []
    runs = [(name, f'long-v065-{name}') for name in ('opus', 'sol', 'sonnet', 'terra')]
    runs += [(name, f'long-v067-{name}') for name in ('astra', 'fable') if (base / f'long-v067-{name}/pilot.json').exists()]
    if (base / 'long-v069-luna/pilot.json').exists():
        runs.append(('luna', 'long-v069-luna'))
    if (base / 'long-v073-haiku/pilot.json').exists():
        runs.append(('haiku', 'long-v073-haiku'))
    runs = [(name, reruns.get(name, run_id)) for name, run_id in runs]
    runs += [(name, run_id) for name, run_id in reruns.items() if name not in {n for n, _ in runs}]
    extensions = defaultdict(list)
    for path in sorted(base.glob('long-*/continuation.json')):
        record = load(path)
        if record.get('protocol') == 'long-decision-boundaries-v1':
            extensions[record['origin_run_id']].append((path.parent, record['decision_limit']))
    for name, run_id in runs:
        if name in reruns:
            # An adopted run states its own limits, and the stored ones describe only the earlier runs.
            root = base / run_id
            limits = load(root / 'run/manifest.json').get('limits', {})
            row = long_row(root, web, name, limits.get('max_model_calls') or 2000)
            if not (root / 'pilot.json').exists():
                row['token_limit'] = limits.get('max_total_tokens') or row['token_limit']
        else:
            row = long_row(base / run_id, web, name)
        row['extensions'] = [long_row(root, web, name, limit)
                             for root, limit in sorted(extensions[run_id], key=lambda item: item[1])]
        rows.append(row)
    return sorted(rows, key=lambda r: -r['score'])


SUITE_FILE = 'short-red-v0.63.json'


def inside(base, relative):
    """The folder a source names, only when it is a folder below the data folder."""
    base = Path(base).resolve()
    path = (base / str(relative)).resolve()
    return path if path.is_relative_to(base) and path != base and path.is_dir() else None


def rerun_sources(path):
    """Read the checked-in map from a model to its new Short batch and Long run."""
    sources = load(path)
    if sources.get('format') != RERUN_FORMAT:
        raise ValueError(f'{path} is not a {RERUN_FORMAT} file')
    for model, entry in sources.get('models', {}).items():
        if not isinstance(entry, dict) or not set(entry) <= {'short', 'short_web', 'long', 'note'}:
            raise ValueError(f'{path}: {model} may only name short, short_web, long and note')
    return sources.get('models', {})


def adopt_short(base, model, folder, suite):
    """Return (cells, None) when a new batch finished every start of the stored suite for this model, else (None, why)."""
    root = inside(base, folder)
    if root is None:
        return None, f'{folder} is not a folder under the data folder.'
    if not (root / 'progress.json').exists():
        return None, f'{folder} has no progress.json yet.'
    rows = [c for c in load(root / 'progress.json').get('cells', []) if c.get('model') == model]
    if not rows:
        return None, f'{folder} has no cells for this model.'
    states = Counter(c.get('state') for c in rows)
    if states['finished'] != len(rows):
        others = ', '.join(f'{n} {s}' for s, n in sorted(states.items(), key=lambda kv: str(kv[0])) if s != 'finished')
        return None, f'{states["finished"]} of {len(rows)} cells finished ({others}).'
    specs, starts = suite_hashes(suite)
    keys = Counter((c.get('task_id'), c.get('variant')) for c in rows)
    missing = sorted(set(starts) - set(keys), key=str)
    unknown = sorted(set(keys) - set(starts), key=str)
    repeated = sorted((k for k, n in keys.items() if n > 1), key=str)
    if missing or unknown or repeated:
        return None, (f'{len(keys)} of {len(starts)} {suite["benchmark"]} starts, with {len(missing)} missing, '
                      f'{len(unknown)} not in the suite and {len(repeated)} repeated.')
    for c in rows:
        if c.get('evaluation_spec_sha256') != specs[c['task_id']] or c.get('fixture_sha256') not in starts[c['task_id'], c['variant']]:
            return None, f'{c["id"]} ran a task definition or start that {SUITE_FILE} does not list. Regenerate it from the tag the batch ran.'
        tag = harness_tag(root / c['id'])
        if tag != suite['benchmark']:
            return None, f'{c["id"]} recorded harness {tag}, not {suite["benchmark"]}.'
    return rows, None


def adopt_long(base, model, run_id, suite):
    """Return (row name, None) when a new Long run finished for this model on the suite's release, else (None, why)."""
    if model not in LONG_NAMES:
        return None, 'this model has no Long row.'
    root = inside(base, run_id)
    if root is None:
        return None, f'{run_id} is not a folder under the data folder.'
    if not (root / 'run/result.json').exists() or not (root / 'run/manifest.json').exists():
        return None, f'{run_id} has no result yet.'
    state = load(root / 'run/result.json').get('state')
    if state != 'finished':
        return None, f'{run_id} is {state}, not finished.'
    manifest = load(root / 'run/manifest.json')
    if manifest.get('agent', {}).get('model') != model:
        return None, f'{run_id} ran {manifest.get("agent", {}).get("model")}, not this model.'
    release = suite['package'].rsplit('.', 1)[0] + '.'
    if not str(manifest.get('package_version')).startswith(release):
        return None, f'{run_id} ran package {manifest.get("package_version")}, not {release}x.'
    return LONG_NAMES[model], None


MAINTAINER_FORMAT = 'pokebench-maintainer-rows-v1'
MAINTAINER_KEYS = {'id', 'model', 'suite', 'report', 'report_sha256', 'runs', 'replaced', 'release', 'label', 'detail'}


def maintainer_sources(path):
    """Read the checked-in list of maintainer rows, each a verified report beside the model's earlier row."""
    sources = load(path)
    if sources.get('format') != MAINTAINER_FORMAT:
        raise ValueError(f'{path} is not a {MAINTAINER_FORMAT} file')
    for entry in sources.get('rows', []):
        if not isinstance(entry, dict) or set(entry) != MAINTAINER_KEYS:
            raise ValueError(f'{path}: each row names exactly {", ".join(sorted(MAINTAINER_KEYS))}')
        if entry['suite'] != 'short':
            raise ValueError(f'{path}: {entry["id"]} is a {entry["suite"]} row, and only Short rows are supported')
    return sources.get('rows', [])


def adopt_maintainer(base, entry, suite):
    """Return (row, None) when a verified report and the run folder it came from agree on every stored start, else (None, why)."""
    base = Path(base)
    report_path = base / str(entry['report'])
    if not report_path.resolve().is_relative_to(base.resolve()) or not report_path.is_file():
        return None, f'{entry["report"]} is not a file under the data folder.'
    if hashlib.sha256(report_path.read_bytes()).hexdigest() != entry['report_sha256']:
        return None, f'{entry["report"]} does not match its listed sha256.'
    report = load(report_path)
    if report.get('format') != 'pokebench-verified-report-v1' or report.get('verified') is not True or report.get('problems'):
        return None, f'{entry["report"]} is not a verified report with no problems.'
    if report.get('suite') != entry['suite'] or report.get('model') != entry['model']:
        return None, f'{entry["report"]} is {report.get("suite")} {report.get("model")}, not {entry["suite"]} {entry["model"]}.'
    if report.get('harness', {}).get('benchmark') != suite['benchmark']:
        return None, f'{entry["report"]} ran {report.get("harness", {}).get("benchmark")}, not {suite["benchmark"]}.'
    root = inside(base, entry['runs'])
    if root is None:
        return None, f'{entry["runs"]} is not a folder under the data folder.'
    rows = report.get('cells', [])
    walls = []
    why = suite_mismatch(rows, suite)
    if why:
        return None, why
    for c in rows:
        if c.get('state') != 'finished' or c.get('replay_verified') is not True:
            return None, f'{c.get("id")} is {c.get("state")} and not replay verified.'
        run = root / str(c['id'])
        if not re.fullmatch(r'cell-\d+', str(c['id'])) or not (run / 'manifest.json').is_file() or not (run / 'result.json').is_file():
            return None, f'{entry["runs"]} has no run folder for {c.get("id")}.'
        manifest, result = load(run / 'manifest.json'), load(run / 'result.json')
        if manifest.get('agent', {}).get('model') != entry['model'] or manifest.get('scenario', {}).get('task_id') != c['task_id']:
            return None, f'{c["id"]} in {entry["runs"]} ran a different model or task than the report.'
        usage = result.get('usage', {})
        if usage.get('input_tokens', 0) + usage.get('output_tokens', 0) != c.get('tokens'):
            return None, f'{c["id"]} in {entry["runs"]} used a different token count than the report.'
        if harness_tag(run) != suite['benchmark']:
            return None, f'{c["id"]} recorded harness {harness_tag(run)}, not {suite["benchmark"]}.'
        walls.append(result.get('wall_seconds'))
    for folder in entry['replaced']:
        if inside(base, folder) is None or not re.match(r'cell-\d+', Path(folder).name):
            return None, f'{folder} is not a kept cell folder under the data folder.'
    packages = sorted({load(root / str(c['id']) / 'manifest.json').get('package_version') for c in rows}, key=str)
    note = {'label': entry['label'], 'detail': entry['detail'], 'model': entry['model'], 'release': entry['release'],
            'packages': packages, 'verified_on': report['harness'].get('package_version'),
            'report_sha256': entry['report_sha256'], 'bundle_sha256': report.get('bundle_sha256'),
            # The kept attempts' own play time, summed. Replaced attempts and pauses between attempts are not in it.
            'wall_seconds': round(sum(walls)) if all(isinstance(w, (int, float)) for w in walls) else None}
    return {'id': entry['id'], 'model': entry['model'], 'runs': entry['runs'], 'cells': rows,
            'replaced': entry['replaced'], 'note': note}, None


def build(base, web, *, sources=None, frozen=None, suite=None, maintainer=None):
    """Return the showcase data. A model keeps its earlier source unless its listed new source is complete."""
    base, web = Path(base), Path(web)
    sources = rerun_sources(sources or SOURCES / 'rerun-sources.json')
    listed = maintainer_sources(maintainer or SOURCES / 'maintainer-rows.json')
    frozen = load(frozen or SOURCES / 'frozen.json')
    suite = load(suite or SOURCES / SUITE_FILE)
    source = load(web / 'focused-analysis.json')
    extra = []
    for folder in ('main-v066-astra', 'main-v067-fable'):
        path = base / folder / 'progress.json'
        if path.exists():
            batch = load(path)
            batch['web_prefix'] = folder
            extra.append(batch)
    short, long = {}, {}
    for model, entry in sources.items():
        if entry.get('short'):
            cells, why = adopt_short(base, model, entry['short'], suite)
            if cells is None:
                print(f'{model} Short: kept the old row. {why}', file=sys.stderr)
            else:
                short[model] = {'folder': entry['short'], 'web': entry.get('short_web', entry['short']), 'cells': cells}
        if entry.get('long'):
            name, why = adopt_long(base, model, entry['long'], suite)
            if name is None:
                print(f'{model} Long: kept the old row. {why}', file=sys.stderr)
            else:
                long[name] = entry['long']
    maintained = []
    for entry in listed:
        row, why = adopt_maintainer(base, entry, suite)
        if row is None:
            print(f'{entry["id"]}: left off the site. {why}', file=sys.stderr)
        else:
            maintained.append(row)
    # A community row joins the current set or stays off. It never ranks among the earlier rows.
    community = []
    for report in community_reports(web):
        why = community_mismatch(report, suite)
        if why:
            print(f'{community_id(report)}: left off the site. {why}', file=sys.stderr)
        else:
            community.append(report)
    return {'schema': 'pokebench-showcase-v1', 'updated_at': datetime.now(timezone.utc).isoformat(),
            'short': short_snapshot(source, web, extra, base, community, short, frozen, suite, maintained),
            'long': long_snapshot(base, web, long),
            'pricing': PRICING,
            'report': existing_link(web, 'technical-report.pdf')}


def compact(value):
    return json.dumps(value, ensure_ascii=True, allow_nan=False, separators=(',', ':')) + '\n'


def replace_text(path, text):
    temporary = path.with_name(path.name + '.tmp')
    temporary.write_text(text)
    temporary.replace(path)


def file_names(ids):
    """Map each id to a file name of safe characters, adding a hash of the id where two names would match."""
    plain = {key: re.sub(r'[^A-Za-z0-9._-]', '-', key) for key in ids}
    taken = Counter(plain.values())
    return {key: name if taken[name] == 1 else f'{name}-{hashlib.sha256(key.encode()).hexdigest()[:8]}' for key, name in plain.items()}


def site_files(data):
    """Split the showcase data into the summary the page loads and the attempt files it fetches when opened.

    The summary keeps every row, score, label and cost, and holds no attempts. In their place each row has
    its score interval, its attempt file and a string with a 1 for every task, in task order, that it has an
    attempt on. A row on the stored suite also has its token cap. Each task has its attempt file, its
    finished count and its score group when that differs from its id. Each path ends in a hash of its file,
    so a changed file is fetched again.
    """
    short = data['short']
    tasks, models = short.get('tasks', []), short.get('models', [])
    order = {m['id']: i for i, m in enumerate(models)}
    by_model, by_task = defaultdict(list), defaultdict(list)
    for cell in short['cells']:
        by_model[cell['model']].append(cell)
        by_task[cell['task_id']].append(cell)
    files = {}

    def add(kind, name, rows):
        path = f'{ATTEMPTS}/{kind}/{name}.json'
        files[path] = compact(rows)
        return f'{path}?v={hashlib.sha256(files[path].encode()).hexdigest()[:12]}'

    names = file_names(order)
    rows = []
    for m in models:
        cells = by_model[m['id']]
        ran = {c['task_id'] for c in cells}
        row = dict(m, cells=add('model', names[m['id']], cells), ran=''.join('1' if t['id'] in ran else '0' for t in tasks))
        if m.get('suite'):
            row['token_cap'] = sum(c.get('token_limit') or 0 for c in cells if not c.get('retired'))
        rows.append(row)
    names = file_names([t['id'] for t in tasks])
    listed = []
    for t in tasks:
        cells = sorted(by_task[t['id']], key=lambda c: order.get(c['model'], len(order)))
        group = {c.get('score_group') or c['task_id'] for c in cells}
        if len(group) > 1:
            raise ValueError(f'{t["id"]} has attempts in more than one score group: {", ".join(sorted(group))}')
        task = dict(t, cells=add('task', names[t['id']], cells),
                    coverage={'finished': sum(c['state'] == 'finished' for c in cells), 'attempts': len(cells)})
        if group and group != {t['id']}:
            task['score_group'] = group.pop()
        listed.append(task)
    summary = dict(data, schema='pokebench-showcase-summary-v1',
                   short=dict({k: v for k, v in short.items() if k != 'cells'}, models=rows, tasks=listed))
    return summary, files


def write_site(data, folder):
    """Write the full data file, the attempt files and, last, the summary the page loads.

    Each Short row gets its score interval first, so the page computes none. The summary goes last, so it
    never names a file that is not there yet. Attempt files that no row or task names any more are removed.
    Returns the full data as written.
    """
    folder = Path(folder)
    short = data['short']
    by_model = defaultdict(list)
    for cell in short['cells']:
        by_model[cell['model']].append(cell)
    unranked = short.get('unranked_categories', [])
    models = [m if 'ci' in m else dict(m, ci=score_interval(by_model[m['id']], unranked=unranked)) for m in short.get('models', [])]
    data = dict(data, short=dict(short, models=models))
    summary, files = site_files(data)
    replace_text(folder / 'showcase-data.json', json.dumps(data, ensure_ascii=True, allow_nan=False) + '\n')
    for relative, text in files.items():
        (folder / relative).parent.mkdir(parents=True, exist_ok=True)
        replace_text(folder / relative, text)
    if (folder / ATTEMPTS).is_dir():
        kept = {folder / relative for relative in files}
        for path in (folder / ATTEMPTS).rglob('*'):
            if path.is_file() and path not in kept:
                path.unlink()
    replace_text(folder / SUMMARY, compact(summary))
    return data


def export(base, web, *, install=False, sources=None, maintainer=None):
    base, web = Path(base), Path(web)
    data = write_site(build(base, web, sources=sources, maintainer=maintainer), web)
    if install:
        assets = Path(__file__).with_name('showcase_assets')
        for name in ASSETS:
            shutil.copy2(assets / name, web / name)
        if (web / 'index.html').exists() and not (web / 'analysis-v060.html').exists():
            shutil.copy2(web / 'index.html', web / 'analysis-v060.html')
        shutil.copy2(assets / 'index.html', web / 'index.html')
    return data


REPLAY_DETAILS = ('label', 'score', 'maximum', 'badges', 'stop_reason', 'decisions', 'milestones', 'harness', 'versions')


def public_replay(web, relative, model, output, details=None):
    """Write a public replay with screenshots, controller actions and harness facts only.

    Returns the viewer link. The data file is replays/<name>.gz and the page
    at the old address, replays/<name>.html, opens the viewer.
    """
    import re
    from .public_site import replay_payload, write_replay
    path = web / relative
    match = re.search(r'<script[^>]*id="data"[^>]*>(.*?)</script>', path.read_text(), re.S)
    runs = json.loads(match[1]).get('runs', []) if match else []
    if len(runs) != 1 or runs[0].get('model') != model:
        raise ValueError(f'Replay does not match its result: {relative}')
    payload, body = replay_payload(path, {'id': runs[0]['id'], 'model': model, 'completed': runs[0].get('completed')}, details)
    return write_replay(output / 'replays', relative.removesuffix('.html').replace('/', '--'), payload, body)


def public_image(web, relative, output):
    from PIL import Image
    target = 'images/' + Path(relative).name
    with Image.open(web / relative) as image:
        clean = Image.new('RGB', image.size)
        clean.paste(image.convert('RGB'))
        clean.save(output / target, format='PNG')
    return target


def export_public(web, output, *, report=None):
    """Build a static public copy of the showcase in a new directory.

    Local replays carry model plans and observations, so each is rebuilt from
    verified screenshots and executed controller actions only. Local run
    reports and the detailed analysis page are not published.
    """
    from .public_site import REPLAY
    web, output = Path(web), Path(output)
    data = load(web / 'showcase-data.json')
    output.mkdir()
    (output / 'replays').mkdir()
    (output / 'images').mkdir()
    (output / 'replays' / 'view.html').write_text(REPLAY)
    for cell in data['short']['cells']:
        cell['replay'] = public_replay(web, cell['replay'], cell['model'], output) if cell.get('replay') else None
    by_label = {label: model for model, label in LABELS.items()}
    for row in data['long']:
        for run in [row, *row.get('extensions', [])]:
            run['report'] = None
            details = {key: run.get(key) for key in REPLAY_DETAILS}
            run['replay'] = public_replay(web, run['replay'], by_label[run['label']], output, details) if run.get('replay') else None
            size = (output / (run['replay'].replace('view.html?r=', '') + '.gz')).stat().st_size if run['replay'] else 0
            run['replay_mb'] = max(0.1, round(size / 1e6, 1)) if run['replay'] else None
            run['image'] = public_image(web, run['image'], output) if run.get('image') else None
    data['report'] = None
    if report:
        shutil.copy2(report, output / 'technical-report.pdf')
        data['report'] = 'technical-report.pdf'
    data = write_site(data, output)
    assets = Path(__file__).with_name('showcase_assets')
    for name in ASSETS:
        shutil.copy2(assets / name, output / name)
    page = (assets / 'index.html').read_text().replace('<a href="analysis-v060.html">Detailed analysis ↗</a>', '')
    if not report:
        page = page.replace('<a id="report-link" href="technical-report.pdf">Technical report ↗</a>', '')
        page = page.replace(' The technical report covers an earlier snapshot.', '')
    # The hero shows the Opus Long row, whichever run that row uses.
    hero = next((r for r in data['long'] if r.get('id') == 'opus'), None)
    if hero and hero['replay'] and hero['image']:
        page = page.replace('href="long-v065-opus-replay.html"', f'href="{hero["replay"]}"').replace('src="long-v065-opus.png"', f'src="{hero["image"]}"')
        page = page.replace('<span>2 badges.', f'<span>{hero["badges"]} badge{"" if hero["badges"] == 1 else "s"}.')
    (output / 'index.html').write_text(page)
    (output / '.nojekyll').write_text('')
    return data
