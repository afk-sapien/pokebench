"""Private, task-specific Gen 1 graders for the focused catalog.

Goals are fixed predicates, not interpreted natural-language instructions.
Native inputs and stable state transitions supply the operation ledger.
"""
from collections import Counter
from copy import deepcopy

from pokecore.gen1 import W_EVENT_FLAGS, event_set
from pokecore.gen1_ui import read_screen
from pokecore.storage import decode_box, memory_bytes

from .campaign_runtime import CampaignTracker, read_campaign_evidence
from .gameplay import ui_state

VERSION = 'catalog-runtime-v062'
NAVIGATION = {
    'navigation-town-landmark', 'navigation-forest-crossing', 'navigation-branching-cave',
    'navigation-warp-puzzle', 'navigation-spinning-floors', 'navigation-boulder-puzzle',
    'navigation-blocked-route-alternative', 'navigation-multifloor-required-stops',
}
BATTLES = {
    'battle-wild-basics', 'battle-prepared-gym', 'battle-unfavorable-lead',
    'battle-ineffective-attack-adaptation', 'battle-heal-switch-attack-tradeoff',
    'battle-underleveled-status-setup', 'battle-preserve-specialist',
    'battle-losing-midbattle-recovery', 'battle-restricted-pp', 'battle-uncertain-opponent-lineup',
    'battle-league-balanced', 'battle-league-constrained',
}
OBJECTIVES = {
    'objectives-capture-pikachu-fixed', 'objectives-starter-selection', 'objectives-parcel-roundtrip', 'objectives-npc-instruction',
    'objectives-prerequisite-chain', 'objectives-find-capture-species',
    'objectives-constrained-valuable-capture', 'objectives-infeasible-plan-alternate',
    'objectives-recover-earlier-mistake', 'objectives-quest-trainer', 'objectives-capture-prepare-battle',
}
OPERATIONS = {
    'operations-heal-potion-target', 'operations-cure-poison', 'operations-restore-move-pp',
    'operations-battle-switch', 'operations-party-reorder', 'operations-buy-pokeballs',
    'operations-deposit-withdraw', 'operations-teach-tm-replace-move',
    'operations-withdraw-item-and-use', 'operations-menu-checklist',
}
TASK_IDS = NAVIGATION | BATTLES | OBJECTIVES | OPERATIONS
# Gen 1 shops selling balls. Native ball acquisition here is a purchase.
BALL_SHOPS = {42, 56, 67, 91, 123, 150, 152, 172, 173, 174, 180}
CAPTURES = {'objectives-capture-pikachu-fixed': 84, 'objectives-find-capture-species': 84,
            'objectives-constrained-valuable-capture': 132, 'objectives-capture-prepare-battle': 148}


def _identity(mon):
    return mon['species'], mon['trainer_id'], tuple(mon['dvs'])


def _lineage(mon):
    return mon['trainer_id'], tuple(mon['dvs'])


def _canonical(value):
    if isinstance(value, dict):
        return {key: _canonical(item) for key, item in value.items()}
    if isinstance(value, (tuple, list)):
        return [_canonical(item) for item in value]
    return value


def _bag(state):
    return dict(state['items'])


def catalog_evidence(engine, task_id):
    if task_id not in TASK_IDS:
        raise ValueError('Unknown catalog task')
    state = read_campaign_evidence(engine)
    memory = engine.memory
    flags = bytes(memory[W_EVENT_FLAGS:W_EVENT_FLAGS + 0x140])
    screen = read_screen(memory)
    ui = ui_state(memory)
    state.update(x=memory[0xD362], y=memory[0xD361], last_map=memory[0xD365],
                 saffron_open=bool(memory[0xD728] & 64),
                 bike_voucher_received=event_set(flags, 337), bicycle_received=event_set(flags, 192),
                 hideout_open=event_set(flags, 441),
                 moon_stone_removed=bool(memory[0xD5A6 + 125 // 8] & (1 << (125 % 8))),
                 enemy_hp=int.from_bytes(bytes(memory[0xCFE6:0xCFE8]), 'big'),
                 active_slot=memory[0xCC2F], active_species=memory[0xD014], trainer_class=memory[0xD031], run_attempts=memory[0xD120],
                 ui=ui, menu_index=screen['menu_index'],
                 party_menu=bool(ui.get('visible_choices')) and all(
                     row.split(':', 1)[0].isdigit() for row in ui['visible_choices']),
                 settled=ui['kind'] == 'overworld' or (
                     ui['kind'] == 'menu' and any(row in ('ITEM', 'SAVE', 'EXIT')
                                               for row in ui.get('visible_choices', []))))
    state['overworld'] = ui['kind'] == 'overworld'
    if task_id in OPERATIONS or task_id == 'objectives-capture-prepare-battle':
        count = min(memory[0xD53A], 50)
        state['pc_items'] = [[memory[0xD53B + 2 * index], memory[0xD53C + 2 * index]] for index in range(count)]
        count = min(memory[0xDA80], 20)
        structs = bytes(memory[0xDA96:0xDA96 + count * 33]) if count else b''
        names = bytes(memory[0xDE06:0xDE06 + count * 11]) if count else b''
        # Box structures preserve the identity fields omitted by the public storage view.
        state['box'] = [{'species': mon.species, 'trainer_id': mon.trainer_id, 'dvs': list(mon.dvs),
                         'level': mon.level, 'hp': mon.hp, 'status': mon.status,
                         'moves': list(mon.moves), 'pp': list(mon.pp), 'experience': mon.experience,
                         'stat_exp': list(mon.stat_exp)} for mon in decode_box(structs, names)]
    else:
        state['pc_items'], state['box'] = [], []
    state['stored'] = state['box']
    if task_id == 'objectives-capture-prepare-battle':
        stored = list(state['box'])
        initialized = bool(memory[0xD5A0] & 128)
        if initialized:
            for box in range(12):
                if box == state['active_box']:
                    continue
                bank, base = 2 + box // 6, 0xA000 + (box % 6) * 1122
                count = min(memory[bank, base], 20)
                if count:
                    raw = memory_bytes(memory, bank, base + 22, count * 33)
                    names = memory_bytes(memory, bank, base + 902, count * 11)
                    stored.extend({'species': mon.species, 'trainer_id': mon.trainer_id,
                                   'dvs': list(mon.dvs), 'level': mon.level}
                                  for mon in decode_box(raw, names))
        state['stored'] = stored
    return _canonical(state)


class CatalogEvaluator:
    """One normalized point after two different confirming game frames."""

    def __init__(self, initialfacts, objective):
        if (set(objective) != {'kind', 'task_id', 'description'} or objective['kind'] != 'catalog-task'
                or objective['task_id'] not in TASK_IDS):
            raise ValueError('Invalid catalog objective')
        if not initialfacts['valid']:
            raise ValueError('Catalog checkpoint must be a valid started game')
        self.objective = deepcopy(objective)
        self.task_id = objective['task_id']
        self.baseline = _canonical(initialfacts)
        self.last = deepcopy(self.baseline)
        self.initial_keys = set()
        self.awarded = {}
        self.previous = False
        self.last_frame = None
        self.disqualified = False
        self.disqualification_reason = None
        self.events = []
        self.visits = set()
        self.stages = {}
        self.pending_stages = {}
        self.wild_xp = False
        self.wild_finished = False
        self.wild_won = False
        self.capture_tracker = CampaignTracker(self.baseline) if self.task_id in CAPTURES else None
        self.capture_record = None
        self.capture_event_count = 0
        self.command_ledger = []
        self.deposited = False
        self.withdrawn = False
        self.switched = False
        self._validate_start()
        if self.reached(self.baseline):
            raise ValueError('Catalog task is already complete at its start')

    def _validate_start(self):
        state = self.baseline
        if self.task_id in BATTLES and self.task_id not in ('battle-league-balanced', 'battle-league-constrained'):
            expected = 1 if self.task_id == 'battle-wild-basics' else 2
            if state['battle'] != expected:
                raise ValueError('Battle task needs its live initial encounter')
        if self.task_id in CAPTURES:
            target = CAPTURES[self.task_id]
            if any(mon['species'] == target for mon in state['party'] + state.get('stored', state['box'])):
                raise ValueError('Capture target already owned at start')
        if self.task_id == 'objectives-capture-pikachu-fixed' and (state['battle'] != 1 or state['enemy_species'] != 84):
            raise ValueError('Fixed Pikachu task needs its live initial encounter')
        if self.task_id == 'operations-battle-switch' and (state['battle'] != 2 or state['active_slot'] != 0):
            raise ValueError('Switch task needs a trainer battle with the first party member active')
        if self.task_id in OPERATIONS - {'operations-battle-switch'} and state['battle']:
            raise ValueError('Menu task must start outside battle')

    def reject(self, reason):
        if not self.disqualified:
            self.disqualified = True
            self.disqualification_reason = reason

    def observe_input(self, button, facts):
        """Record the selected visible command before native A is pressed."""
        if button != 'a' or self.awarded:
            return
        ui = facts['ui']
        selected = ui.get('selected_text')
        if self.task_id == 'battle-wild-basics' and ui['kind'] == 'battle_menu' and selected == 'RUN':
            self.reject('The wild battle forbids running')
        if self.task_id != 'operations-battle-switch':
            return
        if ui['kind'] == 'battle_menu':
            if selected != 'PKMN' or self.command_ledger:
                self.reject('Only the initial PKMN switch command is allowed')
            else:
                self.command_ledger.append('PKMN')
        elif facts['party_menu']:
            if facts['menu_index'] != 2 or self.command_ledger != ['PKMN']:
                self.reject('The requested party selection is Pikachu in slot 3')
            else:
                self.command_ledger.append('slot:3')
        elif selected == 'SWITCH':
            if self.command_ledger != ['PKMN', 'slot:3']:
                self.reject('Unexpected switch selection')
            else:
                self.command_ledger.append('SWITCH')
        elif ui['kind'] == 'move_menu' or selected in ('FIGHT', 'ITEM', 'RUN'):
            self.reject('An extra player battle command was selected')

    def _stage(self, name, condition, frame):
        if name in self.stages:
            return
        if condition:
            if name in self.pending_stages and self.pending_stages[name] < frame:
                self.stages[name] = frame
                self.events.append({'kind': name, 'frame': frame})
            else:
                self.pending_stages[name] = frame
        else:
            self.pending_stages.pop(name, None)

    def _track(self, state, frame):
        task, old, initial = self.task_id, self.last, self.baseline
        if state['battle'] == 255 or (state['party'] and not any(mon['hp'] for mon in state['party'])):
            self.reject('Blackout during the focused task')
        if state['battle'] == 0:
            self.visits.add(state['map_id'])
        if task in BATTLES and Counter(_lineage(mon) for mon in state['party']) != Counter(_lineage(mon) for mon in initial['party']):
            self.reject('Changed the supplied battle roster')
        if task in OPERATIONS - {'operations-battle-switch'} and state['battle']:
            self.reject('Entered battle during a menu operation')
        if task == 'navigation-warp-puzzle' and state['battle']:
            self.reject('Started a battle instead of reaching the target tile')
        if task == 'navigation-blocked-route-alternative' and state['saffron_open']:
            self.reject('Opened the Saffron guard route')
        if task == 'navigation-spinning-floors':
            self._stage('moon-stone', state['map_id'] == 200 and state['moon_stone_removed']
                        and not initial['moon_stone_removed'] and _bag(state).get(10, 0) > _bag(initial).get(10, 0), frame)
        if task == 'navigation-boulder-puzzle':
            self._stage('ladder', state['map_id'] == 194 and (old['map_id'] == 108 or 'ladder' in self.pending_stages), frame)
        if task == 'objectives-parcel-roundtrip':
            self._stage('parcel-receipt', state['story']['parcel-collected'] and not initial['story']['parcel-collected'], frame)
        if task in ('objectives-infeasible-plan-alternate', 'objectives-recover-earlier-mistake'):
            self._stage('voucher', state['bike_voucher_received'] and not initial['bike_voucher_received'], frame)
        if task == 'objectives-quest-trainer':
            self._stage('hideout', state['hideout_open'] and not initial['hideout_open'], frame)
            self._stage('lift-key', 'hideout' in self.stages and state['map_id'] == 202 and _bag(state).get(74, 0) > 0, frame)
            if state['story']['hideout-giovanni'] and 'lift-key' not in self.stages:
                self.reject('Giovanni victory preceded the required Lift Key acquisition')
            self._stage('giovanni', 'lift-key' in self.stages and state['story']['hideout-giovanni'], frame)
            self._stage('scope', 'giovanni' in self.stages and state['map_id'] == 202 and _bag(state).get(72, 0) > 0, frame)
        if task in CAPTURES:
            self.capture_tracker.observe(state, frame, 0)
            captures = [event for event in self.capture_tracker.events if event['kind'] == 'capture']
            if len(captures) > self.capture_event_count:
                event = captures[-1]
                if event['species'] == CAPTURES[task]:
                    old_ids = Counter(_identity(mon) for mon in old['party'] + old['box'])
                    candidates = [mon for mon in state['party'] + state['box'] if mon['species'] == event['species']]
                    # The tracker confirms on the next frame, after the party entry exists.
                    # Match against the original encounter population, not this last frame.
                    encounter = self.capture_tracker.battle_start
                    if encounter is not None:
                        old_ids = Counter(_identity(mon) for mon in encounter['party'] + encounter.get('box', []))
                    new = [mon for mon in candidates if not old_ids[_identity(mon)]]
                    if len(new) == 1 and (task != 'objectives-capture-prepare-battle' or state['map_id'] == 35):
                        self.capture_record = {'identity': _lineage(new[0]), 'level': new[0]['level'], 'frame': frame}
                self.capture_event_count = len(captures)
            if task == 'objectives-find-capture-species':
                if state['map_id'] in BALL_SHOPS and any(
                        _bag(state).get(item, 0) > _bag(old).get(item, 0) for item in (1, 2, 3, 4)):
                    self.reject('Purchased additional balls, which this task forbids')
            if task in ('objectives-constrained-valuable-capture', 'objectives-capture-pikachu-fixed'):
                if state['battle'] == 0 and self.capture_record is None and self.capture_tracker.pending_capture is None:
                    self.reject('Initial encounter ended without its capture')
            if task == 'objectives-capture-prepare-battle':
                raised = self.capture_record is not None and any(
                    _lineage(mon) == tuple_identity(self.capture_record['identity']) and mon['level'] > self.capture_record['level']
                    for mon in state['party'] + state.get('stored', state['box']))
                self._stage('trained-abra', raised, frame)
                self._stage('misty-started', state['battle'] == 2 and state.get('trainer_class') == 35, frame)
                if 'misty-started' in self.stages and 'trained-abra' not in self.stages:
                    self.reject('Started the Misty battle before training the captured Abra')
                if state['badges'] & 2 and state['gym_flags'][1] and 'trained-abra' not in self.stages:
                    self.reject('Misty was defeated before the captured Abra gained a level')
        if task == 'battle-wild-basics':
            if any(_bag(state).get(item, 0) < _bag(initial).get(item, 0) for item in (1, 2, 3, 4)) or state['captured_species']:
                self.reject('The battle requires a knockout, not a capture')
            if not self.wild_finished:
                if state['battle'] == 1:
                    self.wild_xp |= any(mon['experience'] > oldmon['experience']
                        for mon, oldmon in zip(state['party'], initial['party']) if _lineage(mon) == _lineage(oldmon))
                elif state['battle'] == 0:
                    self.wild_finished = True
                    self.wild_won = self.wild_xp and not self.disqualified
        if task in OPERATIONS:
            self._track_operations(state, frame)

    def _track_operations(self, state, frame):
        task, initial = self.task_id, self.baseline
        if task == 'operations-battle-switch':
            if state['active_slot'] not in (0, 2):
                self.reject('Switched to the wrong Pokemon')
            if state['active_slot'] == 2 and self.command_ledger not in (['PKMN', 'slot:3'], ['PKMN', 'slot:3', 'SWITCH']):
                self.reject('Missing native menu command evidence for the switch')
            if _bag(state) != _bag(initial):
                self.reject('Used an item before completing the switch')
            if any(a['pp'] != b['pp'] for a, b in zip(state['party'], initial['party'])):
                self.reject('Used a player move before completing the switch')
        if task in ('operations-withdraw-item-and-use', 'operations-menu-checklist'):
            withdrawn = (dict(state['pc_items']).get(20, 0) == 0 and _bag(state).get(20, 0) == 1)
            self._stage('withdraw-potion', withdrawn, frame)
            used = ('withdraw-potion' in self.stages and _bag(state).get(20, 0) == 0
                    and any(_identity(mon) == _identity(initial['party'][1]) and mon['hp'] == 30 for mon in state['party']))
            self._stage('use-potion', used, frame)
            if task == 'operations-menu-checklist':
                order = [_identity(mon) for mon in state['party']]
                original = [_identity(mon) for mon in initial['party']]
                if order != original and 'use-potion' not in self.stages:
                    self.reject('Party reordering preceded the requested item use')
                self._stage('reorder', 'use-potion' in self.stages and order == [original[2], original[0], original[1]], frame)
        if task == 'operations-deposit-withdraw':
            target = _identity(initial['party'][1])
            party_ids = [_identity(mon) for mon in state['party']]
            boxed_ids = [_identity(mon) for mon in state['box']]
            self._stage('deposit', target not in party_ids and target in boxed_ids, frame)
            self._stage('withdraw', 'deposit' in self.stages and party_ids and party_ids[-1] == target
                        and target not in boxed_ids, frame)
            self._stage('switch-back', 'withdraw' in self.stages and party_ids == [_identity(mon) for mon in initial['party']], frame)

    def _unchanged_party(self, state, *, order=None, target=None, changes=None):
        expected = deepcopy(self.baseline['party'])
        if target is not None:
            expected[target].update(changes or {})
        if order is not None:
            expected = [expected[index] for index in order]
        return _canonical(state['party']) == _canonical(expected)

    def _bag_change(self, state, item, delta):
        expected = _bag(self.baseline)
        expected[item] = expected.get(item, 0) + delta
        return {key: count for key, count in expected.items() if count} == {key: count for key, count in _bag(state).items() if count}

    def _operation_reached(self, state):
        task, initial = self.task_id, self.baseline
        local = state['map_id'] == initial['map_id']
        if task == 'operations-battle-switch':
            return (state['battle'] == 2 and state['active_slot'] == 2 and state['active_species'] == 84 and state['party'][2]['species'] == 84
                    and self.command_ledger in (['PKMN', 'slot:3'], ['PKMN', 'slot:3', 'SWITCH']))
        if task == 'operations-heal-potion-target':
            return local and state['settled'] and self._bag_change(state, 20, -1) and self._unchanged_party(state, target=1, changes={'hp': 32})
        if task == 'operations-cure-poison':
            return local and state['settled'] and self._bag_change(state, 11, -1) and self._unchanged_party(state, target=2, changes={'status': 0})
        if task == 'operations-restore-move-pp':
            pp = list(initial['party'][0]['pp'])
            pp[3] = 15
            return local and state['settled'] and self._bag_change(state, 80, -1) and self._unchanged_party(state, target=0, changes={'pp': pp})
        if task == 'operations-party-reorder':
            return (local and (state['x'], state['y']) == (initial['x'], initial['y']) and state['settled']
                    and _bag(state) == _bag(initial) and self._unchanged_party(state, order=[2, 0, 1]))
        if task == 'operations-buy-pokeballs':
            return (state['map_id'] == 1 and state['overworld'] and state['money'] == 0
                    and self._bag_change(state, 4, 10) and self._unchanged_party(state))
        if task == 'operations-deposit-withdraw':
            return ('switch-back' in self.stages and state['settled'] and state['map_id'] == initial['map_id']
                    and self._unchanged_party(state) and _bag(state) == _bag(initial)
                    and state['active_box'] == initial['active_box'] and state['box'] == initial['box'])
        if task == 'operations-teach-tm-replace-move':
            moves, pp = list(initial['party'][1]['moves']), list(initial['party'][1]['pp'])
            moves[1], pp[1] = 117, 10
            return (local and state['settled'] and self._bag_change(state, 234, -1)
                    and self._unchanged_party(state, target=1, changes={'moves': moves, 'pp': pp}))
        if task in ('operations-withdraw-item-and-use', 'operations-menu-checklist'):
            pc = dict(initial['pc_items'])
            pc.pop(20, None)
            order = [2, 0, 1] if task == 'operations-menu-checklist' else None
            stage = 'reorder' if order else 'use-potion'
            return (stage in self.stages and state['settled'] and state['map_id'] == initial['map_id']
                    and dict(state['pc_items']) == pc and _bag(state) == _bag(initial)
                    and self._unchanged_party(state, target=1, changes={'hp': 30}, order=order))
        return False

    def reached(self, state):
        if self.disqualified or not state['valid']:
            return False
        task, initial, bag = self.task_id, self.baseline, _bag(state)
        outside = state['battle'] == 0 and state['overworld']
        if task in OPERATIONS:
            return self._operation_reached(state)
        if task in {'navigation-town-landmark', 'navigation-forest-crossing', 'navigation-branching-cave'}:
            target = {'navigation-town-landmark': 41, 'navigation-forest-crossing': 2, 'navigation-branching-cave': 3}[task]
            return outside and state['map_id'] == target and initial['map_id'] != target
        if task == 'navigation-warp-puzzle':
            return outside and (state['map_id'], state['x'], state['y']) == (178, 9, 9)
        if task == 'navigation-spinning-floors':
            return outside and 'moon-stone' in self.stages
        if task == 'navigation-boulder-puzzle':
            return outside and state['map_id'] == 194 and 'ladder' in self.stages
        if task == 'navigation-blocked-route-alternative':
            return outside and state['map_id'] == 5 and not state['saffron_open']
        if task == 'navigation-multifloor-required-stops':
            return outside and state['map_id'] == 126 and {123, 125} <= self.visits
        if task == 'objectives-starter-selection':
            return (state['story']['starter'] and not initial['story']['starter'] and len(state['party']) == 1
                    and state['party'][0]['species'] in (153, 176, 177) and state['ui']['kind'] != 'naming'
                    and state['party'][0].get('nick') == {153: 'BULBASAUR', 176: 'CHARMANDER', 177: 'SQUIRTLE'}[state['party'][0]['species']])
        if task == 'objectives-parcel-roundtrip':
            return outside and 'parcel-receipt' in self.stages and state['story']['parcel'] and not bag.get(70, 0)
        if task == 'objectives-npc-instruction':
            return outside and state['story']['bill-ticket'] and not initial['story']['bill-ticket'] and bag.get(63, 0) == 1
        if task == 'objectives-prerequisite-chain':
            return outside and state['story']['fuji-flute'] and state['story']['ghost-marowak'] and bag.get(73, 0) == 1
        if task in CAPTURES:
            retained = self.capture_record is not None and any(_lineage(mon) == tuple_identity(self.capture_record['identity'])
                for mon in state['party'] + (state.get('stored', state['box']) if task == 'objectives-capture-prepare-battle' else []))
            if task == 'objectives-capture-prepare-battle':
                return outside and retained and 'trained-abra' in self.stages and bool(state['badges'] & 2) and state['gym_flags'][1]
            return outside and retained
        if task in ('objectives-infeasible-plan-alternate', 'objectives-recover-earlier-mistake'):
            voucher = 'voucher' in self.stages if task == 'objectives-infeasible-plan-alternate' else _bag(initial).get(45, 0) == 1
            return (outside and voucher and state['bicycle_received'] and not initial['bicycle_received']
                    and bag.get(6, 0) == 1 and not bag.get(45, 0))
        if task == 'objectives-quest-trainer':
            return outside and 'scope' in self.stages and bag.get(72, 0) == 1
        if task == 'battle-wild-basics':
            return outside and self.wild_won
        targets = {
            'battle-prepared-gym': 'boulder', 'battle-unfavorable-lead': 'Lorelei',
            'battle-ineffective-attack-adaptation': 'Lorelei', 'battle-heal-switch-attack-tradeoff': 'Bruno',
            'battle-underleveled-status-setup': 'Lorelei', 'battle-losing-midbattle-recovery': 'Agatha',
        }
        if task in targets:
            target = targets[task]
            return outside and (bool(state['badges'] & 1) and state['gym_flags'][0] and not initial['gym_flags'][0]
                if target == 'boulder' else state['elite'].get(target, False) and not initial['elite'].get(target, False))
        if task == 'battle-restricted-pp':
            return outside and all(state['elite'].get(name, False) and not initial['elite'].get(name, False) for name in ('Lorelei', 'Bruno'))
        if task in ('battle-preserve-specialist', 'battle-uncertain-opponent-lineup'):
            return state['battle'] == 0 and state['champion'] and not initial['champion']
        if task in ('battle-league-balanced', 'battle-league-constrained'):
            return (state['battle'] == 0 and state['champion'] and state['map_id'] == 118
                    and state['hall_of_fame'] > initial['hall_of_fame']
                    and all(state['elite'].get(name, False) for name in ('Lorelei', 'Bruno', 'Agatha', 'Lance')))
        return False

    def observe(self, facts, frame, wall_seconds):
        if self.last_frame is not None and frame < self.last_frame:
            raise ValueError('Catalog evaluation frame moved backwards')
        if frame == self.last_frame:
            return []
        self.last_frame = frame
        state = _canonical(facts)
        if not state['valid']:
            self.previous = False
            return []
        self._track(state, frame)
        reached = self.reached(state)
        new = []
        if reached and self.previous and not self.awarded:
            award = {'id': 'challenge:complete', 'points': 1, 'frame': frame,
                     'wall_seconds': round(wall_seconds, 6), 'task_id': self.task_id}
            self.awarded[award['id']] = award
            new.append(award)
        self.previous = reached
        self.last = deepcopy(state)
        return new

    @property
    def score(self):
        return int(bool(self.awarded))

    def complete(self, goal=None):
        return bool(self.awarded)


def tuple_identity(value):
    return value[0], tuple(value[1])
