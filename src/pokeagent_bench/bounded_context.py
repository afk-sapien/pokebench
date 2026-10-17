"""Public snapshots and state updates for bounded conversation segments."""
from copy import deepcopy
import json

from .core import encoded
from .readable_context import command, tree

STATE_FIELDS = ('location', 'screen', 'local_map', 'party', 'bag', 'money', 'badges', 'battle')
RESULT_FIELDS = ('request', 'outcome', 'shortcut', 'position_before', 'position_after', 'map_changed',
                 'requested_tiles', 'tiles_moved', 'dialogue', 'visible_object_changes', 'blocked_at')
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


def state(public, notes, detail="full"):
    game = public['game']
    result = {'game': {key: deepcopy(game[key]) for key in STATE_FIELDS if key in game},
              'agent': {'notes': notes or None, 'plan': deepcopy(game.get('memory', {}).get('agent_plan'))}}
    if detail == 'on-demand':
        for mon in result['game'].get('party', []):
            for move in mon.get('moves', []):
                for key in ('id', 'base_pp', 'power', 'accuracy_percent', 'effect'):
                    move.pop(key, None)
    elif detail != 'full':
        raise ValueError('Unknown bounded observation detail')
    return result


def field_changes(old, current):
    return {"replace": {key: deepcopy(value) for key, value in current.items()
                        if key not in old or value != old[key]},
            "remove": [key for key in old if key not in current]}


def party_updates(old, current):
    """Lossless slot updates within a segment, with full replacements on roster changes."""
    if not isinstance(old, list) or len(old) != len(current):
        return None
    identity = ("slot", "species", "nickname")
    if any(any(a.get(key) != b.get(key) for key in identity) for a, b in zip(old, current)):
        return None
    updates = []
    for slot, (before, after) in enumerate(zip(old, current), 1):
        changes = field_changes(before, after)
        moves_before, moves_after = before.get("moves"), after.get("moves")
        if isinstance(moves_before, list) and isinstance(moves_after, list) and len(moves_before) == len(moves_after):
            same_moves = all(all(a.get(key) == b.get(key) for key in ("slot", "id", "name"))
                             for a, b in zip(moves_before, moves_after))
            if same_moves and "moves" in changes["replace"]:
                del changes["replace"]["moves"]
                changes["move_updates"] = [{"slot": a.get("slot", index), **field_changes(a, b)}
                                           for index, (a, b) in enumerate(zip(moves_before, moves_after), 1) if a != b]
        if changes["replace"] or changes["remove"] or changes.get("move_updates"):
            updates.append({"slot": slot, **changes})
    return updates


def build(public, notes, recent, previous, sequence, segment, detail="full"):
    current = state(public, notes, detail)
    snapshot = previous is None
    packet = {'protocol': 'bounded-gameplay-context-v3', 'kind': 'snapshot' if snapshot else 'update',
              'sequence': sequence, 'base_sequence': None if snapshot else sequence - 1,
              'segment': segment, 'frame': public['frame'], 'token_budget': deepcopy(public['token_budget']),
              'decision_budget': deepcopy(public.get('decision_budget')),
              'location': deepcopy(current['game'].get('location')), 'replace': {}, 'remove': []}
    if 'task_status' in public:
        packet['task_status'] = deepcopy(public['task_status'])
    for group in ('game', 'agent'):
        old = {} if snapshot else previous[group]
        packet['replace'][group] = {key: value for key, value in current[group].items()
                                    if key not in old or value != old[key]}
        packet['remove'].extend(group + '.' + key for key in old if key not in current[group])
    if not snapshot and "party" in packet["replace"]["game"]:
        updates = party_updates(previous['game'].get('party'), current['game']['party'])
        if updates is not None:
            del packet['replace']['game']['party']
            packet['party_updates'] = updates
    game = public['game']
    last = game.get('last_command')
    packet['last_result'] = {key: deepcopy(last[key]) for key in RESULT_FIELDS if key in last} if last else None
    packet['controller_errors'] = [{'error': str(row['error'])} for row in recent if 'error' in row]
    if 'inspection' in game:
        packet['requested_inspection'] = deepcopy(game['inspection'])
    if snapshot:
        packet['inspection_help'] = ('Inspect party for complete owned moves including power, accuracy and effects. '
                                     'Inspect bag, storage, map or memory for their recorded details. '
                                     'Inspection uses a metered decision but advances no game frames.')
        packet['detail_policy'] = detail
        packet['task'] = {key: deepcopy(public[key]) for key in ('objective', 'goal', 'track', 'action_policy', 'tested_skill', 'max_action_frames',
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


def render(packet, *, compact_inspection=False):
    data = json.loads(json.dumps(packet, sort_keys=True, ensure_ascii=False))
    recall = data.pop('recall', None)
    inspection = data.pop('requested_inspection', None) if compact_inspection else None
    lines = ['GAME UPDATE. Replace listed fields, remove listed paths, retain other fields in this segment.',
             'A snapshot starts a new segment and replaces all earlier state.',
             *(['Party and move updates use one-based slots. Replace/remove only listed fields. Retain the rest.']
               if 'party_updates' in data else []), *tree(data)]
    if recall is not None:
        decisions = recall.pop('recent_decisions')
        encounters = {row['id']: row for row in recall.get('encounters', [])}
        lines.extend(['', 'RECENT OBSERVED DECISIONS (OLDEST FIRST)'])
        for row in decisions:
            lines.append('Decision ' + str(row['decision']) + ':')
            for item in row.get('commands', []):
                lines.extend('  ' + line for line in command(item, encounters))
        lines.extend(['', 'CHECKPOINT RECALL', *tree(recall)])
    if inspection is not None:
        lines.extend(['', 'REQUESTED INSPECTION (compact JSON, all fields retained)',
                      json.dumps(inspection, ensure_ascii=False, sort_keys=True, separators=(',', ':'))])
    text = '\n'.join(lines) + '\n'
    if not compact_inspection and 'requested_inspection' in packet and len(text.encode()) > INSPECTION_BYTES:
        return render(packet, compact_inspection=True)
    return text


def check_size(packet, text):
    maximum = INSPECTION_BYTES if 'requested_inspection' in packet else PACKET_BYTES
    if len(text.encode()) > maximum:
        raise ObservationBudgetError(f'Observation text exceeds {maximum} UTF-8 bytes before a model request')
