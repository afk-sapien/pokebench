"""Scripted references for the milestone tasks. No model calls.

A reference issues only the assisted commands a model gets, through the same
command executor, and counts one decision per command. A second emulator, synced
from the live state before each plan, finds walking paths offline. The native
inputs the commands produced are then replayed through the catalog runner, which
writes the reference proof next to the fixture.
"""
import argparse
from collections import deque
import json
from pathlib import Path
import shutil

from pokeagent_bench import navigation_conditions
from pokeagent_bench.catalog_execution import run_task, select_scenario
from pokeagent_bench.catalog_fixtures import command as native
from pokeagent_bench.core import Limits, write_json
from pokeagent_bench.evaluation_catalog import task_definition
from pokeagent_bench.gameplay import load_catalog, menu_options, read_screen, ui_state
from pokeagent_bench.gameplay_commands import execute
from pokeagent_bench.session import Session, load_engine
from pokecore.gen1 import read_bag, read_party
from pokecore.gen1_ui import read_sprites

STEPS = {'up': (0, -1), 'down': (0, 1), 'left': (-1, 0), 'right': (1, 0)}
# wStatusFlags7 bit BIT_TRAINER_BATTLE: set when a trainer spots the player, cleared after the battle.
TRAINER_FLAGS, TRAINER_ENGAGED = 0xD733, 0x08
# wStatusFlags5 bit 7: the game is feeding the player simulated joypad input, as on a spinner.
SIMULATED_JOYPAD = 0xD730


def locate(engine):
    memory = engine.memory
    return memory[0xD35E], memory[0xD362], memory[0xD361]


def sprite(engine, slot):
    found = read_sprites(engine.memory)[slot]
    return found['x'], found['y']


def step(engine, direction):
    """One tile of the move command, as the command executor sends it."""
    memory = engine.memory
    here, facing = locate(engine), memory[0xC109]
    native(engine, direction, 8, 16)
    if memory[0xC200]:
        native(engine, None, 16, 0)
    if locate(engine) == here and memory[0xC109] != facing and ui_state(memory)['kind'] == 'overworld':
        native(engine, direction, 8, 16)
        if memory[0xC200]:
            native(engine, None, 16, 0)


class Driver:
    def __init__(self, rom, game_data, scenario, output):
        self.rom, self.scenario, self.game_data = Path(rom), Path(scenario), Path(game_data)
        self.engine, manifest = load_engine(self.rom, self.scenario)
        self.planner, _ = load_engine(self.rom, self.scenario)
        task = task_definition(manifest['task_id'])
        self.session = Session(self.engine, Path(output), manifest, track='gameplay', goal='challenge',
                               gameplay_catalog=load_catalog(Path(game_data)),
                               limits=Limits(max_total_tokens=task['token_limit']),
                               agent={'provider': 'reference', 'model': 'scripted-assisted-commands'})
        self.raw = []
        self.log = []
        # Tiles the planner never steps onto, such as holes that drop the player a floor.
        self.avoid = set()
        # Called when a move command ends in a battle, so walking resumes after it.
        self.on_battle = None
        # Walk into the nearest trainer's line of sight when no path avoids every trainer.
        self.fight = False
        # Let spinners finish on the planner, as the command executor waits for them after a move.
        self.spinners = False

    def calm_planner(self):
        """Turn off wild encounters on the planner only, so paths never depend on dodging them.

        The live game keeps its encounters. Without this the search would drop tiles where the
        copied random state starts a battle, and the reference would walk around encounters.
        """
        for index, value in enumerate(navigation_conditions.NO_ENCOUNTER):
            self.planner.memory[navigation_conditions.BANK, navigation_conditions.ADDRESS + index] = value

    @property
    def done(self):
        return bool(self.session.reason)

    def do(self, kind, argument='', count=1):
        if self.done:
            raise RuntimeError(f'Run already stopped: {self.session.reason}')
        operation = str(len(self.log) + 1)
        result = execute(self.session, operation, {'command': kind, 'argument': argument, 'count': count},
                         on_action=lambda raw, before, observed: self.raw.append(dict(raw)))
        self.log.append({'command': kind, 'argument': argument, 'count': count,
                         'outcome': result['outcome'], 'position_after': result['position_after']})
        return result

    def field_move(self, mon, move):
        self.do('press', 'start')
        for option in ('POKéMON', mon, move):
            result = self.do('choose', option)
            if 'No confirmation' in result['outcome'] or 'No active menu' in result['outcome']:
                raise RuntimeError(f'Menu option {option} not available: {result["outcome"]}')

    def sync(self):
        self.planner.load(self.engine.save())
        return self.planner

    def search(self, goal, limit=20000):
        """Shortest single-tile path, on the planner, to a tile or warp that meets goal.

        The position reads stale on the frame the map changes, so a step that changes the
        map is judged as (new map, warp tile stepped onto).
        """
        engine = self.sync()
        start = locate(engine)
        queue = deque([(engine.save(), start, [])])
        seen = {start}
        engaged = None
        for _ in range(limit):
            if not queue:
                break
            state, origin, path = queue.popleft()
            for direction in STEPS:
                dx, dy = STEPS[direction]
                if (origin[0], origin[1] + dx, origin[2] + dy) in self.avoid:
                    continue
                engine.load(state)
                step(engine, direction)
                for _ in range(40 if self.spinners else 0):
                    if not engine.memory[SIMULATED_JOYPAD] & 0x80:
                        break
                    native(engine, None, 30, 0)
                here = locate(engine)
                if here[0] != start[0]:
                    if goal((here[0], origin[1] + dx, origin[2] + dy)):
                        return path + [direction]
                    continue
                if goal(here):
                    return path + [direction]
                if self.fight and engine.memory[TRAINER_FLAGS] & TRAINER_ENGAGED:
                    engaged = engaged or path + [direction]
                    continue
                if here in seen or ui_state(engine.memory)['kind'] != 'overworld' or engine.memory[0xD057]:
                    continue
                seen.add(here)
                queue.append((engine.save(), here, path + [direction]))
        if engaged:
            return engaged
        raise RuntimeError(f'No path from {start}. Searched {len(seen)} tiles')

    def follow(self, goal, attempts=40):
        """Walk with move commands of at most 8 tiles, replanning whenever a run ends early.

        Stops at the first map change. The caller checks that it was the intended one.
        """
        moves = 0
        while moves < attempts:
            before = locate(self.engine)
            if goal(before):
                return
            path = self.search(goal)
            direction = path[0]
            count = 1
            while count < min(8, len(path)) and path[count] == direction:
                count += 1
            result = self.do('move', direction, count)
            engaged = self.fight and self.engine.memory[TRAINER_FLAGS] & TRAINER_ENGAGED
            if self.on_battle and not self.done and (self.engine.memory[0xD057] or engaged):
                self.on_battle(self)
                if self.done:
                    return
                # A wild battle stops the walk. Its moves are not counted against the walk.
                continue
            moves += 1
            after = locate(self.engine)
            if self.done or after[0] != before[0] or goal(after):
                return
            if after == before:
                raise RuntimeError(f'Move made no progress: {result["outcome"]}')
        raise RuntimeError('Walking did not reach the goal')

    def walk(self, x, y):
        map_id = locate(self.engine)[0]
        self.follow(lambda here: here == (map_id, x, y))

    def enter(self, map_id, via=None):
        """Walk to a map change, optionally through the warp tile via on the current map."""
        self.follow(lambda here: here[0] == map_id and (via is None or here[1:] == tuple(via)))
        self.settle()
        if not self.done and locate(self.engine)[0] != map_id:
            raise RuntimeError(f'Expected map {map_id}, reached {locate(self.engine)}')

    def settle(self):
        # A warp finishes loading while the next command waits. Record nothing until the map is ready.
        if self.done:
            return
        if ui_state(self.engine.memory)['kind'] != 'overworld':
            self.do('advance_dialogue')
            return
        # Leaving through a door changes the map id about 50 frames before the position, while the
        # screen still reads as overworld. The observation tells the model to wait, so the reference does.
        planner = self.sync()
        before = locate(planner)
        native(planner, None, 60, 0)
        if locate(planner) != before:
            self.do('wait', '', 60)

    def push(self, slot, direction, tries=3):
        before = sprite(self.engine, slot)
        for _ in range(tries):
            self.do('move', direction, 1)
            if sprite(self.engine, slot) != before:
                return sprite(self.engine, slot)
        raise RuntimeError(f'Boulder {slot} at {before} did not move {direction}')

    def boulder(self, start, pushes):
        """Push the boulder at start through (direction, times) legs, walking to each stand tile first."""
        found = [s for s in read_sprites(self.engine.memory)[1:] if s['picture'] and (s['x'], s['y']) == tuple(start)]
        if len(found) != 1:
            raise RuntimeError(f'No single sprite at {start}')
        slot = found[0]['slot']
        for direction, times in pushes:
            for _ in range(times):
                x, y = sprite(self.engine, slot)
                dx, dy = STEPS[direction]
                self.walk(x - dx, y - dy)
                self.push(slot, direction)

    def close(self):
        if not self.done:
            self.session.finish('reference_exhausted')
        self.session.close()
        self.planner.close()


def victory_road(driver):
    d = driver
    d.field_move('NIDOKING', 'STRENGTH')
    # 1F: boulder 5 onto the switch at (17, 13), which opens the wall to the ladder.
    d.boulder((5, 15), [('down', 1), ('right', 4), ('up', 2), ('right', 7), ('up', 2), ('right', 1), ('down', 1)])
    d.enter(194)
    # 2F: Strength ends at every map change. The first boulder goes onto the switch at (1, 16).
    d.field_move('NIDOKING', 'STRENGTH')
    d.boulder((4, 14), [('left', 1), ('down', 2), ('left', 2)])
    d.enter(198)
    # 3F: the top boulder goes along the top row onto the switch at (3, 5), which opens a way to the south room.
    d.field_move('NIDOKING', 'STRENGTH')
    d.boulder((22, 3), [('up', 2), ('left', 16), ('down', 1), ('left', 4), ('down', 3), ('right', 1)])
    # The south boulder goes into the hole at (23, 15) and lands on 2F at (23, 16). The player follows it down.
    d.boulder((22, 15), [('right', 1)])
    d.enter(194)
    d.field_move('NIDOKING', 'STRENGTH')
    d.boulder((23, 16), [('left', 14)])
    # The second 2F switch opens the ladder at (25, 14). It leads to the east side of 3F and the exit.
    d.enter(198, via=(25, 14))
    d.enter(194, via=(26, 8))
    d.enter(34)


def seafoam(driver):
    d = driver
    # Ladders down to B3F: 1F (7, 5), B1F (13, 7) and B2F (5, 13). The upper boulder puzzles are optional.
    d.enter(159, via=(7, 5))
    d.enter(160, via=(13, 7))
    d.enter(161, via=(5, 13))
    # The two B3F holes drop the player to B4F, so the planner never steps on them.
    d.avoid = {(161, 3, 16), (161, 6, 16)}
    d.field_move('NIDOKING', 'STRENGTH')
    # Move the west boulder aside, then push the boulder below it into the west hole at (3, 16).
    d.boulder((5, 14), [('left', 3)])
    d.boulder((3, 15), [('down', 1)])
    # Lift the right boulder of the pair, then take the left one down, left and into the east hole at (6, 16).
    d.boulder((9, 14), [('up', 2)])
    d.boulder((8, 14), [('down', 1), ('left', 2), ('down', 1)])
    # Both holes are filled, so the B4F current is slow enough to surf from (7, 11) to Articuno.
    d.enter(162, via=(8, 6))
    d.walk(7, 11)
    d.field_move('NIDOKING', 'SURF')
    d.follow(lambda here: here[0] == 162 and abs(here[1] - 6) + abs(here[2] - 1) == 1)


FACING = {'down': 0x0, 'up': 0x4, 'left': 0x8, 'right': 0xC}
SILPH_CO_ELEVATOR, ROCKET_HIDEOUT_ELEVATOR = 236, 203
# Where to stand and which way to face to use each car's floor panel. The Hideout car's doors
# are on its top row, so its panel at (1, 1) is used from the tile below.
ELEVATOR_PANELS = {SILPH_CO_ELEVATOR: ((3, 1), 'up'), ROCKET_HIDEOUT_ELEVATOR: ((1, 2), 'up')}


def face(driver, direction):
    """Turn toward a wall, door or ball. A move into a blocked tile only turns the player."""
    if driver.engine.memory[0xC109] != FACING[direction]:
        driver.do('move', direction, 1)


def ride_elevator(driver, floor, map_id, car=SILPH_CO_ELEVATOR):
    (x, y), direction = ELEVATOR_PANELS[car]
    driver.enter(car)
    driver.walk(x, y)
    face(driver, direction)
    driver.do('interact')
    # The list shows three floors the cursor can reach. Scroll down until the floor is one of them.
    for _ in range(12):
        memory = driver.engine.memory
        if floor in [option['text'] for option in menu_options(memory, read_screen(memory), ui_state(memory)['kind'])]:
            break
        driver.do('press', 'down')
    driver.do('choose', floor)
    # The car shakes for a few seconds after the choice and ignores the joypad until it stops.
    for _ in range(10):
        engine = driver.sync()
        here = locate(engine)
        step(engine, 'down')
        if locate(engine) != here:
            break
        driver.do('wait', '', 60)
    driver.enter(map_id)


def silph_co(driver):
    d = driver
    # The Card Key lies on the bottom corridor of 5F at (21, 16). Trainers block both ends of it,
    # so the way in is the 5F pad at (9, 15): ride it to 9F and back, then step off it downward.
    ride_elevator(d, '5F', 210)
    d.enter(233, via=(9, 15))
    d.enter(210)
    d.walk(20, 16)
    face(d, 'right')
    d.do('interact')
    d.settle()
    # The corridor is a dead end, so leave by the same pad and take the 9F elevator.
    d.enter(233, via=(9, 15))
    # The 3F door at (17, 8) opens into the room with the pad at (11, 11), which leads to 7F.
    ride_elevator(d, '3F', 208)
    d.walk(18, 8)
    face(d, 'left')
    d.do('interact')
    d.settle()
    d.enter(212, via=(11, 11))
    # The second pad in that 7F room, at (5, 7), is the only way into the west hall of 11F.
    d.enter(235, via=(5, 7))
    # The 11F door at (6, 13) is the only way into Giovanni's room.
    d.walk(6, 14)
    face(d, 'up')
    d.do('interact')
    d.settle()
    d.follow(lambda here: here[0] == 235 and 5 <= here[1] <= 12 and 5 <= here[2] <= 13)


PEWTER_CITY, CERULEAN_CITY, LAVENDER_TOWN, ROUTE_3, ROUTE_4, ROUTE_9, ROUTE_10 = 2, 3, 4, 14, 15, 20, 21
MT_MOON_1F, MT_MOON_B1F, MT_MOON_B2F, ROCK_TUNNEL_1F, ROCK_TUNNEL_B1F = 59, 60, 61, 82, 232


def cross_mt_moon(d):
    """From Route 4 west of Mt. Moon to Route 4 east of it.

    The 1F ladder at (5, 5) and the B1F ladder at (21, 17) reach the B2F fossil floor,
    whose west ladder at (5, 7) climbs to the B1F room with the exit to Route 4.
    """
    d.enter(MT_MOON_1F, via=(18, 5))
    d.enter(MT_MOON_B1F, via=(5, 5))
    d.enter(MT_MOON_B2F, via=(21, 17))
    # The two fossils at (12, 6) and (13, 6) fill the only gap north. Taking one makes the
    # Super Nerd walk over and take the other, which opens it.
    d.walk(13, 7)
    face(d, 'up')
    d.do('interact')
    d.do('choose', 'YES')
    for _ in range(10):
        try:
            d.sync()
            d.search(lambda here: here == (MT_MOON_B2F, 13, 5), limit=200)
            break
        except RuntimeError:
            if ui_state(d.engine.memory)['kind'] != 'overworld':
                d.do('advance_dialogue')
            else:
                d.do('wait', '', 60)
    d.enter(MT_MOON_B1F, via=(5, 7))
    d.enter(ROUTE_4, via=(27, 3))


def pewter_to_lavender(driver):
    d = driver
    d.enter(PEWTER_CITY)
    d.enter(ROUTE_3)
    d.enter(ROUTE_4)
    cross_mt_moon(d)
    d.enter(CERULEAN_CITY)
    # A guard blocks the robbed house until the S.S. Ticket, so the way east is the small tree at
    # (19, 28) and the southeast path around to the Route 9 exit.
    d.walk(19, 27)
    face(d, 'down')
    d.field_move('CHARMELEON', 'CUT')
    d.settle()
    d.enter(ROUTE_9)
    # The small tree at (5, 8) is the only way east from Cerulean City.
    d.walk(4, 8)
    face(d, 'right')
    d.field_move('CHARMELEON', 'CUT')
    d.settle()
    d.enter(ROUTE_10)
    d.enter(ROCK_TUNNEL_1F, via=(8, 17))
    # Rock Tunnel is dark until Flash. The ladders alternate floors: 1F (37, 3), B1F (27, 3),
    # 1F (17, 11) and B1F (3, 3) end in the 1F room with the south exit at (15, 33).
    d.field_move('PIKACHU', 'FLASH')
    d.settle()
    d.enter(ROCK_TUNNEL_B1F, via=(37, 3))
    d.enter(ROCK_TUNNEL_1F, via=(27, 3))
    d.enter(ROCK_TUNNEL_B1F, via=(17, 11))
    d.enter(ROCK_TUNNEL_1F, via=(3, 3))
    d.enter(ROUTE_10, via=(15, 33))
    d.enter(LAVENDER_TOWN)


BRUNOS_ROOM, AGATHAS_ROOM, LANCES_ROOM, CHAMPIONS_ROOM, HALL_OF_FAME = 246, 247, 113, 120, 118
# Gen 1 battle structs: wEnemyMon at 0xCFE5 and wBattleMon at 0xD014 share one layout.
ENEMY_MON, BATTLE_MON = 0xCFE5, 0xD014
# Gen 1 moves of these types use Special on both sides. The rest use Attack and Defense.
SPECIAL_TYPES = frozenset(range(20, 27))


def battler(memory, base):
    word = lambda offset: memory[base + offset] << 8 | memory[base + offset + 1]
    return {'species': memory[base], 'hp': word(1), 'types': (memory[base + 5], memory[base + 6]),
            'moves': tuple(memory[base + 8:base + 12]), 'max_hp': word(15), 'attack': word(17),
            'defense': word(19), 'speed': word(21), 'special': word(23),
            'pp': tuple(v & 63 for v in memory[base + 25:base + 29])}


class Tactics:
    """A plain greedy battler: the move with the most expected damage, a heal when low, the best matchup on a switch."""

    HEAL = 'HEAL_EFFECT'

    def __init__(self, game_data):
        bundle = json.loads((game_data / 'current.json').read_text())['bundle']
        strategy = json.loads((game_data / 'bundles' / bundle / 'strategy.json').read_text())
        self.moves = {int(key): value for key, value in strategy['moves'].items()}
        self.chart = {(attack, defend): factor for attack, defend, factor in strategy['matchups']}

    def damage(self, move_id, attacker, defender):
        move = self.moves[move_id]
        power = move['power'] * (2 if move['effect'] == 'ATTACK_TWICE_EFFECT' else 1)
        stat = ('special', 'special') if move['type'] in SPECIAL_TYPES else ('attack', 'defense')
        factor = 1.5 if move['type'] in attacker['types'] else 1
        for kind in dict.fromkeys(defender['types']):
            factor *= self.chart.get((move['type'], kind), 1)
        return power * factor * move['accuracy'] / 100 * attacker[stat[0]] / max(1, defender[stat[1]])

    def best(self, attacker, defender):
        options = [(self.damage(move, attacker, defender), slot)
                   for slot, move in enumerate(attacker['moves']) if move and attacker['pp'][slot]]
        return max(options, default=(0, None))

    def choose_move(self, memory):
        mine, theirs = battler(memory, BATTLE_MON), battler(memory, ENEMY_MON)
        heals = [slot for slot, move in enumerate(mine['moves'])
                 if move and mine['pp'][slot] and self.moves[move]['effect'] == self.HEAL]
        if heals and mine['hp'] * 3 < mine['max_hp']:
            return heals[0]
        score, slot = self.best(mine, theirs)
        # Out of PP on every move: FIGHT uses Struggle whatever the slot.
        return 0 if slot is None else slot

    def choose_switch(self, memory, party, active):
        theirs = battler(memory, ENEMY_MON)
        ready = [(self.best(mon, theirs)[0] * (1 + mon['hp'] / mon['max_hp']), slot)
                 for slot, mon in enumerate(party) if mon['hp'] and slot != active]
        if not ready:
            raise RuntimeError('No Pokemon left to send out')
        return max(ready)[1]


def wait(driver, frames):
    """Advance text when a text box is open, otherwise let a scripted scene play."""
    if ui_state(driver.engine.memory)['kind'] == 'overworld':
        driver.do('wait', '', frames)
    else:
        driver.do('advance_dialogue')


def arrive(driver, limit=8):
    """Wait out a walk the game scripts on entry, such as the League rooms' walk inside."""
    for _ in range(limit):
        before = locate(driver.engine)
        driver.settle()
        if locate(driver.engine) == before or driver.done:
            return


def battle(driver, tactics, limit=400):
    """Play one League battle to its end with assisted commands, then clear the text after it."""
    d, memory = driver, driver.engine.memory
    for _ in range(40):
        if memory[0xD057] or d.done:
            break
        wait(d, 60)
    else:
        raise RuntimeError('The battle did not start')
    for _ in range(limit):
        if d.done:
            return
        ui = ui_state(memory)
        if not memory[0xD057] and ui['kind'] == 'overworld':
            return
        options = ui['visible_choices'] if ui['kind'] == 'menu' else []
        party = read_party(memory)
        if ui['kind'] in ('battle_menu', 'move_menu'):
            d.do('use_move', str(tactics.choose_move(memory) + 1))
        elif memory[0xD057] and any(text.partition(': ')[0].isdigit() for text in options):
            # The party menu opens by itself after a faint.
            d.do('switch_pokemon', str(tactics.choose_switch(memory, party, memory[0xCC2F]) + 1))
        elif {'YES', 'NO'} <= {text.upper() for text in options}:
            # Keep the battler on "Will you change POKeMON?" and keep the old moves on a new one.
            text = ' '.join(ui['text']).upper()
            d.do('choose', 'YES' if 'ABANDON' in text else 'NO')
        else:
            d.do('advance_dialogue')
    raise RuntimeError('The battle did not end')


def elite_four(driver):
    d = driver
    tactics = Tactics(d.game_data)
    # Lorelei, Bruno and Agatha stand at (5, 2) and battle when spoken to. A win opens the exit north.
    for following in (BRUNOS_ROOM, AGATHAS_ROOM, LANCES_ROOM):
        d.walk(5, 3)
        face(d, 'up')
        d.do('interact')
        battle(d, tactics)
        d.enter(following)
        arrive(d)
    # The game walks the player down Lance's hall. Lance speaks when the player steps onto (6, 2).
    d.walk(6, 3)
    d.do('move', 'up', 1)
    battle(d, tactics)
    d.enter(CHAMPIONS_ROOM)
    # The rival speaks and battles as soon as the player has walked in.
    battle(d, tactics)
    # Oak leads the player to the Hall of Fame, which records the party.
    for _ in range(80):
        if d.done:
            return
        wait(d, 120)
    raise RuntimeError(f'The Hall of Fame did not record the party. At {locate(d.engine)}')


POTION = 20


def potions(memory):
    return sum(count for item, count in read_bag(memory) if item == POTION)


def wild_battle(driver, tactics, limit=200):
    """Get through one wild battle: a Potion when low, run when as fast, otherwise fight.

    Gen 1 always lets the player escape when its Pokemon is at least as fast as the wild one.
    """
    d, memory = driver, driver.engine.memory
    for _ in range(limit):
        if d.done:
            return
        ui = ui_state(memory)
        if not memory[0xD057] and ui['kind'] == 'overworld':
            return
        options = ui['visible_choices'] if ui['kind'] == 'menu' else []
        if ui['kind'] in ('battle_menu', 'move_menu'):
            mine, theirs = battler(memory, BATTLE_MON), battler(memory, ENEMY_MON)
            if mine['hp'] * 3 < mine['max_hp'] and potions(memory):
                d.do('use_item', f'Potion:{memory[0xCC2F] + 1}')
            elif mine['speed'] >= theirs['speed'] and ui['kind'] == 'battle_menu':
                d.do('choose', 'RUN')
            else:
                d.do('use_move', str(tactics.choose_move(memory) + 1))
        elif memory[0xD057] and any(text.partition(': ')[0].isdigit() for text in options):
            party = read_party(memory)
            d.do('switch_pokemon', str(tactics.choose_switch(memory, party, memory[0xCC2F]) + 1))
        elif {'YES', 'NO'} <= {text.upper() for text in options}:
            # Send out the next Pokemon after a faint, and keep the old moves on a new one.
            text = ' '.join(ui['text']).upper()
            d.do('choose', 'NO' if 'DELETE' in text or 'FORGET' in text else 'YES')
        else:
            d.do('advance_dialogue')
    raise RuntimeError('The wild battle did not end')


def mt_moon(driver):
    d = driver
    tactics = Tactics(d.game_data)
    d.calm_planner()
    d.on_battle = lambda drv: wild_battle(drv, tactics)
    d.enter(ROUTE_4)
    cross_mt_moon(d)
    d.enter(CERULEAN_CITY)


CINNABAR_ISLAND, CINNABAR_GYM = 8, 166
MANSION_1F, MANSION_2F, MANSION_3F, MANSION_B1F = 165, 214, 215, 216
# The quiz machines in gate order, with the tile below each and the answer that opens its gate.
CINNABAR_QUIZ = (((15, 8), 'YES'), ((10, 2), 'NO'), ((9, 8), 'NO'), ((9, 14), 'NO'), ((1, 14), 'YES'), ((1, 8), 'NO'))


def read_up(driver, choice='YES', limit=8):
    """Face up, interact and clear the text, choosing choice at a YES or NO prompt."""
    face(driver, 'up')
    driver.do('interact')
    for _ in range(limit):
        ui = ui_state(driver.engine.memory)
        if driver.done or ui['kind'] == 'overworld':
            return
        options = {text.upper() for text in ui['visible_choices']} if ui['kind'] == 'menu' else set()
        driver.do('choose', choice) if {'YES', 'NO'} <= options else driver.do('advance_dialogue')
    raise RuntimeError('The text did not close')


def cinnabar_gym(driver):
    d = driver
    tactics = Tactics(d.game_data)
    d.calm_planner()
    d.on_battle = lambda drv: (wild_battle if drv.engine.memory[0xD057] == 1 else battle)(drv, tactics)
    # One switch flag moves every Mansion gate. The island resets it to off. With it off, the
    # stairs climb 1F (5, 10) and 2F (6, 1) to the north side of 3F and its switch at (10, 5).
    d.enter(CINNABAR_ISLAND)
    d.enter(MANSION_1F)
    d.enter(MANSION_2F, via=(5, 10))
    d.enter(MANSION_3F, via=(6, 1))
    d.walk(10, 6)
    read_up(d)
    # Switch on: the 3F holes at (16, 14) and (17, 14) drop into the 1F room with the B1F stairs.
    d.enter(MANSION_1F)
    d.enter(MANSION_B1F, via=(21, 23))
    # B1F: the south switch at (18, 25) turns it off, which opens the way to the north switch at
    # (20, 3). Turning that one on opens the Secret Key room.
    d.walk(18, 26)
    read_up(d)
    d.walk(20, 4)
    read_up(d)
    d.walk(5, 14)
    read_up(d)
    # Off again to leave the key room, then on at the south switch so the 1F east door is open.
    d.walk(20, 4)
    read_up(d)
    d.walk(18, 26)
    read_up(d)
    d.enter(MANSION_1F, via=(23, 22))
    d.enter(CINNABAR_ISLAND)
    # The Secret Key unlocks the gym door. Each right answer opens the next gate and skips its trainer.
    d.enter(CINNABAR_GYM)
    for (x, y), choice in CINNABAR_QUIZ:
        d.walk(x, y)
        read_up(d, choice)
    d.walk(3, 4)
    face(d, 'up')
    d.do('interact')
    battle(d, tactics)
    # The Volcano Badge is set after the badge and TM38 text.
    for _ in range(20):
        if d.done:
            return
        wait(d, 60)
    raise RuntimeError(f'The Volcano Badge was not recorded. At {locate(d.engine)}')


CELADON_CITY, ROUTE_7, ROUTE_8, GAME_CORNER = 6, 18, 19, 135
UNDERGROUND_ROUTE_7, UNDERGROUND_WEST_EAST, UNDERGROUND_ROUTE_8 = 77, 121, 80
HIDEOUT_B1F, HIDEOUT_B2F, HIDEOUT_B3F, HIDEOUT_B4F = 199, 200, 201, 202
POKEMON_TOWER_1F, POKEMON_TOWER_6F, POKEMON_TOWER_7F, MR_FUJIS_HOUSE = 142, 147, 148, 149


def talk(driver, direction='up'):
    face(driver, direction)
    driver.do('interact')
    driver.settle()


def poke_flute(driver):
    d = driver
    tactics = Tactics(d.game_data)
    d.calm_planner()
    # Running from the ghost Marowak only pushes the player back, so it is fought like a trainer.
    d.on_battle = lambda drv: (wild_battle if drv.engine.memory[0xD057] == 1
                               and locate(drv.engine)[0] != POKEMON_TOWER_6F else battle)(drv, tactics)
    # Trainers face most Hideout and Tower corridors, and spinners cover B2F and B3F.
    d.fight = True
    d.spinners = True
    # West to Celadon through the Underground Path, then into the Game Corner at (28, 19).
    d.enter(LAVENDER_TOWN)
    d.enter(ROUTE_8)
    d.enter(UNDERGROUND_ROUTE_8, via=(13, 3))
    d.enter(UNDERGROUND_WEST_EAST, via=(4, 4))
    d.enter(UNDERGROUND_ROUTE_7, via=(2, 5))
    d.enter(ROUTE_7)
    d.enter(CELADON_CITY)
    d.enter(GAME_CORNER, via=(28, 19))
    # The Rocket at (9, 5) guards the poster at (9, 4). He walks off after the battle, and the
    # poster switch opens the stairs at (17, 4).
    d.walk(9, 6)
    face(d, 'up')
    d.do('interact')
    battle(d, tactics)
    for _ in range(10):
        try:
            d.walk(9, 5)
            break
        except RuntimeError:
            wait(d, 60)
    read_up(d)
    d.enter(HIDEOUT_B1F, via=(17, 4))
    d.enter(HIDEOUT_B2F, via=(23, 2))
    d.enter(HIDEOUT_B3F, via=(21, 8))
    d.enter(HIDEOUT_B4F, via=(19, 18))
    # The Rocket at (11, 2) is fought on the way in. Talking to him again drops the Lift Key at (10, 2).
    d.walk(11, 3)
    talk(d)
    d.walk(10, 3)
    talk(d)
    # The lift reaches the east side of B4F, where both guards must be beaten to open Giovanni's door.
    d.enter(HIDEOUT_B3F, via=(19, 10))
    d.enter(HIDEOUT_B2F, via=(25, 6))
    ride_elevator(d, 'B4F', HIDEOUT_B4F, ROCKET_HIDEOUT_ELEVATOR)
    # Giovanni at (25, 3) has a wall below him, so he is spoken to from the side.
    for (x, y), direction in (((23, 13), 'up'), ((26, 13), 'up'), ((24, 3), 'right')):
        d.walk(x, y)
        face(d, direction)
        d.do('interact')
        battle(d, tactics)
    # Giovanni leaves after the battle and the Silph Scope appears at (25, 2).
    for _ in range(10):
        try:
            d.walk(24, 2)
            break
        except RuntimeError:
            wait(d, 60)
    talk(d, 'right')
    # Back the same way: the lift to B1F, the stairs to the Game Corner and east to Lavender.
    ride_elevator(d, 'B1F', HIDEOUT_B1F, ROCKET_HIDEOUT_ELEVATOR)
    d.enter(GAME_CORNER)
    d.enter(CELADON_CITY)
    d.enter(ROUTE_7)
    d.enter(UNDERGROUND_ROUTE_7)
    d.enter(UNDERGROUND_WEST_EAST)
    d.enter(UNDERGROUND_ROUTE_8)
    d.enter(ROUTE_8)
    d.enter(LAVENDER_TOWN)
    d.enter(POKEMON_TOWER_1F)
    for floor in range(POKEMON_TOWER_1F + 1, POKEMON_TOWER_6F + 1):
        d.enter(floor)
    # On 6F the Rare Candy at (6, 8) fills the only corridor south, so it is picked up. The ghost
    # Marowak at (10, 16) stands beside the stairs at (9, 16) and is fought from (10, 15).
    d.walk(6, 7)
    talk(d, 'down')
    d.walk(10, 15)
    d.do('move', 'down')
    battle(d, tactics)
    d.enter(POKEMON_TOWER_7F)
    # Mr. Fuji at (10, 3) sends the player to his house, where he gives the Flute from (3, 1).
    d.walk(10, 4)
    talk(d)
    for _ in range(20):
        if locate(d.engine)[0] == MR_FUJIS_HOUSE or d.done:
            break
        wait(d, 60)
    d.walk(3, 2)
    talk(d)
    for _ in range(10):
        if d.done:
            return
        wait(d, 60)
    raise RuntimeError(f'The Poke Flute was not recorded. At {locate(d.engine)}')


SOLUTIONS = {'navigation-victory-road': victory_road, 'navigation-seafoam-islands': seafoam,
             'navigation-silph-co': silph_co, 'navigation-pewter-to-lavender': pewter_to_lavender,
             'battle-elite-four-no-items': elite_four, 'battle-mt-moon-underleveled': mt_moon,
             'objectives-cinnabar-gym': cinnabar_gym, 'objectives-poke-flute': poke_flute}


def build(task_id, rom, game_data, fixtures, output):
    scenario = select_scenario(fixtures, task_id)
    work = Path(output)
    shutil.rmtree(work / 'drive', ignore_errors=True)
    shutil.rmtree(work / 'replay', ignore_errors=True)
    work.mkdir(parents=True, exist_ok=True)
    driver = Driver(rom, game_data, scenario, work / 'drive')
    error = None
    try:
        SOLUTIONS[task_id](driver)
    except RuntimeError as failure:
        error = str(failure)
    finally:
        reason = driver.session.reason
        position = locate(driver.engine)
        driver.close()
    summary = {'task': task_id, 'decisions': len(driver.log), 'raw_actions': len(driver.raw),
               'drive_stop_reason': reason, 'final_position': position, 'error': error}
    write_json(work / 'reference-commands.json', {'summary': summary, 'commands': driver.log})
    write_json(work / 'reference-actions.json', driver.raw)
    if error or reason != 'completed':
        print(json.dumps(summary))
        raise SystemExit(1)
    proof = run_task(fixtures, task_id, rom, game_data, work / 'replay', actions=driver.raw, reference=True)
    summary.update(completed=proof['result']['completed'], score=proof['result']['score'],
                   replay_verified=proof['replay'].get('verified'))
    write_json(work / 'reference-summary.json', summary)
    print(json.dumps(summary))
    return summary


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--rom', required=True)
    parser.add_argument('--game-data', required=True)
    parser.add_argument('--fixtures', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--tasks', nargs='+', required=True)
    args = parser.parse_args()
    for task_id in args.tasks:
        build(task_id, args.rom, args.game_data, args.fixtures, args.output / task_id)


if __name__ == '__main__':
    main()
