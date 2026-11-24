"""Ordered milestones for the Gen II prep tasks, read from Crystal RAM.

The rules match milestone_runtime for Red. A run earns one point per milestone, in order,
and each one is confirmed on two different game frames. A map check fails during a battle.
A start where any milestone already holds is refused, and a blackout ends the run. Only the
checks differ: maps are [group, number] pairs, Crystal has 16 badges and two bag pockets
are read, and an events check needs every flag it lists.
"""
from __future__ import annotations

from copy import deepcopy
import re

VERSION = 'gen2-milestones-v1'
CHECKS = frozenset({'map', 'area', 'near', 'event', 'events', 'item', 'key_item', 'badge'})
EVENTS = 2048


def _whole(value, lower, upper):
    return type(value) is int and lower <= value <= upper


def validate_check(check):
    """Accept only RAM conditions engine.facts reads."""
    if not isinstance(check, dict) or not check or not set(check) <= CHECKS:
        raise ValueError('A Gen II milestone check needs known RAM conditions')
    if 'map' in check:
        place = check['map']
        if not isinstance(place, list) or len(place) != 2 or not _whole(place[0], 1, 26) or not _whole(place[1], 1, 255):
            raise ValueError('A Gen II milestone map is [group, number]')
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
    if 'event' in check and not _whole(check['event'], 0, EVENTS - 1):
        raise ValueError('Invalid milestone event flag')
    if 'events' in check:
        flags = check['events']
        if (not isinstance(flags, list) or len(flags) < 2 or len(set(flags)) != len(flags)
                or not all(_whole(flag, 0, EVENTS - 1) for flag in flags)):
            raise ValueError('An events check lists two or more distinct event flags')
    for key in ('item', 'key_item'):
        if key in check and not _whole(check[key], 1, 255):
            raise ValueError(f'Invalid milestone {key}')
    if 'badge' in check and not _whole(check['badge'], 0, 15):
        raise ValueError('Invalid milestone badge')
    return check


def validate_milestones(milestones):
    if not isinstance(milestones, list) or not milestones:
        raise ValueError('Milestone tasks need ordered milestones')
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


def watched_events(milestones):
    """Every event flag the milestones read, for engine.facts."""
    flags = set()
    for milestone in milestones:
        check = milestone['check']
        flags.update([check['event']] if 'event' in check else [])
        flags.update(check.get('events', ()))
    return tuple(sorted(flags))


def holds(check, facts):
    if 'map' in check and (facts['map'] != check['map'] or facts['battle']):
        return False
    if 'area' in check:
        x0, y0, x1, y1 = check['area']
        if not (x0 <= facts['x'] <= x1 and y0 <= facts['y'] <= y1):
            return False
    if 'near' in check and abs(facts['x'] - check['near'][0]) + abs(facts['y'] - check['near'][1]) > 1:
        return False
    if 'event' in check and not facts['events'].get(str(check['event'])):
        return False
    if 'events' in check and not all(facts['events'].get(str(flag)) for flag in check['events']):
        return False
    if 'item' in check and not any(item == check['item'] and count > 0 for item, count in facts['items']):
        return False
    if 'key_item' in check and check['key_item'] not in facts['key_items']:
        return False
    if 'badge' in check and not facts['badges'] & (1 << check['badge']):
        return False
    return True


def blackout(facts):
    return bool(facts['party']) and not any(mon['hp'] for mon in facts['party'])


class MilestoneEvaluator:
    """One point per milestone, earned in order, each confirmed on two different game frames."""

    def __init__(self, initialfacts, task):
        objective = task['objective']
        if set(objective) != {'kind', 'task_id', 'description'} or objective['kind'] != 'catalog-task':
            raise ValueError('Invalid milestone objective')
        if task['id'] != objective['task_id']:
            raise ValueError('Milestone objective names a different task')
        if not initialfacts['valid']:
            raise ValueError('Milestone start must be a valid started game')
        self.task_id = task['id']
        self.milestones = deepcopy(validate_milestones(task['milestones']))
        self.events_read = watched_events(self.milestones)
        self.score_max = len(self.milestones)
        self.awarded = {}
        self.pending = None
        self.last_frame = None
        self.disqualified = False
        self.disqualification_reason = None
        if blackout(initialfacts):
            raise ValueError('Task cannot start blacked out')
        for milestone in self.milestones:
            if holds(milestone['check'], initialfacts):
                raise ValueError(f'Milestone {milestone["id"]} is already met at the start')

    def reject(self, reason):
        if not self.disqualified:
            self.disqualified = True
            self.disqualification_reason = reason

    def observe(self, facts, frame):
        if self.last_frame is not None and frame < self.last_frame:
            raise ValueError('Milestone evaluation frame moved backwards')
        if frame == self.last_frame:
            return []
        self.last_frame = frame
        if not facts['valid'] or self.disqualified or self.complete():
            self.pending = None
            return []
        if blackout(facts):
            self.reject('Blackout during the task')
            return []
        milestone = self.milestones[len(self.awarded)]
        if not holds(milestone['check'], facts):
            self.pending = None
            return []
        if self.pending is None:
            self.pending = frame
            return []
        award = {'id': 'milestone:' + milestone['id'], 'points': 1, 'frame': frame, 'task_id': self.task_id}
        self.awarded[award['id']] = award
        self.pending = None
        return [award]

    @property
    def score(self):
        return len(self.awarded)

    def complete(self):
        return len(self.awarded) == self.score_max
