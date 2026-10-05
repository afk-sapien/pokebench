"""Replay Sol's League menu regression cases without model calls or RAM edits."""
import argparse
import json
from pathlib import Path

from pokesim_core.gen1 import read_bag, read_party

from pokeagent_bench.core import Limits, digest, encoded, write_json
from pokeagent_bench.game import RedEngine
from pokeagent_bench.gameplay import load_catalog, ui_state
from pokeagent_bench.gameplay_commands import execute
from pokeagent_bench.menu_shortcuts import identity, parse_item
from pokeagent_bench.session import Session, replay

# Decision numbers identify retained states in the audited Sol League attempt.
CASES = [(30,'use_item','Full Restore:1'), (96,'use_item','Revive:2'),
         (88,'switch_pokemon','3'), (89,'switch_pokemon','3'), (93,'switch_pokemon','3'),
         (150,'use_item','Full Restore:1'), (150,'use_item','Revive:2'), (150,'use_item','Elixer:1'),
         (150,'switch_pokemon','3'), (108,'use_item','Full Restore:1'),
         (119,'use_item','Full Restore:1'), (185,'use_item','Full Restore:1'),
         (186,'use_item','Full Restore:1'), (194,'switch_pokemon','3')]


def extract(rom, run, destination):
    manifest = json.loads((run/'manifest.json').read_text())
    assert manifest['scenario']['rom_sha256'] == digest(rom.read_bytes())
    state = (run/'initial.state').read_bytes()
    assert digest(state) == manifest['initial_sha256']
    decisions = [json.loads(line) for line in (run/'decisions.jsonl').read_text().splitlines()]
    targets = {decisions[index-1]['frame']:index for index, _, _ in CASES}
    engine = RedEngine(rom, state)
    found = {}
    head = '0' * 64
    frame = 0
    try:
        for line in (run/'actions.jsonl').read_text().splitlines():
            row = json.loads(line)
            claimed = row.pop('hash')
            assert row['previous_hash'] == head and digest(encoded(row)) == claimed
            assert row['before_frame'] == frame
            head = claimed
            command = row['action']
            hold = min(command['hold_frames'], row['executed_frames'])
            if command['button'] is not None:
                engine.press(command['button'])
            if hold:
                engine.tick(hold)
            if command['button'] is not None:
                engine.release(command['button'])
            if row['executed_frames'] > hold:
                engine.tick(row['executed_frames'] - hold)
            frame += row['executed_frames']
            assert frame == row['frame']
            if frame in targets:
                index = targets[frame]
                assert digest(engine.screenshot()) == row['screenshot_sha256']
                state = engine.save()
                (destination/f'decision-{index}.state').write_bytes(state)
                (destination/f'decision-{index}.png').write_bytes(engine.screenshot())
                found[index] = {'frame':frame, 'state_sha256':digest(state),
                                'screenshot_sha256':row['screenshot_sha256']}
            if frame >= max(targets):
                break
    finally:
        engine.close()
    assert len(found) == len(targets)
    write_json(destination/'sources.json', {'run':str(run.resolve()), 'decisions':found})
    return manifest['scenario']


def facts(engine):
    return {'party':read_party(engine.memory), 'bag':read_bag(engine.memory),
            'active':engine.memory[0xCC2F], 'battle':engine.memory[0xD057], 'screen':ui_state(engine.memory)}


def verify_case(rom, fixtures, scenario, catalog, output, index, command, argument, *, frame_limit=None):
    engine = RedEngine(rom, (fixtures/f'decision-{index}.state').read_bytes())
    engine.initial_screen = (fixtures/f'decision-{index}.png').read_bytes()
    limits = Limits(max_action_frames=600, **({'max_frames':frame_limit} if frame_limit else {}))
    session = Session(engine, output, scenario, track='gameplay', goal='challenge',
                      gameplay_catalog=catalog, limits=limits, agent={'provider':'controller-verification','model':'none'})
    try:
        before = facts(engine)
        request = {'command':command, 'argument':argument, 'count':1}
        result = execute(session, 'test', request)
        after = facts(engine)
        saved_frame = session.frame
        assert execute(session, 'test', request)['retried']
        assert session.frame == saved_frame and facts(engine) == after
        if frame_limit:
            assert session.reason == 'frame_budget' and session.frame == frame_limit
            assert before['bag'] == after['bag']
        else:
            assert result['shortcut']['completed'], result['outcome']
            if command == 'use_item':
                item, slot = parse_item(argument)
                assert dict(before['bag'])[item] - dict(after['bag']).get(item,0) == 1
                assert result['shortcut']['item_consumed']
                assert [identity(m) for m in before['party']] == [identity(m) for m in after['party']]
                if item == 53:
                    assert after['party'][slot]['hp'] == after['party'][slot]['max_hp'] // 2
                if item == 82:
                    assert sum(after['party'][slot]['pp']) > sum(before['party'][slot]['pp'])
                if item == 16 and not before['battle']:
                    assert after['party'][slot]['hp'] == after['party'][slot]['max_hp']
                    assert after['party'][slot]['status'] == 0
            elif before['battle']:
                assert after['active'] == int(argument) - 1
            else:
                expected = [identity(m) for m in before['party']]
                slot = int(argument) - 1
                expected[0], expected[slot] = expected[slot], expected[0]
                assert [identity(m) for m in after['party']] == expected
            assert after['screen']['kind'] == ('battle_menu' if before['battle'] else 'overworld')
        session.finish('verification_complete')
    finally:
        session.close()
    proof = replay(rom, output)
    return {'source_decision':index, 'request':request, 'result':result,
            'before':before, 'after':after, 'replay':proof, 'frame_limit':frame_limit}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--rom', type=Path, required=True)
    parser.add_argument('--run', type=Path, required=True)
    parser.add_argument('--game-data', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=False)
    fixtures = args.output/'fixtures'
    fixtures.mkdir()
    scenario = extract(args.rom,args.run,fixtures)
    catalog = load_catalog(args.game_data)
    cases = []
    for i,(index,command,argument) in enumerate(CASES):
        cases.append(verify_case(args.rom,fixtures,scenario,catalog,args.output/f'case-{i+1:02d}',index,command,argument))
        write_json(args.output/'verification.json', {'cases':cases, 'complete':False})
        print(index,command,argument,'verified',flush=True)
    cases.append(verify_case(args.rom,fixtures,scenario,catalog,args.output/'budget-stop',30,'use_item','Full Restore:1',frame_limit=50))
    write_json(args.output/'verification.json', {'cases':cases, 'complete':True, 'model_calls':0})
    print(f'{len(cases)} cases passed with exact controller replays. No model calls.')


if __name__ == '__main__':
    main()
