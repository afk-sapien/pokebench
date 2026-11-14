"""Scripted references for PokeBench Hard. No model calls.

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

from pokeagent_bench.catalog_execution import run_task, select_scenario
from pokeagent_bench.catalog_fixtures import command as native
from pokeagent_bench.core import Limits, write_json
from pokeagent_bench.evaluation_catalog import task_definition
from pokeagent_bench.gameplay import load_catalog, ui_state
from pokeagent_bench.gameplay_commands import execute
from pokeagent_bench.session import Session, load_engine
from pokecore.gen1_ui import read_sprites

STEPS = {'up': (0, -1), 'down': (0, 1), 'left': (-1, 0), 'right': (1, 0)}


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
        self.rom, self.scenario = Path(rom), Path(scenario)
        self.engine, manifest = load_engine(self.rom, self.scenario)
        self.planner, _ = load_engine(self.rom, self.scenario)
        task = task_definition(manifest['task_id'])
        self.session = Session(self.engine, Path(output), manifest, track='gameplay', goal='challenge',
                               gameplay_catalog=load_catalog(Path(game_data)),
                               limits=Limits(max_total_tokens=task['token_limit']),
                               agent={'provider': 'reference', 'model': 'scripted-assisted-commands'})
        self.raw = []
        self.log = []

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
        for _ in range(limit):
            if not queue:
                break
            state, origin, path = queue.popleft()
            for direction in STEPS:
                engine.load(state)
                step(engine, direction)
                here = locate(engine)
                if here[0] != start[0]:
                    dx, dy = STEPS[direction]
                    if goal((here[0], origin[1] + dx, origin[2] + dy)):
                        return path + [direction]
                    continue
                if goal(here):
                    return path + [direction]
                if here in seen or ui_state(engine.memory)['kind'] != 'overworld' or engine.memory[0xD057]:
                    continue
                seen.add(here)
                queue.append((engine.save(), here, path + [direction]))
        raise RuntimeError(f'No path from {start}. Searched {len(seen)} tiles')

    def follow(self, goal, attempts=40):
        """Walk with move commands of at most 8 tiles, replanning whenever a run ends early.

        Stops at the first map change. The caller checks that it was the intended one.
        """
        for _ in range(attempts):
            before = locate(self.engine)
            if goal(before):
                return
            path = self.search(goal)
            direction = path[0]
            count = 1
            while count < min(8, len(path)) and path[count] == direction:
                count += 1
            result = self.do('move', direction, count)
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
        if not self.done and ui_state(self.engine.memory)['kind'] != 'overworld':
            self.do('advance_dialogue')

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


SOLUTIONS = {'navigation-hard-victory-road': victory_road}


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
