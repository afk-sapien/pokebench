"""Scripted references for the candidate tasks. No model calls.

The candidates reuse the milestone reference driver, so a reference issues only the assisted
commands a model gets and counts one decision per command. Battles add one rule to the greedy
battler. When the opponent's strongest move could knock out the active Pokemon, it heals with
Recover if it moves first, or else switches to the party member that best takes the hit. Any faint
fails these tasks, so a finished reference proves the start can be won with no faint.

Each reference writes its pins next to its proof: the start state digest, the digest and count
of the native inputs, the replayed frames and the decisions.
"""
import argparse
import json
from pathlib import Path

import reference_milestone_tasks as base
from reference_milestone_tasks import (
    AGATHAS_ROOM, BATTLE_MON, BRUNOS_ROOM, CHAMPIONS_ROOM, ENEMY_MON, LANCES_ROOM, SPECIAL_TYPES,
    Tactics, arrive, face, locate, wait,
)
from pokeagent_bench.catalog_execution import select_scenario
from pokeagent_bench.core import digest, encoded, write_json
from pokeagent_bench.gameplay import ui_state
from pokecore.gen1 import W_PARTY_COUNT, W_PARTY_MONS

ACTIVE_SLOT = 0xCC2F
IN_BATTLE = 0xD057
# wPlayerBattleStatus1 bit 7: confused. wBattleMonStatus bits 3 and 4: poisoned and burned.
PLAYER_STATUS1, CONFUSED = 0xD062, 0x80
POISON_OR_BURN = 0x18
# Status bits 0 to 2 count sleep turns and bit 5 is frozen. Neither can act.
HELPLESS = 0x27
# Damage of the fixed-damage moves: Sonic Boom, Dragon Rage, Seismic Toss, Night Shade and Psywave at most.
FIXED = {49: lambda level: 20, 82: lambda level: 40, 69: lambda level: level, 101: lambda level: level,
         149: lambda level: level * 3 // 2}
HITS = {'ATTACK_TWICE_EFFECT': 2, 'TWINEEDLE_EFFECT': 2, 'TWO_TO_FIVE_ATTACKS_EFFECT': 5}


def fighter(memory, address, level):
    word = lambda offset: memory[address + offset] << 8 | memory[address + offset + 1]
    return {'hp': word(1), 'status': memory[address + 4], 'types': (memory[address + 5], memory[address + 6]),
            'moves': tuple(memory[address + 8:address + 12]), 'level': level}


def in_battle(memory, address):
    """The active Pokemon on either side, with its stat changes."""
    word = lambda offset: memory[address + offset] << 8 | memory[address + offset + 1]
    mon = fighter(memory, address, memory[address + 14])
    mon.update(max_hp=word(15), attack=word(17), defense=word(19), speed=word(21), special=word(23),
               pp=tuple(v & 63 for v in memory[address + 25:address + 29]))
    return mon


def benched(memory, slot):
    """A party member out of battle, from its party record."""
    address = W_PARTY_MONS + 44 * slot
    word = lambda offset: memory[address + offset] << 8 | memory[address + offset + 1]
    mon = fighter(memory, address, memory[address + 33])
    mon.update(max_hp=word(34), attack=word(36), defense=word(38), speed=word(40), special=word(42),
               pp=tuple(v & 63 for v in memory[address + 29:address + 33]))
    return mon


class Careful(Tactics):
    """The greedy battler, plus a heal or a switch when the opponent could knock out the active Pokemon."""

    def __init__(self, game_data):
        super().__init__(game_data)
        self.heals = 0
        self.switches = 0
        # One row per battle menu decision, and the party HP when each battle ends.
        self.trace = []

    def hit(self, move_id, attacker, defender, roll=255):
        """Gen 1 damage of one use, at the given random roll, with no critical hit."""
        move = self.moves[move_id]
        effect = move['effect']
        if effect == 'SPECIAL_DAMAGE_EFFECT':
            return FIXED[move_id](attacker['level'])
        if effect == 'SUPER_FANG_EFFECT':
            return defender['hp'] // 2
        if effect == 'OHKO_EFFECT':
            # A one-hit knockout move fails against a faster target.
            return 999 if attacker['speed'] >= defender['speed'] else 0
        if not move['power']:
            return 0
        attack, defense = (('special', 'special') if move['type'] in SPECIAL_TYPES else ('attack', 'defense'))
        a, d = attacker[attack], defender[defense]
        if effect == 'EXPLODE_EFFECT':
            d = d // 2
        if a > 255 or d > 255:
            a, d = a // 4, d // 4
        damage = min((2 * attacker['level'] // 5 + 2) * move['power'] * a // max(1, d) // 50, 997) + 2
        if move['type'] in attacker['types']:
            damage += damage // 2
        for kind in dict.fromkeys(defender['types']):
            damage = int(damage * self.chart.get((move['type'], kind), 1))
        return damage * roll // 255 * HITS.get(effect, 1)

    def threat(self, enemy, mon):
        """The most one enemy move can deal. Mirror Move copies the player's strongest move."""
        moves = [move for move in enemy['moves'] if move]
        if any(self.moves[move]['effect'] == 'MIRROR_MOVE_EFFECT' for move in moves):
            moves += [move for move in mon['moves'] if move]
        return max((self.hit(move, enemy, mon) for move in moves), default=0)

    def danger(self, memory, mon, enemy, active=True):
        """The hit the opponent may deal this turn, plus poison or burn damage and a confused self-hit."""
        total = self.threat(enemy, mon)
        if mon['status'] & POISON_OR_BURN:
            total += max(1, mon['max_hp'] // 16)
        if active and memory[PLAYER_STATUS1] & CONFUSED:
            total += self.hit(1, mon, mon)
        return total

    def usable(self, mon):
        return [(slot, move) for slot, move in enumerate(mon['moves']) if move and mon['pp'][slot]]

    def replacement(self, memory, enemy, active):
        """The party member that best comes in against enemy: it survives two hits if any can, then hits hardest."""
        options = []
        for slot in range(memory[W_PARTY_COUNT]):
            mon = benched(memory, slot)
            if slot == active or not mon['hp']:
                continue
            danger = self.danger(memory, mon, enemy, active=False)
            if mon['hp'] <= danger:
                continue
            damage = max((self.hit(move, mon, enemy, 217) * self.moves[move]['accuracy'] // 100
                          for _, move in self.usable(mon)), default=0)
            options.append((not mon['status'] & HELPLESS, mon['hp'] > 2 * danger, damage, mon['hp'] - danger, slot))
        return max(options)[-1] if options else None

    def decide(self, memory):
        """Return ('move', slot) or ('switch', party slot), both zero-based, and trace the turn."""
        mine, theirs = in_battle(memory, BATTLE_MON), in_battle(memory, ENEMY_MON)
        choice = self.choose(memory)
        self.trace.append({'mine': memory[BATTLE_MON], 'hp': mine['hp'], 'enemy': memory[ENEMY_MON],
                           'enemy_hp': theirs['hp'], 'danger': self.danger(memory, mine, theirs),
                           'choice': list(choice)})
        return choice

    def cost(self, memory, mon, enemy, entering, active):
        """The HP mon may lose knocking out enemy at average rolls, taking the strongest hit every turn.

        A faster Pokemon takes no hit on the turn it lands the knockout. One switched in mid-turn takes one more."""
        danger = self.danger(memory, mon, enemy, active=active)
        out = max((self.hit(move, mon, enemy, 236) * self.moves[move]['accuracy'] // 100
                   for _, move in self.usable(mon)), default=0)
        if not out or mon['status'] & HELPLESS:
            return None
        turns = -(-enemy['hp'] // out)
        hits = turns - (mon['speed'] > enemy['speed']) + entering
        return danger * hits

    def matchup(self, memory, mine, theirs, active, free=False):
        """A benched Pokemon that knocks out the opponent for less than half the HP the active one would lose.

        free is the switch offered after a knockout, before the next opponent moves."""
        mine_cost = self.cost(memory, mine, theirs, False, True)
        options = []
        for slot in range(memory[W_PARTY_COUNT]):
            mon = benched(memory, slot)
            if slot == active or not mon['hp']:
                continue
            spent = self.cost(memory, mon, theirs, not free, False)
            if spent is not None and spent < mon['hp']:
                options.append((spent, slot))
        if not options:
            return None
        spent, slot = min(options)
        if mine_cost is None or mine_cost >= mine['hp'] or 2 * spent < mine_cost:
            return slot
        return None

    def choose(self, memory):
        mine, theirs = in_battle(memory, BATTLE_MON), in_battle(memory, ENEMY_MON)
        active = memory[ACTIVE_SLOT]
        danger = self.danger(memory, mine, theirs)
        faster = mine['speed'] > theirs['speed']
        heals = [slot for slot, move in self.usable(mine) if self.moves[move]['effect'] == self.HEAL]
        greedy = self.choose_move(memory)
        if mine['status'] & HELPLESS:
            # Asleep or frozen, it cannot act. Bring in one that wins the matchup, or one that survives.
            slot = self.matchup(memory, mine, theirs, active)
            if slot is None and mine['hp'] <= danger:
                slot = self.replacement(memory, theirs, active)
            if slot is not None:
                self.switches += 1
                return 'switch', slot
            return 'move', greedy
        if heals and greedy in heals:
            # The plain battler heals below a third of its HP. Only heal when it lands before the next hit.
            if faster or mine['hp'] > danger:
                self.heals += 1
                return 'move', greedy
            greedy = self.best(mine, theirs)[1] or 0
        if heals and faster and 2 * mine['hp'] <= mine['max_hp'] and 4 * danger < mine['max_hp']:
            # Recover outpaces a weak opponent, so HP lost earlier comes back before the next battle.
            self.heals += 1
            return 'move', heals[0]
        if mine['hp'] > danger:
            slot = self.matchup(memory, mine, theirs, active)
            if slot is not None:
                self.switches += 1
                return 'switch', slot
            return 'move', greedy
        sure = [slot for slot, move in self.usable(mine) if self.moves[move]['accuracy'] == 100
                and self.hit(move, mine, theirs, 217) >= theirs['hp']]
        if faster and sure:
            return 'move', sure[0]
        healed = min(mine['max_hp'], mine['hp'] + mine['max_hp'] // 2)
        if heals and faster and healed - mine['hp'] > danger:
            # Recover lands first and gains more than the next hit can take.
            self.heals += 1
            return 'move', heals[0]
        slot = self.replacement(memory, theirs, active)
        if slot is not None:
            self.switches += 1
            return 'switch', slot
        if heals and faster and healed > danger:
            # No one can come in safely. Recover still keeps it standing this turn.
            self.heals += 1
            return 'move', heals[0]
        return 'move', greedy

    def shift(self, memory):
        """At the free switch after a knockout, change Pokemon for a better matchup or when the active one is in danger."""
        mine, theirs = in_battle(memory, BATTLE_MON), in_battle(memory, ENEMY_MON)
        slot = self.matchup(memory, mine, theirs, memory[ACTIVE_SLOT], free=True)
        if slot is not None or mine['hp'] > self.danger(memory, mine, theirs):
            return slot
        return self.replacement(memory, theirs, memory[ACTIVE_SLOT])


def careful_battle(driver, tactics, limit=600):
    """One trainer battle to its end, as the League battle loop, with the careful choices."""
    d, memory = driver, driver.engine.memory
    for _ in range(40):
        if memory[IN_BATTLE] or d.done:
            break
        wait(d, 60)
    else:
        raise RuntimeError('The battle did not start')
    chosen = None
    for _ in range(limit):
        if d.done:
            return
        ui = ui_state(memory)
        if not memory[IN_BATTLE] and ui['kind'] == 'overworld':
            tactics.trace.append({'battle_end': [benched(memory, slot)['hp'] for slot in range(memory[W_PARTY_COUNT])]})
            return
        options = ui['visible_choices'] if ui['kind'] == 'menu' else []
        if ui['kind'] in ('battle_menu', 'move_menu'):
            kind, slot = tactics.decide(memory)
            d.do('use_move' if kind == 'move' else 'switch_pokemon', str(slot + 1))
        elif memory[IN_BATTLE] and any(text.partition(': ')[0].isdigit() for text in options):
            if chosen is None:
                raise RuntimeError('The party menu opened with no switch chosen')
            d.do('switch_pokemon', str(chosen + 1))
            chosen = None
        elif {'YES', 'NO'} <= {text.upper() for text in options}:
            text = ' '.join(ui['text']).upper()
            if 'CHANGE' in text:
                chosen = tactics.shift(memory)
                if chosen is not None:
                    tactics.switches += 1
                d.do('choose', 'NO' if chosen is None else 'YES')
            else:
                # Keep the old moves when a Pokemon learns a new one.
                d.do('choose', 'YES' if 'ABANDON' in text else 'NO')
        else:
            d.do('advance_dialogue')
    raise RuntimeError('The battle did not end')


def hall_of_fame(driver):
    """Oak leads the player to the Hall of Fame, which records the party."""
    for _ in range(80):
        if driver.done:
            return
        wait(driver, 120)
    raise RuntimeError(f'The Hall of Fame did not record the party. At {locate(driver.engine)}')


def league(driver):
    d = driver
    tactics = d.tactics = Careful(d.game_data)
    for following in (BRUNOS_ROOM, AGATHAS_ROOM, LANCES_ROOM):
        d.walk(5, 3)
        face(d, 'up')
        d.do('interact')
        careful_battle(d, tactics)
        if d.done:
            return
        d.enter(following)
        arrive(d)
    d.walk(6, 3)
    d.do('move', 'up', 1)
    careful_battle(d, tactics)
    if d.done:
        return
    d.enter(CHAMPIONS_ROOM)
    careful_battle(d, tactics)
    hall_of_fame(d)


def champion(driver):
    d = driver
    tactics = d.tactics = Careful(d.game_data)
    careful_battle(d, tactics)
    hall_of_fame(d)


VERMILION_GYM = 92
# The trash cans in the game's index order, five columns of three from (1, 7) to (9, 11).
TRASH_CANS = tuple((1 + 2 * (index // 3), 7 + 2 * (index % 3)) for index in range(15))
LT_SURGE = (5, 1)


def can_neighbors(index):
    """The cans beside a can in the grid. The game hides the second switch under one of them."""
    column, row = divmod(index, 3)
    return [c * 3 + r for c, r in ((column - 1, row), (column + 1, row), (column, row - 1), (column, row + 1))
            if 0 <= c < 5 and 0 <= r < 3]


def closest_can(driver, cans):
    _, x, y = locate(driver.engine)
    return min(cans, key=lambda index: (abs(TRASH_CANS[index][0] - x) + abs(TRASH_CANS[index][1] - y), index))


def pages(result):
    return (result or {}).get('dialogue', {}).get('pages', [])


def read_text(driver, result=None, limit=12):
    """Clear the open text and return every page shown on the way, as the model reads it.

    The executor pages through plain text itself and reports the pages with the command that
    opened it, so the text a command opened comes from its result.
    """
    lines = list(pages(result))
    for _ in range(limit):
        ui = ui_state(driver.engine.memory)
        if driver.done or ui['kind'] == 'overworld':
            return ' '.join(lines).upper()
        lines.extend(ui['text'])
        lines.extend(pages(driver.do('advance_dialogue')))
    raise RuntimeError(f'The text did not close. At {locate(driver.engine)}')


def check_can(driver, index):
    """Stand beside a can, face it, look inside and return the text the game prints."""
    x, y = TRASH_CANS[index]
    sides = {(x, y + 1): 'up', (x, y - 1): 'down', (x - 1, y): 'right', (x + 1, y): 'left'}
    driver.follow(lambda here: here[0] == VERMILION_GYM and here[1:] in sides)
    face(driver, sides[locate(driver.engine)[1:]])
    return read_text(driver, driver.do('interact'))


def vermilion_gym(driver):
    """Search the cans by their text only, never by the lock bytes in RAM.

    Look in the closest can not yet ruled out. When the first lock opens, try the closest can
    beside it. A wrong second can resets both locks and moves the first switch, so the search
    starts again from every can.
    """
    d = driver
    unchecked, first = set(range(15)), None
    for _ in range(150):
        index = closest_can(d, can_neighbors(first) if first is not None else unchecked)
        text = check_can(d, index)
        d.notes.setdefault('cans', []).append(index)
        if d.done:
            return
        if 'MOTORIZED' in text or '2ND ELECTRIC' in text:
            break
        if '1ST ELECTRIC' in text:
            first = index
        elif 'RESET' in text:
            first, unchecked = None, set(range(15))
            d.notes['resets'] = d.notes.get('resets', 0) + 1
        else:
            unchecked.discard(index)
            if not unchecked:
                raise RuntimeError('No can opened the first lock')
    else:
        raise RuntimeError('The locks did not open')
    d.follow(lambda here: here[0] == VERMILION_GYM and abs(here[1] - LT_SURGE[0]) + abs(here[2] - LT_SURGE[1]) <= 1)


SAFARI_EAST, SAFARI_NORTH, SAFARI_WEST, SAFARI_SECRET_HOUSE = 217, 218, 219, 222
# Only the two exits at the west end of the north area's south edge reach the house's part of the
# west area. A map change is judged on the tile stepped onto, one below the exit.
NORTH_TO_HOUSE_SIDE = {(2, 36), (3, 36)}
FISHING_GURU_FRONT = (3, 4)
SAFARI_STEPS = 0xD70D


def safari_secret_house(driver):
    d = driver
    d.enter(SAFARI_EAST)
    d.enter(SAFARI_NORTH)
    d.follow(lambda here: here[0] == SAFARI_WEST and here[1:] in NORTH_TO_HOUSE_SIDE)
    d.settle()
    if locate(d.engine)[0] != SAFARI_WEST:
        raise RuntimeError(f'Expected the west area, reached {locate(d.engine)}')
    d.enter(SAFARI_SECRET_HOUSE)
    arrive(d)
    d.walk(*FISHING_GURU_FRONT)
    # For the summary only. The route above never reads the step counter.
    memory = d.engine.memory
    d.notes['safari_steps_left_at_guru'] = memory[SAFARI_STEPS] << 8 | memory[SAFARI_STEPS + 1]
    face(d, 'up')
    read_text(d, d.do('interact'), limit=20)


ROUTE_7, CELADON_CITY, SAFFRON_CITY, ROUTE_7_GATE = 18, 6, 10, 76
CELADON_MART = (122, 123, 124, 125, 136)
CELADON_MART_ROOF = 126
# The tiles in front of the three roof vending machines. All three sell the same drinks.
VENDING_MACHINES = {(10, 2): 'up', (11, 2): 'up', (12, 3): 'up'}
DRINK = 'FRESH WATER'
# The guard's script runs when the player steps on the tile in front of him.
GATE_GUARD_FRONT = (3, 4)
# The east door is the gate's right edge at x 5. A map change is judged one tile past it.
GATE_EAST_DOOR = {(6, 3), (6, 4)}


def buy_drink(driver):
    d = driver
    d.follow(lambda here: here[0] == CELADON_MART_ROOF and here[1:] in VENDING_MACHINES)
    face(d, VENDING_MACHINES[locate(d.engine)[1:]])
    d.do('interact')
    for _ in range(12):
        ui = ui_state(d.engine.memory)
        if d.done or ui['kind'] == 'overworld':
            return
        choices = [text.upper() for text in ui['visible_choices']] if ui['kind'] == 'menu' else []
        if any(choice.startswith(DRINK) for choice in choices):
            d.do('choose', DRINK)
        else:
            d.do('advance_dialogue')
    raise RuntimeError('The vending machine text did not close')


def meet_guard(driver):
    """Walk right along the row to the guard. Without a drink he stops the player and steps them back."""
    _, x, _ = locate(driver.engine)
    text = read_text(driver, driver.do('move', 'right', GATE_GUARD_FRONT[0] - x))
    arrive(driver)
    return text


def saffron_gate_drink(driver):
    """Hear the guard out, climb the store by its stairs, buy the cheapest drink and bring it back."""
    d = driver
    tactics = Tactics(d.game_data)
    d.calm_planner()
    d.on_battle = lambda drv: base.wild_battle(drv, tactics)
    d.notes['guard_without_drink'] = meet_guard(d)
    for map_id in (ROUTE_7, CELADON_CITY, *CELADON_MART, CELADON_MART_ROOF):
        d.enter(map_id)
    buy_drink(d)
    for map_id in (*CELADON_MART[::-1], CELADON_CITY, ROUTE_7, ROUTE_7_GATE):
        d.enter(map_id)
    d.notes['guard_with_drink'] = meet_guard(d)
    # The gate splits Route 7. Its east door leads to the part of the route that meets Saffron.
    d.follow(lambda here: here[0] == ROUTE_7 and here[1:] in GATE_EAST_DOOR)
    d.settle()
    d.enter(SAFFRON_CITY)


SOLUTIONS = {'battle-elite-four-no-items-no-faint': league, 'battle-champion-no-items-no-faint': champion,
             'navigation-vermilion-gym-switches': vermilion_gym,
             'navigation-safari-zone-secret-house': safari_secret_house,
             'objectives-saffron-gate-drink': saffron_gate_drink}


class Recorded(base.Driver):
    """The reference driver, kept reachable after the run so its counts can be reported."""

    last = None

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.tactics = None
        self.notes = {}
        Recorded.last = self


def build(task_id, rom, game_data, fixtures, output):
    base.SOLUTIONS.update(SOLUTIONS)
    base.Driver = Recorded
    work = Path(output)
    try:
        summary = base.build(task_id, rom, game_data, fixtures, output)
    except SystemExit:
        tactics = Recorded.last.tactics
        if tactics is not None:
            write_json(work / 'reference-battle-trace.json', tactics.trace)
            print(json.dumps({'task': task_id, 'heals': tactics.heals, 'switches': tactics.switches}))
        print(json.dumps({'task': task_id, 'notes': Recorded.last.notes}))
        raise
    actions = json.loads((work / 'reference-actions.json').read_text())
    manifest = json.loads((select_scenario(fixtures, task_id) / 'scenario.json').read_text())
    proof = json.loads((select_scenario(fixtures, task_id) / 'reference-validation.json').read_text())
    pins = {'state_sha256': manifest['state_sha256'], 'actions_sha256': digest(encoded(actions)),
            'actions': len(actions), 'frames': proof['replay']['frames'], 'decisions': summary['decisions']}
    tactics = Recorded.last.tactics
    if tactics is not None:
        summary.update(heals=tactics.heals, switches=tactics.switches)
        write_json(work / 'reference-battle-trace.json', tactics.trace)
    summary.update(Recorded.last.notes)
    summary['pins'] = pins
    write_json(work / 'reference-summary.json', summary)
    print(json.dumps({'task': task_id, 'pins': pins, **{k: summary.get(k) for k in ('heals', 'switches', 'score')}}))
    return summary


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--rom', required=True)
    parser.add_argument('--game-data', type=Path, required=True)
    parser.add_argument('--fixtures', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--tasks', nargs='+', required=True)
    args = parser.parse_args()
    for task_id in args.tasks:
        build(task_id, args.rom, args.game_data, args.fixtures, args.output / task_id)


if __name__ == '__main__':
    main()
