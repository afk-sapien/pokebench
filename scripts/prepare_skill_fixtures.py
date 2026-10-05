"""Extract five fixed tasks from archived controller traces, without model calls."""
import argparse
import json
from pathlib import Path

from pokesim_core.gen1 import W_IS_IN_BATTLE, W_TRAINER_CLASS

from pokeagent_bench.core import digest, encoded, write_json
from pokeagent_bench.gameplay import ui_state
from pokeagent_bench.session import load_engine
from pokeagent_bench.suite import NEW_SKILL_TASKS, check_start, read, reference
from prepare_basic_fixtures import advance, save_fixture


DESCRIPTIONS = {
    'first-capture': 'Catch the wild Pokemon in this encounter and add it to your party. Keep its default name. Do not flee or knock it out.',
    'parcel-delivery': "You are in Viridian City carrying Oak's Parcel. Return to Professor Oak in Pallet Town and deliver it to receive the Pokedex. Keep default Pokemon names.",
    'lorelei': 'Defeat Lorelei in this battle using the party and supplies provided. Keep default Pokemon names.',
    'bruno': 'Defeat Bruno in this battle using the party and supplies provided. Keep default Pokemon names.',
    'champion-duel': 'Defeat the Champion in this final battle and complete the Hall of Fame registration. Use the party and supplies provided. Keep default Pokemon names.',
}


def command_for(row):
    if 'action' not in row:
        return {key: row[key] for key in ('button', 'hold_frames', 'release_frames')}
    command = dict(row['action'])
    hold = min(command['hold_frames'], row['executed_frames'])
    return {**command, 'hold_frames': hold, 'release_frames': row['executed_frames'] - hold}


def extract(rom, source, trace, output, select, expected):
    engine, manifest = load_engine(rom, source)
    rows = [json.loads(line) for line in trace.read_text().splitlines()]
    commands = [command_for(row) for row in rows]
    found = {}
    frame = 0
    head = '0' * 64
    try:
        for index, (row, command) in enumerate(zip(rows, commands)):
            if 'hash' in row:
                body = dict(row)
                claimed = body.pop('hash')
                assert body['previous_hash'] == head and digest(encoded(body)) == claimed
                assert body['before_frame'] == frame
                head = claimed
            advance(engine, command)
            frame += command['hold_frames'] + command['release_frames']
            assert frame == row['frame']
            key = select(engine)
            if key and key not in found:
                if 'screenshot_sha256' in row:
                    assert digest(engine.screenshot()) == row['screenshot_sha256']
                task = next(t for t in NEW_SKILL_TASKS if t['id'] == key)
                check_start(task, engine)
                save_fixture(engine, manifest, output/key,
                             {**task['objective'], 'description': DESCRIPTIONS[key]},
                             {'source_scenario': str(source), 'source_state_sha256': manifest['state_sha256'],
                              'trace': str(trace), 'trace_sha256': digest(trace.read_bytes()),
                              'prefix_actions': index+1, 'prefix_frames': frame,
                              'controller_only': True, 'extractor_sha256': digest(Path(__file__).read_bytes())})
                found[key] = index+1
                print('Captured', key, 'at frame', frame, flush=True)
            if set(found) == set(expected):
                break
        if set(found) != set(expected):
            raise ValueError(f'Missing checkpoints: {set(expected) - set(found)}')
    finally:
        engine.close()
    for key, offset in found.items():
        proof = reference(rom, output/key, commands[offset:], output/key/'reference')
        assert proof['verified']
        print('Verified', key, flush=True)
    return found


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, required=True)
    parser.add_argument('--rom', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    root = args.root.resolve()
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=False)

    def league(engine):
        if engine.memory[W_IS_IN_BATTLE] == 2 and ui_state(engine.memory)['kind'] == 'battle_menu':
            return {44: 'lorelei', 33: 'bruno', 43: 'champion-duel'}.get(engine.memory[W_TRAINER_CLASS])
        return None

    source = root/'data/red-league-v1-core014/fixtures/league'
    extract(args.rom, source, source/'reference/actions.jsonl', output,
            league, ('lorelei', 'bruno', 'champion-duel'))

    def delivery(engine):
        facts = engine.challenge_evidence({'kind': 'opening', 'target': 'parcel'})
        if (facts['parcel'] == 1 and not facts['parcel_delivered'] and engine.evidence()['map_id'] == 1
                and facts['battle'] == 0 and ui_state(engine.memory)['kind'] == 'overworld'):
            return 'parcel-delivery'
        return None

    source = root/'data/red-basic-v1-core014/fixtures/parcel'
    extract(args.rom, source, source/'reference/actions.jsonl', output, delivery, ('parcel-delivery',))

    def capture(engine):
        facts = engine.challenge_evidence({'kind': 'capture'})
        if (facts['party_count'] == 1 and len(facts['owned']) == 1 and facts['balls'] > 0
                and engine.evidence()['story']['pokedex'] and facts['battle'] == 1
                and facts['battle_type'] == 0 and ui_state(engine.memory)['kind'] == 'battle_menu'):
            return 'first-capture'
        return None

    source = root/'scenarios/wild-battle-v015'
    archived = read(root/'data/pokesim-gym-v015-story/source.json')['source_scenario']
    assert read(source/'scenario.json')['state_sha256'] == archived['state_sha256']
    extract(args.rom, source, root/'data/pokesim-gym-v015-story/actions.jsonl', output,
            capture, ('first-capture',))
    mapping = {task['id']: {'scenario': str(output/task['id']), 'reference': str(output/task['id']/'reference')}
               for task in NEW_SKILL_TASKS}
    write_json(output/'bindings.json', mapping)
    original = root/'data/red-ability-v1'
    for key, fixture in read(original/'suite.json')['fixtures'].items():
        path = original/fixture['scenario']
        mapping[key] = {'scenario': str(path), 'reference': str(path/'reference')}
    write_json(output/'expanded-bindings.json', mapping)
    print('Five new tasks and fourteen-task suite bindings ready', flush=True)


if __name__ == '__main__':
    main()
