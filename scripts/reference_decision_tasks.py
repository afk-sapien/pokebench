"""Offline decision references. Battle policies consume public observations only."""
import argparse
from concurrent.futures import ProcessPoolExecutor
import json
from pathlib import Path

from pokeagent_bench.core import Limits, digest, write_json
from pokeagent_bench.gameplay import load_catalog, observe_gameplay
from pokeagent_bench.gameplay_commands import execute
from pokeagent_bench.session import load_engine, Session, replay
from calibrate_tactical import Policy, request


class DecisionPolicy(Policy):
    def __init__(self, task, mode):
        super().__init__(mode)
        self.task=task
        self.second=False

    def choose(self, view):
        party,battle,screen=view['party'],view['battle'],view['screen']
        slot=battle.get('active_party_slot',1)
        active=party[slot-1]
        hud=' '.join(battle.get('visible_hud',[])).upper()
        if self.task=='healthy-capture':
            if screen['kind'] in ('battle_menu','move_menu'):
                if self.mode=='tactical':
                    if slot!=2 and party[1]['hp']:
                        return request('switch_pokemon',2)
                    if 'SLP' not in hud and active['moves'][0]['pp']:
                        return request('use_move',1)
                    if battle.get('opponent_hp_bar',{}).get('filled_pixels',48)>14 and active['moves'][1]['pp']:
                        return request('use_move',2)
                return request('choose','ITEM')
            ball=next((s for s in screen['visible_choices'] if 'BALL' in s.upper()),None)
            if ball:
                return request('choose',ball)
            if 'NO' in screen['visible_choices']:
                return request('choose','NO')
            if screen['kind']=='party_menu' or any('Bring out which' in t for t in screen['text']):
                return request('switch_pokemon',2)
            return request('advance_dialogue')
        if self.task=='team-rescue' and battle['kind']=='none':
            bag={i['id']:i['quantity'] for i in view['bag']}
            if self.mode=='tactical' and party[0]['species']=='Jynx':
                if party[2]['hp']==0 and bag.get(53):
                    return request('use_item','Revive:3')
                if party[0]['moves'][0]['pp']==0 and bag.get(82):
                    return request('use_item','Elixer:1')
                for mon in (party[2],party[0]):
                    if 0<mon['hp']<mon['max_hp'] and bag.get(17):
                        return request('use_item',f'Max Potion:{mon["slot"]}')
            if self.mode=='tactical' and party[0]['species']!='Jolteon' and party[2]['hp']>0:
                return request('switch_pokemon',3)
            if screen['kind']!='overworld':
                return request('press','b')
            return {'command':'move','argument':'up','count':3}
        if self.task=='pp-gauntlet' and battle['kind']=='none':
            if screen['kind']!='overworld':
                return request('advance_dialogue')
            pos=view['location']
            x,y=pos['x'],pos['y']
            target_x=4 if pos['map_id']==245 else 5
            if x!=target_x:
                return request('move','right' if x<target_x else 'left')
            if pos['map_id']==245 or y>3:
                return {'command':'move','argument':'up','count':min(4,max(1,y-3))}
            if pos['facing']!='up':
                return request('move','up')
            return request('interact')
        fighting=screen['kind'] in ('battle_menu','move_menu')
        if fighting and self.mode=='tactical':
            if self.task=='bad-matchup' and slot==1:
                return request('switch_pokemon',2)
            if self.task=='pp-gauntlet':
                if any(n in hud for n in ('ONIX','HITMONCHAN','HITMONLEE','MACHAMP')):
                    self.second=True
                if self.second:
                    if slot!=2 and party[1]['hp'] and party[1]['moves'][0]['pp']:
                        return request('switch_pokemon',2)
                    if slot==2 and active['moves'][0]['pp']:
                        return request('use_move',1)
            if self.task in ('team-rescue','adaptive-champion'):
                if self.task=='team-rescue':
                    species='Jolteon' if any(n in hud for n in ('GYARADOS','AERODACTYL')) else 'Jynx'
                    desired=next(m['slot'] for m in party if m['species']==species)
                    move=1
                else:
                    desired=(3 if 'EXEGGUTOR' in hud else 2 if any(n in hud for n in ('RHYDON','ARCANINE','CHARIZARD')) else 1)
                    move=3 if 'ALAKAZAM' in hud else 1
                if party[desired-1]['hp'] and desired!=slot:
                    return request('switch_pokemon',desired)
                bag={i['id']:i['quantity'] for i in view['bag']}
                if active['hp'] < active['max_hp']*.55 and bag.get(16):
                    return request('use_item',f'Full Restore:{slot}')
                if active['moves'][move-1]['pp']:
                    return request('use_move',move)
        if self.task in ('team-rescue','adaptive-champion') and not fighting:
            if 'NO' in screen['visible_choices']:
                return request('choose','NO')
            if screen['kind']=='party_menu' or any('Bring out which' in t for t in screen['text']):
                alive=next((m for m in party if m['hp']>0 and m['slot']!=slot),None)
                if alive:
                    return request('switch_pokemon',alive['slot'])
            return request('advance_dialogue')
        return super().choose(view)


def run(args):
    rom,data,scenario,output,key,mode,*extra=args
    initial_wait=extra[0] if extra else 0
    scenario,output=Path(scenario),Path(output)
    e,m=load_engine(Path(rom),scenario)
    session=Session(e,output,m,track='gameplay',goal='challenge',gameplay_catalog=load_catalog(Path(data)),
                    limits=Limits(max_actions=30000,max_frames=200000,max_action_frames=600,max_dialogue_frames=7200),
                    agent={'provider':'offline-reference','model':mode,'policy_sha256':digest(Path(__file__).read_bytes())})
    policy=DecisionPolicy(key,mode)
    choices=[]
    invalid=0
    try:
        if initial_wait:
            session.wait('curation-prefix',initial_wait)
        for i in range(600):
            if session.reason:
                break
            view=observe_gameplay(session)
            command=policy.choose(view)
            result=execute(session,str(i),command)
            policy.feedback(view,command,result)
            choices.append({'observation':view,'request':command,'result':result})
            invalid+=result['end_frame']==result['start_frame']
            if invalid>=3:
                session.finish('invalid_reference_actions')
                break
        if not session.reason:
            session.finish('reference_limit')
    finally:
        write_json(output/'public-decisions.json',choices)
        session.close()
    result=json.loads((output/'result.json').read_text())
    proof=replay(Path(rom),output)
    row={'task':key,'variant':scenario.name,'mode':mode,'completed':result['completed'],'reason':result['stop_reason'],
         'decisions':len(choices),'initial_wait':initial_wait,'invalid_actions':invalid,'replay':proof}
    write_json(output/'calibration.json',row)
    return row


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--rom',required=True)
    parser.add_argument('--game-data',required=True)
    parser.add_argument('--fixtures',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--tasks',nargs='+',required=True)
    parser.add_argument('--modes',nargs='+',default=['tactical','attack-first'])
    parser.add_argument('--variants',type=int,default=1)
    parser.add_argument('--workers',type=int,default=4)
    args=parser.parse_args()
    args.output.mkdir(exist_ok=False,parents=True)
    jobs=[(args.rom,args.game_data,str(args.fixtures/key/f'variant-{variant:02d}'),str(args.output/f'{key}-{variant:02d}-{mode}'),key,mode)
          for key in args.tasks for variant in range(1,args.variants+1) for mode in args.modes]
    results=[]
    with ProcessPoolExecutor(max_workers=args.workers) as pool:
        for row in pool.map(run,jobs):
            results.append(row)
            write_json(args.output/'results.json',results)
            print(row,flush=True)


if __name__=='__main__':
    main()
