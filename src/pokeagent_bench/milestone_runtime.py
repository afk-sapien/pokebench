"""Private ordered-milestone graders for PokeBench Hard.

Each Hard task lists ordered milestones in its catalog entry. A milestone is a fixed
predicate over RAM facts: map, position, event flags, bag items, badges, story flags and
League wins. The model sees only the task goal, never the milestones or their checks.
A run earns one point per milestone, in order, and keeps them if it later blacks out
or runs out of decisions. The score maximum is the number of milestones.
"""
from copy import deepcopy
from functools import cache
import json
import re

from pokecore.gen1 import W_EVENT_FLAGS, event_set

from .campaign_runtime import STORY_FLAGS, read_campaign_evidence
from .core import encoded

VERSION = 'milestone-runtime-v1'
PROTOCOL = 'catalog-milestones-v1'
ELITE = ('Lorelei', 'Bruno', 'Agatha', 'Lance')
STORY = frozenset(STORY_FLAGS) | {'snorlax-resolved', 'ss-anne-rival'}
CHECKS = frozenset({'map', 'area', 'near', 'event', 'item', 'badge', 'story', 'elite', 'champion', 'hall_of_fame'})


def _whole(value, lower, upper):
    return type(value) is int and lower <= value <= upper


def validate_check(check):
    """Accept only RAM conditions this module knows how to read."""
    if not isinstance(check, dict) or not check or not set(check) <= CHECKS:
        raise ValueError('A milestone check needs known RAM conditions')
    if 'map' in check and not _whole(check['map'], 0, 255):
        raise ValueError('Invalid milestone map')
    if ('area' in check or 'near' in check) and 'map' not in check:
        raise ValueError('A position check needs its map')
    if 'area' in check:
        area = check['area']
        if (not isinstance(area, list) or len(area) != 4 or not all(_whole(v, 0, 255) for v in area)
                or area[0] > area[2] or area[1] > area[3]):
            raise ValueError('A milestone area is [x0, y0, x1, y1]')
    if 'near' in check:
        near = check['near']
        if not isinstance(near, list) or len(near) != 2 or not all(_whole(v, 0, 255) for v in near):
            raise ValueError('A milestone near check is [x, y]')
    if 'event' in check and not _whole(check['event'], 0, 2559):
        raise ValueError('Invalid milestone event flag')
    if 'item' in check and not _whole(check['item'], 1, 255):
        raise ValueError('Invalid milestone item')
    if 'badge' in check and not _whole(check['badge'], 0, 7):
        raise ValueError('Invalid milestone badge')
    if 'story' in check and check['story'] not in STORY:
        raise ValueError('Unknown milestone story flag')
    if 'elite' in check and check['elite'] not in ELITE:
        raise ValueError('Unknown milestone League opponent')
    for key in ('champion', 'hall_of_fame'):
        if key in check and check[key] is not True:
            raise ValueError(f'Milestone {key} check must be true')
    return check


def validate_milestones(milestones):
    if not isinstance(milestones, list) or not milestones:
        raise ValueError('Hard tasks need ordered milestones')
    seen = set()
    for milestone in milestones:
        if not isinstance(milestone, dict) or set(milestone) != {'id', 'description', 'check'}:
            raise ValueError('A milestone has an id, a description and a check')
        identifier = milestone['id']
        if not isinstance(identifier, str) or not re.fullmatch(r'[a-z0-9]+(?:-[a-z0-9]+)*', identifier) or identifier in seen:
            raise ValueError('Milestone IDs are distinct lowercase words')
        if not isinstance(milestone['description'], str) or not milestone['description'].strip():
            raise ValueError(f'{identifier}: missing description')
        validate_check(milestone['check'])
        seen.add(identifier)
    return milestones


@cache
def _events(task_id):
    from .evaluation_catalog import task_definition
    return tuple(sorted({row['check']['event'] for row in task_definition(task_id)['milestones'] if 'event' in row['check']}))


def milestone_evidence(engine, task_id):
    """Read the facts the task's milestones check, and only the event flags they name."""
    state = read_campaign_evidence(engine)
    memory = engine.memory
    flags = bytes(memory[W_EVENT_FLAGS:W_EVENT_FLAGS + 0x140])
    state.update(x=memory[0xD362], y=memory[0xD361],
                 events={str(index): event_set(flags, index) for index in _events(task_id)})
    return json.loads(encoded(state))


def blackout(state):
    return state['battle'] == 255 or bool(state['party']) and not any(mon['hp'] for mon in state['party'])


class MilestoneEvaluator:
    """One point per milestone, earned in order, each confirmed on two different game frames."""

    def __init__(self, initialfacts, objective, task=None):
        if set(objective) != {'kind', 'task_id', 'description'} or objective['kind'] != 'catalog-task':
            raise ValueError('Invalid Hard objective')
        if task is None:
            from .evaluation_catalog import task_definition
            task = task_definition(objective['task_id'])
        if task['id'] != objective['task_id']:
            raise ValueError('Hard objective names a different task')
        if not initialfacts['valid']:
            raise ValueError('Hard checkpoint must be a valid started game')
        self.objective = deepcopy(objective)
        self.task_id = task['id']
        self.milestones = deepcopy(validate_milestones(task['milestones']))
        self.score_max = len(self.milestones)
        self.baseline = deepcopy(initialfacts)
        self.initial_keys = set()
        self.awarded = {}
        self.events = []
        self.pending = None
        self.last_frame = None
        self.disqualified = False
        self.disqualification_reason = None
        if blackout(self.baseline):
            raise ValueError('Hard task cannot start blacked out')
        for milestone in self.milestones:
            if self.holds(milestone['check'], self.baseline):
                raise ValueError(f'Milestone {milestone["id"]} is already met at the start')

    def holds(self, check, state):
        if 'map' in check and (state['map_id'] != check['map'] or state['battle']):
            return False
        if 'area' in check:
            x0, y0, x1, y1 = check['area']
            if not (x0 <= state['x'] <= x1 and y0 <= state['y'] <= y1):
                return False
        if 'near' in check and abs(state['x'] - check['near'][0]) + abs(state['y'] - check['near'][1]) > 1:
            return False
        if 'event' in check and not state['events'].get(str(check['event'])):
            return False
        if 'item' in check and not any(item == check['item'] and count > 0 for item, count in state['items']):
            return False
        if 'badge' in check and not state['badges'] & (1 << check['badge']):
            return False
        if 'story' in check and not state['story'].get(check['story']):
            return False
        if 'elite' in check and not state['elite'].get(check['elite']):
            return False
        if check.get('champion') and not state['champion']:
            return False
        if check.get('hall_of_fame') and state['hall_of_fame'] <= self.baseline['hall_of_fame']:
            return False
        return True

    def reject(self, reason):
        if not self.disqualified:
            self.disqualified = True
            self.disqualification_reason = reason

    def observe(self, facts, frame, wall_seconds):
        if self.last_frame is not None and frame < self.last_frame:
            raise ValueError('Milestone evaluation frame moved backwards')
        if frame == self.last_frame:
            return []
        self.last_frame = frame
        if not facts['valid'] or self.disqualified or self.complete():
            self.pending = None
            return []
        if blackout(facts):
            self.reject('Blackout during the Hard task')
            return []
        milestone = self.milestones[len(self.awarded)]
        if not self.holds(milestone['check'], facts):
            self.pending = None
            return []
        if self.pending is None:
            self.pending = frame
            return []
        award = {'id': 'milestone:' + milestone['id'], 'points': 1, 'frame': frame,
                 'wall_seconds': round(wall_seconds, 6), 'task_id': self.task_id}
        self.awarded[award['id']] = award
        self.events.append({'kind': milestone['id'], 'frame': frame})
        self.pending = None
        return [award]

    @property
    def score(self):
        return len(self.awarded)

    def complete(self, goal=None):
        return len(self.awarded) == self.score_max
