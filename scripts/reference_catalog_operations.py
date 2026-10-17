"""Record native input references for the ten manual menu operation tasks."""
import argparse
from pathlib import Path

from pokesim_core.shortcuts.actions import (
    UseItem, ReorderParty, SwitchPokemon, DepositPokemon, WithdrawPokemon,
    WithdrawItem, BuyItem,
)
from pokesim_core.shortcuts.machine import Done
from pokesim_core.shortcuts.screens import current_screen
from pokeagent_bench.catalog_fixtures import load_source, command, snapshot, read, walk_to
from pokeagent_bench.catalog_runtime import CatalogEvaluator, catalog_evidence
from pokeagent_bench.gameplay import ui_state
from pokeagent_bench.core import write_json, digest


def cases():
    options = {'version': 'red'}
    return {
        'operations-heal-potion-target': [UseItem(20, 1, **options)],
        'operations-cure-poison': [UseItem(11, 2, **options)],
        'operations-restore-move-pp': [UseItem(80, 0, 3, **options)],
        'operations-battle-switch': [SwitchPokemon(2, **options)],
        'operations-party-reorder': [ReorderParty(0, 2, **options), ReorderParty(1, 2, **options)],
        'operations-buy-pokeballs': [BuyItem(4, 10, **options)],
        'operations-deposit-withdraw': [DepositPokemon(1, **options), WithdrawPokemon(1, **options), ReorderParty(1, 2, **options)],
        'operations-teach-tm-replace-move': [UseItem(234, 1, forget_move=1, **options)],
        'operations-withdraw-item-and-use': [WithdrawItem(20, 1, **options), UseItem(20, 1, **options)],
        'operations-menu-checklist': [WithdrawItem(20, 1, **options), UseItem(20, 1, **options), ReorderParty(0, 2, **options), ReorderParty(1, 2, **options)],
    }


def run(rom, root, key, machines):
    folder = root / key
    engine, _ = load_source(rom, folder / 'initial.state')
    evaluator = CatalogEvaluator(catalog_evidence(engine, key), read(folder / 'scenario.json')['objective'])
    before = snapshot(engine)
    actions = []
    frame = 0

    def advance(button, hold=8, release=24):
        nonlocal frame
        evaluator.observe_input(button, catalog_evidence(engine, key))
        actions.append(command(engine, button, hold, release))
        frame += hold + release
        evaluator.observe(catalog_evidence(engine, key), frame, 0)

    outcomes = []
    try:
        if key == 'operations-buy-pokeballs':
            advance('up')
            advance('up')
            advance(None, 0, 90)
            original = engine.save()
            route = walk_to(engine, 2, 5)
            engine.load(original)
            for action in route:
                advance(action['button'], action['hold_frames'], action['release_frames'])
            advance('left', 1, 12)
        target_menu = 'mart' if key == 'operations-buy-pokeballs' else 'pc'
        if key in ('operations-buy-pokeballs', 'operations-deposit-withdraw', 'operations-withdraw-item-and-use', 'operations-menu-checklist'):
            if target_menu == 'pc':
                advance('up', 1, 12)
            for _ in range(50):
                if current_screen(engine.memory, ui_state(engine.memory), version='red') == target_menu:
                    break
                advance('a')
            if target_menu == 'pc':
                submenu = 'bills_pc' if key == 'operations-deposit-withdraw' else 'players_pc'
                if submenu == 'players_pc':
                    advance('down')
                for _ in range(40):
                    if current_screen(engine.memory, ui_state(engine.memory), version='red') == submenu:
                        break
                    advance('a')
        for machine in machines:
            if isinstance(machine, (UseItem, ReorderParty)) and current_screen(engine.memory, ui_state(engine.memory), version='red') in ('pc', 'players_pc', 'bills_pc', 'pc_items', 'pc_party', 'pc_box'):
                for _ in range(50):
                    if ui_state(engine.memory)['kind'] == 'overworld':
                        break
                    advance('b')
            for _ in range(1000):
                result = machine.step(engine.memory, ui_state(engine.memory))
                if isinstance(result, Done):
                    outcomes.append({'completed': result.completed, 'settled': result.settled,
                                     'outcome': result.outcome})
                    break
                advance(result)
            else:
                outcomes.append({'completed': False, 'outcome': 'Reference exceeded 1000 controller inputs'})
                break
            if not result.completed:
                break
        for _ in range(50):
            if ui_state(engine.memory)['kind'] in ('overworld', 'battle_menu'):
                break
            advance('b')
        if key == 'operations-buy-pokeballs' and outcomes and all(outcome['completed'] for outcome in outcomes):
            original = engine.save()
            route = walk_to(engine, 3, 6)
            engine.load(original)
            for action in route:
                advance(action['button'], action['hold_frames'], action['release_frames'])
            advance('down')
            advance('down')
            advance(None, 0, 90)
        advance(None, 0, 1)
        advance(None, 0, 1)
        output = folder / 'reference'
        output.mkdir(exist_ok=True)
        write_json(folder / 'reference-commands.json', actions)
        write_json(output / 'commands.json', actions)
        receipt = {'completed': evaluator.complete(), 'macro_outcomes': outcomes,
                   'before': before, 'after': snapshot(engine),
                   'disqualification': evaluator.disqualification_reason,
                   'initial_state_sha256': digest((folder / 'initial.state').read_bytes()),
                   'controller_only': True, 'frames': frame,
                   'purpose': 'Offline reference. The evaluated agent receives manual buttons only.'}
        write_json(output / 'receipt.json', receipt)
        (output / 'final.state').write_bytes(engine.save())
        print(key, receipt['completed'], outcomes, flush=True)
        return receipt['completed']
    finally:
        engine.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--rom', type=Path, required=True)
    parser.add_argument('--root', type=Path, required=True)
    parser.add_argument('--tasks', nargs='+')
    args = parser.parse_args()
    selected = cases()
    report = {key: run(args.rom, args.root, key, selected[key]) for key in args.tasks or selected}
    write_json(args.root / 'operations-reference-summary.json', report)


if __name__ == '__main__':
    main()
