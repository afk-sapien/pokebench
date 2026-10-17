"""Build concrete catalog starts from archived states in a separate private directory."""
from __future__ import annotations

import argparse
from pathlib import Path

from pokeagent_bench.catalog_fixtures import (
    read, load_source, set_party, set_bag, set_event, command, save, snapshot, walk_to, set_active_box,
)
from pokeagent_bench.core import digest, write_json
from pokesim_core.gen1 import W_BADGES




def mon(species, level, moves, **kw):
    return {'species': species, 'level': level, 'moves': moves, **kw}


SQUIRTLE = [mon('SQUIRTLE', 10, [33, 39, 145])]
WARTORTLE = [mon('WARTORTLE', 20, [33, 39, 145, 55])]
NIDOKING = [mon('NIDOKING', 50, [70, 57, 24, 30])]
BULBA = mon('BULBASAUR', 10, [33, 45, 73], max_hp=29)
PIKA = mon('PIKACHU', 13, [84, 45, 39, 86], max_hp=35)
PIDGEY = mon('PIDGEY', 7, [16, 28], max_hp=23)
PARTY = [BULBA, PIKA, PIDGEY]
BASIC_BAG = [[20, 5], [11, 2], [4, 10]]


def archive(event, map_id, **kw):
    return {'archive': event, 'map_id': map_id, **kw}


RECIPES = {
    'navigation-forest-crossing': archive(44, 51, position=[17,47], party=SQUIRTLE, bag=BASIC_BAG, money=300),
    'navigation-branching-cave': archive(109, 59, position=[14,35], party=WARTORTLE, bag=[[20,10],[11,3],[29,1]], money=1000),
    'navigation-warp-puzzle': archive(591, 178, position=[8,17], party=NIDOKING, bag=[[84,20]], events={**{f'EVENT_BEAT_SAFFRON_GYM_TRAINER_{i}':True for i in range(7)}}),
    'navigation-spinning-floors': archive(381, 200, position=[27,8], party=NIDOKING, bag=[[84,20]], events={'EVENT_BEAT_ROCKET_HIDEOUT_2_TRAINER_0':True}),
    'navigation-boulder-puzzle': archive(740, 108, position=[8,17], party=NIDOKING, bag=[[84,20]], events={'EVENT_BEAT_VICTORY_ROAD_1_TRAINER_0':True,'EVENT_BEAT_VICTORY_ROAD_1_TRAINER_1':True,'EVENT_VICTORY_ROAD_1_BOULDER_ON_SWITCH':False}),
    'navigation-multifloor-required-stops': archive(364, 122, position=[16,7], party=NIDOKING, bag=[[84,20]], money=0),
    'objectives-npc-instruction': archive(199,88,position=[2,7],party=WARTORTLE,bag=[[20,5]]),
    'operations-restore-move-pp': archive(150,35,position=[10,35],party=[mon('SQUIRTLE',15,[33,39,145,55],pp=[35,30,8,5]),PIDGEY],bag=[[80,1],[20,1],[4,5]]),
    'operations-teach-tm-replace-move': archive(344,6,position=[49,11],party=PARTY,bag=[[234,1],[20,1],[4,3]]),
    'operations-cure-poison': archive(18,1,party=[BULBA,PIDGEY,mon('NIDORAN_M',9,[33,43],max_hp=28,hp=18,status=8)],bag=[[11,1],[20,2],[4,4]],path=[('down',2)]),
    'operations-party-reorder': archive(66,2,party=PARTY,bag=[[20,1],[4,3]],path=[('down',2)]),
    'operations-withdraw-item-and-use': archive(18,41,position=[13,4],party=[BULBA,{**PIKA,'hp':10},PIDGEY],bag=[[11,1],[4,3]],walk=[13,4],pc_items=[[20,1],[11,1]]),
    'operations-menu-checklist': archive(18,41,position=[13,4],party=[BULBA,{**PIKA,'hp':10},PIDGEY],bag=[[11,1],[4,3]],walk=[13,4],pc_items=[[20,1],[11,1]]),
    'objectives-find-capture-species': archive(18,41,position=[3,7],party=SQUIRTLE,bag=BASIC_BAG,money=300),
    'objectives-starter-selection': archive(3,40,party=[],bag=[],money=3000,starter_dialogue=True),
}

RECIPES.update({
    'navigation-town-landmark': archive(18,1,position=[29,20],party=SQUIRTLE,bag=BASIC_BAG,money=300,path=[('down',2)],walk=[29,20]),
    'navigation-blocked-route-alternative': archive(212,16,position=[10,28],party=WARTORTLE,bag=[[19,5],[11,2]],money=0,walk=[10,28],badges=3,events={**{f'EVENT_BEAT_ROUTE_6_TRAINER_{i}':True for i in range(6)}}),
    'operations-heal-potion-target': archive(12,12,position=[11,3],party=[BULBA,{**PIKA,'hp':12},PIDGEY],bag=[[20,1],[11,1],[4,3]],walk=[11,3]),
    'operations-buy-pokeballs': archive(18,1,position=[29,20],party=[BULBA],bag=[[20,1],[11,1]],money=2000,path=[('down',2)],walk=[29,20]),
    'objectives-infeasible-plan-alternate': archive(1729,66,position=[4,2],party=WARTORTLE,bag=[[20,5]],money=3000,walk=[4,2],face='right',badges=3,events={'EVENT_GOT_BIKE_VOUCHER':False,'EVENT_GOT_BICYCLE':False}),
    'objectives-recover-earlier-mistake': archive(1729,66,position=[4,2],party=WARTORTLE,bag=[[45,1],[20,1],[11,1],[14,1],[12,1],[13,1],[15,1],[29,1],[30,1],[19,1],[4,1],[3,1],[2,1],[65,1],[66,1],[67,1],[68,1],[55,1],[56,1],[46,1]],money=0,walk=[4,2],face='right',events={'EVENT_GOT_BICYCLE':False}),
})

RECIPES.update({
    'operations-deposit-withdraw': archive(18,41,position=[13,4],party=PARTY,bag=[[20,1]],walk=[13,4],box=[mon('RATTATA',5,[33,39],max_hp=18)]),
    'battle-prepared-gym': archive(68,54,party=[mon('SQUIRTLE',15,[145,33,39,55]),mon('PIDGEY',12,[16,28,98])],bag=[[20,2]],walk=[4,2],battle=True),
    'battle-preserve-specialist': {'source':'data/decision-v1-sources-v2/champion','map_id':120,'party':[mon('JOLTEON',55,[85,86,24,42]),mon('LAPRAS',55,[57,58,109,34]),mon('SNORLAX',55,[34,89,156,133])],'bag':[[18,2],[16,1]],'battle':True},
    'battle-losing-midbattle-recovery': {'source':'data/decision-v1-sources-v2/agatha','map_id':247,'party':[mon('JYNX',55,[94,58,142,156]),mon('ALAKAZAM',55,[94,105,86,115]),mon('RHYDON',55,[89,157,34,164])],'bag':[[18,1],[16,1]],'hp_fraction':0.3,'battle':True},
})

RECIPES.update({
    'objectives-parcel-roundtrip': archive(12,0,position=[12,12],party=SQUIRTLE,bag=[[20,5]],money=3000,path=[('down',2)],walk=[12,12]),
    'objectives-prerequisite-chain': archive(336,4,position=[14,6],party=[mon('KADABRA',35,[60,93,105,50]),mon('WARTORTLE',35,[55,44,145,110])],bag=[[72,1],[19,10],[53,3],[11,5]],money=0,walk=[14,6],events={'EVENT_BEAT_POKEMON_TOWER_RIVAL':True}),
    'objectives-quest-trainer': archive(376,6,party=[mon('CHARMELEON',31,[52,43,99,10]),mon('KADABRA',29,[100,93,50,60]),mon('GYARADOS',28,[33,44,43,82])],bag=[[19,4],[11,2],[29,1]],money=6200,badges=7,path=[('down',2)]),
    'objectives-capture-prepare-battle': archive(150,3,party=[mon('IVYSAUR',20,[33,45,73,22]),mon('PIDGEOTTO',18,[16,28,98]),mon('PIKACHU',18,[84,45,39,98])],bag=[[4,8],[20,2],[11,1]],money=2400,badges=1,path=[('down',2)],events={'EVENT_BEAT_CERULEAN_RIVAL':True}),
})

POST_PARCEL_SOURCE = 'data/red-ability-v4/fixtures/buy-pokeballs'
RECIPES['navigation-town-landmark'].update(source=POST_PARCEL_SOURCE, path=[])
RECIPES['operations-buy-pokeballs'].update(source=POST_PARCEL_SOURCE, path=[])
RECIPES['objectives-find-capture-species'].update(source=POST_PARCEL_SOURCE, position=[3,3], route=[{'walk':[23,26]}, {'button':'up','hold_frames':8,'release_frames':90}, {'walk':[3,3]}])
for key in ('operations-party-reorder','operations-cure-poison'):
    RECIPES[key]['settle_after_path'] = 60

# Existing starts have already been prepared with the exact listed team.
REUSE = {
    'battle-unfavorable-lead': 'data/decision-v1-curation/bad-matchup/variant-01',
    'battle-underleveled-status-setup': 'data/tactical-lorelei-v2/variant-01',
    'battle-restricted-pp': 'data/decision-v1-curation/pp-gauntlet/variant-01',
    'objectives-constrained-valuable-capture': 'data/decision-v1-curation/healthy-capture/variant-01',
    'battle-league-balanced': 'data/red-ability-v4/fixtures/league',
    'battle-league-constrained': 'data/red-ability-v7/fixtures/league-hard',
    'campaign-full-game': 'scenarios/starter-v010',
}


def step(engine, direction, count, trace):
    for _ in range(count):
        before = snapshot(engine)['state']['location']
        trace.append(command(engine, direction, 8, 24))
        after = snapshot(engine)['state']['location']
        if before == after:
            raise ValueError(f'Construction movement blocked: {direction} at {before}')


def build(args, key, entry, strategy):
    if key in REUSE:
        folder = args.root / REUSE[key]
        source = folder / 'initial.state'
        engine, provenance = load_source(args.rom, source)
        original = read(folder / 'scenario.json')
        if original['state_sha256'] != digest(source.read_bytes()):
            raise ValueError('Archived source digest mismatch')
        provenance['source_manifest'] = original
        recipe = {'map_id': engine.structured()['location']['map_id']}
    else:
        recipe = RECIPES[key]
        source = args.root / recipe['source'] / 'initial.state' if 'source' in recipe else args.archive / f'event-{recipe["archive"]}.state'
        engine, provenance = load_source(args.rom, source, 0 if 'source' in recipe else 90)
    trace = []
    try:
        if key in RECIPES:
            # Walk before installing a poisoned or injured party.
            for direction, count in recipe.get('path', []):
                step(engine, direction, count, trace)
            for segment in recipe.get('route', []):
                if 'walk' in segment:
                    trace.extend(walk_to(engine, *segment['walk'], limit=2000))
                else:
                    trace.append(command(engine, segment['button'], segment['hold_frames'], segment['release_frames']))
            if recipe.get('settle_after_path'):
                trace.append(command(engine, None, 0, recipe['settle_after_path']))
            if 'walk' in recipe:
                trace.extend(walk_to(engine, *recipe['walk'], limit=2000))
            if 'face' in recipe:
                trace.append(command(engine, recipe['face'], 1, 12))
            if 'party' in recipe:
                set_party(engine, strategy, recipe['party'])
            if 'box' in recipe:
                set_active_box(engine, strategy, recipe['box'])
            if 'hp_fraction' in recipe:
                from pokesim_core.gen1 import W_PARTY_MONS
                hp = int(engine.structured()['party'][0]['max_hp'] * recipe['hp_fraction'])
                engine.memory[W_PARTY_MONS+1] = hp >> 8
                engine.memory[W_PARTY_MONS+2] = hp & 255
            if 'bag' in recipe:
                set_bag(engine, recipe['bag'], recipe.get('money'))
            for name, value in recipe.get('events', {}).items():
                set_event(engine, strategy, name, value)
            if 'badges' in recipe:
                engine.memory[W_BADGES] = recipe['badges']
            if key == 'navigation-branching-cave':
                engine.memory[W_BADGES] = 1
            if key == 'navigation-boulder-puzzle':
                engine.memory[W_BADGES] = 255
            if 'pc_items' in recipe:
                # Native Red wNumBoxItems and wBoxItems, not Pokemon storage.
                engine.memory[0xD53A] = len(recipe['pc_items'])
                for i, (item, quantity) in enumerate(recipe['pc_items']):
                    engine.memory[0xD53B+2*i] = item
                    engine.memory[0xD53C+2*i] = quantity
                engine.memory[0xD53B+2*len(recipe['pc_items'])] = 255
            if recipe.get('starter_dialogue'):
                for _ in range(100):
                    asked = strategy['events']['EVENT_OAK_ASKED_TO_CHOOSE_MON']
                    from pokesim_core.gen1 import W_EVENT_FLAGS
                    if engine.memory[W_EVENT_FLAGS+asked//8] & (1 << (asked % 8)):
                        break
                    trace.append(command(engine, 'a'))
                else:
                    raise ValueError('Oak did not reach starter choice')
            if recipe.get('battle'):
                if 'source' in recipe:
                    for action in read(args.root / recipe['source'] / 'entry-commands.json'):
                        trace.append(command(engine, action['button'], action['hold_frames'], action['release_frames']))
                for _ in range(100):
                    if snapshot(engine)['ui'] == 'battle_menu':
                        break
                    trace.append(command(engine, 'a'))
                else:
                    raise ValueError('Could not reach initial battle menu')
            provenance['offline_setup'] = recipe
            provenance['setup_writes'] = 'Own party, bag, PC items and explicitly listed initial event flags only. No writes during evaluation.'
        expected = {'map_id': recipe['map_id'], 'ui': 'battle_menu' if (key in REUSE and 'league' not in key and key != 'campaign-full-game') or recipe.get('battle') else 'overworld'}
        if recipe.get('position') and not recipe.get('battle'):
            expected['position'] = recipe['position']
        if 'party' in recipe:
            expected['party'] = engine.structured()['party']
        if 'bag' in recipe:
            expected['inventory'] = engine.structured()['inventory']
        from pokeagent_bench.navigation_conditions import AFFECTED, prepare
        if key in AFFECTED:
            provenance['navigation_setup'] = prepare(engine, key, strategy)
        provenance['setup_commands'] = trace
        provenance['builder_sha256'] = digest(Path(__file__).read_bytes())
        return save(engine, args.rom, entry, args.output / key, provenance, expected)
    finally:
        engine.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, required=True, help='Private benchmark data root')
    parser.add_argument('--archive', type=Path, required=True, help='Saved adventure states directory')
    parser.add_argument('--rom', type=Path, required=True)
    parser.add_argument('--game-data', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--tasks', nargs='+')
    args = parser.parse_args()
    current = read(args.game_data / 'current.json')['bundle']
    strategy = read(args.game_data / 'bundles' / current / 'strategy.json')
    catalog = Path(__file__).resolve().parents[1] / 'src/pokeagent_bench/catalogs'
    entries = {e['id']: e for p in catalog.glob('*.json') for e in read(p)['evals'] if e.get('active', True)}
    args.output.mkdir(parents=True, exist_ok=True)
    report_path = args.output / 'fixture-build.json'
    report = read(report_path) if report_path.exists() else {'fixtures': {}, 'pending': {}}
    for key in args.tasks or sorted((set(RECIPES) | set(REUSE)) & entries.keys()):
        if (args.output / key / 'scenario.json').exists():
            continue
        try:
            report['fixtures'][key] = build(args, key, entries[key], strategy)
            report['pending'].pop(key, None)
            print('Built', key, flush=True)
        except (ValueError, FileNotFoundError, KeyError) as error:
            report['pending'][key] = str(error)
            print('Pending', key, str(error), flush=True)
        write_json(report_path, report)
    for key, entry in entries.items():
        if key not in report['fixtures'] and entry.get('tested_skill') != 'preparation':
            report['pending'].setdefault(key, 'Exact source checkpoint and controller reference still required')
    write_json(report_path, report)
    write_json(args.output / 'bindings.json', report['fixtures'])


if __name__ == '__main__':
    main()
