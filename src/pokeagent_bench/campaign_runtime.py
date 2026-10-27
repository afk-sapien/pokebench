"""Private Gen 1 campaign scoring from native game evidence.

This is a new scoring protocol. It never rewrites earlier run scores and never
advances the emulator. Call observe at controller frame boundaries, not only at
model decisions, so capture and evolution transitions remain observable.
"""
from collections import Counter
from copy import deepcopy
from functools import lru_cache
import json
from pathlib import Path
from statistics import median

from pokecore.gen1 import BADGES, event_set, read_progress
from pokecore.snapshot import read_fields

VERSION = 'campaign-progress-v1'

# Zero-based event indices from pret/pokered event_constants.asm.
STORY_FLAGS = {
    'starter': (34,), 'parcel-collected': (57,), 'parcel': (56, 37),
    'cerulean-rival': (152,), 'bill-ticket': (1371, 1372), 'hm-cut': (1504,),
    'hideout-giovanni': (1703,), 'ghost-marowak': (271,),
    'fuji-flute': (279, 296), 'silph-rival': (1856,), 'silph-giovanni': (1935,),
    'hm-surf': (2176,), 'hm-strength': (568, 569),
}
# Native item pickups have no named event flag. Require a new inventory entry
# while at the actual pickup map. Starting inventory never earns these awards.
ITEM_MILESTONES = {
    'lift-key': (74, 202), 'silph-scope': (72, 202), 'card-key': (48, 210),
    'gold-teeth': (64, 219), 'secret-key': (43, 216),
}
VISITS = {
    1: 'viridian-city', 2: 'pewter-city', 3: 'cerulean-city', 5: 'vermilion-city',
    4: 'lavender-town', 6: 'celadon-city', 7: 'fuchsia-city', 10: 'saffron-city',
    8: 'cinnabar-island', 9: 'indigo-plateau',
}


@lru_cache(maxsize=1)
def milestone_definitions():
    """Use the catalog as the one source of milestone IDs and weights."""
    path = Path(__file__).with_name('catalogs') / 'campaign.json'
    rows = json.loads(path.read_text())['evals'][0]['milestones']
    if len(rows) != 50 or sum(row['points'] for row in rows) != 1000:
        raise ValueError('Campaign milestone definition changed without a protocol update')
    return {row['id']: {key: row[key] for key in ('id', 'label', 'group', 'points')} for row in rows}


def read_evolution_families(memory):
    """Read native Red evolution records directly from ROM, without shipping tables.

    Red's EvosMovesPointerTable is bank 14 at 0x705c. A family is the connected
    component of native evolution edges, including Eevee's branches.
    """
    parents = {species: species for species in range(1, 191)}
    edges = []

    def family(species):
        while parents[species] != species:
            species = parents[species]
        return species

    for species in range(1, 191):
        address = 0x705C + (species - 1) * 2
        cursor = memory[14, address] | (memory[14, address + 1] << 8)
        if not 0x4000 <= cursor < 0x8000:
            raise ValueError('Invalid Red evolution ROM pointer')
        for _ in range(4):
            method = memory[14, cursor]
            if method == 0:
                break
            if method not in (1, 2, 3):
                raise ValueError('Invalid Red evolution method')
            width = 4 if method == 2 else 3
            target = memory[14, cursor + width - 1]
            if not 1 <= target <= 190:
                raise ValueError('Invalid Red evolution target')
            edges.append([species, target])
            left, right = family(species), family(target)
            parents[max(left, right)] = min(left, right)
            cursor += width
        else:
            raise ValueError('Too many Red evolution records')
    return {'families': {str(species): family(species) for species in parents}, 'edges': edges}


def read_campaign_evidence(engine):
    """Read private facts without exposing quest flags to the agent."""
    fields = read_fields(engine.memory)
    progress = read_progress(engine.memory)
    if not hasattr(engine, '_campaign_evolution_data'):
        engine._campaign_evolution_data = read_evolution_families(engine.memory)
    flags = fields['event_flags']
    story = {name: all(event_set(flags, index) for index in indices)
             for name, indices in STORY_FLAGS.items()}
    story['snorlax-resolved'] = any(event_set(flags, index) for index in (1167, 1225))
    # SCRIPT_SSANNE2F_NOOP is reached after the rival exits following victory.
    story['ss-anne-rival'] = engine.memory[0xD665] == 4
    party = fields['party']
    valid_party = len(party) <= 6 and all(1 <= mon['species'] <= 190 and 1 <= mon['level'] <= 100
                                        and 0 < mon['max_hp'] <= 999 and mon['hp'] <= mon['max_hp']
                                        for mon in party)
    started = bool(fields['player_name']) and (bool(party) or fields['map'] in (0, 37, 38, 40))
    return {
        'valid': valid_party and started, 'map_id': fields['map'], 'story': story,
        'badges': progress['badges'], 'gym_flags': progress['gym_flags'],
        'elite': progress['elite'], 'champion': progress['champion'],
        'hall_of_fame': progress['hall_of_fame'], 'party': deepcopy(party),
        'money': fields['money'], 'items': [list(row) for row in fields['items']],
        'owned': sorted(fields['owned']), 'seen': sorted(fields['seen']),
        'battle': fields['in_battle'], 'enemy_species': fields['enemy_species'],
        'battle_type': fields['battle_type'], 'captured_species': engine.memory[0xD11C],
        'evolution_occurred': bool(engine.memory[0xD121]),
        'battle_result': engine.memory[0xCF0B],
        'active_box': fields['active_box'], 'box_species': [row[0] for row in fields['boxed_pokemon']],
        'overworld': not fields['in_battle'] and not fields['textbox'] and not fields['start_menu'],
        'evolution_data': engine._campaign_evolution_data,
    }


def _identity(mon):
    return (mon['trainer_id'], tuple(mon['dvs']))


def _population(state, species):
    return sum(mon['species'] == species for mon in state['party']) + state['box_species'].count(species)


def party_profile(state):
    """Descriptive readiness, not a fabricated win probability or power score."""
    party = deepcopy(state['party'])
    levels = [mon['level'] for mon in party]
    return {
        'party': party, 'total_level': sum(levels), 'median_level': median(levels) if levels else None,
        'nonfainted': sum(mon['hp'] > 0 for mon in party),
        'distinct_party_species': len({mon['species'] for mon in party}),
        'remaining_pp': sum(sum(mon['pp']) for mon in party),
        'owned_species': len(state['owned']), 'seen_species': len(state['seen']),
        'active_box': state['active_box'], 'active_box_species': list(state['box_species']),
        'money': state['money'], 'bag': deepcopy(state['items']),
        'battle_power': None, 'battle_power_status': 'not calculated without full game tables',
        'all_storage_species': None, 'all_storage_status': 'only active box sampled at frame boundaries',
    }


class CampaignTracker:
    """Persistent, baseline-excluding awards for one continuous campaign."""

    def __init__(self, initial):
        if not initial['valid']:
            raise ValueError('Campaign requires a valid started game')
        self.baseline = deepcopy(initial)
        self.last_state = deepcopy(initial)
        self.awarded = {}
        self.collected_items = set()
        self.caught_species = set()
        self.evolved_families = set()
        self.events = []
        self.previous = set()
        self.previous_frame = None
        self.captured_this_battle = False
        self.pending_capture = None
        self.pending_evolution = None
        self.pending_items = {}
        self.battle_start = deepcopy(initial) if initial['battle'] == 1 else None
        self.counters = {'captures': 0, 'evolutions': 0, 'observed_faints': 0, 'blackouts': 0}
        self.metrics = {'decision': 0, 'tokens': 0, 'actions': 0}
        self.initial_keys = self.candidates(initial)
        if initial['champion'] or initial['hall_of_fame']:
            self.initial_keys.add('champion')
        self.initial_keys.update(key for key, (item, _) in ITEM_MILESTONES.items()
                                 if dict(initial['items']).get(item, 0))
        self.profiles = [{'id': 'start', 'frame': 0, 'profile': party_profile(initial)}]

    def candidates(self, state):
        if not state['valid']:
            return set()
        keys = {key for key, done in state['story'].items() if done}
        keys.update(self.collected_items)
        keys.update(f'badge:{name.lower()}' for index, name in enumerate(BADGES)
                    if state['badges'] & (1 << index) and state['gym_flags'][index])
        keys.update(f'elite:{name.lower()}' for name, won in state['elite'].items() if won)
        if (state['champion'] and state['map_id'] == 118
                and state['hall_of_fame'] > self.baseline['hall_of_fame']):
            keys.add('champion')
        if state['overworld'] and state['map_id'] in VISITS:
            keys.add('visit:' + VISITS[state['map_id']])
        keys.update(f'caught-species:{n}' for n in (1, 5, 10, 20) if len(self.caught_species) >= n)
        keys.update(f'evolved-lines:{n}' for n in (1, 3) if len(self.evolved_families) >= n)
        if len({mon['species'] for mon in state['party']}) == 6:
            keys.add('party-six-species')
        return keys & milestone_definitions().keys()

    def _transitions(self, state, stamp):
        old = self.last_state
        bag, old_bag = dict(state['items']), dict(old['items'])
        for key, (item, room) in ITEM_MILESTONES.items():
            if (state['map_id'] == room and state['battle'] == 0 and bag.get(item, 0) > old_bag.get(item, 0)
                    and key not in self.initial_keys):
                # Hold the candidate until a second frame confirms the inventory.
                self.pending_items[key] = item
        for key, item in list(self.pending_items.items()):
            if bag.get(item, 0) > 0 and old_bag.get(item, 0) > 0:
                self.collected_items.add(key)
                del self.pending_items[key]
            elif not bag.get(item, 0):
                del self.pending_items[key]

        if state['battle'] == 1 and old['battle'] != 1:
            self.battle_start = deepcopy(state)
            self.captured_this_battle = False
            self.pending_capture = None
        captured = state['captured_species']
        if (state['battle'] == 1 and 1 <= captured <= 190 and not self.captured_this_battle
                and captured == state['enemy_species'] and self.battle_start is not None):
            self.pending_capture = captured
        if self.pending_capture is not None and self.battle_start is not None:
            species = self.pending_capture
            confirmed = (state['active_box'] == self.battle_start['active_box']
                         and _population(state, species) > _population(self.battle_start, species)
                         and _population(old, species) > _population(self.battle_start, species))
            if confirmed:
                self.caught_species.add(species)
                self.counters['captures'] += 1
                self.events.append({'kind': 'capture', 'species': species, **stamp})
                self.captured_this_battle = True
                self.pending_capture = None
            elif state['battle'] not in (0, 1):
                self.pending_capture = None

        edges = {tuple(pair) for pair in state['evolution_data']['edges']}
        if self.pending_evolution is not None:
            identity, before, after = self.pending_evolution
            if any(_identity(mon) == identity and mon['species'] == after for mon in state['party']):
                self.evolved_families.add(state['evolution_data']['families'][str(after)])
                self.counters['evolutions'] += 1
                self.events.append({'kind': 'evolution', 'from_species': before, 'species': after, **stamp})
            self.pending_evolution = None
        if state['evolution_occurred'] and len(state['party']) == len(old['party']):
            old_ids = Counter(_identity(mon) for mon in old['party'])
            new_ids = Counter(_identity(mon) for mon in state['party'])
            for before, after in zip(old['party'], state['party']):
                identity = _identity(before)
                if ((before['species'], after['species']) in edges and _identity(after) == identity
                        and old_ids[identity] == new_ids[identity] == 1
                        and before['experience'] <= after['experience']
                        and tuple(before['stat_exp']) == tuple(after['stat_exp'])):
                    self.pending_evolution = (identity, before['species'], after['species'])
        old_alive = {_identity(mon): mon['hp'] > 0 for mon in old['party']}
        if state['battle'] in (1, 2, 255) or old['battle'] in (1, 2):
            self.counters['observed_faints'] += sum(old_alive.get(_identity(mon), False) and mon['hp'] == 0
                                                   for mon in state['party'])
        if state['battle'] == 255 and old['battle'] != 255:
            self.counters['blackouts'] += 1
            self.events.append({'kind': 'blackout', **stamp})

    def observe(self, state, frame, wall_seconds, *, decision=None, tokens=None, actions=None):
        if self.previous_frame is not None and frame < self.previous_frame:
            raise ValueError('Campaign frame cannot move backwards')
        if frame == self.previous_frame:
            return []
        for name, value in [('decision', decision), ('tokens', tokens), ('actions', actions)]:
            if value is not None:
                self.metrics[name] = value
        stamp = {'frame': frame, 'wall_seconds': round(wall_seconds, 6), **self.metrics}
        self.previous_frame = frame
        if not state['valid']:
            self.previous = set()
            return []
        self._transitions(state, stamp)
        candidates = self.candidates(state)
        confirmed = (self.previous & candidates) - self.initial_keys - self.awarded.keys()
        self.previous = candidates
        new = []
        definitions = milestone_definitions()
        for key in sorted(confirmed):
            award = {**definitions[key], **stamp}
            self.awarded[key] = award
            self.events.append({'kind': 'milestone', **award})
            self.profiles.append({'id': key, **stamp, 'profile': party_profile(state)})
            new.append(award)
        self.last_state = deepcopy(state)
        return new

    @property
    def score(self):
        return sum(row['points'] for row in self.awarded.values())

    def complete(self, goal=None):
        return 'champion' in self.awarded

    def report(self):
        definitions = milestone_definitions()
        groups = {}
        for row in definitions.values():
            group = groups.setdefault(row['group'], {'points': 0, 'maximum_points': 0, 'completed': 0, 'total': 0})
            group['maximum_points'] += row['points']
            group['total'] += 1
            if row['id'] in self.awarded:
                group['points'] += row['points']
                group['completed'] += 1
        return {'version': VERSION, 'score': self.score, 'maximum_points': 1000, 'champion': self.complete(),
                'completed_milestones': len(self.awarded), 'total_milestones': 50,
                'groups': groups, 'milestones': [{**row, 'status': 'achieved' if key in self.awarded else
                    'present-at-start' if key in self.initial_keys else 'not-reached',
                    'achievement': deepcopy(self.awarded.get(key))} for key, row in definitions.items()],
                'events': deepcopy(self.events), 'profiles': deepcopy(self.profiles),
                'current_profile': party_profile(self.last_state),
                'counters': {**self.counters, 'distinct_wild_species': len(self.caught_species),
                             'distinct_evolved_families': len(self.evolved_families),
                             'purchases': None, 'sales': None, 'item_uses': None,
                             'wild_wins': None, 'escapes': None, 'unique_trainer_wins': None},
                'unavailable_reason': 'Transaction and generic battle outcome provenance is not supplied by Core. '
                                      'Inventory or money changes are not classified as purchases or wins.'}

    def to_dict(self):
        """JSON-safe resumable state, including in-flight capture evidence."""
        value = deepcopy(vars(self))
        for key in ('collected_items', 'caught_species', 'evolved_families', 'previous', 'initial_keys'):
            value[key] = sorted(value[key])
        return {'version': VERSION, 'state': value}

    @classmethod
    def from_dict(cls, value):
        if value.get('version') != VERSION:
            raise ValueError('Unsupported campaign checkpoint version')
        instance = object.__new__(cls)
        instance.__dict__.update(deepcopy(value['state']))
        for key in ('collected_items', 'caught_species', 'evolved_families', 'previous', 'initial_keys'):
            setattr(instance, key, set(getattr(instance, key)))
        pending = instance.pending_evolution
        if pending is not None:
            instance.pending_evolution = ((pending[0][0], tuple(pending[0][1])), pending[1], pending[2])
        return instance
