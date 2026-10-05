"""Build isolated synthetic teams at authentic prebattle checkpoints."""
import argparse
import json
from pathlib import Path

from pokeagent_bench.core import write_json, digest
from pokeagent_bench.session import load_engine
from pokeagent_bench.decision_tasks import TASKS, DESCRIPTIONS, TEAMS, BAGS, OFFSETS, check_start
from pokesim_core.gen1 import W_NUM_BAG_ITEMS, W_BAG_ITEMS, W_PARTY_MONS
from pokeagent_bench.gameplay import ui_state
from prepare_basic_fixtures import advance, save_fixture
import prepare_tactical_fixture as party_builder


def build(root, rom, data, output, key):
    task=next(t for t in TASKS if t['id']==key)
    locations={'bad-matchup':'lorelei','team-rescue':'lance-stable','pp-gauntlet':'lorelei','adaptive-champion':'champion'}
    source=(root/'data/decision-v1-sources-v2'/locations[key] if key in locations else
            root/'data/decision-v1-sources/snorlax' if key=='healthy-capture' else root/'data/decision-v1-sources-v2/route')
    engine,manifest=load_engine(rom,source)
    assert engine.memory[0xD057]==0
    strategy=data/'bundles'/json.loads((data/'current.json').read_text())['bundle']/'strategy.json'
    party_builder.S=json.loads(strategy.read_text())
    if key in TEAMS:
        party_builder.TEAM=TEAMS[key]
        party_builder.party(engine)
    bag=BAGS[key]
    engine.memory[W_NUM_BAG_ITEMS]=len(bag)
    for index,(item,count) in enumerate(bag):
        engine.memory[W_BAG_ITEMS+2*index]=item
        engine.memory[W_BAG_ITEMS+2*index+1]=count
    engine.memory[W_BAG_ITEMS+2*len(bag)]=255
    if key=='team-rescue':
        for slot in (1,2):
            engine.memory[W_PARTY_MONS+44*slot+1]=0
            engine.memory[W_PARTY_MONS+44*slot+2]=0
        engine.memory[W_PARTY_MONS+1]=0
        engine.memory[W_PARTY_MONS+2]=35
        engine.memory[W_PARTY_MONS+29]=0
    if key=='pp-gauntlet':
        engine.memory[W_PARTY_MONS+31]=4
        engine.memory[W_PARTY_MONS+44+29]=5
    if key=='recovery-detour':
        engine.memory[W_PARTY_MONS+4]=8
        engine.memory[W_PARTY_MONS+1]=0
        engine.memory[W_PARTY_MONS+2]=4
    if key not in ('team-rescue','recovery-detour'):
        for command in json.loads((source/'entry-commands.json').read_text()):
            advance(engine,command)
        for _ in range(30):
            if ui_state(engine.memory)['kind']=='battle_menu':
                break
            advance(engine,{'button':'a','hold_frames':8,'release_frames':24})
    check_start(task,engine)
    base=engine.save()
    for index,offset in enumerate(OFFSETS,1):
        engine.load(base)
        if offset:
            engine.tick(offset)
        check_start(task,engine)
        save_fixture(engine,manifest,output/key/f'variant-{index:02d}',{**task['objective'],'description':DESCRIPTIONS[key]},
                     {'synthetic_team':key in TEAMS,'synthetic_status':key=='recovery-detour',
                      'source':str(source),'source_state_sha256':manifest['state_sha256'],
                      'team':TEAMS.get(key),'bag':bag,'offset_frames':offset,
                      'setup_memory_writes':'Own party and bag before battle only. No enemy or RNG edits.',
                      'builder_sha256':digest(Path(__file__).read_bytes())})
    engine.close()
    print('Built',key,flush=True)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root',type=Path,default=Path.cwd())
    parser.add_argument('--rom',type=Path,required=True)
    parser.add_argument('--game-data',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--tasks',nargs='+',default=[t['id'] for t in TASKS])
    args=parser.parse_args()
    for key in args.tasks:
        build(args.root,args.rom,args.game_data,args.output,key)
    write_json(args.output/'build.json',{'tasks':args.tasks,'variants':list(OFFSETS)})


if __name__=='__main__':
    main()
