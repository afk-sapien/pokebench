"""Build the Gen II prep starts and their scripted references from a fresh Crystal game. No model calls.

PokeSim's Gen II story policy at its pinned tag plays from power-on on the frame-locked
clock. When the run first settles on a task's start map with the task's events in the
named state, for two actions in a row with no battle and no script running, the script
saves initial.state and its clock lock. A task whose capture names a later entry waits until
the run has entered its start maps from elsewhere that many times. The run then keeps playing and records every native
action until the task's success check holds on two different frames. That recording is the
task's scripted reference. The Kabuto panel task needs its own run, which leaves the story
for the Ruins of Alph once the Zephyr Badge and the Togepi egg are in hand.

A reference that blacks out is no reference. When the story run blacks out after a capture,
that attempt moves to blackouts/ and the task waits for the run's next entry that meets its
capture rule, up to MAX_ATTEMPTS entries. The manifest lists every attempt.

Outputs go to --output, which must sit in the gitignored data/ folder and must not exist.
Each task folder holds initial.state, initial.clock.json, reference.json and trace.json.
manifest.json records the ROM, Core, PokeSim provenance and, per task, the start, the
reference and the milestones the evaluator awarded while it played.
"""
import argparse
import json
from pathlib import Path
import platform
import time

from pokeagent_bench.core import core_provenance
from pokeagent_bench.gen2 import catalog, engine
from pokeagent_bench.gen2.curation import PokeSimDriver, play
from pokeagent_bench.gen2.evaluator import VERSION, MilestoneEvaluator, blackout, holds, watched_events

ROOT = Path(__file__).resolve().parents[1]
ROUTE_FRAME_CAPS = {'story': 2_600_000, 'kabuto': 900_000}
FLAG_BYTES = 256
FORMAT = 'gen2-fixtures-v1'
MAX_ATTEMPTS = 3


def flag_bytes(emulator):
    return engine.read(emulator.memory, 'wEventFlags', FLAG_BYTES)


def changed_flags(before, after):
    for index, (old, new) in enumerate(zip(before, after)):
        if old != new:
            for bit in range(8):
                if (old ^ new) >> bit & 1:
                    yield index * 8 + bit, bool(new >> bit & 1)


class Names:
    def __init__(self, data_root):
        data = json.loads((Path(data_root) / 'gen2' / 'crystal' / 'data.json').read_text())
        self.maps = {(row['group'], row['number']): row['constant'] for row in data['maps'].values()}
        self.events = {index: name for name, index in data['events'].items()}


def summary(facts):
    return {'map': facts['map'], 'x': facts['x'], 'y': facts['y'], 'badges': facts['badges'],
            'party': [[mon['species'], mon['level'], mon['hp'], mon['max_hp']] for mon in facts['party']],
            'time_of_day': engine.TIMES_OF_DAY[facts['time_of_day']] if facts['time_of_day'] < 4 else facts['time_of_day']}


class Recorder:
    """A saved start and every action played after it, until the success check holds twice."""

    def __init__(self, task, folder, emulator, frame, names):
        self.task, self.folder, self.start_frame, self.names = task, folder, frame, names
        self.success = task['milestones'][-1]['check']
        self.events = watched_events(task['milestones'])
        self.clock = engine.save_start(emulator, folder)
        self.evaluator = MilestoneEvaluator(self.facts(emulator), task)
        self.start = summary(self.facts(emulator))
        self.actions, self.awards, self.trace = [], [], []
        self.flags, self.place = flag_bytes(emulator), self.start['map']
        self.held, self.outcome = False, None

    def facts(self, emulator):
        return engine.facts(emulator, self.events)

    def note(self, emulator, facts, elapsed):
        flags = flag_bytes(emulator)
        for index, value in changed_flags(self.flags, flags):
            self.trace.append({'frame': elapsed, 'action': len(self.actions), 'event': index,
                               'name': self.names.events.get(index), 'set': value})
        self.flags = flags
        if facts['map'] != self.place:
            self.place = facts['map']
            self.trace.append({'frame': elapsed, 'action': len(self.actions), 'map': facts['map'],
                               'name': self.names.maps.get(tuple(facts['map']))})

    def step(self, emulator, action, frame):
        self.actions.append(list(action))
        elapsed = frame - self.start_frame
        facts = self.facts(emulator)
        for award in self.evaluator.observe(facts, elapsed):
            self.awards.append({'id': award['id'], 'frame': award['frame'], 'action': len(self.actions)})
        self.note(emulator, facts, elapsed)
        if blackout(facts):
            self.outcome = 'blackout'
        elif holds(self.success, facts):
            self.outcome, self.held = ('success' if self.held else None), True
        else:
            self.held = False
        if self.outcome is None and elapsed > self.task['capture']['frame_cap']:
            self.outcome = 'frame-cap'
        return self.outcome

    def write(self):
        state = (self.folder / engine.STATE_FILE).read_bytes()
        (self.folder / 'reference.json').write_text(json.dumps(
            {'format': 'gen2-reference-v1', 'task_id': self.task['id'], 'state_sha256': engine.sha256(state),
             'actions': self.actions}, separators=(',', ':')) + '\n')
        (self.folder / 'trace.json').write_text(json.dumps(self.trace, indent=1) + '\n')
        return {'task_id': self.task['id'], 'route': self.task['capture']['route'], 'outcome': self.outcome,
                'start_frame': self.start_frame, 'start': self.start, 'clock': self.clock,
                'fixture': catalog.pins(state, self.actions), 'awards': self.awards, 'complete': self.evaluator.complete(),
                'disqualified': self.evaluator.disqualification_reason}


def captures(task, facts):
    capture = task['capture']
    return (facts['valid'] and not facts['battle'] and not facts['script'] and not blackout(facts)
            and facts['map'] in capture['maps']
            and all(facts['events'][str(flag)] for flag in capture['after'])
            and not any(facts['events'][str(flag)] for flag in capture['before']))


def kabuto_journey(driver):
    """PokeSim's own Ruins of Alph goal for the Kabuto board, as its ruins focus sets it."""
    def journey(snapshot, mem):
        if not snapshot.event('EVENT_SOLVED_KABUTO_PUZZLE'):
            return driver.Goal('alph_kabuto', 'Solve the Kabuto picture puzzle', 'RUINS_OF_ALPH_KABUTO_CHAMBER', 3, 3, 'up')
        return driver.Goal('collection_wait', 'Focused scenario complete',
                           driver.data.maps[snapshot.map]['constant'], snapshot.x, snapshot.y)
    return journey


def run_route(route, tasks, args, names, log):
    rom = engine.check_rom(args.rom)
    emulator = engine.boot(rom)
    driver = PokeSimDriver(args.pokesim, args.data)
    waiting = {task['id']: task for task in tasks}
    ready, recorders, results = set(), {}, []
    attempts = {task['id']: [] for task in tasks}
    entries = {task['id']: 0 for task in tasks}
    place = None
    frame, steps, turned = 0, 0, route != 'kabuto'
    started = time.monotonic()
    while (waiting or recorders) and frame < ROUTE_FRAME_CAPS[route]:
        action = driver.decide(emulator, frame)
        frame += play(emulator, action)
        steps += 1
        if not turned and 'togepi' in driver.policy.completed:
            driver.policy.journey = kabuto_journey(driver)
            turned = True
            log({'route': route, 'turned_to_ruins': frame})
        for identifier, recorder in list(recorders.items()):
            if recorder.step(emulator, action, frame):
                result = recorder.write()
                del recorders[identifier]
                log({'route': route, 'task': identifier, 'outcome': recorder.outcome, 'frame': frame,
                     'actions': len(recorder.actions), 'awards': [award['id'] for award in recorder.awards]})
                if recorder.outcome == 'blackout' and len(attempts[identifier]) + 1 < MAX_ATTEMPTS:
                    kept = args.output / 'blackouts' / f'{identifier}-{len(attempts[identifier]) + 1}'
                    kept.parent.mkdir(exist_ok=True)
                    recorder.folder.rename(kept)
                    attempts[identifier].append({key: result[key] for key in ('outcome', 'start_frame', 'start', 'fixture')}
                                                | {'end_frame': frame, 'kept': kept.relative_to(args.output).as_posix()})
                    waiting[identifier] = recorder.task
                    continue
                results.append(result | {'attempts': attempts[identifier]})
        last, place = place, [engine.byte(emulator.memory, 'wMapGroup'), engine.byte(emulator.memory, 'wMapNumber')]
        for task in tasks:
            if place in task['capture']['maps'] and last not in task['capture']['maps']:
                entries[task['id']] += 1
        for identifier, task in list(waiting.items()):
            if place not in task['capture']['maps'] or entries[identifier] < task['capture'].get('entry', 1):
                ready.discard(identifier)
                continue
            flags = task['capture']['after'] + task['capture']['before']
            if not captures(task, engine.facts(emulator, flags)):
                ready.discard(identifier)
            elif identifier not in ready:
                ready.add(identifier)
            else:
                recorders[identifier] = Recorder(task, args.output / identifier, emulator, frame, names)
                del waiting[identifier]
                log({'route': route, 'task': identifier, 'captured': frame, 'entry': entries[identifier],
                     'start': recorders[identifier].start})
    wall = time.monotonic() - started
    final = engine.facts(emulator)
    emulator.stop(save=False)
    for identifier in waiting:
        results.append({'task_id': identifier, 'route': route, 'outcome': 'not-captured', 'attempts': attempts[identifier]})
    for identifier, recorder in recorders.items():
        recorder.outcome = 'route-frame-cap'
        results.append(recorder.write() | {'attempts': attempts[identifier]})
    stats = {'frames': frame, 'steps': steps, 'seconds': round(wall, 2), 'fps': round(frame / wall),
             'final_map': names.maps.get(tuple(final['map'])), 'final_badges': final['badges'],
             'pokesim': driver.provenance}
    return stats, results


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--rom', type=Path, required=True)
    parser.add_argument('--pokesim', type=Path, required=True, help='PokeSim checkout at its pinned tag')
    parser.add_argument('--data', type=Path, required=True, help='PokeSim Gen II game data root')
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--tasks', nargs='*', help='Only these task IDs')
    args = parser.parse_args()
    args.output = args.output.resolve()
    if not args.output.is_relative_to(ROOT / 'data'):
        parser.error(f'{args.output} is outside {ROOT / "data"}, the gitignored output folder')
    if args.output.exists():
        parser.error(f'{args.output} exists')
    tasks = catalog.load_tasks()
    if args.tasks:
        unknown = set(args.tasks) - {task['id'] for task in tasks}
        if unknown:
            parser.error(f'Unknown tasks: {sorted(unknown)}')
        tasks = [task for task in tasks if task['id'] in args.tasks]
    engine.check_rom(args.rom)
    args.output.mkdir(parents=True)
    names = Names(args.data)
    log_path = args.output / 'log.jsonl'

    def log(row):
        line = json.dumps(row)
        print(line, flush=True)
        with log_path.open('a') as stream:
            stream.write(line + '\n')

    manifest = {'format': FORMAT, 'rom_sha1': engine.ROM_SHA1, 'core': core_provenance(),
                'python': platform.python_version(), 'evaluator': VERSION, 'routes': {}, 'tasks': []}
    for route in catalog.ROUTES:
        selected = [task for task in tasks if task['capture']['route'] == route]
        if selected:
            stats, results = run_route(route, selected, args, names, log)
            manifest['routes'][route] = stats
            manifest['tasks'] += results
    order = [task['id'] for task in tasks]
    manifest['tasks'].sort(key=lambda row: order.index(row['task_id']))
    (args.output / 'manifest.json').write_text(json.dumps(manifest, indent=2) + '\n')
    failed = [row['task_id'] for row in manifest['tasks'] if row['outcome'] != 'success']
    print(json.dumps({'built': [row['task_id'] for row in manifest['tasks'] if row['outcome'] == 'success'],
                      'failed': failed, 'routes': {route: {key: stats[key] for key in ('frames', 'seconds', 'fps')}
                                                   for route, stats in manifest['routes'].items()}}, indent=2))
    if failed:
        raise SystemExit(f'Reference did not reach success for {failed}')


if __name__ == '__main__':
    main()
