"""Native preparation actions and frozen, controller-only battle assessment.

The evaluated model never controls the assessment battles. Its submission is a
sequence of legal preparation decisions, executed through Core menu machines.
Assessment uses one declared fixed controller, not an optimal-play oracle.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import json
import math
import time

from pokesim_core.gen1 import W_IS_IN_BATTLE, W_MONEY, bcd, read_bag, read_party
from pokesim_core.shortcuts import (
    BuyItem, DepositPokemon, ReorderParty, UseItem, WithdrawPokemon, Done, current_screen,
)

from .core import Limits, core_provenance, digest, encoded, emulator_manifest, write_json
from .gameplay import load_catalog, observe_gameplay, ui_state
from .gameplay_commands import execute
from .session import Session, initialize_controls, load_engine

PROTOCOL = 'native-preparation-frozen-assessment-v1'
OFFSETS = (0, 17, 37, 67, 97)
POLICY_VERSION = 'fixed-battle-v4'
RUNTIME_SHA256 = digest(Path(__file__).read_bytes())


@dataclass(frozen=True)
class PreparationRule:
    operations: tuple[str, ...]
    items: tuple[int, ...] = ()
    shop: tuple[tuple[int, int], ...] = ()
    teaching: tuple[tuple[int, tuple[int, ...]], ...] = ()
    max_teaching: int = 0


ORDER = ('reorder_party',)
RULES = {
    'preparation-lead-selection': PreparationRule(ORDER),
    'preparation-recovery-before-continuing': PreparationRule(
        ORDER + ('use_item', 'heal_at_center'), (20,)),
    'preparation-assemble-storage-roster': PreparationRule(
        ORDER + ('deposit_pokemon', 'withdraw_pokemon')),
    'preparation-shop-for-challenge': PreparationRule(
        ORDER + ('buy_item',), shop=((20, 300), (11, 100), (15, 200), (12, 250), (4, 200))),
    'preparation-move-replacement-across-fights': PreparationRule(
        ORDER + ('teach_move',), teaching=((206, (38,)), (245, (38,))), max_teaching=1),
    'preparation-scarce-tm-allocation': PreparationRule(
        ORDER + ('teach_move',), teaching=((224, (84, 104)),), max_teaching=1),
    'preparation-damaged-team-rescue': PreparationRule(
        ORDER + ('use_item',), (53, 17, 82)),
    'preparation-uncertain-opponent': PreparationRule(
        ORDER + ('use_item',), (18, 16)),
    'preparation-pp-allocation-gauntlet': PreparationRule(
        ORDER + ('use_item',), (82,)),
    'preparation-scarce-resource-league': PreparationRule(
        ORDER + ('use_item', 'buy_item'), (17, 18, 16, 53, 82),
        shop=((17, 2500), (16, 3000), (53, 1500))),
}

# Transfer submitted player identity, owned party, names, bag and remaining cash. This is
# offline assessment-fixture construction, never an evaluated game action.
TRANSFER_RANGES = ((0xD158, 0xD2F7), (0xD31D, 0xD34A), (0xD359, 0xD35B))


def preparation_schema(task_id):
    rule = RULES[task_id]
    integer = {'type': ['integer', 'null']}
    fields = {'operation': {'type': 'string', 'enum': list(rule.operations)},
              **{key: integer for key in ('first', 'second', 'item', 'slot', 'quantity', 'forget')}}
    return {'type': 'object', 'additionalProperties': False,
            'properties': {'actions': {'type': 'array', 'maxItems': 40,
                'items': {'type': 'object', 'additionalProperties': False,
                          'properties': fields, 'required': list(fields)}}},
            'required': ['actions']}



def normalize_preparation_response(value, schema, limits=None):
    """Validate a preparation response without gameplay-command coercion."""
    from jsonschema import Draft202012Validator
    errors = list(Draft202012Validator(schema).iter_errors(value))
    if errors:
        raise ValueError('Preparation response does not match its JSON schema')
    return value


def public_preparation_state(session, task_id=None):
    """Publish owned resources only, never opponent RAM or evaluator flags."""
    from pokesim_core.shortcuts import list_box
    view = observe_gameplay(session)
    result = {key: view[key] for key in ('party', 'bag')}
    result['money'] = bcd(session.engine.memory[W_MONEY:W_MONEY + 3])
    if task_id == 'preparation-assemble-storage-roster':
        result['box'] = list_box(session.engine.memory, version='red')
    return result


def request_submission(provider, task, public_state, token_limit, timeout=180, *, record_usage=None):
    """One text-only structured turn using the existing subscription transport.

    Like the gameplay transports, this is a reported-usage ceiling. An individual
    CLI call cannot be hard-capped and can overshoot. No retry or compaction call
    is made. The caller must instantiate a dedicated, unused provider.
    """
    if type(token_limit) is not int or token_limit < 8000:
        raise ValueError('Preparation needs at least an 8000-token call reserve')
    if provider.server is not None or provider.thread_id is not None:
        raise ValueError('Use a fresh provider for the isolated preparation turn')
    provider.prompt = (
        'Prepare the supplied Pokemon Red team for the disclosed fight. Return only '
        'a JSON preparation plan. All slot indices are ZERO BASED. Unused fields must '
        'be null. reorder_party swaps first and second. use_item uses item on slot. '
        'teach_move uses TM item on slot and replaces move slot forget. buy_item buys '
        'quantity of item. deposit_pokemon and withdraw_pokemon use slot. '
        'heal_at_center requests the disclosed free Center service. Choose decisions, '
        'not button presses. An empty actions list submits the current configuration. '
        'After submission a fixed automated controller plays the battles. You cannot '
        'revise the preparation after seeing outcomes. There are no external tools.'
    )
    schema = preparation_schema(task['id'])
    provider.schema = schema
    provider.response_normalizer = normalize_preparation_response
    provider.decision_limits = Limits()
    from pokesim_core.shortcuts import item_names
    names = item_names('red')
    rule = RULES[task['id']]
    payload = {'task': {key: task[key] for key in ('id', 'agent_goal', 'scenario_details')},
               'state': public_state, 'allowed_operations': rule.operations,
               'legal_restoratives': [{'id': item, 'name': names.get(item)} for item in rule.items],
               'shop': [{'id': item, 'name': names.get(item), 'unit_price': price}
                        for item, price in rule.shop],
               'teaching': [{'item_id': item, 'name': names.get(item),
                             'recipient_species_ids': list(species)} for item, species in rule.teaching],
               'max_teaching_actions': rule.max_teaching}
    deadline = time.monotonic() + min(timeout, 180)
    try:
        provider._start(deadline)
        from .decision_contract import wire_schema
        message, usage = provider._complete('turn/start', {
            'threadId': provider.thread_id, 'input': [{'type': 'text', 'text': json.dumps(payload)}],
            'effort': provider.reasoning_effort,
            'outputSchema': wire_schema(schema, provider.provider)}, deadline)
        # Preserve reported charges even if the response cannot be interpreted.
        usage = {**usage, 'calls': 1}
        usage['accounting_complete'] = usage.get('accounting_complete', True) and all(
            type(usage.get(key)) is int and usage[key] >= 0
            for key in ('input_tokens', 'output_tokens'))
        if record_usage is not None:
            record_usage(usage)
        if not usage['accounting_complete']:
            raise ValueError('Missing preparation token accounting')
        invalid = None
        try:
            result = json.loads(message)
            normalize_preparation_response(result, schema)
        except (ValueError, TypeError) as exc:
            invalid = str(exc)
        total = usage['input_tokens'] + usage['output_tokens']
        return {'actions': result['actions'] if invalid is None else [], 'usage': usage,
                'invalid_response': invalid,
                'token_limit': token_limit, 'budget_exceeded': total > token_limit,
                'protocol': PROTOCOL, 'model': provider.model,
                'provider': provider.provider, 'prompt_sha256': digest(provider.prompt.encode()),
                'input_sha256': digest(encoded(payload))}
    finally:
        provider.close()


class InvalidPreparationAction(ValueError):
    """A model plan violates the disclosed preparation action contract."""


def _integer(action, name, lower, upper):
    value = action.get(name)
    if type(value) is not int or not lower <= value <= upper:
        raise InvalidPreparationAction(f'{name} must be an integer from {lower} through {upper}')
    return value


class PreparationSession:
    """Gate native menu actions, then seal a private immutable submission."""

    def __init__(self, session, task_id):
        self.session = session
        self.task_id = task_id
        self.rule = RULES[task_id]
        self.frozen = False
        self.history = []
        self.taught = 0
        if session.engine.memory[W_IS_IN_BATTLE]:
            raise ValueError('Preparation must start outside battle')
        self.initial = session.engine.save()

    def _send(self, operation_id, button, hold=8, release=24):
        if self.session.reason or self.session.engine.memory[W_IS_IN_BATTLE]:
            return False
        self.counter += 1
        self.session.act(f'{operation_id}.{self.counter}', button=button,
                         hold_frames=hold, release_frames=release)
        return not self.session.reason and not self.session.engine.memory[W_IS_IN_BATTLE]

    def _commands(self, name):
        commands = self.session.scenario.get('preparation', {}).get('facilities', {}).get(name)
        if commands is None:
            raise ValueError(f'Fixture lacks registered {name} controller route')
        for index, command in enumerate(commands):
            if not self._send(f'facility-{name}-{len(self.history)}-{index}',
                              command['button'], command['hold_frames'], command['release_frames']):
                raise ValueError('Preparation route entered battle or exceeded its budget')
            ready = {'shop': ('mart',), 'pc': ('pc', 'bills_pc')}
            if name in ready and current_screen(self.session.engine.memory, version='red') in ready[name]:
                break

    def act(self, action):
        if self.frozen:
            raise ValueError('Preparation has already been submitted')
        if len(self.history) >= 40:
            raise InvalidPreparationAction('Preparation plan exceeds forty actions')
        allowed_fields = {'operation', 'first', 'second', 'item', 'slot', 'quantity', 'forget'}
        if not isinstance(action, dict) or set(action) - allowed_fields:
            raise InvalidPreparationAction('Unknown preparation action field')
        operation = action.get('operation')
        if operation not in self.rule.operations:
            raise InvalidPreparationAction('This task does not allow that preparation operation')
        party = read_party(self.session.engine.memory)
        options = {'version': 'red', 'max_steps': 600}
        relevant = {'reorder_party': {'first', 'second'}, 'use_item': {'item', 'slot'},
                    'teach_move': {'item', 'slot', 'forget'}, 'buy_item': {'item', 'quantity'},
                    'deposit_pokemon': {'slot'}, 'withdraw_pokemon': {'slot'},
                    'heal_at_center': set()}[operation]
        if any(value is not None for key, value in action.items()
               if key not in relevant | {'operation'}):
            raise InvalidPreparationAction('Unexpected non-null argument for preparation operation')
        if operation == 'reorder_party':
            first = _integer(action, 'first', 0, len(party)-1)
            second = _integer(action, 'second', 0, len(party)-1)
            if self.task_id == 'preparation-lead-selection' and first != 0 and second != 0:
                raise InvalidPreparationAction('Lead selection may only swap the lead')
            machine = ReorderParty(first, second, **options)
        elif operation in ('use_item', 'teach_move'):
            item = _integer(action, 'item', 1, 255)
            slot = _integer(action, 'slot', 0, len(party)-1)
            if operation == 'teach_move':
                recipients = dict(self.rule.teaching).get(item, ())
                if party[slot]['species'] not in recipients or self.taught >= self.rule.max_teaching:
                    raise InvalidPreparationAction('TM recipient or teaching count violates this task')
                machine = UseItem(item, slot, forget_move=_integer(action, 'forget', 0, 3), **options)
            else:
                if item not in self.rule.items:
                    raise InvalidPreparationAction('Item is not allowed during this preparation task')
                machine = UseItem(item, slot, **options)
        elif operation == 'buy_item':
            item = _integer(action, 'item', 1, 255)
            quantity = _integer(action, 'quantity', 1, 99)
            price = dict(self.rule.shop).get(item)
            cash = bcd(self.session.engine.memory[W_MONEY:W_MONEY+3])
            if price is None or price * quantity > cash:
                raise InvalidPreparationAction('Purchase exceeds supplied stock or cash')
            machine = BuyItem(item, quantity, **options)
        elif operation == 'deposit_pokemon':
            machine = DepositPokemon(_integer(action, 'slot', 0, len(party)-1), **options)
        elif operation == 'withdraw_pokemon':
            machine = WithdrawPokemon(_integer(action, 'slot', 0, 19), **options)
        else:
            machine = None
        self.counter = 0
        if operation not in ('buy_item', 'deposit_pokemon', 'withdraw_pokemon'):
            for _ in range(15):
                screen = current_screen(self.session.engine.memory, version='red')
                if screen not in ('pc', 'bills_pc', 'players_pc', 'pc_box', 'pc_party', 'mart', 'mart_list'):
                    break
                if not self._send(f'leave-facility-{len(self.history)}', 'b', 8, 60):
                    raise ValueError('Could not close the facility menu within the controller budget')
        if operation == 'heal_at_center':
            self._commands('heal_at_center')
            after = read_party(self.session.engine.memory)
            result = {'shortcut': {'completed': all(m['hp'] == m['max_hp'] and not m['status'] for m in after)}}
        else:
            facility = {'buy_item': 'shop', 'deposit_pokemon': 'pc', 'withdraw_pokemon': 'pc'}.get(operation)
            ready = {'shop': ('mart',), 'pc': ('pc', 'bills_pc')}
            if facility and current_screen(self.session.engine.memory, version='red') not in ready[facility]:
                self._commands(facility)
            from .dialogue import continue_ready
            while True:
                view = ui_state(self.session.engine.memory)
                view['continue_ready'] = continue_ready(self.session.engine)
                step = machine.step(self.session.engine.memory, view)
                if isinstance(step, Done):
                    result = step.as_result(machine.kind)
                    break
                if not self._send(f'prep-{len(self.history)}', step,
                                  30 if step is None else 8, 0 if step is None else 36):
                    result = {'shortcut': {'completed': False, 'settled': False},
                              'outcome': 'Preparation controller budget exhausted'}
                    break
        if self.session.engine.memory[W_IS_IN_BATTLE]:
            raise ValueError('Preparation must not play or initiate assessment battles')
        completed = result.get('shortcut', {}).get('completed', False)
        if operation == 'teach_move' and completed:
            self.taught += 1
        record = {'request': action.copy(), 'result': result, 'frame': self.session.frame}
        self.history.append(record)
        write_json(self.session.output / 'preparation-actions.json', self.history)
        return record

    def submit(self, output):
        if self.frozen:
            raise ValueError('Preparation has already been submitted')
        memory = self.session.engine.memory
        if memory[W_IS_IN_BATTLE] or not any(m['hp'] for m in read_party(memory)):
            raise ValueError('Submission requires a usable party outside battle')
        output = Path(output)
        output.mkdir(parents=True, exist_ok=False)
        state = self.session.engine.save()
        transfer = {str(start): list(memory[start:end]) for start, end in TRANSFER_RANGES}
        record = {'protocol': PROTOCOL, 'task_id': self.task_id,
                  'initial_sha256': digest(self.initial), 'state_sha256': digest(state),
                  'transfer': transfer, 'transfer_sha256': digest(encoded(transfer)),
                  'party': read_party(memory), 'bag': list(read_bag(memory)),
                  'money': bcd(memory[W_MONEY:W_MONEY+3]), 'actions': self.history}
        (output / 'submission.state').write_bytes(state)
        write_json(output / 'submission.json', record)
        self.frozen = True
        return record


def load_submission(directory):
    directory = Path(directory)
    record = json.loads((directory / 'submission.json').read_text())
    if (digest((directory / 'submission.state').read_bytes()) != record['state_sha256']
            or digest(encoded(record['transfer'])) != record['transfer_sha256']):
        raise ValueError('Frozen preparation submission changed')
    expected = {str(start): end-start for start, end in TRANSFER_RANGES}
    if set(record['transfer']) != set(expected) or any(
        len(values) != expected[key] or any(type(v) is not int or not 0 <= v <= 255 for v in values)
        for key, values in record['transfer'].items()
    ):
        raise ValueError('Invalid preparation transfer payload')
    return record


class FixedBattlePolicy:
    """Shared deterministic tactics using public HUD and verified Gen 1 tables.

    It estimates move value, status opportunities and replacement matchups. It
    has no hidden opponent state, future roster, RNG access or optimality claim.
    """

    def __init__(self, strategy=None):
        from .gameplay import TYPES
        strategy = strategy or {}
        self.species = {v['name']: v for v in strategy.get('species', {}).values()}
        self.matchups = {(TYPES[a], TYPES[b]): value for a, b, value in strategy.get('matchups', [])}
        self.types = TYPES
        self.turn = 0
        self.last_switch = -10
        self.active_slot = None
        self.boosts = 0
        self.opponent = ''
        self.status_attempts = 0

    def enemy(self, view):
        hud = ' '.join(view['battle'].get('visible_hud', [])).upper()
        names = sorted(self.species, key=len, reverse=True)
        name = next((name for name in names if name in hud), '')
        return name, list(dict.fromkeys(self.types[t] for t in self.species.get(name, {}).get('types', [])))

    def effectiveness(self, attacking, defending):
        return math.prod(self.matchups.get((attacking, kind), 1) for kind in set(defending))

    def move_value(self, mon, move, enemy_types, asleep=False):
        if not move.get('pp'):
            return 0
        multiplier = self.effectiveness(move.get('type'), enemy_types)
        if not multiplier or (move['id'] == 138 and not asleep):
            return 0
        accuracy = (move.get('accuracy_percent') or 100) / 100
        if move['id'] in (49, 69, 82, 101):
            return ({49: 20, 82: 40}.get(move['id'], mon.get('level', 50))) * accuracy
        value = (move.get('power') or 0) * multiplier * accuracy
        if move.get('type') in mon.get('types', []):
            value *= 1.5
        if move['id'] in (120, 153):
            value *= .25
        if move['id'] == 63:
            value *= .65
        if move['id'] in (13, 19, 76, 91, 130, 143):
            value *= .55
        if move.get('type') in ('Fire', 'Water', 'Grass', 'Electric', 'Psychic', 'Ice', 'Dragon'):
            value *= 1 + .65 * self.boosts if mon.get('slot') == self.active_slot else 1
        elif 'burned' in mon.get('status', []):
            value *= .5
        return value

    def matchup_value(self, mon, enemy_types):
        attack = max((self.move_value(mon, move, enemy_types) for move in mon.get('moves', [])), default=0)
        danger = max((self.effectiveness(kind, mon.get('types', [])) for kind in enemy_types), default=1)
        health = mon['hp'] / max(mon.get('max_hp', mon['hp']), 1)
        return attack * (.5 + .5 * health) / max(.5, danger ** .5)

    def feedback(self, before, action, result):
        if action['command'] == 'use_move':
            active = before['party'][before['battle'].get('active_party_slot', 1)-1]
            move = next((m for m in active.get('moves', []) if str(m['slot']) == action['argument']), {})
            pages = ' '.join(result.get('dialogue', {}).get('pages', [])).upper()
            if move.get('id') == 133 and 'SPECIAL GREATLY ROSE' in pages:
                self.boosts = min(3, self.boosts + 1)

    def choose(self, view):
        def command(name, argument=''):
            return {'command': name, 'argument': str(argument), 'count': 1}
        party, battle, screen = view['party'], view['battle'], view['screen']
        slot = battle.get('active_party_slot', 1)
        active = party[slot-1]
        if self.active_slot != slot:
            self.active_slot, self.boosts = slot, 0
        enemy, enemy_types = self.enemy(view)
        if enemy and enemy != self.opponent:
            self.opponent, self.status_attempts = enemy, 0
        alive = [m for m in party if m['hp'] > 0 and m['slot'] != slot]
        best = max(alive, key=lambda m: self.matchup_value(m, enemy_types), default=None)
        if screen['kind'] not in ('battle_menu', 'move_menu'):
            if 'NO' in screen['visible_choices']:
                text = ' '.join(screen.get('text', [])).upper()
                # Keep the submitted moves, including the second confirmation.
                abandon = 'ABANDON LEARNING' in text or 'STOP LEARNING' in text
                return command('choose', 'YES' if abandon and 'YES' in screen['visible_choices'] else 'NO')
            if (screen['kind'] == 'party_menu' or any('BRING OUT WHICH' in line.upper()
                    for line in screen['text'])) and best:
                self.last_switch = self.turn
                return command('switch_pokemon', best['slot'])
            if screen['kind'] == 'menu':
                return command('press', 'b')
            if screen['kind'] == 'overworld':
                return command('interact')
            return command('advance_dialogue')
        self.turn += 1
        bag = {item['id']: item['quantity'] for item in view['bag']}
        moves = [m for m in active['moves'] if m['pp'] > 0]
        available = {m['id']: m for m in moves}
        hud = ' '.join(battle.get('visible_hud', [])).upper()
        asleep = 'SLP' in hud
        afflicted = any(status in hud for status in ('SLP', 'PAR', 'FRZ', 'PSN', 'BRN'))
        ratio = active['hp'] / active['max_hp']
        awake = 'asleep' not in active.get('status', [])
        if bag.get(16) and (ratio < .4 or ('frozen' in active.get('status', []))):
            return command('use_item', f'Full Restore:{slot}')
        if ratio < .4:
            for item, name in ((17, 'Max Potion'), (18, 'Hyper Potion'), (19, 'Super Potion'), (20, 'Potion')):
                if bag.get(item):
                    return command('use_item', f'{name}:{slot}')
        if awake and ratio < .55:
            for move in (105, 135, 156):
                if move in available:
                    return command('use_move', available[move]['slot'])
        fainted = [m for m in party if not m['hp']]
        if bag.get(53) and fainted and (not alive or ratio > .7):
            replacement = max(fainted, key=lambda m: self.matchup_value({**m, 'hp': m['max_hp']}, enemy_types))
            return command('use_item', f"Revive:{replacement['slot']}")
        current_attack = max((self.move_value(active, m, enemy_types, asleep) for m in moves), default=0)
        rested_attack = max((self.move_value(active, {**m, 'pp': 1}, enemy_types, asleep)
                            for m in active['moves']), default=0)
        if bag.get(82) and rested_attack > max(20, current_attack * 1.8):
            return command('use_item', f'Elixer:{slot}')
        current = self.matchup_value(active, enemy_types)
        if best and self.turn - self.last_switch >= 3 and self.matchup_value(best, enemy_types) > max(20, current * 1.8):
            self.last_switch = self.turn
            return command('switch_pokemon', best['slot'])
        if awake and ratio > .4 and not afflicted and self.status_attempts < 2:
            for move in (147, 79, 142, 95, 86):
                if move in available and self.effectiveness(available[move]['type'], enemy_types):
                    self.status_attempts += 1
                    return command('use_move', available[move]['slot'])
        special_types = {'Fire', 'Water', 'Grass', 'Electric', 'Psychic', 'Ice', 'Dragon'}
        special_attack = any(m.get('power', 0) and m.get('type') in special_types for m in moves)
        special_defense = bool(set(enemy_types) & special_types)
        if (awake and 133 in available and self.boosts < 3 and (special_attack or special_defense)
                and (asleep or ratio > .75)):
            return command('use_move', available[133]['slot'])
        damaging = [m for m in moves if self.move_value(active, m, enemy_types, asleep) > 0]
        if damaging:
            return command('use_move', max(damaging, key=lambda m: self.move_value(active, m, enemy_types, asleep))['slot'])
        if bag.get(82):
            return command('use_item', f'Elixer:{slot}')
        if best:
            self.last_switch = self.turn
            return command('switch_pokemon', best['slot'])
        return command('use_move', moves[0]['slot']) if moves else command('choose', 'FIGHT')


def between_battle_item(view):
    """Fixed assessment maintenance using only submitted resources and public party data."""
    bag = {item['id']: item['quantity'] for item in view['bag']}
    party = view['party']
    def use(name, mon):
        return {'command': 'use_item', 'argument': f"{name}:{mon['slot']}", 'count': 1}
    fainted = next((mon for mon in party if not mon['hp']), None)
    if fainted and bag.get(53):
        return use('Revive', fainted)
    conscious = [mon for mon in party if mon['hp']]
    damaged = min(conscious, key=lambda mon: mon['hp'] / mon['max_hp'], default=None)
    if damaged and damaged['hp'] / damaged['max_hp'] < .75:
        for item, name in ((20, 'Potion'), (19, 'Super Potion'), (18, 'Hyper Potion'),
                           (17, 'Max Potion'), (16, 'Full Restore')):
            if bag.get(item):
                return use(name, damaged)
    for mon in conscious:
        if any(status != 'healthy' for status in mon.get('status', [])):
            for item, name in ((52, 'Full Heal'), (16, 'Full Restore')):
                if bag.get(item):
                    return use(name, mon)
        attacks = [move for move in mon['moves'] if move.get('power', 0)]
        strongest = max(attacks, key=lambda move: move['power'] * (1.5 if move.get('type') in mon.get('types', []) else 1), default=None)
        if strongest and strongest['pp'] <= 2 and bag.get(82):
            return use('Elixer', mon)
    return None


def score_trials(rows, expected_trials, threshold=None):
    if len(rows) != expected_trials or len({r['trial_id'] for r in rows}) != expected_trials:
        raise ValueError('Every registered preparation assessment trial is required exactly once')
    errors = sum(bool(row.get('evaluation_error')) for row in rows)
    wins = sum(row['completed'] for row in rows if not row.get('evaluation_error'))
    if threshold is not None and (not isinstance(threshold, (int, float)) or not 0 <= threshold <= 1):
        raise ValueError('Win-rate threshold must be between zero and one')
    return {'trials': expected_trials, 'wins': wins, 'evaluation_errors': errors,
            'win_rate': wins / expected_trials if not errors else None,
            'completed': None if errors or threshold is None else wins >= math.ceil(threshold * expected_trials),
            'threshold': threshold, 'calibration': 'pending' if threshold is None else 'threshold-supplied',
            'qualification': 'Observed fixed-controller performance. Not optimal play or independent RNG samples.'}


def assess_submission(rom, submission, targets, output, game_data, *, offsets=OFFSETS,
                      threshold=None, max_decisions=500, target_variants=None):
    """Run each frozen target checkpoint at every registered timing offset.

    targets contain id, scenario path, objective and entry_commands. The target
    states must be before battle. Sequences can use multiple targets and carry
    the resulting party resources forward without restoring HP or PP.
    target_variants supplies alternative sequences. Each gets every offset with
    equal weight, rather than selecting the most favorable opponent result.
    """
    record = load_submission(submission)
    if not targets or not offsets or len(set(offsets)) != len(offsets):
        raise ValueError('Assessment needs targets and distinct fixed timing offsets')
    if any(type(n) is not int or n < 0 for n in offsets):
        raise ValueError('Timing offsets must be nonnegative integers')
    output = Path(output)
    output.mkdir(parents=True, exist_ok=False)
    catalog = load_catalog(Path(game_data))
    bundle = json.loads((Path(game_data) / 'current.json').read_text())['bundle']
    strategy = json.loads((Path(game_data) / 'bundles' / bundle / 'strategy.json').read_text())
    schedules = target_variants if target_variants is not None else [targets]
    if not schedules or any(not stages for stages in schedules):
        raise ValueError('Every disclosed opponent variant needs a nonempty sequence')
    rows = []
    policy_hash = RUNTIME_SHA256
    trials = [(schedule, offset) for schedule in schedules for offset in offsets]
    for variant, (schedule, offset) in enumerate(trials):
        transfer = record['transfer']
        stages = []
        error = None
        for stage, target in enumerate(schedule):
            destination = output / f'trial-{variant:02d}' / f'stage-{stage:02d}'
            session = None
            engine = None
            try:
                engine, source = load_engine(Path(rom), Path(target['scenario']))
                if engine.memory[W_IS_IN_BATTLE]:
                    raise ValueError('Assessment checkpoint must precede battle')
                for start, values in transfer.items():
                    for index, value in enumerate(values):
                        engine.memory[int(start) + index] = value
                state = engine.save()
                target_objective = target['objective']
                target_key = target_objective.get('target') or target_objective['targets'][0]
                objective = {'kind': 'preparation-submission', 'task_id': record['task_id'],
                             'description': 'Enter the registered assessment battle through controller input'}
                manifest = {'format': 1, 'game': 'red', 'name': target['id'],
                            'rom_sha256': engine.rom_sha256, 'state_sha256': digest(state),
                            **emulator_manifest(), 'core': core_provenance(), 'objective': objective,
                            **({'input_policy': source['input_policy']} if 'input_policy' in source else {}),
                            'preparation_assessment': {'protocol': PROTOCOL, 'offset': offset,
                                'submission_sha256': record['state_sha256'],
                                'source_sha256': source['state_sha256'], 'policy_sha256': policy_hash,
                                'setup': 'Submitted party and bag copied before battle, no opponent or RNG writes'}}
                session = Session(engine, destination / 'entry', manifest, track='gameplay', goal='challenge',
                                  gameplay_catalog=catalog,
                                  limits=Limits(max_actions=30000, max_frames=300000,
                                                max_action_frames=600, max_dialogue_frames=7200),
                                  agent={'provider': 'offline-preparation-assessment', 'model': POLICY_VERSION})
                if offset:
                    session.act('offset', button=None, hold_frames=offset, release_frames=0)
                for index, action in enumerate(target['entry_commands']):
                    if session.reason or (engine.memory[W_IS_IN_BATTLE] and
                                          ui_state(engine.memory)['kind'] == 'battle_menu'):
                        break
                    session.act(f'entry-{index}', **action)
                if not session.reason and engine.memory[W_IS_IN_BATTLE] != 2:
                    raise ValueError('Registered assessment entry did not start a trainer battle')
                battle_state = engine.save()
                session.finish('assessment_entry_complete')
                session.close()
                from .game import RedEngine
                engine = RedEngine(Path(rom), battle_state)
                manifest = {**manifest, 'state_sha256': digest(battle_state),
                            'input_policy': 'release-all-before-first-tick-v1',
                            'objective': {'kind': 'battle-milestone', 'target': target_key,
                                          'description': target_objective['description']}}
                initialize_controls(engine, manifest)
                session = Session(engine, destination / 'battle', manifest, track='gameplay', goal='challenge',
                                  gameplay_catalog=catalog,
                                  limits=Limits(max_actions=30000, max_frames=300000,
                                                max_action_frames=600, max_dialogue_frames=7200),
                                  agent={'provider': 'offline-preparation-assessment', 'model': POLICY_VERSION})
                policy = FixedBattlePolicy(strategy)
                idle = 0
                for decision in range(max_decisions):
                    if session.reason:
                        break
                    if engine.memory[W_IS_IN_BATTLE] == 255 or not any(m['hp'] for m in read_party(engine.memory)):
                        session.finish('battle_loss')
                        break
                    before = session.frame
                    view = observe_gameplay(session)
                    action = policy.choose(view)
                    outcome = execute(session, f'assess-{decision}', action)
                    policy.feedback(view, action, outcome)
                    if not session.reason and outcome.get('shortcut', {}).get('completed') is False:
                        raise ValueError('Native assessment shortcut failed: ' + outcome.get('outcome', 'unknown'))
                    idle = idle + 1 if session.frame == before else 0
                    if idle >= 3:
                        raise ValueError('Assessment controller stalled without advancing the game')
                if not session.reason:
                    session.finish('assessment_decision_limit')
                if session.reason not in ('completed', 'battle_loss'):
                    raise ValueError('Assessment controller ended without a battle outcome: ' + session.reason)
                completed = session.reason == 'completed'
                after_battle = engine.save()
                session.close()
                session = None
                result = json.loads((destination / 'battle' / 'result.json').read_text())
                engine = RedEngine(Path(rom), after_battle)
                if completed and stage + 1 < len(schedule):
                    maintenance_manifest = {**manifest, 'state_sha256': digest(after_battle),
                                            'objective': objective}
                    initialize_controls(engine, maintenance_manifest)
                    session = Session(engine, destination / 'maintenance', maintenance_manifest,
                                      track='gameplay', goal='challenge', gameplay_catalog=catalog,
                                      limits=Limits(max_actions=30000, max_frames=300000,
                                                    max_action_frames=600, max_dialogue_frames=7200),
                                      agent={'provider': 'offline-preparation-assessment', 'model': POLICY_VERSION})
                    # Finish the defeated trainer's dialogue before using owned items.
                    # The next opponent checkpoint may already have a battle script queued.
                    for settling in range(40):
                        if ui_state(engine.memory)['kind'] == 'overworld' and not engine.memory[W_IS_IN_BATTLE]:
                            break
                        execute(session, f'settle-{settling}',
                                {'command': 'advance_dialogue', 'argument': '', 'count': 1})
                    else:
                        raise ValueError('Between-battle dialogue did not settle')
                    for maintenance in range(40):
                        action = between_battle_item(observe_gameplay(session))
                        if action is None:
                            break
                        outcome = execute(session, f'maintenance-{maintenance}', action)
                        if outcome.get('shortcut', {}).get('completed') is not True:
                            raise ValueError('Between-battle item controller failed')
                    else:
                        raise ValueError('Between-battle maintenance exceeded its item limit')
                    session.finish('maintenance_complete')
                transfer = {str(start): list(engine.memory[start:end]) for start, end in TRANSFER_RANGES}
                if session:
                    session.close()
                    session = None
                else:
                    engine.close()
                stages.append({'target': target['id'], 'completed': result['completed'],
                               'stop_reason': result['stop_reason']})
                if not result['completed']:
                    break
            except (ValueError, RuntimeError, OSError) as exc:
                error = str(exc)
                if session:
                    session.finish('assessment_error')
            finally:
                if session:
                    session.close()
                elif engine is not None and (not stages or error):
                    engine.close()
            if error:
                break
        rows.append({'trial_id': variant, 'offset': offset,
                     'completed': len(stages) == len(schedule) and all(s['completed'] for s in stages),
                     'evaluation_error': error, 'stages': stages})
        write_json(output / 'trials.json', rows)
    result = {**score_trials(rows, len(trials), threshold), 'rows': rows,
              'protocol': PROTOCOL, 'policy_sha256': policy_hash, 'policy_version': POLICY_VERSION,
              'submission_sha256': record['state_sha256'], 'model_calls': 0}
    write_json(output / 'assessment.json', result)
    return result


def run_preparation(rom, scenario, output, game_data, task_id, *, actions=None,
                    provider=None, token_limit=180000, targets=None, threshold=None,
                    offsets=OFFSETS, max_decisions=500, target_variants=None):
    """Execute one preparation submission and its separate optional assessment.

    Supply either explicit actions for offline references or a dedicated fresh
    BoundedGameplayProvider / ClaudeCodeProvider for an evaluated model.
    """
    from .evaluation_catalog import load_catalog as load_evaluation_catalog
    if (actions is None) == (provider is None):
        raise ValueError('Supply exactly one of actions or provider')
    task = next(item for category in load_evaluation_catalog('preparation')
                for item in category['evals'] if item['id'] == task_id)
    engine, manifest = load_engine(Path(rom), Path(scenario))
    manifest = {**manifest, 'objective': {'kind': 'preparation-submission',
                'task_id': task_id, 'description': task['agent_goal']}}
    output = Path(output)
    session = Session(engine, output / 'preparation', manifest, track='gameplay', goal='challenge',
                      gameplay_catalog=load_catalog(Path(game_data)),
                      limits=Limits(max_actions=30000, max_frames=200000, max_total_tokens=token_limit, max_model_calls=1,
                                    max_action_frames=600, max_dialogue_frames=7200),
                      agent={'provider': provider.provider if provider else 'offline-preparation-reference',
                             'model': provider.model if provider else 'supplied-actions'})
    preparation = PreparationSession(session, task_id)
    model_record = None
    usage = {'input_tokens': 0, 'output_tokens': 0, 'calls': 0, 'accounting_complete': provider is None}

    def record_usage(value):
        nonlocal usage
        usage = dict(value)
        write_json(output / 'model-usage.json', usage)
        session.usage.update(**usage)

    try:
        record_usage(usage)
        if provider:
            model_record = request_submission(provider, task, public_preparation_state(session, task_id),
                                              token_limit, record_usage=record_usage)
            write_json(output / 'model-submission.json', model_record)
            session.usage.update(calls=1, input_tokens=model_record['usage']['input_tokens'],
                                 output_tokens=model_record['usage']['output_tokens'])
            if model_record['budget_exceeded'] or model_record['invalid_response']:
                reason = 'token_budget' if model_record['budget_exceeded'] else 'invalid_submission'
                session.finish(reason)
                result = {'protocol': PROTOCOL, 'benchmark_track': 'pokebench', 'task_id': task_id, 'submitted': False, 'reason': reason,
                          'usage': model_record['usage']}
                write_json(output / 'preparation-result.json', result)
                return result
            actions = model_record['actions']
        for action in actions:
            outcome = preparation.act(action)
            if not outcome['result'].get('shortcut', {}).get('completed'):
                session.finish('preparation_action_failed')
                result = {'protocol': PROTOCOL, 'benchmark_track': 'pokebench', 'task_id': task_id, 'submitted': False,
                          'reason': 'preparation_action_failed', 'failed_action': outcome,
                          'usage': usage}
                write_json(output / 'preparation-result.json', result)
                return result
        frozen = preparation.submit(output / 'submission')
        session.finish('submitted')
    except InvalidPreparationAction as exc:
        session.finish('invalid_submission')
        result = {'protocol': PROTOCOL, 'benchmark_track': 'pokebench', 'task_id': task_id, 'submitted': False,
                  'reason': 'invalid_submission', 'error': str(exc), 'usage': usage}
        write_json(output / 'preparation-result.json', result)
        return result
    except (ValueError, RuntimeError, OSError) as exc:
        session.finish('preparation_error')
        write_json(output / 'preparation-result.json', {
            'protocol': PROTOCOL, 'task_id': task_id, 'submitted': False,
            'reason': 'preparation_error', 'error': str(exc), 'evaluation_error': str(exc),
            'usage': usage})
        raise
    finally:
        session.close()
    assessment = assess_submission(rom, output / 'submission', targets, output / 'assessment',
                                   game_data, offsets=offsets, threshold=threshold,
                                   max_decisions=max_decisions, target_variants=target_variants) if targets else None
    result = {'protocol': PROTOCOL, 'benchmark_track': 'pokebench', 'submitted': True, 'task_id': task_id,
              'submission_sha256': frozen['state_sha256'], 'assessment': assessment,
              'usage': usage}
    write_json(output / 'preparation-result.json', result)
    return result
