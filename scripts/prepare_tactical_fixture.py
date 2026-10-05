"""Curate a synthetic tactical team before battle, then calibrate through controls only."""
import argparse
import json
from pathlib import Path
from pokeagent_bench.core import Limits, write_json, digest
from pokeagent_bench.tactical import TEAM, TIMING_OFFSETS, validate_team
from pokeagent_bench.session import Session, load_engine, replay
from pokeagent_bench.gameplay import load_catalog, ui_state
from pokeagent_bench.gameplay_commands import execute
from pokesim_core.gen1 import read_party, W_PARTY_COUNT, W_PARTY_SPECIES, W_PARTY_MONS, W_PARTY_NICKS, W_NUM_BAG_ITEMS, W_BAG_ITEMS
from pokesim_core.gen1_ui import read_battler
from prepare_basic_fixtures import advance, save_fixture

def party(engine):
 m=engine.memory
 m[W_PARTY_COUNT]=len(TEAM)
 for i in range(6):
  m[W_PARTY_SPECIES+i]=TEAM[i][0] if i<len(TEAM) else 255
  for j in range(44):
   m[W_PARTY_MONS+44*i+j]=0
  if i>=len(TEAM):
   continue
  sid,level,moves=TEAM[i]
  sp=S['species'][str(sid)]
  b=bytearray(44)
  b[0]=sid
  b[3]=level
  b[5:7]=bytes(sp['types'])
  b[7]=sp['catch_rate']
  b[8:12]=bytes(moves)
  b[12:14]=(12345).to_bytes(2,'big')
  xp=level**3 if sp['growth']=='MEDIUM_FAST' else 6*level**3//5-15*level**2+100*level-140
  b[14:17]=xp.to_bytes(3,'big')
  b[27:29]=bytes([0x88,0x88])
  b[29:33]=bytes(S['moves'][str(move)]['pp'] for move in moves)
  b[33]=level
  for j,base in enumerate(sp['stats']):
   dv=0 if j==0 else 8
   stat=(2*(base+dv)*level)//100+(level+10 if j==0 else 5)
   b[34+2*j:36+2*j]=stat.to_bytes(2,'big')
  b[1:3]=b[34:36]
  for j,v in enumerate(b):
   m[W_PARTY_MONS+44*i+j]=v
  nick=bytes(ord(c)-ord('A')+0x80 for c in sp['name'])+b'\x50'
  for j in range(11):
   m[W_PARTY_NICKS+11*i+j]=nick[j] if j<len(nick) else 0x50
 m[W_NUM_BAG_ITEMS]=1
 m[W_BAG_ITEMS]=82
 m[W_BAG_ITEMS+1]=1
 m[W_BAG_ITEMS+2]=255

def build(out):
 source=SOURCE
 e,manifest=load_engine(ROM,source)
 assert e.memory[0xD057]==0
 party(e)
 commands=json.loads((source/'reference-commands.json').read_text())
 for command in commands:
  advance(e,command)
  if ui_state(e.memory)['kind']=='battle_menu':
   break
 assert e.memory[0xD031]==44
 validate_team(e.memory)
 # Refresh the battle HUD through its native menu code after custom setup.
 print('Captured Lorelei battle menu with curated party', flush=True)
 save_fixture(e,manifest,out,{'kind':'battle-milestone','target':'elite:lorelei','description':'Defeat Lorelei with the supplied party and one Elixer. No resets. Keep default Pokemon names.'},{'synthetic_team':True,'source':str(source),'source_state_sha256':manifest['state_sha256'],
   'builder_sha256':digest(Path(__file__).read_bytes()), 'team':TEAM,
   'setup_memory_writes':'Party slots, names and bag only, before battle. No opponent or RNG edits.',
   'dvs':[0,8,8,8,8], 'stat_experience':0})
 e.close()

def pilot(scenario,out,mode,delay=0,rest_threshold=0.78):
 e,manifest=load_engine(ROM,scenario)
 s=Session(e,out,manifest,track='gameplay',goal='challenge',gameplay_catalog=CAT,limits=Limits(max_actions=20000,max_frames=120000,max_action_frames=600,max_dialogue_frames=7200),agent={'provider':'offline-calibration','model':mode,'calibration_policy_sha256':digest(Path(__file__).read_bytes()),'rest_threshold':rest_threshold})
 boosts=0
 choices=[]
 if delay:
  s.wait('variant',delay)
 try:
  for index in range(220):
   if s.reason:
    break
   ui=ui_state(e.memory)
   active=read_battler(e.memory)
   enemy=read_battler(e.memory,0xCFE5)
   mons=read_party(e.memory)
   if e.memory[0xD35E]!=245 and not e.evidence()['elite']['Lorelei']:
    s.finish('battle_loss')
    break
   if not any(mon['hp'] for mon in mons):
    s.finish('battle_loss')
    break
   cmd,arg='advance_dialogue',''
   if ui['kind'] in ('battle_menu','move_menu'):
    if active['species']==110:
     slot=3
     if mode=='tactical':
      if active['hp']<active['max_hp']*rest_threshold and not active['status']&7:
       slot=4
      elif not enemy['status'] and active['pp'][0] and not active['status']&7:
       slot=1
      elif boosts<3 and active['pp'][1] and not active['status']&7:
       slot=2
       boosts+=1
     cmd,arg='use_move',str(slot)
     if active['pp'][2]==0:
      cmd,arg='use_item','Elixer:1'
    elif active['species']==147:
     slot=3
     if mode=='tactical':
      slot=3
      if enemy['status']&7 and active['hp']<active['max_hp']*.65 and active['pp'][1]:
       slot=2
      elif not enemy['status'] and active['pp'][0]:
       slot=1
     cmd,arg='use_move',str(slot)
    else:
     cmd,arg='use_move','1'
     if mode=='tactical' and enemy['status']==0 and active['pp'][1]:
      cmd,arg='use_move','2'
    choices.append({'ui':ui['kind'],'active':active,'enemy':enemy,'command':cmd,'argument':arg})
    print(mode,delay,index,active['species'],active['hp'],enemy['species'],enemy['hp'],cmd,arg,flush=True)
   elif ui['kind']=='party_menu' or any('Bring out which' in t for t in ui['text']):
    order=[0,2,1] if mode=='tactical' else [0,1,2]
    alive=next((i for i in order if mons[i]['hp']>0 and i!=e.memory[0xCC2F]),None)
    if alive is not None:
     cmd,arg='switch_pokemon',str(alive+1)
    else:
     cmd,arg='press','a'
   elif ui['kind']=='menu' and 'NO' in ui['visible_choices']:
    cmd,arg='choose','NO'
   elif ui['kind']=='menu':
    cmd,arg='press','a'
   elif ui['kind'] in ('yes_no','choice'):
    cmd,arg='press','a'
   execute(s,str(index),{'command':cmd,'argument':arg,'count':1})
  if not s.reason:
   s.finish('calibration_limit')
 finally:
  write_json(out/'choices.json',choices)
  s.close()
 result=json.loads((out/'result.json').read_text())
 print('RESULT',mode,delay,result['completed'],result['stop_reason'],flush=True)
 return result

def main():
 parser=argparse.ArgumentParser(description=__doc__)
 parser.add_argument('mode', choices=['build','calibrate'])
 parser.add_argument('--rom',type=Path,required=True)
 parser.add_argument('--game-data',type=Path,required=True)
 parser.add_argument('--source',type=Path,required=True)
 parser.add_argument('--output',type=Path,required=True)
 parser.add_argument('--variant',type=int,choices=range(1,6))
 parser.add_argument('--rest-threshold',type=float,default=0.78)
 parser.add_argument('--tag',default='v3')
 parser.add_argument('--modes',nargs='+',choices=['tactical','damage-only'],default=['damage-only','tactical'])
 args=parser.parse_args()
 if not 0.5 <= args.rest_threshold <= 0.95:
  parser.error('Recovery threshold must be between 0.5 and 0.95')
 if not args.tag or any(c not in 'abcdefghijklmnopqrstuvwxyz0123456789-.' for c in args.tag):
  parser.error('Calibration tag must be a lowercase name')
 global ROM, DATA, CAT, S, SOURCE
 ROM,DATA,SOURCE=args.rom,args.game_data,args.source
 CAT=load_catalog(DATA)
 S=json.loads((DATA/'bundles'/json.loads((DATA/'current.json').read_text())['bundle']/'strategy.json').read_text())
 root=args.output
 if args.mode=='build':
  root.mkdir(parents=True,exist_ok=False)
  build(root/'base')
  for index,offset in enumerate(TIMING_OFFSETS,1):
   engine,manifest=load_engine(ROM,root/'base')
   if offset:
    engine.tick(offset)
   assert ui_state(engine.memory)['kind']=='battle_menu'
   validate_team(engine.memory)
   dest=root/f'variant-{index:02d}'
   save_fixture(engine,manifest,dest,manifest['objective'],
                {**manifest['provenance'],'timing_offset_frames':offset,
                 'variant':index,'variant_policy':'Fixed released-button wait at the initial menu, no RNG writes'})
   saved=json.loads((dest/'scenario.json').read_text())
   saved['curation']='synthetic-team-offline-calibration-pending'
   write_json(dest/'scenario.json',saved)
   write_json(dest/'starting-team.json',engine.structured(CAT['labels']))
   engine.close()
  return
 if args.variant is None:
  parser.error('Calibration requires --variant')
 scenario=root/f'variant-{args.variant:02d}'
 results={}
 for mode in args.modes:
  output=scenario/(mode+'-'+args.tag)
  result=pilot(scenario,output,mode,rest_threshold=args.rest_threshold)
  proof=replay(ROM,output)
  results[mode]={'completed':result['completed'],'reason':result['stop_reason'],'replay':proof}
 write_json(scenario/('calibration-'+args.tag+'.json'),results)
 print(json.dumps(results),flush=True)


if __name__=='__main__':
 main()
