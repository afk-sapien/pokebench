"""Exploratory cross-run analysis with one preselected comparison per benchmark."""
from copy import deepcopy

from .costs import efficiency

RANKING_VERSION = 'ability-ranking-v2'
# Retire these exact easy saves, not every future version of these tasks.
RETIREMENTS = {
    'wild-battle': (
        'e20b2ce22cf070d417fec48c582fe7c631c0b8f304a23e9bb95d75a380aae6e3',
        'A full-health starter wins by repeating its only damaging move. All seven models used three decisions.'),
    'first-capture': (
        '5defcf481eb040ea54d815aee3b5baef9944be9805ce00c5d40253f3f64c1bdc',
        'The opponent is already weakened and plentiful Poke Balls make repeated capture attempts sufficient.'),
    'brock': (
        'a591ed16188851f327b7be19896d9d0b95e8178e505ab7bb4a07f50b6effbbc3',
        'The supplied healthy Squirtle can repeatedly use Bubble. Little adaptation is needed.'),
    'erika': (
        'a58f66cbb099c1d5b5fa6f7ce77b8b533214db8e316e166d28f8bb6e910d5379',
        'The supplied level-39 Charizard can repeatedly use Ember against the Grass team.'),
    'sabrina': (
        '913c65e8314f3514c6ab3eb768097a8cef26121f657c87aed6ce5676f037e519',
        'The supplied level-48 Charizard can repeatedly use Slash without meaningful resource tradeoffs.'),
}
CURATION_POLICY = (
    'Ability ranking v2 removes five exact starting saves after reviewing task structure and recorded play. '
    'This is a retrospective task selection change. Scores are not directly comparable with the previous 27-task ranking. '
    'Useful basic tasks remain, including tasks passed by all models. '
    'Retired results remain in historical comparisons. Calibrated battles enter scores only after shared verified model coverage.'
)

POLICY = (
    'Newest configured comparison that has started the task, independent of outcomes. '
    'One comparison supplies all models and repeats for that task. '
    'Only tasks with matching completed, replay-verified coverage for every model enter scores. '
    'Equal task weights. Pending tasks and infrastructure errors remain visible and unscored. '
    'Tool versions differ across tasks, so this is an exploratory aggregate, not a single controlled run.'
)


def summarize(tasks, attempts, models):
    eligible = []
    for task in tasks:
        if task.get('validation', {}).get('status', 'validated') != 'validated':
            continue
        groups = [[a for a in attempts if a['task'] == task['id'] and a['model'] == model] for model in models]
        repeats = [sorted((a['repeat'], a.get('variant', 1)) for a in group) for group in groups]
        if (groups and all(groups) and all(r == repeats[0] and len(r) == len(set(r)) for r in repeats)
                and all(a['status'] == 'finished' and a.get('replay_verified') for group in groups for a in group)):
            eligible.append(task['id'])
    rows = []
    for model in models:
        selected = [a for a in attempts if a['model'] == model]
        task_scores = []
        for task in eligible:
            group = [a for a in selected if a['task'] == task]
            task_scores.append(sum(bool(a['completed']) for a in group) / len(group))
        rows.append({'model':model, 'score':100 * sum(task_scores) / len(task_scores) if task_scores else None,
                     'tokens':sum(a.get('tokens', 0) for a in selected),
                     'scored_tasks':len(eligible), 'total_tasks':len(tasks)})
    rows.sort(key=lambda r: (r['score'] is None, -(r['score'] or 0), r['model']))
    for row in rows:
        row['rank'] = 1 + sum(other['score'] > row['score'] for other in rows) if eligible else None
    return eligible, rows


def combine_reports(cohorts):
    """Input order is explicit recency priority, never chosen by score or completion."""
    registered = [c for c in cohorts if c.get('models')]
    if not registered:
        return None
    models = sorted({m['model'] for c in registered for m in c['models']})
    catalog = max(cohorts, key=lambda c: len(c['tasks']))
    tasks = []
    attempts = []
    for canonical in catalog['tasks']:
        key = canonical['id']
        candidates = []
        for cohort in registered:
            task = next((t for t in cohort['tasks'] if t['id'] == key), None)
            rows = [a for a in cohort['attempts'] if a['task'] == key]
            if (task and rows and task['state_hash'] == canonical['state_hash']
                    and task['objective'] == canonical['objective'] and task['tokens'] == canonical['tokens']
                    and task.get('variant_state_hashes') == canonical.get('variant_state_hashes')
                    and cohort['configuration'].get('rom_sha256') == catalog['configuration'].get('rom_sha256')):
                candidates.append((cohort, task, rows))
        started = [c for c in candidates if any(a['status'] != 'pending' for a in c[2])]
        selected = (started or candidates)[0] if candidates else None
        task = deepcopy(canonical)
        task['source'] = None
        if selected:
            cohort, _, rows = selected
            task['source'] = {'id':cohort['id'], 'label':cohort['label'],
                              'benchmark_versions':cohort.get('benchmark_versions', []),
                              'configuration':deepcopy(cohort['configuration'])}
            for row in rows:
                attempts.append({**deepcopy(row), 'id':cohort['id']+'/'+row['id'], 'source_run_id':row['id'],
                                 'source_cohort':cohort['id'], 'source_label':cohort['label']})
        tasks.append(task)
    retired = []
    active = []
    for task in tasks:
        retirement = RETIREMENTS.get(task['id'])
        if retirement and task['state_hash'] == retirement[0]:
            retired.append({'id':task['id'], 'name':task['name'], 'state_hash':task['state_hash'],
                            'reason':retirement[1], 'source':deepcopy(task['source'])})
        else:
            active.append(task)
    tasks = active
    active_ids = {task['id'] for task in tasks}
    attempts = [attempt for attempt in attempts if attempt['task'] in active_ids]
    selected_pairs = {(a['source_cohort'], a['task'], a['model']) for a in attempts}
    interruptions = [dict(deepcopy(h), source_cohort=c['id']) for c in cohorts
                     for h in c.get('interrupted_attempts', [])
                     if (c['id'], h['task'], h['model']) in selected_pairs]
    eligible, scores = summarize(tasks, attempts, models)
    for task in tasks:
        task['included_in_score'] = task['id'] in eligible
    return {'id':'combined', 'label':f'Main ability ranking · {len(tasks)} tasks', 'suite':catalog['suite'],
            'analysis':RANKING_VERSION, 'phase':'Combined saved results',
            'retired_tasks':retired,
            'configuration':{'ranking_version':RANKING_VERSION, 'curation_policy':CURATION_POLICY,
                             'selection_policy':POLICY, 'priority':[c['id'] for c in registered]},
            'tasks':tasks, 'attempts':attempts, 'models':scores, 'scored_task_ids':eligible,
            'ranking_ready':bool(eligible), 'coverage_complete':len(eligible) == len(tasks),
            'tokens':sum(a.get('tokens',0) for a in attempts),
            'interrupted_attempts':interruptions,
            'cost_analysis':efficiency(attempts, models, eligible),
            'sources':[c['id'] for c in cohorts]}
