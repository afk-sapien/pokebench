"""Run the task catalog through the same native sessions used by existing suites."""
from pathlib import Path
import json

from .core import Limits, digest, encoded, write_json
from .evaluation_catalog import load_catalog, task_definition


def _read(path):
    return json.loads(Path(path).read_text())


def scenarios(fixtures, task_id):
    root = Path(fixtures) / task_id
    primary = root / 'scenario.json'
    children = sorted(path.parent for path in root.glob('*/scenario.json'))
    return ([root] if primary.is_file() else []) + children


def preparation_binding(fixtures, task_id):
    source = Path(fixtures) / 'preparation-bindings.json'
    if not source.is_file():
        raise ValueError('Preparation assessment targets have not been bound')
    bindings = _read(source)
    value = bindings.get('tasks', bindings).get(task_id)
    if not value:
        raise ValueError(f'No preparation assessment binding for {task_id}')
    return value


def inventory(fixtures, *, category=None):
    """Report actual frozen fixtures without mistaking old reuse candidates for them."""
    root = Path(fixtures)
    result = []
    for group in load_catalog(category):
        for task in group['evals']:
            rows = []
            for path in scenarios(root, task['id']):
                manifest = _read(path / 'scenario.json')
                problems = []
                state = path / 'initial.state'
                if manifest.get('task_id') != task['id']:
                    problems.append('Fixture belongs to a different task')
                if not state.is_file() or digest(state.read_bytes()) != manifest.get('state_sha256'):
                    problems.append('Missing or changed starting state')
                if manifest.get('catalog_sha256') != digest(encoded(task)):
                    problems.append('Fixture specification changed')
                if manifest.get('action_policy') != task['action_policy']:
                    problems.append('Task controls differ')
                validation = path / 'start-validation.json'
                if not validation.is_file() or not _read(validation).get('passed'):
                    problems.append('Starting state has not been checked')
                reference = path / 'reference-validation.json'
                proof = _read(reference) if reference.is_file() else {}
                verified = bool(proof.get('completed') and proof.get('replay', {}).get('verified')
                                and proof.get('state_sha256') == manifest.get('state_sha256')
                                and proof.get('input_policy') == manifest.get('input_policy')
                                and proof.get('evaluation_spec_sha256') == digest(encoded(task)))
                rows.append({'variant': path.name if path.name != task['id'] else 'default',
                             'path': str(path), 'start_checked': not problems,
                             'reference_verified': verified, 'issues': problems})
            issues = []
            if task['mode'] == 'preparation':
                try:
                    binding = preparation_binding(root, task['id'])
                    if not binding.get('targets') and not binding.get('target_variants'):
                        issues.append('Missing assessment opponents')
                except ValueError as error:
                    issues.append(str(error))
            runnable = bool(rows) and all(row['start_checked'] for row in rows) and not issues
            result.append({'id': task['id'], 'category': group['category'], 'mode': task['mode'],
                           'runtime': True, 'runnable': runnable, 'variants': rows, 'issues': issues,
                           'calibration': 'pending', 'model_calls': 0})
    return {'protocol': 'catalog-execution-v1', 'task_count': len(result),
            'runnable': sum(row['runnable'] for row in result),
            'reference_verified': sum(any(v['reference_verified'] for v in row['variants']) for row in result),
            'tasks': result}


def select_scenario(fixtures, task_id, variant='default'):
    candidates = scenarios(fixtures, task_id)
    matches = [path for path in candidates if (path.name == task_id and variant == 'default') or path.name == variant]
    if not matches:
        raise ValueError(f'No fixture for {task_id}, variant {variant}')
    row = next(row for row in inventory(fixtures)['tasks'] if row['id'] == task_id)
    selected = next(v for v in row['variants'] if v['path'] == str(matches[0]))
    if selected['issues']:
        raise ValueError('. '.join(selected['issues']))
    return matches[0]


def validate_fixtures(fixtures, rom):
    """Load every frozen native start and construct its actual evaluator."""
    from .challenges import create_challenge_evaluator, evidence
    from .campaign_runtime import CampaignTracker, read_campaign_evidence
    from .session import load_engine
    result = inventory(fixtures)
    for row in result['tasks']:
        for variant in row['variants']:
            if variant['issues']:
                continue
            engine = None
            try:
                engine, scenario = load_engine(Path(rom), Path(variant['path']))
                if row['id'] == 'campaign-full-game':
                    facts = read_campaign_evidence(engine)
                    if facts['party'] or facts['badges'] or facts['hall_of_fame'] or facts['map_id'] != 38:
                        raise ValueError('Campaign must start in the bedroom without a starter or earned badges')
                    evaluator = CampaignTracker(facts)
                else:
                    objective = scenario['objective']
                    expected_kind = 'preparation-submission' if row['mode'] == 'preparation' else 'catalog-task'
                    if objective['kind'] != expected_kind or objective['task_id'] != row['id']:
                        raise ValueError('Fixture is not bound to its catalog evaluator')
                    evaluator = create_challenge_evaluator(evidence(engine, objective), objective)
                if evaluator.score or evaluator.complete('campaign' if row['id'] == 'campaign-full-game' else 'challenge'):
                    raise ValueError('Fixture is already complete')
                variant['runtime_loaded'] = True
            except (ValueError, KeyError, OSError) as error:
                variant['runtime_loaded'] = False
                variant['issues'].append(str(error))
                row['runnable'] = False
            finally:
                if engine is not None:
                    engine.close()
    result['runnable'] = sum(row['runnable'] for row in result['tasks'])
    return result


def run_task(fixtures, task_id, rom, game_data, output, *, provider=None, model=None,
             variant='default', token_limit=None, decision_limit=None, actions=None, reasoning_effort='low',
             reference=False, presentation='current'):
    """Run a registered task, with an optional zero-model native input reference."""
    task = task_definition(task_id)
    if presentation not in ('current', 'before-after'):
        raise ValueError('Unknown catalog screenshot presentation')
    if presentation != 'current' and (task['mode'] == 'preparation' or actions is not None):
        raise ValueError('Screenshot presentation requires a gameplay model run')
    scenario = select_scenario(fixtures, task_id, variant)
    token_limit = task['token_limit'] if token_limit is None else token_limit
    if type(token_limit) is not int or token_limit <= 0:
        raise ValueError('Token limit must be a positive integer')
    decision_limit = task.get('decision_limit', Limits().max_model_calls) if decision_limit is None else decision_limit
    if type(decision_limit) is not int or decision_limit <= 0:
        raise ValueError('Decision limit must be a positive integer')
    if task['mode'] == 'preparation' and decision_limit != 1:
        raise ValueError('Preparation accepts one frozen submission')
    if task['mode'] == 'preparation':
        from .preparation_runtime import run_preparation
        binding = preparation_binding(fixtures, task_id)
        transport = None
        if actions is None:
            transport = make_provider(provider, model, reasoning_effort)
        try:
            options = {key: binding[key] for key in ('targets', 'threshold', 'offsets', 'max_decisions', 'target_variants') if key in binding}
            return run_preparation(Path(rom), scenario, Path(output), Path(game_data), task_id,
                                   actions=actions, provider=transport, token_limit=token_limit, **options)
        finally:
            if transport is not None:
                transport.close()
    if actions is not None:
        from .session import Session, load_engine, replay
        from .gameplay import load_catalog as game_catalog
        engine, manifest = load_engine(Path(rom), scenario)
        session = None
        try:
            session = Session(engine, Path(output), manifest, track='gameplay',
                goal='campaign' if task_id == 'campaign-full-game' else 'challenge',
                gameplay_catalog=game_catalog(Path(game_data)), limits=Limits(max_total_tokens=token_limit),
                agent={'provider': 'reference', 'model': 'fixed-native-inputs'})
            for index, command in enumerate(actions):
                if session.reason:
                    break
                command = dict(command)
                if command.get('button') is None and command.get('hold_frames') == 0:
                    command['hold_frames'], command['release_frames'] = command['release_frames'], 0
                session.act(f'reference-{index}', **command)
            if not session.reason:
                session.finish('reference_exhausted')
            result = _read(Path(output) / 'result.json')
        finally:
            if session is not None:
                session.close()
            else:
                engine.close()
        proof = replay(Path(rom), Path(output))
        if reference:
            run_manifest = _read(Path(output) / 'manifest.json')
            write_json(scenario / 'reference-validation.json', {
                'completed': result['completed'], 'score': result['score'],
                'state_sha256': manifest['state_sha256'],
                'input_policy': manifest.get('input_policy'),
                'evaluation_spec_sha256': run_manifest['evaluation_spec_sha256'],
                'run': str(Path(output).resolve()), 'replay': proof,
            })
        return {'result': result, 'replay': proof}
    if provider not in ('codex', 'claude') or not model:
        raise ValueError('Select a Codex or Claude model, or supply native reference actions')
    from .cli import execute, parser
    args = ['run', '--rom', str(rom), '--scenario', str(scenario), '--output', str(output),
            '--game-data', str(game_data), '--track', 'gameplay',
            '--goal', 'campaign' if task_id == 'campaign-full-game' else 'challenge',
            '--provider', provider, '--model', model, '--codex-policy', 'bounded',
            '--observation-format', 'text', '--context-detail', 'on-demand',
            '--reasoning-effort', reasoning_effort, '--max-total-tokens', str(token_limit),
            '--presentation', presentation, '--max-model-calls', str(decision_limit)]
    return execute(parser().parse_args(args))


def make_provider(provider, model, reasoning_effort):
    if not model:
        raise ValueError('A model is required for preparation')
    if provider == 'codex':
        from .bounded_provider import BoundedGameplayProvider
        return BoundedGameplayProvider(model, reasoning_effort=reasoning_effort,
                                       observation_format='text', context_detail='on-demand')
    if provider == 'claude':
        from .claude_provider import ClaudeCodeProvider
        return ClaudeCodeProvider(model, reasoning_effort=reasoning_effort, context_detail='on-demand')
    raise ValueError('Preparation supports Codex or Claude subscription providers')
