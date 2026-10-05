"""Six experimental decision tasks with explicit fixture contracts."""


def battle(key, name, targets, tokens=750_000, no_faints=False, difficulty='hard'):
    return {'id':key,'name':name,'difficulty':difficulty,'tokens':tokens,'variants':5,
            'objective':{'kind':'guarded-milestones','targets':targets,'no_faints':no_faints}}


TASKS = [
    battle('bad-matchup','Recover from a bad matchup',['elite:lorelei'],500_000,True,'medium'),
    {'id':'healthy-capture','name':'Capture a healthy Snorlax','difficulty':'medium','tokens':500_000,'variants':5,
     'objective':{'kind':'encounter-capture'}},
    battle('team-rescue','Rescue a damaged team before Lance',['elite:lance'],750_000,difficulty='medium'),
    battle('pp-gauntlet','Win Lorelei and Bruno with limited PP',['elite:lorelei','elite:bruno'],1_000_000),
    battle('adaptive-champion','Defeat the Champion with a specialist team',['champion'],750_000),
    {'id':'recovery-detour','name':'Reach Viridian Forest with a poisoned partner','difficulty':'hard','tokens':1_000_000,'variants':5,
     'objective':{'kind':'resource-route','map_id':51}},
]
DESCRIPTIONS = {
    'bad-matchup':'Defeat Lorelei without letting any of your Pokemon faint. Use the supplied team. No resets. Keep default names.',
    'healthy-capture':'Catch this full-health wild Snorlax and add it to your party. Do not flee, knock it out or black out. Keep its default name.',
    'team-rescue':'Prepare your damaged party with the limited supplies, then defeat Lance. You may choose which Pokemon to restore. Do not black out. Keep default names.',
    'pp-gauntlet':'Defeat Lorelei and then Bruno using the supplied party and limited PP supplies. Manage resources across both battles. Do not black out. Keep default names.',
    'adaptive-champion':'Defeat the Champion and complete the Hall of Fame registration with the supplied specialist team and limited supplies. Do not black out. Keep default names.',
    'recovery-detour':'Travel from Viridian City to Viridian Forest without blacking out. Your partner is injured and poisoned. Choose whether and where to recover before continuing. Keep default names.',
}
# Synthetic parties are installed only during offline construction before battle.
TEAMS = {
    'recovery-detour':[(177,15,(33,39,145,55))],
    'bad-matchup':[(39,45,(89,157,111,120)),(111,50,(95,133,57,156)),(147,45,(95,138,101,109))],
    'healthy-capture':[(46,30,(147,10,78,141)),(147,30,(95,101,109,122))],
    'team-rescue':[(72,55,(58,94,142,156)),(132,40,(34,133,156,29)),(104,55,(85,86,42,97))],
    'pp-gauntlet':[(111,50,(95,133,57,156)),(38,50,(94,105,115,134))],
    'adaptive-champion':[(104,55,(85,86,42,97)),(105,55,(57,58,34,156)),(83,55,(53,109,98,156))],
}
BAGS = {
    'bad-matchup':[(82,1)],
    'healthy-capture':[(3,12),(73,1)],
    'team-rescue':[(53,1),(17,2),(82,1)],
    'pp-gauntlet':[(82,1)],
    'adaptive-champion':[(16,2)],
    'recovery-detour':[],
}
OFFSETS = (0,17,37,67,97)


def check_start(task, engine):
    from pokesim_core.gen1 import read_party, read_bag
    from .gameplay import ui_state
    key=task['id']
    party=read_party(engine.memory)
    if key in TEAMS and [(m['species'],m['level'],tuple(m['moves'])) for m in party]!=TEAMS[key]:
        raise ValueError('Decision fixture party differs from the registered team')
    if list(read_bag(engine.memory))!=BAGS[key]:
        raise ValueError('Decision fixture inventory differs from registration')
    expected={'bad-matchup':44,'pp-gauntlet':44,'adaptive-champion':43}
    if key in expected and (engine.memory[0xD057]!=2 or engine.memory[0xD031]!=expected[key] or ui_state(engine.memory)['kind']!='battle_menu'):
        raise ValueError('Decision battle requires the expected trainer menu')
    if key=='team-rescue' and (engine.memory[0xD057]!=0 or ui_state(engine.memory)['kind']!='overworld'
                              or engine.memory[0xD35E]!=113 or party[0]['hp']!=35
                              or party[1]['hp']!=0 or party[2]['hp']!=0 or party[0]['pp'][0]!=0):
        raise ValueError('Rescue starts before battle with fainted reserves and depleted Ice Beam')
    if key=='healthy-capture':
        from pokesim_core.gen1_ui import read_battler
        enemy=read_battler(engine.memory,0xCFE5)
        if engine.memory[0xD057]!=1 or enemy['species']!=132 or enemy['hp']!=enemy['max_hp'] or enemy['status'] or ui_state(engine.memory)['kind']!='battle_menu':
            raise ValueError('Capture must start against a healthy, natural Snorlax')
    if key=='pp-gauntlet' and (party[0]['pp'][2]!=4 or party[1]['pp'][0]!=5):
        raise ValueError('PP challenge starting reserves changed')
    if key=='recovery-detour' and (engine.memory[0xD35E]!=1 or not party[0]['status'] & 8 or party[0]['hp']!=4):
        raise ValueError('Recovery route must start in Viridian with the registered poisoned partner')
