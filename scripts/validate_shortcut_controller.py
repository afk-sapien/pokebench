"""Exercise restorative shortcuts on a private Gen 1 save without model calls."""
import argparse
from itertools import permutations
from pathlib import Path
import tempfile

from pokecore.gen1 import read_bag, read_party
from pokecore.shortcuts import current_screen
from pokeagent_bench.core import Limits, digest, write_json
from pokeagent_bench.session import Session, load_engine, replay
from pokeagent_bench.gameplay import load_catalog, ui_state
from pokeagent_bench.gameplay_commands import execute
from pokeagent_bench.menu_shortcuts import parse_item, identity, normalize


def run_case(args, catalog, commands, menu, directory):
    engine, original = load_engine(args.rom, args.scenario)
    scenario = dict(original, name='shortcut-controller-regression', action_policy='assisted-gameplay-v1',
                    objective={'kind':'location','map_id':255,'x':0,'y':0,
                               'description':'Offline controller regression, not a scored gameplay trial.'})
    session = Session(engine, directory, scenario, goal='challenge', track='gameplay', gameplay_catalog=catalog,
                      limits=Limits(max_frames=100000, max_actions=10000, max_action_frames=600,
                                    max_dialogue_frames=7200, max_wall_seconds=120))
    records = []
    try:
        if menu != 'overworld':
            execute(session, 'prepare-pause', {'command':'press','argument':'start','count':1})
            if menu in ('bag','party'):
                wanted = 'ITEM' if menu == 'bag' else 'POKEMON'
                option = next(x for x in ui_state(engine.memory)['visible_choices'] if normalize(x) == wanted)
                execute(session, 'prepare-menu', {'command':'choose','argument':option,'count':1})
        for index, argument in enumerate(commands):
            old_party = read_party(engine.memory)
            old_bag = dict(read_bag(engine.memory))
            item, slot = parse_item(argument)
            command = {'command':'use_item','argument':argument,'count':1}
            result = execute(session, str(index), command)
            new_party = read_party(engine.memory)
            new_bag = dict(read_bag(engine.memory))
            assert result['shortcut']['completed'], result
            assert result['shortcut']['item_consumed'], result
            resting = current_screen(engine.memory, version='red')
            assert resting == ('pause' if menu == 'pause' else 'overworld'), result
            assert result['shortcut']['settled'], result
            assert old_bag[item] - new_bag.get(item, 0) == 1
            assert {k:v for k,v in old_bag.items() if k != item} == {k:v for k,v in new_bag.items() if k != item}
            assert [identity(m) for m in old_party] == [identity(m) for m in new_party]
            for other in range(len(old_party)):
                if other != slot:
                    assert new_party[other] == old_party[other]
            if item == 53:
                assert old_party[slot]['hp'] == 0 and new_party[slot]['hp'] > 0
            else:
                assert new_party[slot]['hp'] == new_party[slot]['max_hp']
                if item == 16:
                    assert new_party[slot]['status'] == 0
            frame = session.frame
            retry = execute(session, str(index), command)
            assert retry['retried'] and session.frame == frame
            assert read_party(engine.memory) == new_party and dict(read_bag(engine.memory)) == new_bag
            records.append(dict(request=argument, frames=result['end_frame']-result['start_frame'],
                                completed=True, one_item_consumed=True, correct_target=True, resting_screen=resting, settled=True,
                                retry_did_not_repeat=True))
        assert all(m['hp'] == m['max_hp'] and m['status'] == 0 for m in read_party(engine.memory))
        session.finish('validation_complete')
    finally:
        session.close()
    proof = replay(args.rom, directory)
    return dict(starting_menu=menu, requests=list(commands), checks=records, replay=proof)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--rom', type=Path, required=True)
    parser.add_argument('--scenario', type=Path, required=True)
    parser.add_argument('--game-data', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise ValueError('Refusing to overwrite existing controller evidence')
    catalog = load_catalog(args.game_data)
    recipes = []
    for middle, last in [('Full Restore:2','Max Potion:3'),('Max Potion:2','Full Restore:3')]:
        actions = ('Full Restore:1','Revive:2',middle,last)
        recipes.extend(p for p in permutations(actions) if p.index('Revive:2') < p.index(middle))
    cases = [(recipe,'overworld') for recipe in recipes]
    cases.extend([(tuple(['Revive:2','Full Restore:1','Full Restore:3','Max Potion:2']),menu)
                  for menu in ['pause','bag','party']])
    outcomes = []
    with tempfile.TemporaryDirectory(prefix='pokebench-shortcuts-') as temporary:
        for index, (recipe, menu) in enumerate(cases):
            outcome = run_case(args, catalog, recipe, menu, Path(temporary)/str(index))
            outcomes.append(outcome)
            print(f'Passed {index + 1}/{len(cases)}: {menu} {recipe}', flush=True)
    write_json(args.output, dict(format=1, model_calls=0, fixture_sha256=digest((args.scenario/'initial.state').read_bytes()),
                                cases=outcomes, passed=len(outcomes), attempted=len(cases),
                                limitation='Fixed Gen 1 field-healing fixture. This is not proof of all battle menus or every possible game state.'))


if __name__ == '__main__':
    main()
