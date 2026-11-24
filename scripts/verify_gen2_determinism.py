"""Prove that Crystal replays exactly under a frame-locked clock. No model calls.

Process A plays from a fresh cartridge and records every native action with the hash of the
frame, all work RAM (every WRAM bank), HRAM and the clock after it. At the middle it saves a
start with its clock lock and a Core checkpoint. Then, one process at a time:

  B replays A's actions from a fresh cartridge, pausing on the host clock twice.
  C opens the mid start through the Gen II loader in a fresh process and replays the rest.
  D restores the Core checkpoint in a fresh process and replays the rest.
  E checks that a start without its lock, or with a lock before its save time, is refused.

Every step of B, C and D must match A. Actions come from PokeSim's story policy at its
pinned tag (--pokesim) or, without it, from a seeded button sequence. Outputs go to --output,
which must sit in the gitignored data/ folder.
"""
import argparse
import json
from pathlib import Path
import pickle
import platform
import random
import shutil
import subprocess
import sys
import time

from pokeagent_bench.core import core_provenance
from pokeagent_bench.gen2 import engine
from pokeagent_bench.gen2.curation import PokeSimDriver, play

SECONDS_PER_FRAME = 4389 / 262144
BUTTONS = ('a', 'a', 'a', 'b', 'start', 'up', 'down', 'left', 'right')


def seeded_actions(seed, frames):
    rng = random.Random(seed)
    total, actions = 0, []
    while total < frames:
        action = (rng.choice(BUTTONS), rng.choice((2, 4, 8)), rng.choice((8, 16, 24)))
        actions.append(action)
        total += action[1] + action[2]
    return actions


def write_steps(path, steps):
    path.write_text(''.join(json.dumps(step, sort_keys=True) + '\n' for step in steps))


def read_steps(path):
    return [json.loads(line) for line in path.read_text().splitlines()]


def record(args):
    rom = engine.check_rom(args.rom)
    emulator = engine.boot(rom)
    driver = PokeSimDriver(args.pokesim, args.data) if args.pokesim else None
    scripted = None if driver else seeded_actions(args.seed, args.frames)
    actions, steps, frame, mid = [], [], 0, None
    started = time.monotonic()
    while frame < args.frames:
        action = driver.decide(emulator, frame) if driver else scripted[len(actions)]
        frame += play(emulator, action)
        actions.append(list(action))
        step = {'step': len(actions), 'frames': frame, **engine.digests(emulator)}
        step['clock_matches_frames'] = abs(step['clock'] - (engine.EPOCH + frame * SECONDS_PER_FRAME)) < 1e-6
        steps.append(step)
        if mid is None and frame >= args.frames // 2:
            mid = len(actions)
            engine.save_start(emulator, args.output / 'mid')
            (args.output / 'mid' / 'checkpoint.pickle').write_bytes(pickle.dumps(emulator.checkpoint()))
    seconds = time.monotonic() - started
    final = engine.facts(emulator)
    emulator.stop(save=False)
    (args.output / 'actions.json').write_text(json.dumps({'mid_step': mid, 'actions': actions}) + '\n')
    write_steps(args.output / 'A.jsonl', steps)
    source = driver.provenance if driver else {'seeded_actions': args.seed}
    (args.output / 'A.json').write_text(json.dumps({'seconds': seconds, 'frames': frame, 'steps': len(actions),
                                                    'source': source, 'final_map': final['map'],
                                                    'final_party': len(final['party'])}, indent=2) + '\n')


def replay(emulator, actions, first, pauses=()):
    steps, frame = [], 0
    for index, action in enumerate(actions, first + 1):
        if index in pauses:
            time.sleep(1.5)
        frame += play(emulator, tuple(action))
        steps.append({'step': index, **engine.digests(emulator)})
    return steps


def at_load(emulator):
    loaded = engine.digests(emulator)
    return {key: loaded[key] for key in ('wram', 'hram', 'clock')}


def run_role(args):
    rom = engine.check_rom(args.rom)
    plan = json.loads((args.output / 'actions.json').read_text())
    actions, mid = plan['actions'], plan['mid_step']
    if args.role == 'B':
        emulator = engine.boot(rom)
        steps = replay(emulator, actions, 0, pauses={len(actions) // 3, 2 * len(actions) // 3})
        head = None
    elif args.role == 'C':
        emulator, _ = engine.load_start(rom, args.output / 'mid')
        head = at_load(emulator)
        steps = replay(emulator, actions[mid:], mid)
    else:
        emulator = engine.clock.boot(rom, sound=False)
        emulator.restore_checkpoint(pickle.loads((args.output / 'mid' / 'checkpoint.pickle').read_bytes()))
        head = at_load(emulator)
        steps = replay(emulator, actions[mid:], mid)
    emulator.stop(save=False)
    write_steps(args.output / f'{args.role}.jsonl', steps)
    (args.output / f'{args.role}.json').write_text(json.dumps({'at_load': head}) + '\n')


def refused(call):
    try:
        call()
    except ValueError as error:
        return str(error)
    return None


def refusals(args):
    """E: the loader refuses a start without its lock or with a lock before its save time."""
    rom = engine.check_rom(args.rom)
    source, root = args.output / 'mid', args.output / 'refusals'
    shutil.rmtree(root, ignore_errors=True)
    root.mkdir()
    record = json.loads((source / engine.CLOCK_FILE).read_text())

    def variant(name, change=None):
        folder = root / name
        folder.mkdir(parents=True)
        shutil.copy(source / engine.STATE_FILE, folder / engine.STATE_FILE)
        if change is not None:
            edited = json.loads(json.dumps(record))
            change(edited)
            (folder / engine.CLOCK_FILE).write_text(json.dumps(edited))
        return folder

    def earlier(edited):
        edited['lock']['frames'] -= 60

    def unlocked(edited):
        edited['lock']['follow_frames'] = False

    def other_state(edited):
        edited['state_sha256'] = '0' * 64

    def opened(folder):
        emulator, _ = engine.load_start(rom, folder)
        emulator.stop(save=False)

    emulator, loaded = engine.load_start(rom, source)
    accepted_clock = emulator.clock_now()
    emulator.stop(save=False)
    junk = root / 'not-crystal.gbc'
    junk.write_bytes(bytes(1 << 20))
    result = {
        'accepted_lock_reads_at_or_after_save': accepted_clock >= record['clock'],
        'accepted_clock': accepted_clock, 'save_clock': record['clock'],
        'no_lock_file': refused(lambda: opened(variant('no-lock'))),
        'lock_before_save_time': refused(lambda: opened(variant('earlier', earlier))),
        'lock_not_following_frames': refused(lambda: opened(variant('unlocked', unlocked))),
        'lock_for_another_state': refused(lambda: opened(variant('other-state', other_state))),
        'other_rom': refused(lambda: engine.check_rom(junk)),
    }
    # The record is meant to be kept, so it names folders relative to the output.
    result = {key: value.replace(str(args.output), '<output>') if isinstance(value, str) else value
              for key, value in result.items()}
    (args.output / 'E.json').write_text(json.dumps(result, indent=2) + '\n')


def compare(args):
    plan = json.loads((args.output / 'actions.json').read_text())
    mid = plan['mid_step']
    reference = read_steps(args.output / 'A.jsonl')
    keys = ('frame', 'wram', 'hram', 'clock')
    by_step = {step['step']: step for step in reference}
    mid_state = json.loads((args.output / 'mid' / engine.CLOCK_FILE).read_text())
    summary = {'protocol': 'gen2-determinism-v1', 'rom_sha1': engine.ROM_SHA1, 'core': core_provenance(),
               'python': platform.python_version(), 'source': json.loads((args.output / 'A.json').read_text()),
               'steps': len(reference), 'mid_step': mid, 'mid_clock': mid_state,
               'clock_follows_frames_every_step': all(step['clock_matches_frames'] for step in reference),
               'final_step': {key: reference[-1][key] for key in keys + ('frames',)}, 'runs': {}}
    for role in ('B', 'C', 'D'):
        steps = read_steps(args.output / f'{role}.jsonl')
        mismatched = [step['step'] for step in steps if any(step[key] != by_step[step['step']][key] for key in keys)]
        head = json.loads((args.output / f'{role}.json').read_text())['at_load']
        head_matches = None if head is None else all(head[key] == by_step[mid][key] for key in head)
        summary['runs'][role] = {'compared_steps': len(steps), 'first_step': steps[0]['step'], 'last_step': steps[-1]['step'],
                                 'mismatched_steps': mismatched[:20], 'mismatches': len(mismatched),
                                 'state_at_load_matches_A': head_matches}
    summary['refusals'] = json.loads((args.output / 'E.json').read_text())
    refusal_keys = ('no_lock_file', 'lock_before_save_time', 'lock_not_following_frames', 'lock_for_another_state', 'other_rom')
    summary['passed'] = (summary['clock_follows_frames_every_step']
                         and all(run['mismatches'] == 0 and run['compared_steps'] > 0 and run['state_at_load_matches_A'] in (None, True)
                                 for run in summary['runs'].values())
                         and summary['runs']['B']['compared_steps'] == len(reference)
                         and summary['runs']['C']['last_step'] == len(reference)
                         and summary['refusals']['accepted_lock_reads_at_or_after_save']
                         and all(summary['refusals'][key] for key in refusal_keys))
    (args.output / 'summary.json').write_text(json.dumps(summary, indent=2) + '\n')
    return summary


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--rom', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--pokesim', type=Path, help='PokeSim checkout at its pinned tag')
    parser.add_argument('--data', type=Path, help='PokeSim Gen II game data root')
    parser.add_argument('--frames', type=int, default=60000)
    parser.add_argument('--seed', type=int, default=7)
    parser.add_argument('--role', choices=('A', 'B', 'C', 'D', 'E'))
    args = parser.parse_args()
    if args.pokesim and not args.data:
        parser.error('--pokesim needs --data')
    if args.role:
        {'A': record, 'E': refusals}.get(args.role, run_role)(args)
        return
    if args.output.exists():
        parser.error(f'{args.output} exists')
    args.output.mkdir(parents=True)
    base = [sys.executable, __file__, '--rom', str(args.rom), '--output', str(args.output),
            '--frames', str(args.frames), '--seed', str(args.seed)]
    if args.pokesim:
        base += ['--pokesim', str(args.pokesim), '--data', str(args.data)]
    timings = {}
    for role in ('A', 'B', 'C', 'D', 'E'):
        started = time.monotonic()
        subprocess.run(base + ['--role', role], check=True)
        timings[role] = round(time.monotonic() - started, 2)
    summary = compare(args)
    summary['process_seconds'] = timings
    (args.output / 'summary.json').write_text(json.dumps(summary, indent=2) + '\n')
    print(json.dumps({key: summary[key] for key in ('passed', 'steps', 'mid_step', 'runs', 'process_seconds')}, indent=2))
    if not summary['passed']:
        raise SystemExit('Determinism check failed')


if __name__ == '__main__':
    main()
