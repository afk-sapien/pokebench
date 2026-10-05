"""Offline tactical validation using the public observation and controller interface."""
import argparse
from concurrent.futures import ProcessPoolExecutor
import json
from pathlib import Path
import random
import shutil

from pokeagent_bench.core import Limits, digest, write_json
from pokeagent_bench.gameplay import load_catalog, observe_gameplay
from pokeagent_bench.gameplay_commands import execute
from pokeagent_bench.session import Session, load_engine, replay
from prepare_basic_fixtures import save_fixture
import prepare_tactical_fixture as builder

MODES = ('tactical', 'attack-first', 'type-aware-attacker')
POLICY_SHA256 = digest(Path(__file__).read_bytes())
DEV_OFFSETS = (131, 197, 251, 307, 373, 439, 503, 571)


def request(kind, argument=''):
    return {'command': kind, 'argument': str(argument), 'count': 1}


class Policy:
    """No emulator, evaluator, RNG or enemy memory access is available here."""
    def __init__(self, mode):
        self.mode = mode
        self.boosts = 0
        self.active_slot = None
        self.last_move = None

    def feedback(self, before, command, result):
        active = before['party'][before['battle'].get('active_party_slot', 1)-1]
        pages = result.get('dialogue', {}).get('pages', [])
        text = ' '.join(pages).upper()
        if command['command'] == 'use_move':
            move = next(m for m in active['moves'] if m['slot'] == int(command['argument']))
            if (move['id'] == 133 and active['nickname'].upper()+"'S SPECIAL" in text
                    and 'SPECIAL GREATLY ROSE' in text):
                self.boosts = min(3, self.boosts + 1)

    def power(self, mon, move, opponent):
        if move['id'] == 101:
            return mon['level']
        if move['id'] == 138:
            return 0
        value = move['power']
        if move['type'] in mon['types']:
            value *= 1.5
        if move['type'] == 'Electric' and opponent in ('DEWGONG','CLOYSTER','SLOWBRO','LAPRAS'):
            value *= 2
        if move['type'] == 'Water' and opponent in ('DEWGONG','CLOYSTER','SLOWBRO','LAPRAS'):
            value *= .5
        return value

    def choose(self, view):
        party, battle, screen = view['party'], view['battle'], view['screen']
        slot = battle.get('active_party_slot', 1)
        active = party[slot-1]
        if slot != self.active_slot:
            self.boosts = 0
            self.active_slot = slot
        hud = ' '.join(battle.get('visible_hud', [])).upper()
        opponent = next((name for name in ('DEWGONG','CLOYSTER','SLOWBRO','JYNX','LAPRAS') if name in hud), '')
        asleep = 'SLP' in hud
        afflicted = asleep or any(status in hud for status in ('PAR','FRZ','PSN','BRN'))
        alive = [m for m in party if m['hp'] > 0 and m['slot'] != slot]
        moves = [m for m in active['moves'] if m['pp'] > 0]
        def available(move_id):
            return next((m for m in moves if m['id'] == move_id), None)
        def use(move_id):
            return request('use_move', available(move_id)['slot'])
        def attack(mon):
            return max((self.power(mon,m,opponent) for m in mon['moves'] if m['pp']), default=0)
        if screen['kind'] not in ('battle_menu', 'move_menu'):
            if 'NO' in screen['visible_choices']:
                return request('choose', 'NO')
            if any('Bring out which' in t for t in screen['text']) or screen['kind']=='party_menu':
                if alive:
                    replacement = (max(alive,key=attack) if self.mode=='type-aware-attacker'
                                   else min(alive,key=lambda m:m['slot']))
                    return request('switch_pokemon',replacement['slot'])
            if screen['kind']=='menu':
                return request('press','a')
            return request('advance_dialogue')
        bag = {item['id']:item['quantity'] for item in view['bag']}
        damaging = [m for m in moves if self.power(active,m,opponent)>0]
        if self.mode=='type-aware-attacker' and alive:
            best = max(alive,key=attack)
            if attack(best)>attack(active)*1.6:
                return request('switch_pokemon',best['slot'])
        if self.mode=='tactical':
            if active['species'] in ('Poliwhirl','Poliwrath'):
                pp = {m['id']:m['pp'] for m in active['moves']}
                if bag.get(82) and (pp.get(57,0)<=1 or pp.get(156,0)<=1):
                    return request('use_item',f'Elixer:{slot}')
                awake = 'asleep' not in active['status']
                ratio = active['hp']/active['max_hp']
                if awake and ratio < .6 and available(156):
                    return use(156)
                if awake and self.boosts < 3:
                    if not afflicted and ratio > .6 and available(95):
                        return use(95)
                    if available(133):
                        return use(133)
                if available(57):
                    return use(57)
            elif active['species']=='Haunter':
                if asleep and active['hp'] < active['max_hp']*.7 and available(138):
                    return use(138)
                if not afflicted and available(95):
                    return use(95)
            elif active['species']=='Pikachu':
                if not afflicted and available(86):
                    return use(86)
        if damaging:
            return request('use_move',max(damaging,key=lambda m:self.power(active,m,opponent))['slot'])
        if bag.get(82):
            return request('use_item',f'Elixer:{slot}')
        if alive:
            useful = [m for m in alive if attack(m)>0]
            if useful:
                return request('switch_pokemon',max(useful,key=attack)['slot'])
        if moves:
            return request('use_move',moves[0]['slot'])
        return request('choose','FIGHT')


def run_one(args):
    rom, game_data, scenario, output, mode = args
    engine, manifest = load_engine(Path(rom),Path(scenario))
    session = Session(engine,Path(output),manifest,track='gameplay',goal='challenge',
                      gameplay_catalog=load_catalog(Path(game_data)),
                      limits=Limits(max_actions=25000,max_frames=150000,max_action_frames=600,max_dialogue_frames=7200),
                      agent={'provider':'offline-public-observation-calibration','model':mode,
                             'policy_sha256':POLICY_SHA256})
    policy = Policy(mode)
    invalid = 0
    choices = []
    try:
        for index in range(350):
            if session.reason:
                break
            view = observe_gameplay(session)
            command = policy.choose(view)
            if command['command']=='use_move':
                active=view['party'][view['battle']['active_party_slot']-1]
                move=next(m for m in active['moves'] if m['slot']==int(command['argument']))
                if move['pp']<=0:
                    raise ValueError('Policy requested an exhausted move')
            result=execute(session,str(index),command)
            policy.feedback(view,command,result)
            invalid += result['end_frame']==result['start_frame']
            choices.append({'observation':view,'request':command,'result':result,'boosts':policy.boosts})
            if invalid >= 3:
                session.finish('calibration_invalid_actions')
                break
        if not session.reason:
            session.finish('calibration_limit')
    finally:
        write_json(Path(output)/'public-decisions.json',choices)
        session.close()
    result=json.loads((Path(output)/'result.json').read_text())
    proof=replay(Path(rom),Path(output))
    summary={'mode':mode,'scenario':Path(scenario).name,'completed':result['completed'],
             'reason':result['stop_reason'],'invalid_actions':invalid,'decisions':len(choices),'replay':proof}
    write_json(Path(output)/'calibration.json',summary)
    return summary


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--rom',type=Path,required=True)
    parser.add_argument('--game-data',type=Path,required=True)
    parser.add_argument('--source',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--candidate',choices=['original','wrath45','wrath48','wrath50','poli50','wrath50-thundershock'],required=True)
    parser.add_argument('--split',choices=['development','holdout'],default='development')
    parser.add_argument('--workers',type=int,default=4)
    parser.add_argument('--limit',type=int)
    parser.add_argument('--seed',type=int,default=20261003)
    parser.add_argument('--exclude-registration',type=Path,action='append',default=[])
    args=parser.parse_args()
    args.output.mkdir(parents=True,exist_ok=False)
    excluded=set()
    for registration in args.exclude_registration:
        excluded.update(json.loads(registration.read_text())['offsets'])
    pool=[n for n in range(1000,20000) if n not in excluded]
    offsets=list(DEV_OFFSETS) if args.split=='development' else random.Random(args.seed).sample(pool,32)
    if args.limit:
        offsets=offsets[:args.limit]
    policy_copy=args.output/'frozen-policy.py'
    shutil.copyfile(Path(__file__),policy_copy)
    prereg={'candidate':args.candidate,'split':args.split,'offsets':offsets,'modes':MODES,
            'policy_sha256':digest(policy_copy.read_bytes()),'model_calls':0,
            'sampling_seed':args.seed,'excluded_offsets':sorted(excluded),
            'criterion':'32 holdout starts. Tactical wins at least 29. Gap over each attack baseline at least 13 wins. No invalid actions or missing trials.',
            'sampling':'Fixed timing variants, not a guarantee of independent random samples'}
    prereg['gate_revision']='Frozen after development, before evaluating any holdout start'
    write_json(args.output/'preregistration.json',prereg)
    builder.ROM,builder.DATA,builder.SOURCE=args.rom,args.game_data,args.source
    builder.CAT=load_catalog(args.game_data)
    builder.S=json.loads((args.game_data/'bundles'/json.loads((args.game_data/'current.json').read_text())['bundle']/'strategy.json').read_text())
    original=list(builder.TEAM)
    level={'wrath45':45,'wrath48':48,'wrath50':50,'poli50':50,'wrath50-thundershock':50}.get(args.candidate,45)
    species=111 if args.candidate.startswith('wrath') else 110
    team=[(species,level,(95,133,57,156)),*original[1:]]
    if args.candidate=='wrath50-thundershock':
        team[1]=(84,45,(84,86,98,97))
    prereg['team']=team
    write_json(args.output/'preregistration.json',prereg)
    # This module only builds new private offline fixtures. Registered v1 remains unchanged.
    builder.TEAM=team
    builder.validate_team=lambda memory: None
    builder.build(args.output/'base')
    jobs=[]
    for index,offset in enumerate(offsets,1):
        engine,manifest=load_engine(args.rom,args.output/'base')
        engine.tick(offset)
        scenario=args.output/f'start-{index:03d}'
        save_fixture(engine,manifest,scenario,manifest['objective'],
                     {**manifest['provenance'],'split':args.split,'offset_frames':offset})
        engine.close()
        for mode in MODES:
            jobs.append((str(args.rom),str(args.game_data),str(scenario),str(args.output/'runs'/f'{index:03d}-{mode}'),mode))
    results=[]
    with ProcessPoolExecutor(max_workers=args.workers) as pool:
        for result in pool.map(run_one,jobs):
            results.append(result)
            write_json(args.output/'results.json',{'registration':prereg,'results':results})
            print(result['scenario'],result['mode'],result['completed'],result['reason'],flush=True)
    print({mode:sum(r['completed'] for r in results if r['mode']==mode) for mode in MODES},flush=True)


if __name__=='__main__':
    main()
