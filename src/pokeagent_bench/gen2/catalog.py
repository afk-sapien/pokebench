"""The Gen II prep task catalog.

The file sits next to this module, outside the catalogs folder, so evaluation_catalog,
quick_run and the released suites never read it. Each task keeps the Red catalog's fields
and adds how its start is captured and, once built, the pins of its start and reference.
"""
from __future__ import annotations

from copy import deepcopy
from functools import cache
import hashlib
import json
from pathlib import Path
import re

from ..action_policy import ASSISTED, SKILLS
from ..evaluation_catalog import REQUIRED
from .evaluator import validate_milestones

CATALOG = Path(__file__).with_name('catalog.json')
CATEGORY = 'gen2'
ROUTES = ('story', 'kabuto')
REFERENCE_MULTIPLE = 5
TOKENS_PER_DECISION = 15000
FIXTURE_KEYS = {'state_sha256', 'actions_sha256', 'actions', 'frames', 'decisions'}


def actions_digest(actions):
    return hashlib.sha256(json.dumps([list(action) for action in actions], separators=(',', ':')).encode()).hexdigest()


def decisions(actions):
    """A provisional decision count until a Gen II assisted executor exists. Each run of the
    same button counts once, so a walk or a run of text presses is one decision. Idle waits
    count as none."""
    count, last = 0, None
    for button, _, _ in actions:
        if button:
            count += button != last
            last = button
    return count


def pins(state, actions):
    """What a built task pins: its start state and its scripted reference."""
    return {'state_sha256': hashlib.sha256(state).hexdigest(), 'actions_sha256': actions_digest(actions),
            'actions': len(actions), 'frames': sum(hold + gap for _, hold, gap in actions),
            'decisions': decisions(actions)}


def _place(value):
    return (isinstance(value, list) and len(value) == 2 and all(type(v) is int for v in value)
            and 1 <= value[0] <= 26 and 1 <= value[1] <= 255)


def _flags(values):
    return isinstance(values, list) and all(type(v) is int and 0 <= v < 2048 for v in values)


def validate_capture(identifier, capture):
    if not isinstance(capture, dict) or set(capture) != {'route', 'maps', 'after', 'before', 'frame_cap'}:
        raise ValueError(f'{identifier}: a capture names its route, maps, events and frame cap')
    if capture['route'] not in ROUTES:
        raise ValueError(f'{identifier}: unknown capture route')
    if not capture['maps'] or not all(_place(place) for place in capture['maps']):
        raise ValueError(f'{identifier}: capture maps are [group, number] pairs')
    if not _flags(capture['after']) or not _flags(capture['before']):
        raise ValueError(f'{identifier}: capture events are event flag lists')
    if type(capture['frame_cap']) is not int or capture['frame_cap'] <= 0:
        raise ValueError(f'{identifier}: the reference frame cap must be a positive integer')


def validate_fixture(identifier, task):
    """A built task pins its start and reference, and its caps follow the reference."""
    fixture = task['fixture']
    if not isinstance(fixture, dict) or set(fixture) != FIXTURE_KEYS:
        raise ValueError(f'{identifier}: invalid fixture pins')
    for key in ('state_sha256', 'actions_sha256'):
        if not isinstance(fixture[key], str) or not re.fullmatch(r'[0-9a-f]{64}', fixture[key]):
            raise ValueError(f'{identifier}: {key} must be a SHA-256')
    for key in ('actions', 'frames', 'decisions'):
        if type(fixture[key]) is not int or fixture[key] <= 0:
            raise ValueError(f'{identifier}: {key} must be a positive integer')
    if task['decision_limit'] != REFERENCE_MULTIPLE * fixture['decisions']:
        raise ValueError(f'{identifier}: the decision cap is {REFERENCE_MULTIPLE} times the reference decisions')
    if task['token_limit'] != TOKENS_PER_DECISION * task['decision_limit']:
        raise ValueError(f'{identifier}: the token budget is {TOKENS_PER_DECISION} per allowed decision')


def validate_task(task):
    if not isinstance(task, dict) or not REQUIRED <= task.keys():
        raise ValueError('Gen II task is missing required specification fields')
    identifier = task['id']
    if not isinstance(identifier, str) or not re.fullmatch(r'gen2-[a-z0-9]+(?:-[a-z0-9]+)*', identifier):
        raise ValueError('Gen II task IDs start with gen2-')
    for field in ('title', 'start', 'agent_goal', 'measures', 'task_family'):
        if not isinstance(task.get(field), str) or not task[field].strip():
            raise ValueError(f'{identifier}: missing {field}')
    for field in ('success', 'failure', 'variants', 'requirements', 'scenario_details', 'sources'):
        values = task.get(field)
        if not isinstance(values, list) or not values or any(not isinstance(v, str) or not v.strip() for v in values):
            raise ValueError(f'{identifier}: {field} must be a nonempty text list')
    if task['difficulty'] not in ('easy', 'medium', 'hard', 'stretch') or task['tested_skill'] not in SKILLS:
        raise ValueError(f'{identifier}: unknown difficulty or tested skill')
    if task['mode'] != 'gameplay' or task['action_policy'] != ASSISTED:
        raise ValueError(f'{identifier}: Gen II tasks are assisted gameplay tasks')
    if task['status'] != 'specified' or task['calibration'] != 'pending' or task['existing_task'] is not None:
        raise ValueError(f'{identifier}: a specification is not a validated or calibrated evaluation')
    objective = task['objective']
    if (not isinstance(objective, dict) or set(objective) != {'kind', 'task_id', 'description'}
            or objective['kind'] != 'catalog-task' or objective['task_id'] != identifier
            or objective['description'] != task['agent_goal']):
        raise ValueError(f'{identifier}: the objective is this catalog task with the agent goal as its text')
    for key in ('token_limit', 'decision_limit'):
        if type(task[key]) is not int or task[key] <= 0:
            raise ValueError(f'{identifier}: {key} must be a positive integer')
    validate_capture(identifier, task.get('capture'))
    validate_milestones(task.get('milestones'))
    if 'fixture' in task:
        validate_fixture(identifier, task)
    return task


def validate_catalog(catalog):
    if catalog.get('category') != CATEGORY or catalog.get('game') != 'pokemon-crystal':
        raise ValueError('Not the Gen II prep catalog')
    tasks = catalog.get('evals')
    if not isinstance(tasks, list) or not tasks:
        raise ValueError('The Gen II catalog needs tasks')
    seen = set()
    for task in tasks:
        validate_task(task)
        if task['id'] in seen:
            raise ValueError('Duplicate Gen II task ID')
        seen.add(task['id'])
    return catalog


@cache
def _load():
    return validate_catalog(json.loads(CATALOG.read_text()))


def load_tasks():
    return deepcopy(_load()['evals'])


def task_definition(task_id):
    for task in _load()['evals']:
        if task['id'] == task_id:
            return deepcopy(task)
    raise KeyError(task_id)
