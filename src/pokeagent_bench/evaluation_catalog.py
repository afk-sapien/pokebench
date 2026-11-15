"""Prospective Gen 1 eval specifications, separate from runnable suites and results."""
from collections import Counter
from copy import deepcopy
from functools import cache
from importlib.resources import files
import json
from pathlib import Path
import re

from .action_policy import ASSISTED, MANUAL, SKILLS
from .challenges import validate_objective

CATEGORIES = ('navigation', 'battle', 'operations', 'objectives', 'campaign')
CATEGORY_REASSIGNMENTS = {'objectives-recover-earlier-mistake': 'operations'}
REQUIRED = {'id', 'title', 'difficulty', 'tested_skill', 'mode', 'action_policy', 'objective',
            'start', 'success', 'failure', 'variants', 'token_limit', 'existing_task', 'requirements',
            'status', 'calibration', 'agent_goal', 'scenario_details', 'open_questions'}


def validate_category(category):
    """Reject misleading permissions or readiness claims before exporting a plan."""
    key = category.get('category')
    if key not in CATEGORIES or not isinstance(category.get('title'), str):
        raise ValueError('Unknown category or missing title')
    evaluations = category.get('evals')
    if not isinstance(evaluations, list) or not evaluations:
        raise ValueError('Each category must specify at least one eval')
    seen = set()
    for evaluation in evaluations:
        if not isinstance(evaluation, dict) or not REQUIRED <= evaluation.keys():
            raise ValueError('Evaluation is missing required specification fields')
        identifier = evaluation['id']
        if not isinstance(identifier, str) or not (re.fullmatch(key + r'-[a-z0-9]+(?:-[a-z0-9]+)*', identifier)
                or CATEGORY_REASSIGNMENTS.get(identifier) == key):
            raise ValueError('Evaluation ID must start with its category')
        if identifier in seen:
            raise ValueError('Duplicate evaluation ID')
        seen.add(identifier)
        for field in ('title', 'start', 'agent_goal'):
            if not isinstance(evaluation[field], str) or not evaluation[field].strip():
                raise ValueError(f'{identifier}: missing {field}')
        for field in ('success', 'failure', 'variants', 'requirements', 'scenario_details'):
            values = evaluation[field]
            if not isinstance(values, list) or not values or any(not isinstance(v, str) or not v.strip() for v in values):
                raise ValueError(f'{identifier}: {field} must be a nonempty text list')
        questions = evaluation['open_questions']
        if not isinstance(questions, list) or any(not isinstance(v, str) or not v.strip() for v in questions):
            raise ValueError('Open questions must be a list of concrete remaining checks')
        if evaluation['difficulty'] not in ('easy', 'medium', 'hard', 'stretch'):
            raise ValueError('Unknown provisional difficulty')
        if evaluation['tested_skill'] not in SKILLS:
            raise ValueError('Unknown tested skill')
        expected_policy = MANUAL if key == 'operations' else ASSISTED
        if evaluation['action_policy'] != expected_policy:
            raise ValueError(f'{identifier}: incorrect task controls')
        if evaluation['mode'] != 'gameplay':
            raise ValueError(f'{identifier}: every task is a gameplay task')
        if evaluation['status'] != 'specified' or evaluation['calibration'] != 'pending':
            raise ValueError('A specification is not a validated or calibrated evaluation')
        if type(evaluation['token_limit']) is not int or evaluation['token_limit'] <= 0:
            raise ValueError('Token limit must be a positive provisional integer')
        if 'decision_limit' in evaluation and (type(evaluation['decision_limit']) is not int or evaluation['decision_limit'] <= 0):
            raise ValueError('Decision limit must be a positive integer')
        source = evaluation['existing_task']
        if source is not None and (not isinstance(source, str) or not re.fullmatch(r'[a-z0-9-]+', source)):
            raise ValueError('Invalid source task')
        objective = evaluation['objective']
        if objective is not None:
            validate_objective(objective)
        # The campaign keeps its own milestone list, scored by the campaign evaluator.
        if 'milestones' in evaluation and key != 'campaign':
            validate_milestone_task(evaluation)
    by_id = {task['id']: task for task in evaluations}
    for task in evaluations:
        parent = task.get('variant_of')
        if parent and (parent not in by_id or by_id[parent].get('variant_of') or parent == task['id']):
            raise ValueError('Task variants require a primary task in the same category')
    return deepcopy(category)


def validate_milestone_task(task):
    """A milestone task is a gameplay task with a decision cap and ordered private milestones."""
    from .milestone_runtime import validate_milestones
    identifier = task['id']
    if 'decision_limit' not in task:
        raise ValueError(f'{identifier}: milestone tasks need a decision cap')
    objective = task['objective'] or {}
    if objective.get('kind') != 'catalog-task' or objective.get('task_id') != identifier:
        raise ValueError(f'{identifier}: milestone tasks use their own catalog evaluator')
    validate_milestones(task['milestones'])


def _root():
    return files('pokeagent_bench').joinpath('catalogs')


def catalog_files():
    """Every catalog file."""
    return [path for path in _root().iterdir() if path.name.endswith('.json')]


def load_catalog(category=None, *, include_retired=False):
    if category == 'quests':
        category = 'objectives'
    if category is not None and category not in CATEGORIES:
        raise ValueError('Unknown category')
    selected = (category,) if category else CATEGORIES
    root = _root()
    groups = [validate_category(json.loads(root.joinpath(key + '.json').read_text())) for key in selected]
    if not include_retired:
        for group in groups:
            group['evals'] = [task for task in group['evals'] if task.get('active', True)]
    return groups


@cache
def milestone_tasks():
    """Task ids scored by the share of their ordered milestones reached, from 0 to 1."""
    return frozenset(task['id'] for group in load_catalog(include_retired=True) if group['category'] != 'campaign'
                     for task in group['evals'] if 'milestones' in task)


def summary(category=None, fixtures=None, *, benchmark=None):
    from .benchmark_tracks import for_category, validate
    categories = load_catalog(category)
    if benchmark is not None:
        validate(benchmark)
        categories = [group for group in categories if for_category(group['category']) == benchmark]
        if not categories:
            raise ValueError('Category belongs to the other benchmark')
    entries = [evaluation for group in categories for evaluation in group['evals']]
    if fixtures is not None:
        root = Path(fixtures)
        if not root.is_dir():
            raise ValueError('Fixture root must be an existing directory')
        for evaluation in entries:
            source = evaluation['existing_task']
            candidates = sorted((root / source).glob('**/scenario.json')) if source else []
            evaluation['source_variants_found'] = len(candidates)
    report = {'benchmark': benchmark, 'catalog': 'gen1-six-category-plan-v3', 'status': 'specified', 'game': 'red',
            'blue_status': 'Requires separate ROM, observation, scoring and fixture validation',
            'difficulty_status': 'Provisional until measured across model tiers and repeated starts',
            'eval_count': len(entries), 'primary_task_count': sum(not e.get('variant_of') for e in entries),
            'variant_count': sum(bool(e.get('variant_of')) for e in entries), 'category_count': len(categories),
            'difficulty_counts': dict(Counter(e['difficulty'] for e in entries)),
            'existing_task_candidates': sum(e['existing_task'] is not None for e in entries),
            'runnable_new_evals': 0, 'model_calls': 0,
            'note': 'Existing task links are reuse candidates. This catalog does not promote fixtures or launch trials.',
            'categories': categories}
    if fixtures is not None:
        from .catalog_execution import inventory
        implementation = inventory(fixtures, category=category)
        by_id = {row['id']: row for row in implementation['tasks']}
        for entry in entries:
            state = by_id[entry['id']]
            entry['implementation'] = {
                'runtime': state['runtime'], 'runnable': state['runnable'],
                'start_variants': len(state['variants']),
                'reference_variants': sum(v['reference_verified'] for v in state['variants']),
                'issues': state['issues'] + [issue for v in state['variants'] for issue in v['issues']],
                'calibration': state['calibration'],
            }
        report.update(catalog='gen1-catalog-v2', status='implemented',
                      runnable_new_evals=sum(by_id[e['id']]['runnable'] for e in entries),
                      reference_verified_evals=sum(any(v['reference_verified'] for v in by_id[e['id']]['variants']) for e in entries),
                      note='Runnable tasks have checked native starting saves and assigned evaluators. Reference proofs and model calibration are shown separately.')
    return report


@cache
def retired_tasks():
    """Task ids kept in the catalog for history but no longer run or scored."""
    return frozenset(task['id'] for group in load_catalog(include_retired=True)
                     for task in group['evals'] if not task.get('active', True))


def task_definition(task_id):
    """Return the concrete definition used by runners, fixtures and reporting."""
    for category in load_catalog(include_retired=True):
        for task in category['evals']:
            if task['id'] == task_id:
                return task
    raise ValueError(f'Unknown catalog task: {task_id}')


def validate_run_spec(manifest):
    """Keep scoring specifications fixed across replay and resume."""
    from .core import digest, encoded
    expected = manifest.get('evaluation_spec_sha256')
    if expected is None:
        return
    scenario = manifest['scenario']
    task_id = scenario.get('task_id') or scenario.get('objective', {}).get('task_id')
    if digest(encoded(task_definition(task_id))) != expected:
        raise ValueError('The catalog specification changed since this run started')
