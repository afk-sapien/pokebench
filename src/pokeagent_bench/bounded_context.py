"""Public snapshots and state updates for bounded conversation segments."""
from copy import deepcopy
import json

from .core import encoded
from .readable_context import command, tree

STATE_FIELDS = ('location', 'screen', 'local_map', 'party', 'bag', 'money', 'badges', 'battle')
RESULT_FIELDS = ('request', 'outcome', 'shortcut', 'position_before', 'position_after', 'map_changed',
                 'requested_tiles', 'tiles_moved', 'dialogue')
PACKET_BYTES = 32000
INSPECTION_BYTES = 64000


class ObservationBudgetError(ValueError):
    pass


def tail_with_budget(items, count, budget):
    selected = []
    for item in reversed(items[-count:]):
        if len(encoded([item, *selected])) > budget:
            break
        selected.insert(0, deepcopy(item))
    return selected, len(items) - len(selected)


def state(public, notes):
    game = public['game']
    return {'game': {key: deepcopy(game[key]) for key in STATE_FIELDS if key in game},
            'agent': {'notes': notes or None, 'plan': deepcopy(game.get('memory', {}).get('agent_plan'))}}


def build(public, notes, recent, previous, sequence, segment):
    current = state(public, notes)
    snapshot = previous is None
    packet = {'protocol': 'bounded-gameplay-context-v1', 'kind': 'snapshot' if snapshot else 'update',
              'sequence': sequence, 'base_sequence': None if snapshot else sequence - 1,
              'segment': segment, 'frame': public['frame'], 'token_budget': deepcopy(public['token_budget']),
              'location': deepcopy(current['game'].get('location')), 'replace': {}, 'remove': []}
    for group in ('game', 'agent'):
        old = {} if snapshot else previous[group]
        packet['replace'][group] = {key: value for key, value in current[group].items()
                                    if key not in old or value != old[key]}
        packet['remove'].extend(group + '.' + key for key in old if key not in current[group])
    game = public['game']
    last = game.get('last_command')
    packet['last_result'] = {key: deepcopy(last[key]) for key in RESULT_FIELDS if key in last} if last else None
    packet['controller_errors'] = [{'error': str(row['error'])} for row in recent if 'error' in row]
    if 'inspection' in game:
        packet['requested_inspection'] = deepcopy(game['inspection'])
    if snapshot:
        packet['task'] = {key: deepcopy(public[key]) for key in ('objective', 'goal', 'track', 'max_action_frames',
                           'max_actions_per_decision', 'max_dialogue_frames', 'max_note_bytes') if key in public}
        memory = game.get('memory', {})
        working = memory.get('working_memory', {})
        decisions, missing_decisions = tail_with_budget(working.get('recent_decisions', []), 8, 3072)
        ranked = sorted(working.get('encounters', []), key=lambda row: row.get('last_decision', row.get('first_decision', 0)))
        encounters, missing_encounters = tail_with_budget(ranked, 64, 2048)
        packet['recall'] = {'recent_decisions': decisions, 'encounters': encounters,
                            'omitted_decisions': missing_decisions,
                            'omitted_encounters': missing_encounters + working.get('omitted_encounters', 0),
                            'known_map': deepcopy(memory.get('known_map')),
                            'more': 'Inspect memory for the larger observed history. Agent notes and plans are unverified.'}
    return packet, current


def render(packet):
    data = json.loads(json.dumps(packet, sort_keys=True, ensure_ascii=False))
    recall = data.pop('recall', None)
    lines = ['GAME UPDATE. Replace listed fields, remove listed paths, retain other fields in this segment.',
             'A snapshot starts a new segment and replaces all earlier state.', *tree(data)]
    if recall is not None:
        decisions = recall.pop('recent_decisions')
        encounters = {row['id']: row for row in recall.get('encounters', [])}
        lines.extend(['', 'RECENT OBSERVED DECISIONS (OLDEST FIRST)'])
        for row in decisions:
            lines.append('Decision ' + str(row['decision']) + ':')
            for item in row.get('commands', []):
                lines.extend('  ' + line for line in command(item, encounters))
        lines.extend(['', 'CHECKPOINT RECALL', *tree(recall)])
    return '\n'.join(lines) + '\n'


def check_size(packet, text):
    maximum = INSPECTION_BYTES if 'requested_inspection' in packet else PACKET_BYTES
    if len(text.encode()) > maximum:
        raise ObservationBudgetError(f'Observation text exceeds {maximum} UTF-8 bytes before a model request')
