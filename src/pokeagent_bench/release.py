"""Prospective release registration and provider-neutral bounded evaluation."""
from datetime import datetime, timezone
import json
import math
from pathlib import Path
import random
import shutil
import traceback

from .core import Limits, core_provenance, digest, encoded, write_json
from .suite import check_start, limits, source_hash, validate

RELEASE_ID = 'pokebench-v1-beta'
MAX_RELEASE_TOKENS = 50_000_000
IN_FLIGHT_RESERVE = 100_000
EVALUATED_STOPS = frozenset(('completed', 'battle_loss', 'token_budget', 'model_call_budget',
    'wall_budget', 'frame_budget', 'action_budget', 'observation_stagnation_budget',
    'area_token_budget', 'loop_token_budget', 'invalid_model_response'))
CANDIDATES = {'bad-matchup','healthy-capture','team-rescue','pp-gauntlet','adaptive-champion','recovery-detour'}
RETIRED = {'wild-battle','first-capture','brock','erika','sabrina'}
PRIORITY = ['lorelei-tactics', 'starter', 'viridian-forest', 'bad-matchup', 'team-rescue',
            'pp-gauntlet', 'adaptive-champion', 'healthy-capture', 'recovery-detour', 'league-hard', 'parcel']


def read(path):
    return json.loads(Path(path).read_text())


def interval(wins, trials):
    """Wilson interval for descriptive binary rates, not an independence guarantee."""
    if not trials:
        return None
    z=1.959963984540054
    p=wins/trials
    denominator=1+z*z/trials
    center=(p+z*z/(2*trials))/denominator
    width=z*math.sqrt(p*(1-p)/trials+z*z/(4*trials*trials))/denominator
    return [max(0,center-width),min(1,center+width)]


def plan(tasks, models, variants):
    identities=[m['model'] for m in models]
    if not models or len(identities)!=len(set(identities)):
        raise ValueError('Model IDs must be present and unique')
    if type(variants) is not int or variants<1:
        raise ValueError('At least one shared starting variant is required')
    if any(not isinstance(m.get('model'), str) or not m['model'].strip() for m in models):
        raise ValueError('Explicit model IDs are required')
    if len({t['id'] for t in tasks}) != len(tasks) or not tasks:
        raise ValueError('Tasks must be present and unique')
    if any(type(t['tokens']) is not int or t['tokens'] <= 0 for t in tasks):
        raise ValueError('Task budgets must be positive integers')
    if any(m['provider'] not in ('codex','claude') or m.get('effort')!='medium' for m in models):
        raise ValueError('Release models require a supported subscription provider and declared medium effort')
    if any(m['provider'] == 'claude' and (not m['model'].startswith('claude-') or 'fable' in m['model']) for m in models):
        raise ValueError('Claude requires exact non-Fable subscription model IDs')
    order={key:i for i,key in enumerate(PRIORITY)}
    tasks=sorted(tasks,key=lambda t:(order.get(t['id'],len(order)),t['id']))
    cells=[]
    for task_index,task in enumerate(tasks):
        for variant in range(variants):
            rotation=(variant+task_index)%len(models)
            for model in models[rotation:]+models[:rotation]:
                cells.append({'id':f'cell-{len(cells)+1:04d}','task':task['id'],'variant':variant+1,
                              'model':model['model'],'provider':model['provider'],'effort':model['effort'],
                              'effective_effort':None if model['provider'] == 'claude' and 'haiku' in model['model'] else model['effort'],
                              'token_limit':task['tokens'],'status':'pending'})
    return cells


def prepare(suite_root, rom, output, variants=3, seed=20261005):
    """Preregister fresh timing offsets, with no selection by subsequent outcome."""
    from .session import load_engine
    from .challenges import ChallengeEvaluator,evidence
    suite_root,rom,output=Path(suite_root),Path(rom),Path(output)
    suite=validate(suite_root,rom)
    tasks=[t for t in suite['definition']['tasks'] if t['id'] not in RETIRED]
    output.mkdir(parents=True,exist_ok=False)
    rng=random.Random(seed)
    offsets={t['id']:rng.sample(range(20001,60001),variants) for t in tasks}
    registration={'id':RELEASE_ID,'status':'preparing','seed':seed,'offsets':offsets,
                  'sampling':'Fixed fresh timing offsets. Not independent RNG seeds. No rejected outcomes replaced.',
                  'source_suite_sha256':digest((suite_root/'suite.json').read_bytes())}
    write_json(output/'fixture-registration.json',registration)
    fixtures={}
    for task in tasks:
        source=suite_root/suite['fixtures'][task['id']]['scenario']
        fixtures[task['id']]=[]
        for index,offset in enumerate(offsets[task['id']],1):
            engine,manifest=load_engine(rom,source)
            try:
                engine.tick(offset)
                check_start(task,engine)
                ChallengeEvaluator(evidence(engine,manifest['objective']),manifest['objective'])
                folder=output/'fixtures'/task['id']/f'variant-{index:02d}'
                folder.mkdir(parents=True)
                state,screen=engine.save(),engine.screenshot()
                (folder/'initial.state').write_bytes(state)
                (folder/'preview.png').write_bytes(screen)
                imported={k:manifest[k] for k in ('format','game','rom_sha256','pyboy_version','objective')}
                imported.update(core=core_provenance(),name=task['id'],state_sha256=digest(state),
                                preview_sha256=digest(screen),setup_wait_frames=0,
                                curation='prospective-timing-variant',provenance={'source_state_sha256':manifest['state_sha256'],
                                  'source_reference':suite['fixtures'][task['id']]['reference'],
                                  'offset_frames':offset,'selection':'preregistered before model execution'})
                write_json(folder/'scenario.json',imported)
                fixtures[task['id']].append({'scenario':str(folder.relative_to(output)),
                                           'state_sha256':digest(state),'manifest_sha256':digest((folder/'scenario.json').read_bytes())})
            finally:
                engine.close()
    registration.update(status='prepared',tasks=tasks,fixtures=fixtures,rom_sha256=digest(rom.read_bytes()),core=core_provenance())
    write_json(output/'fixture-registration.json',registration)
    return registration



def transport_details(models, task):
    """Capture and validate installed CLI versions without making model requests."""
    from .bounded_provider import BoundedGameplayProvider
    from .claude_provider import ClaudeCodeProvider
    transports = {}
    for model in models:
        kind = model['provider']
        if kind in transports:
            continue
        cls = ClaudeCodeProvider if kind == 'claude' else BoundedGameplayProvider
        provider = cls(model['model'], reasoning_effort='medium', context_turns=8, compact_at=12000)
        try:
            configuration = dict(provider.config_identity)
            configuration.pop('effective_effort', None)
            configuration.pop('effort_control_supported', None)
            transports[kind] = {'cli_version': provider.cli_version, 'harness': provider.harness,
                'memory_protocol': provider.memory_protocol,
                'prompt_sha256': digest(provider.prompt.encode()),
                'schema_sha256': digest(encoded(provider.decision_schema(Limits(**limits(task))))),
                'configuration': configuration,
                'max_output_tokens': provider.max_output_tokens}
        finally:
            provider.close()
    if len({(value['prompt_sha256'], value['schema_sha256']) for value in transports.values()}) != 1:
        raise ValueError('Provider prompts or action schemas differ')
    return transports


def freeze(root, models, budget, game_data):
    from .gameplay import load_catalog,catalog_hash
    root=Path(root)
    registration=read(root/'fixture-registration.json')
    if registration['status']!='prepared' or type(budget) is not int or not 0 < budget <= MAX_RELEASE_TOKENS:
        raise ValueError('Verified fixtures and a positive budget no greater than 50 million tokens are required')
    if (root/'protocol.json').exists():
        raise ValueError('Release protocol is immutable')
    counts = {len(value) for value in registration['fixtures'].values()}
    if len(counts) != 1 or not next(iter(counts), 0):
        raise ValueError('Every task requires the same nonzero variant count')
    variants=counts.pop()
    models = [{**model, 'effective_effort':None if model['provider'] == 'claude' and 'haiku' in model['model'] else model['effort']} for model in models]
    cells=plan(registration['tasks'],models,variants)
    transports=transport_details(models, registration['tasks'][0])
    source=source_hash()
    snapshot=root/'runtime/pokeagent_bench'
    snapshot.mkdir(parents=True)
    for path in Path(__file__).parent.glob('*.py'):
        shutil.copyfile(path,snapshot/path.name)
    tasks=[{**t,'variants':variants,'score_eligible':t['id'] not in CANDIDATES,
            'validation_status':'experimental' if t['id'] in CANDIDATES else 'development-qualified',
            'starting_state_sha256':[f['state_sha256'] for f in registration['fixtures'][t['id']]]} for t in registration['tasks']]
    protocol={'id':RELEASE_ID,'frozen_at':datetime.now(timezone.utc).isoformat(),'source_sha256':source,
              'fixture_registration_sha256':digest((root/'fixture-registration.json').read_bytes()),
              'rom_sha256':registration['rom_sha256'],'core':registration['core'],
              'catalog_sha256':catalog_hash(load_catalog(Path(game_data))),
              'models':models,'transports':transports,'tasks':tasks,'variants':variants,'total_token_budget':budget,
              'maximum_planned_tokens':sum(c['token_limit'] for c in cells),'planned_attempts':len(cells),
              'track':'gameplay','context_turns':8,'compact_at':12000,'paid_summaries':0,
              'schedule':'Task first, all paired variants next, rotated models within each variant.',
              'effort_policy':'Requested medium. Haiku has no adjustable effort and records effective effort as null.',
              'in_flight_reserve':IN_FLIGHT_RESERVE,
              'scoring':'Equal weights per eligible task. Only identical completed variant coverage across all registered models enters the aggregate.',
              'uncertainty':'Per-task Wilson intervals are descriptive. Timing variants are paired conditions, not independent random samples.',
              'budget_policy':'No paid fallback or automatic credit purchases. Stop at decision boundaries. One in-flight response may exceed its threshold. Incomplete accounting stops the sweep.',
              'retry_policy':'No gameplay retries. Infrastructure errors remain errors and stop the sweep. All raw attempts preserved.',
              'history_policy':'No development attempt is imported into prospective results.'}
    protocol['sha256']=digest(encoded(protocol))
    write_json(root/'protocol.json',protocol)
    write_json(root/'batch.json',{'phase':'ready','protocol_sha256':protocol['sha256'],'cells':cells})
    report(root)
    return protocol


def validate_batch(protocol, batch):
    unhashed = {key:value for key,value in protocol.items() if key != 'sha256'}
    if digest(encoded(unhashed)) != protocol.get('sha256'):
        raise ValueError('Release protocol checksum mismatch')
    if batch.get('protocol_sha256') != protocol['sha256']:
        raise ValueError('Batch protocol differs')
    expected = plan(protocol['tasks'], protocol['models'], protocol['variants'])
    if len(batch.get('cells', [])) != len(expected):
        raise ValueError('Batch cell count changed')
    for actual, fixed in zip(batch['cells'], expected, strict=True):
        if any(actual.get(key) != value for key,value in fixed.items() if key != 'status'):
            raise ValueError('Batch schedule or cell configuration changed')
        if actual.get('status') not in ('pending', 'running', 'finished', 'error'):
            raise ValueError('Invalid batch cell status')


def accounted_usage(result):
    usage = result.get('usage', {})
    values = [usage.get(key) for key in ('input_tokens', 'output_tokens')]
    if any(type(value) is not int or value < 0 for value in values):
        raise ValueError('Invalid or missing attempt token accounting')
    return sum(values)


def validate_result(result):
    accounted_usage(result)
    if result['usage'].get('accounting_complete') is not True or result['usage'].get('available') is not True:
        raise ValueError('Incomplete provider accounting')
    if result.get('state') != 'finished' or result.get('stop_reason') not in EVALUATED_STOPS:
        raise ValueError('Infrastructure or unfinished attempt cannot be scored')
    if type(result.get('completed')) is not bool:
        raise ValueError('Attempt completion must be an explicit boolean')
    if result['completed'] != (result['stop_reason'] == 'completed'):
        raise ValueError('Attempt completion and stop reason disagree')


def report(root):
    root=Path(root)
    protocol,batch=read(root/'protocol.json'),read(root/'batch.json')
    validate_batch(protocol, batch)
    attempts=[]
    for cell in batch['cells']:
        result_path=root/'runs'/cell['id']/'result.json'
        result=read(result_path) if result_path.exists() else {}
        if cell['status'] == 'finished':
            validate_result(result)
            if digest(result_path.read_bytes()) != cell.get('result_sha256'):
                raise ValueError('Finished attempt result changed')
            if cell.get('replay', {}).get('verified') is not True:
                raise ValueError('Finished attempt is missing a verified replay')
        usage=result.get('usage',{})
        values = [usage.get(key) for key in ('input_tokens', 'output_tokens')]
        valid_counts = all(type(value) is int and value >= 0 for value in values)
        known = valid_counts and usage.get('accounting_complete') is True and usage.get('available') is True
        tokens = sum(value for value in values if type(value) is int and value >= 0)
        attempts.append({**cell,'tokens':tokens,
                         'completed':result.get('completed') if cell['status']=='finished' else None,
                         'stop_reason':result.get('stop_reason'),'decisions':usage.get('calls'),
                         'wall_seconds':result.get('wall_seconds'),
                         'accounting_complete':known if cell['status'] != 'pending' or result else True,
                         'replay_verified':cell.get('replay',{}).get('verified',False)})
    eligible=[]
    model_rows=[]
    for task in protocol['tasks']:
        groups=[[a for a in attempts if a['task']==task['id'] and a['model']==m['model']] for m in protocol['models']]
        if task['score_eligible'] and all(len(g)==protocol['variants'] and all(a['status']=='finished' and a['replay_verified'] and a['accounting_complete'] for a in g) for g in groups):
            eligible.append(task['id'])
    for model in protocol['models']:
        rows=[a for a in attempts if a['model']==model['model']]
        by_task=[]
        for task in protocol['tasks']:
            finished=[a for a in rows if a['task']==task['id'] and a['status']=='finished' and a['replay_verified']]
            wins=sum(bool(a['completed']) for a in finished)
            by_task.append({'id':task['id'],'wins':wins,'finished':len(finished),'planned':protocol['variants'],
                            'interval95':interval(wins,len(finished)),'included_in_score':task['id'] in eligible})
        scores=[t['wins']/t['finished'] for t in by_task if t['included_in_score']]
        model_rows.append({**model,'tasks':by_task,'score':100*sum(scores)/len(scores) if scores else None,
                           'tokens':sum(a['tokens'] for a in rows)})
    complete_accounting=all(a['accounting_complete'] for a in attempts)
    result={'id':protocol['id'],'status':batch['phase'],'protocol_sha256':protocol['sha256'],
            'planned':len(attempts),'finished':sum(a['status']=='finished' for a in attempts),
            'tokens':sum(a['tokens'] for a in attempts),'total_token_budget':protocol['total_token_budget'],
            'accounting_complete':complete_accounting,'tokens_are_lower_bound':not complete_accounting,
            'scored_tasks':eligible,'models':model_rows,'attempts':attempts}
    write_json(root/'release-summary.json',result)
    return result


def _run(root, rom, game_data):
    from .cli import parser,execute
    from .session import replay
    from .recovery import lock_run
    from .gameplay import load_catalog,catalog_hash
    root,rom,game_data=Path(root),Path(rom),Path(game_data)
    protocol=read(root/'protocol.json')
    if type(protocol.get('total_token_budget')) is not int or not 0 < protocol['total_token_budget'] <= MAX_RELEASE_TOKENS:
        raise ValueError('Release token budget exceeds authorization')
    unhashed={k:v for k,v in protocol.items() if k!='sha256'}
    if digest(encoded(unhashed))!=protocol['sha256'] or source_hash()!=protocol['source_sha256']:
        raise ValueError('Protocol or runtime changed after registration')
    if transport_details(protocol['models'], protocol['tasks'][0]) != protocol['transports']:
        raise ValueError('Provider CLI version or protocol changed')
    if digest(rom.read_bytes())!=protocol['rom_sha256'] or core_provenance()!=protocol['core']:
        raise ValueError('ROM or core changed')
    if catalog_hash(load_catalog(game_data))!=protocol['catalog_sha256']:
        raise ValueError('Game observation catalog changed')
    registration=read(root/'fixture-registration.json')
    if digest((root/'fixture-registration.json').read_bytes())!=protocol['fixture_registration_sha256']:
        raise ValueError('Fixture registration changed')
    lease=lock_run(root)
    try:
        batch=read(root/'batch.json')
        validate_batch(protocol, batch)
        for cell in batch['cells']:
            if cell['status']=='finished':
                continue
            if cell['status']!='pending':
                batch['phase']='stopped for infrastructure review'
                break
            summary=report(root)
            if not summary['accounting_complete']:
                batch['phase']='stopped for incomplete accounting'
                break
            if summary['tokens']+cell['token_limit']+protocol['in_flight_reserve']>protocol['total_token_budget']:
                batch['phase']='paused at total token budget'
                break
            fixture=registration['fixtures'][cell['task']][cell['variant']-1]
            scenario=root/fixture['scenario']
            if digest((scenario/'initial.state').read_bytes()) != fixture['state_sha256']:
                raise ValueError('Fixture state changed')
            if digest((scenario/'scenario.json').read_bytes())!=fixture['manifest_sha256']:
                raise ValueError('Fixture manifest changed')
            target=root/'runs'/cell['id']
            cell['status']='running'
            batch['phase']='running'
            write_json(root/'batch.json',batch)
            report(root)
            try:
                task=next(t for t in protocol['tasks'] if t['id']==cell['task'])
                command=['run','--rom',str(rom),'--scenario',str(scenario),'--output',str(target),
                         '--provider',cell['provider'],'--model',cell['model'],'--track','gameplay',
                         '--codex-policy','bounded','--reasoning-effort',cell['effort'],'--context-turns','8',
                         '--compact-at','12000','--game-data',str(game_data),'--goal','challenge']
                for key,value in limits(task).items():
                    command.extend(['--'+key.replace('_','-'),str(value)])
                result=execute(parser().parse_args(command))
                validate_result(result)
                persisted=read(target/'result.json')
                validate_result(persisted)
                if any(result.get(key) != persisted.get(key) for key in ('state','stop_reason','completed','usage')):
                    raise ValueError('CLI result differs from the persisted attempt')
                proof=replay(rom,target)
                if proof.get('verified') is not True:
                    raise ValueError('Controller replay did not verify')
                cell.update(status='finished',replay=proof,result_sha256=digest((target/'result.json').read_bytes()))
            except (Exception, KeyboardInterrupt) as error:
                private=root/'private-errors'
                private.mkdir(exist_ok=True)
                (private/(cell['id']+'.txt')).write_text(traceback.format_exc())
                cell.update(status='error',error=type(error).__name__)
                batch['phase']='stopped for infrastructure review'
                write_json(root/'batch.json',batch)
                break
            write_json(root/'batch.json',batch)
            if report(root)['tokens'] > protocol['total_token_budget']:
                batch['phase']='stopped after in-flight budget overrun'
                break
        else:
            batch['phase']='finished'
        write_json(root/'batch.json',batch)
        return report(root)
    finally:
        lease.close()


def run(root, rom, game_data):
    """Keep preflight diagnostics private as well as per-attempt exceptions."""
    try:
        return _run(root, rom, game_data)
    except (Exception, KeyboardInterrupt):
        root = Path(root)
        if root.is_dir():
            private = root / 'private-errors'
            private.mkdir(exist_ok=True)
            (private / 'sweep-preflight.txt').write_text(traceback.format_exc())
        raise
