"""Versioned development suites with verified local fixtures and bounded batches."""
from __future__ import annotations

from dataclasses import asdict
import json
from pathlib import Path
import shutil
from tempfile import TemporaryDirectory

from .core import Limits, core_provenance, digest, encoded, write_json

TASKS = [
    {"id": "starter", "name": "Get a starter", "difficulty": "easy", "tokens": 1_000_000,
     "objective": {"kind": "opening", "target": "starter"}},
    {"id": "wild-battle", "name": "Win a wild battle", "difficulty": "easy", "tokens": 250_000,
     "objective": {"kind": "wild-battle"}},
    {"id": "heal", "name": "Heal the party", "difficulty": "easy", "tokens": 500_000,
     "objective": {"kind": "heal", "map_id": 41}},
    {"id": "parcel", "name": "Collect and deliver Oak's Parcel", "difficulty": "medium", "tokens": 1_500_000,
     "objective": {"kind": "opening", "target": "parcel-roundtrip"}},
    {"id": "brock", "name": "Defeat Brock with a healthy team", "difficulty": "medium", "tokens": 500_000,
     "objective": {"kind": "milestone", "target": "badge:boulder"}},
]
DEFINITION = {"id": "red-basic-v1", "status": "development", "tasks": TASKS,
              "track": "gameplay", "provider": "codex", "policy": "bounded",
              "reasoning_effort": "medium", "context_turns": 8, "compact_at": 12000,
              "paid_summaries": 0}


LEAGUE_TASK = {"id": "league", "name": "Become Champion", "difficulty": "hard", "tokens": 3_000_000,
               "objective": {"kind": "milestone", "target": "champion"}}
LEAGUE_DEFINITION = {**DEFINITION, "id": "red-league-v1", "tasks": [LEAGUE_TASK]}
EXPANDED_DEFINITION = {**DEFINITION, "id": "red-basic-plus-league-v1", "tasks": [*TASKS, LEAGUE_TASK]}
SKILL_TASKS = [
    {'id': 'item-recovery', 'name': 'Recover the party with items', 'difficulty': 'medium', 'tokens': 250_000,
     'objective': {'kind': 'heal', 'map_id': 113}},
    {'id': 'agatha', 'name': 'Defeat Agatha', 'difficulty': 'hard', 'tokens': 750_000,
     'objective': {'kind': 'milestone', 'target': 'elite:agatha'}},
    {'id': 'lance', 'name': 'Defeat Lance', 'difficulty': 'hard', 'tokens': 750_000,
     'objective': {'kind': 'milestone', 'target': 'elite:lance'}},
]
ABILITY_DEFINITION = {**DEFINITION, 'id': 'red-ability-v1',
                      'tasks': [*TASKS, *SKILL_TASKS, LEAGUE_TASK]}
NEW_SKILL_TASKS = [
    {'id': 'first-capture', 'name': 'Catch your first wild Pokemon', 'difficulty': 'easy', 'tokens': 250_000,
     'objective': {'kind': 'capture'}},
    {'id': 'parcel-delivery', 'name': "Return Oak's Parcel from Viridian", 'difficulty': 'medium', 'tokens': 750_000,
     'objective': {'kind': 'opening', 'target': 'parcel'}},
    {'id': 'lorelei', 'name': 'Defeat Lorelei', 'difficulty': 'hard', 'tokens': 750_000,
     'objective': {'kind': 'milestone', 'target': 'elite:lorelei'}},
    {'id': 'bruno', 'name': 'Defeat Bruno', 'difficulty': 'hard', 'tokens': 750_000,
     'objective': {'kind': 'milestone', 'target': 'elite:bruno'}},
    {'id': 'champion-duel', 'name': 'Win the final Champion battle', 'difficulty': 'hard', 'tokens': 1_000_000,
     'objective': {'kind': 'milestone', 'target': 'champion'}},
]
SKILLS_DEFINITION = {**DEFINITION, 'id': 'red-skills-v1', 'tasks': NEW_SKILL_TASKS}
ABILITY_V2_DEFINITION = {**DEFINITION, 'id': 'red-ability-v2',
                         'tasks': [*ABILITY_DEFINITION['tasks'], *NEW_SKILL_TASKS]}
ADVENTURE_TASKS = [
    {'id': 'buy-pokeballs', 'name': 'Buy ten Poke Balls', 'difficulty': 'easy', 'tokens': 500_000,
     'objective': {'kind': 'purchase', 'item_id': 4, 'quantity': 10, 'unit_price': 200, 'map_id': 42}},
    {'id': 'viridian-forest', 'name': 'Cross Viridian Forest to Pewter', 'difficulty': 'medium', 'tokens': 1_000_000,
     'objective': {'kind': 'reach-map', 'map_id': 2}},
    {'id': 'mt-moon', 'name': 'Reach Cerulean through Mt. Moon', 'difficulty': 'hard', 'tokens': 1_500_000,
     'objective': {'kind': 'reach-map', 'map_id': 3}},
    {'id': 'fossil', 'name': 'Win a fossil in Mt. Moon', 'difficulty': 'medium', 'tokens': 500_000,
     'objective': {'kind': 'obtain-item', 'item_ids': [41, 42]}},
    {'id': 'misty', 'name': 'Defeat Misty', 'difficulty': 'medium', 'tokens': 750_000,
     'objective': {'kind': 'milestone', 'target': 'badge:cascade'}},
]
ADVENTURE_DEFINITION = {**DEFINITION, 'id': 'red-adventure-v1', 'tasks': ADVENTURE_TASKS}
ABILITY_V3_DEFINITION = {**DEFINITION, 'id': 'red-ability-v3',
                         'tasks': [*ABILITY_V2_DEFINITION['tasks'], *ADVENTURE_TASKS]}
GYM_SPECS = {
    'surge': ('Lt. Surge', 'thunder', 36, 92, 2),
    'erika': ('Erika', 'rainbow', 37, 134, 3),
    'koga': ('Koga', 'soul', 38, 157, 4),
    'sabrina': ('Sabrina', 'marsh', 40, 178, 5),
    'blaine': ('Blaine', 'volcano', 39, 166, 6),
    'giovanni': ('Giovanni', 'earth', 29, 45, 7),
}
GYM_TASKS = [
    {'id': key, 'name': f'Defeat {name}', 'difficulty': 'medium', 'tokens': 750_000,
     'objective': {'kind': 'milestone', 'target': f'badge:{badge}'}}
    for key, (name, badge, trainer, map_id, bit) in GYM_SPECS.items()
]
HARD_LEAGUE_TASK = {
    'id': 'league-hard', 'name': 'Become Champion with a difficult team',
    'difficulty': 'hard', 'tokens': 3_000_000,
    'objective': {'kind': 'milestone', 'target': 'champion'},
}
GYM_ADDITIONS = {**DEFINITION, 'id': 'red-gym-additions-v1', 'tasks': [*GYM_TASKS, HARD_LEAGUE_TASK]}
GYM_DEFINITION = {**DEFINITION, 'id': 'red-gyms-v1',
                  'tasks': [TASKS[-1], ADVENTURE_TASKS[-1], *GYM_TASKS, HARD_LEAGUE_TASK]}
ABILITY_V4_DEFINITION = {**DEFINITION, 'id': 'red-ability-v4',
                         'tasks': [*ABILITY_V3_DEFINITION['tasks'], *GYM_ADDITIONS['tasks']]}
COMPLETION_DEFINITION = {**DEFINITION, 'id': 'red-skills-completion-v1', 'tasks': SKILL_TASKS}
TACTICAL_TASK = {
    'id': 'lorelei-tactics', 'name': 'Lorelei with an underleveled control team',
    'difficulty': 'hard', 'tokens': 500_000, 'variants': 5,
    'objective': {'kind': 'battle-milestone', 'target': 'elite:lorelei'},
}
TACTICAL_DEFINITION = {**DEFINITION, 'id': 'red-tactics-v1', 'tasks': [TACTICAL_TASK],
                      'trial_policy': 'Five fixed timing variants, one attempt each. All outcomes count.'}
ABILITY_V5_DEFINITION = {**DEFINITION, 'id': 'red-ability-v5',
                         'tasks': [*ABILITY_V4_DEFINITION['tasks'], TACTICAL_TASK]}
TACTICAL_V2_TASK = {**TACTICAL_TASK, 'team_version': 2,
                    'name': 'Lorelei with a tactical control team'}
TACTICAL_V2_DEFINITION = {**TACTICAL_DEFINITION, 'id': 'red-tactics-v2',
                          'tasks': [TACTICAL_V2_TASK]}
ABILITY_V6_DEFINITION = {**DEFINITION, 'id': 'red-ability-v6',
                         'tasks': [*ABILITY_V4_DEFINITION['tasks'], TACTICAL_V2_TASK]}
from .decision_tasks import TASKS as DECISION_TASKS

DECISION_DEFINITION = {**DEFINITION, 'id': 'red-decisions-v1', 'status': 'experimental',
                       'tasks': DECISION_TASKS,
                       'trial_policy': 'Five shared starting variants. One attempt each. All outcomes count.'}
DECISION_PILOT_DEFINITION = {**DECISION_DEFINITION, 'id': 'red-decisions-pilot-v1',
                             'tasks': [{**t, 'variants': 1} for t in DECISION_TASKS],
                             'trial_policy': 'Development pilot on the first registered starting variant only. Not a reliability estimate.'}
ABILITY_V7_DEFINITION = {**DEFINITION, 'id': 'red-ability-v7',
                         'tasks': [*ABILITY_V6_DEFINITION['tasks'], *DECISION_TASKS]}
DEFINITIONS = {d['id']: d for d in (DEFINITION, LEAGUE_DEFINITION, EXPANDED_DEFINITION,
                                  ABILITY_DEFINITION, SKILLS_DEFINITION, ABILITY_V2_DEFINITION,
                                  ADVENTURE_DEFINITION, ABILITY_V3_DEFINITION,
                                  GYM_ADDITIONS, GYM_DEFINITION, ABILITY_V4_DEFINITION, COMPLETION_DEFINITION,
                                  TACTICAL_DEFINITION, ABILITY_V5_DEFINITION,
                                  TACTICAL_V2_DEFINITION, ABILITY_V6_DEFINITION,
                                  DECISION_DEFINITION, DECISION_PILOT_DEFINITION, ABILITY_V7_DEFINITION)}


def definition_for(suite_id):
    if suite_id not in DEFINITIONS:
        raise ValueError(f'Unknown suite: {suite_id}')
    return DEFINITIONS[suite_id]


def check_start(task, engine):
    """Reject misleading fixtures before collecting any model results."""
    if task['id'] in {t['id'] for t in DECISION_TASKS}:
        from .decision_tasks import check_start as check_decision_start
        check_decision_start(task, engine)
        return
    if task['id'] == 'lorelei-tactics':
        check_start({'id': 'lorelei'}, engine)
        from .tactical import validate_team
        validate_team(engine.memory, task.get('team_version', 1))
        return
    if task['id'] in GYM_SPECS:
        from pokesim_core.gen1 import W_IS_IN_BATTLE, W_TRAINER_CLASS
        from .gameplay import ui_state
        name, badge, trainer, map_id, bit = GYM_SPECS[task['id']]
        progress = engine.evidence()
        if (engine.memory[W_IS_IN_BATTLE] != 2 or engine.memory[W_TRAINER_CLASS] != trainer
                or progress['map_id'] != map_id or ui_state(engine.memory)['kind'] != 'battle_menu'
                or progress['badges'] & (1 << bit) or progress['gym_flags'][bit]):
            raise ValueError(f'{name} fixture requires the correct unbeaten Gym Leader battle menu')
        if not any(mon['hp'] > 0 for mon in engine.structured()['party']):
            raise ValueError('Gym fixture requires a surviving party')
        return
    if task['id'] in ('lorelei', 'bruno', 'agatha', 'lance', 'champion-duel'):
        from pokesim_core.gen1 import W_IS_IN_BATTLE, W_TRAINER_CLASS
        from .gameplay import ui_state
        expected = {'lorelei': 44, 'bruno': 33, 'agatha': 46, 'lance': 47, 'champion-duel': 43}[task['id']]
        progress = engine.evidence()
        if (engine.memory[W_IS_IN_BATTLE] != 2 or engine.memory[W_TRAINER_CLASS] != expected
                or ui_state(engine.memory)['kind'] != 'battle_menu'
                or (progress['champion'] if task['id'] == 'champion-duel'
                    else progress['elite'][task['id'].title()]) or progress['hall_of_fame'] != 0):
            raise ValueError('Elite segment must start at the correct unbeaten trainer battle menu')
        return
    if task['id'] == 'first-capture':
        from .gameplay import ui_state
        facts = engine.challenge_evidence(task['objective'])
        if (facts['party_count'] != 1 or len(facts['owned']) != 1 or facts['balls'] < 1
                or facts['battle'] != 1 or facts['battle_type'] != 0
                or not engine.evidence()['story']['pokedex']
                or ui_state(engine.memory)['kind'] != 'battle_menu'):
            raise ValueError('First capture requires a normal wild battle menu, one owned Pokemon and balls')
        return
    if task['id'] == 'parcel-delivery':
        from .gameplay import ui_state
        facts = engine.challenge_evidence(task['objective'])
        if (facts['parcel'] != 1 or facts['parcel_delivered'] or facts['battle'] != 0
                or engine.evidence()['map_id'] != 1 or ui_state(engine.memory)['kind'] != 'overworld'):
            raise ValueError('Parcel delivery must start outdoors in Viridian with the undelivered parcel')
        return
    if task['id'] in {t['id'] for t in ADVENTURE_TASKS}:
        from .gameplay import ui_state
        from pokesim_core.gen1 import W_IS_IN_BATTLE, W_TRAINER_CLASS, read_bag
        progress = engine.evidence()
        key = task['id']
        if key in ('misty', 'fossil'):
            trainer, map_id = (35, 65) if key == 'misty' else (8, 61)
            if (engine.memory[W_IS_IN_BATTLE] != 2 or engine.memory[W_TRAINER_CLASS] != trainer
                    or progress['map_id'] != map_id or ui_state(engine.memory)['kind'] != 'battle_menu'):
                raise ValueError('Adventure battle must start at the specified trainer menu')
            if key == 'misty' and (progress['badges'] & 2 or progress['gym_flags'][1]):
                raise ValueError('Misty checkpoint already earned the Cascade Badge')
            if key == 'fossil' and any(dict(read_bag(engine.memory)).get(i, 0) for i in (41, 42)):
                raise ValueError('Fossil checkpoint already owns a fossil')
        else:
            expected_map = {'buy-pokeballs': 1, 'viridian-forest': 51, 'mt-moon': 59}[key]
            if (progress['map_id'] != expected_map or engine.memory[W_IS_IN_BATTLE] != 0
                    or ui_state(engine.memory)['kind'] != 'overworld'):
                raise ValueError('Adventure checkpoint must start in its specified overworld area')
            if key == 'buy-pokeballs' and dict(read_bag(engine.memory)).get(4, 0):
                raise ValueError('Shopping checkpoint must start without Poke Balls')
        return
    if task['id'] not in ('brock', 'league', 'league-hard'):

        return
    state = engine.structured()
    party = state['party']
    if not party or any(m['hp'] != m['max_hp'] or m['status'] for m in party):
        raise ValueError(f"{task['id']} fixture requires a healthy party")
    if task['id'] in ('league', 'league-hard'):
        from .gameplay import ui_state
        progress = engine.evidence()
        if (progress['hall_of_fame'] != 0 or progress['champion'] or any(progress['elite'].values())
                or progress['badges'] != 255 or not all(progress['gym_flags'])
                or state['location']['map_id'] != 245 or state['battle']['kind'] != 'none'
                or ui_state(engine.memory)['kind'] != 'overworld'):
            raise ValueError('League fixture must start before the first Lorelei fight with no previous championship')


def source_hash():
    return digest(encoded({p.name: digest(p.read_bytes()) for p in sorted(Path(__file__).parent.glob('*.py'))}))


def read(path):
    return json.loads(Path(path).read_text())


def limits(task):
    return asdict(Limits(max_total_tokens=task['tokens'], max_model_calls=1000,
                        max_action_frames=600, max_actions_per_decision=1, max_note_bytes=2048,
                        max_frames=4_800_000, max_actions=60_000, max_wall_seconds=3600,
                        max_area_tokens=0, max_loop_tokens=0))


def controller_rows(reference):
    """Extract executed controller input, preserving partial final actions."""
    for line in (Path(reference) / 'actions.jsonl').read_text().splitlines():
        row = json.loads(line)
        command = row['action']
        frames = row['executed_frames']
        hold = min(command['hold_frames'], frames)
        yield {"button": command['button'], "hold_frames": hold, "release_frames": frames - hold}


def reference(rom, scenario, commands, output):
    from .session import Session, load_engine, replay
    engine, manifest = load_engine(rom, scenario)
    session = None
    try:
        session = Session(engine, output, manifest, track='visual', goal='challenge',
                          limits=Limits(max_action_frames=600, max_actions=60000, max_frames=4_800_000),
                          agent={"provider": "controller-reference", "model": "none"})
        for index, command in enumerate(commands):
            if session.reason:
                break
            total = command['hold_frames'] + command['release_frames']
            if command['button'] is None:
                session.wait(str(index), total)
            else:
                session.act(str(index), command['button'], command['hold_frames'], command['release_frames'])
        if not session.reason:
            session.finish('reference_exhausted')
    finally:
        if session:
            session.close()
        else:
            engine.close()
    proof = replay(rom, output)
    if not read(output / 'result.json')['completed']:
        raise ValueError(f'Reference did not complete: {output}')
    return proof


def prepare(rom, bindings, output, suite_id="red-basic-v1"):
    """Import local fixtures only after a fresh reference and negative replay."""
    from .session import load_engine, Session, replay
    definition = definition_for(suite_id)
    tasks = definition['tasks']
    mapping = read(bindings)
    if set(mapping) != {t['id'] for t in tasks}:
        raise ValueError('Bindings must include exactly the selected suite task IDs')
    output = Path(output).resolve()
    output.mkdir(parents=True, exist_ok=False)
    suite = {"definition": definition, "fixtures": {}, "rom_sha256": digest(rom.read_bytes()),
             "core": core_provenance(), "status": "preparing"}
    write_json(output / 'suite.json', suite)
    for task in tasks:
        key = task['id']
        bindings_for_task = mapping[key].get('variants', [mapping[key]])
        if len(bindings_for_task) != task.get('variants', 1):
            raise ValueError('Bindings must include every registered starting variant')
        variants = []
        for variant_index, binding in enumerate(bindings_for_task):
            source = Path(binding['scenario']).resolve()
            destination = output / 'fixtures' / key
            if len(bindings_for_task) > 1:
                destination = destination / f'variant-{variant_index+1:02d}'
            destination.mkdir(parents=True)
            manifest = read(source / 'scenario.json')
            objective = {k:v for k,v in manifest.get('objective', {}).items() if k != 'description'}
            if objective != task['objective']:
                raise ValueError(f'{key}: objective does not match the suite')
            for name in ('initial.state', 'preview.png', 'scenario.json'):
                shutil.copyfile(source / name, destination / name)
            engine, _ = load_engine(rom, destination)
            try:
                check_start(task, engine)
            finally:
                engine.close()
            commands = list(controller_rows(binding['reference']))
            proof = reference(rom, destination, commands, destination / 'reference')
            write_json(destination / 'reference-commands.json', commands)
            # No-input evidence catches already-satisfied and automatic-completion fixtures.
            engine, scenario = load_engine(rom, destination)
            session = Session(engine, destination / 'negative', scenario, track='visual', goal='challenge',
                              limits=Limits(max_frames=120, max_action_frames=120),
                              agent={"provider": "controller-negative", "model": "none"})
            try:
                session.wait('idle', 120)
                if session.evaluator.complete('challenge'):
                    raise ValueError(f'{key}: completes without an agent action')
            finally:
                session.close()
            negative = replay(rom, destination / 'negative')
            variant_record = {"scenario": str(destination.relative_to(output)), "state_sha256": manifest['state_sha256'],
                                       "manifest_sha256": digest((destination/'scenario.json').read_bytes()),
                                       "reference_commands_sha256": digest(encoded(commands)),
                                       "reference": proof, "negative": negative, "limits": limits(task)}
            variants.append(variant_record)
        suite['fixtures'][key] = dict(variants[0])
        if len(variants) > 1:
            suite['fixtures'][key]['variants'] = variants
        write_json(output / 'suite.json', suite)
    suite['status'] = 'verified'
    suite['definition_sha256'] = digest(encoded(definition))
    write_json(output / 'suite.json', suite)
    return validate(output, rom)



def combine(roots, output, suite_id):
    """Assemble unchanged verified fixtures without replaying their curation again."""
    definition = definition_for(suite_id)
    sources = [(Path(root).resolve(), validate(root)) for root in roots]
    if not sources:
        raise ValueError('Supply verified source suites')
    if len({source['rom_sha256'] for _, source in sources}) != 1:
        raise ValueError('Source suite ROMs differ')
    tasks = {task['id']: task for task in definition['tasks']}
    selected = {}
    for root, source in sources:
        for task in source['definition']['tasks']:
            key = task['id']
            if key not in tasks or task != tasks[key]:
                raise ValueError('Source task is not an unchanged target task')
            if key in selected:
                raise ValueError('Duplicate source task')
            selected[key] = (root, source['fixtures'][key])
    if set(selected) != set(tasks):
        raise ValueError('Source suites do not cover the target suite')
    output = Path(output).resolve()
    output.mkdir(parents=True, exist_ok=False)
    result = {'definition': definition, 'definition_sha256': digest(encoded(definition)),
              'rom_sha256': sources[0][1]['rom_sha256'], 'core': core_provenance(),
              'status': 'preparing', 'fixtures': {},
              'assembled_from': [{'suite_sha256': digest((root/'suite.json').read_bytes()),
                                  'suite_id': source['definition']['id']} for root, source in sources]}
    write_json(output/'suite.json', result)
    for key, (root, fixture) in selected.items():
        if fixture.get('variants'):
            variants = []
            for index, variant in enumerate(fixture['variants'], 1):
                destination = f'fixtures/{key}/variant-{index:02d}'
                shutil.copytree(root/variant['scenario'], output/destination)
                variants.append({**variant, 'scenario': destination})
            result['fixtures'][key] = {**variants[0], 'variants': variants}
        else:
            shutil.copytree(root/fixture['scenario'], output/'fixtures'/key)
            result['fixtures'][key] = {**fixture, 'scenario': f'fixtures/{key}'}
    result['status'] = 'verified'
    write_json(output/'suite.json', result)
    return validate(output)

def revalidate(root, rom, output):
    """Rebuild fixture proofs on the installed Core without altering the old suite."""
    root = Path(root).resolve()
    original = validate(root, require_runtime=False)
    if digest(rom.read_bytes()) != original['rom_sha256']:
        raise ValueError('Suite ROM mismatch')
    mapping = {key: {'scenario': str(root / fixture['scenario']),
                     'reference': str(root / fixture['scenario'] / 'reference')}
               for key, fixture in original['fixtures'].items()}
    with TemporaryDirectory(prefix='pokeagent-revalidate-') as temporary:
        bindings = Path(temporary) / 'bindings.json'
        write_json(bindings, mapping)
        result = prepare(rom, bindings, output, original['definition']['id'])
    result['revalidated_from'] = {'suite_sha256': digest((root / 'suite.json').read_bytes()),
                                  'core': original['core']}
    write_json(Path(output) / 'suite.json', result)
    return result


def validate(root, rom=None, replay_references=False, *, require_runtime=True):
    from .session import load_engine, replay
    if not require_runtime and (rom is not None or replay_references):
        raise ValueError('Emulator validation requires the matching Core runtime')
    root = Path(root)
    suite = read(root / 'suite.json')
    definition = definition_for(suite['definition']['id'])
    tasks = definition['tasks']
    if (suite.get('status') != 'verified' or suite['definition'] != definition
            or suite.get('definition_sha256') != digest(encoded(definition))
            or set(suite['fixtures']) != {t['id'] for t in tasks}):
        raise ValueError('Suite is incomplete or its definition changed')
    if require_runtime and suite['core'] != core_provenance():
        raise ValueError('Suite Core runtime changed, prepare it again')
    if rom and digest(rom.read_bytes()) != suite['rom_sha256']:
        raise ValueError('Suite ROM mismatch')
    for task in tasks:
        primary = suite['fixtures'][task['id']]
        variants = primary.get('variants', [primary])
        if len(variants) != task.get('variants', 1):
            raise ValueError('Missing registered starting variant')
        if 'variants' in primary and {k:v for k,v in primary.items() if k != 'variants'} != variants[0]:
            raise ValueError('Primary fixture differs from first starting variant')
        if len({v['state_sha256'] for v in variants}) != len(variants):
            raise ValueError('Starting variants must have distinct saved states')
        for fixture in variants:
            path = (root / fixture['scenario']).resolve()
            if not path.is_relative_to(root.resolve()):
                raise ValueError('Fixture path escapes suite')
            if (digest((path/'initial.state').read_bytes()) != fixture['state_sha256']
                    or digest((path/'scenario.json').read_bytes()) != fixture['manifest_sha256']
                    or digest(encoded(read(path/'reference-commands.json'))) != fixture['reference_commands_sha256']
                    or fixture['limits'] != limits(task)):
                raise ValueError('Fixture or budget changed')
            manifest = read(path/'scenario.json')
            if digest((path/'preview.png').read_bytes()) != manifest['preview_sha256']:
                raise ValueError('Fixture preview changed')
            if not fixture['reference']['verified'] or fixture['reference']['score'] != 1:
                raise ValueError('Missing successful fixture reference')
            if not fixture['negative']['verified'] or fixture['negative']['score'] != 0:
                raise ValueError('Missing unsuccessful fixture reference')
            if rom:
                engine, _ = load_engine(rom, path)
                try:
                    check_start(task, engine)
                finally:
                    engine.close()
            if replay_references:
                for name in ('reference', 'negative'):
                    if replay(rom, path/name) != fixture[name]:
                        raise ValueError('Fixture replay proof changed')
    return suite


def plan(root, models, repeats):
    suite = validate(root)
    tasks = suite['definition']['tasks']
    if not models or len(set(models)) != len(models) or any(not m.strip() for m in models):
        raise ValueError('Supply unique model IDs')
    if type(repeats) is not int or repeats < 1:
        raise ValueError('Repeats must be positive')
    if any(repeats % task.get('variants', 1) for task in tasks):
        raise ValueError('Repeats must cover complete cycles of all registered starting variants')
    cells = []
    for repeat in range(repeats):
        for task in tasks:
            for model in models[repeat % len(models):] + models[:repeat % len(models)]:
                cells.append({"id": f'cell-{len(cells)+1:04d}', "task": task['id'], "model": model,
                              "repeat": repeat + 1, "variant": repeat % task.get('variants', 1) + 1, "token_limit": task['tokens'], "status": "pending"})
    return {"models": models, "repeats": repeats, "cells": cells,
            "maximum_tokens": sum(c['token_limit'] for c in cells)}


def accounted(cells):
    return sum(c.get('tokens', 0) for c in cells)


def run_batch(root, rom, game_data, output, models=None, repeats=1, budget=None, resume=False, pause_after_cells=None):
    from .cli import parser, execute
    from .gameplay import load_catalog, catalog_hash
    from .recovery import lock_run
    from .session import replay
    root, output = Path(root).resolve(), Path(output).resolve()
    suite = validate(root, rom)
    tasks = suite['definition']['tasks']
    if pause_after_cells is not None and (type(pause_after_cells) is not int or pause_after_cells < 1):
        raise ValueError('Cell pause boundary must be a positive integer')
    if type(budget) is not int or budget <= 0:
        raise ValueError('A positive total token budget is required')
    if not resume:
        proposal = plan(root, models, repeats)
        output.mkdir(parents=True, exist_ok=False)
    elif not output.is_dir():
        raise ValueError('Batch does not exist')
    lease = lock_run(output)
    try:
        config = {"suite": str(root), "suite_sha256": digest((root/'suite.json').read_bytes()),
                  "rom_sha256": digest(rom.read_bytes()), "source_sha256": source_hash(),
                  "catalog_sha256": catalog_hash(load_catalog(game_data)), "core": core_provenance()}
        if resume:
            batch = read(output/'batch.json')
            if batch['configuration'] != config:
                raise ValueError('Batch runtime, suite or game data changed')
            if budget < batch['budget']:
                raise ValueError('Cannot reduce a previously allocated batch budget')
            batch['budget'] = budget
        else:
            batch = {**proposal, "configuration": config, "budget": budget, "phase": "ready"}
        write_json(output/'batch.json', batch)
        for cell in batch['cells']:
            if cell['status'] == 'finished':
                continue
            if pause_after_cells is not None and sum(c['status'] == 'finished' for c in batch['cells']) >= pause_after_cells:
                batch['phase'] = 'paused for sweep audit'
                break
            if cell['status'] == 'error':
                batch['phase'] = 'stopped for error'
                break
            target = output/cell['id']
            existing = read(target/'result.json') if (target/'result.json').exists() else None
            if existing:
                usage = existing['usage']
                cell['tokens'] = usage['input_tokens'] + usage['output_tokens']
            remaining = budget - accounted(batch['cells'])
            reserve = cell['token_limit'] - cell.get('tokens', 0)
            if remaining < reserve and not (existing and existing['state'] == 'finished'):
                batch['phase'] = 'paused at batch budget'
                break
            task = next(t for t in tasks if t['id'] == cell['task'])
            cell['status'] = 'running'
            batch['phase'] = 'running'
            write_json(output/'batch.json', batch)
            try:
                if existing and existing['state'] == 'finished':
                    result = existing
                elif target.exists():
                    result = execute(parser().parse_args(['resume', '--rom', str(rom), '--run', str(target)]))
                else:
                    fixture = suite['fixtures'][task['id']]
                    variants = fixture.get('variants', [fixture])
                    variant_id = cell.get('variant', 1)
                    if variant_id != (cell['repeat'] - 1) % len(variants) + 1:
                        raise ValueError('Trial starting variant differs from its registered repeat')
                    scenario = root/variants[variant_id-1]['scenario']
                    command = ['run', '--rom', str(rom), '--scenario', str(scenario), '--output', str(target),
                               '--provider', 'codex', '--model', cell['model'], '--track', 'gameplay',
                               '--codex-policy', 'bounded', '--reasoning-effort', 'medium', '--context-turns', '8',
                               '--compact-at', '12000', '--game-data', str(game_data), '--goal', 'challenge']
                    for key, value in limits(task).items():
                        command += ['--'+key.replace('_','-'), str(value)]
                    result = execute(parser().parse_args(command))
                usage = result['usage']
                cell['tokens'] = usage['input_tokens'] + usage['output_tokens']
                cell['result'] = result
                if not usage.get('accounting_complete') or result['stop_reason'] in (
                        'provider_error', 'infrastructure_error', 'usage_unavailable'):
                    raise ValueError('Trial has an infrastructure or usage error')
                if result['state'] == 'paused':
                    cell['status'] = 'paused'
                    batch['phase'] = 'paused at decision boundary'
                    break
                proof = replay(rom, target)
                cell.update(status='finished', replay=proof)
            except Exception as error:
                cell.update(status='error', error=f'{type(error).__name__}: {error}')
                if (target/'result.json').exists():
                    cell['result'] = read(target/'result.json')
                    usage = cell['result']['usage']
                    cell['tokens'] = usage['input_tokens'] + usage['output_tokens']
                batch['phase'] = 'stopped for error'
                break
            finally:
                write_json(output/'batch.json', batch)
            if accounted(batch['cells']) > budget:
                batch['phase'] = 'stopped after in-flight budget overrun'
                break
        else:
            batch['phase'] = 'finished'
        write_json(output/'batch.json', batch)
        return batch
    finally:
        lease.close()
