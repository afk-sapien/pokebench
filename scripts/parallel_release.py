"""Run independent release trials concurrently against an unchanged frozen gameplay runtime."""
import argparse
from collections import Counter
from datetime import datetime, timezone
import os
from pathlib import Path
import subprocess
import sys
import time
import traceback


def reservation_ledger(cells, results, reserve):
    """Reserve full ceilings for running trials, including already consumed tokens once."""
    spent = 0
    reserved = 0
    for cell in cells:
        result = results.get(cell['id'], {})
        usage = result.get('usage', {})
        values = [usage.get(key) for key in ('input_tokens', 'output_tokens')]
        valid = all(type(value) is int and value >= 0 for value in values)
        used = sum(values) if valid else 0
        if cell['status'] == 'running':
            if result and (not valid or usage.get('accounting_complete') is not True):
                raise ValueError('Running worker has incomplete usage')
            reserved += max(cell['token_limit'] + reserve, used)
        elif cell['status'] == 'error' and cell.get('budget_hold_tokens'):
            hold = cell['budget_hold_tokens']
            if type(hold) is not int or hold < cell['token_limit'] + reserve or hold < used:
                raise ValueError('Error budget hold is insufficient')
            spent += hold
        elif cell['status'] != 'pending':
            if not valid or usage.get('accounting_complete') is not True or usage.get('available') is not True:
                raise ValueError('Stopped worker has incomplete usage')
            spent += used
        elif result:
            raise ValueError('Pending cell already has an attempt')
    return spent, reserved


def next_cell(cells, workers, provider_limit):
    """Keep a task and starting-variant barrier, then admit earliest eligible models."""
    outstanding = [c for c in cells if c['status'] != 'finished'
                   and not (c['status'] == 'error' and c.get('budget_hold_tokens'))]
    if not outstanding:
        return None
    first = outstanding[0]
    group = (first['task'], first['variant'])
    running = [c for c in cells if c['status'] == 'running']
    if len(running) >= workers:
        return None
    providers = Counter(c['provider'] for c in running)
    for cell in outstanding:
        if (cell['task'], cell['variant']) != group:
            continue
        if cell['status'] == 'pending' and providers[cell['provider']] < provider_limit:
            return cell
    return None


def preflight(root, rom, game_data):
    from pokeagent_bench import release as api
    from pokeagent_bench.gameplay import load_catalog, catalog_hash
    protocol = api.read(root / 'protocol.json')
    batch = api.read(root / 'batch.json')
    api.validate_batch(protocol, batch)
    if api.source_hash() != protocol['source_sha256']:
        raise ValueError('Frozen runtime checksum mismatch')
    if not 0 < protocol['total_token_budget'] <= api.MAX_RELEASE_TOKENS:
        raise ValueError('Token authorization changed')
    if api.transport_details(protocol['models'], protocol['tasks'][0]) != protocol['transports']:
        raise ValueError('Provider configuration changed')
    if api.digest(rom.read_bytes()) != protocol['rom_sha256'] or api.core_provenance() != protocol['core']:
        raise ValueError('ROM or core changed')
    if catalog_hash(load_catalog(game_data)) != protocol['catalog_sha256']:
        raise ValueError('Observation catalog changed')
    if api.digest((root / 'fixture-registration.json').read_bytes()) != protocol['fixture_registration_sha256']:
        raise ValueError('Fixture registration changed')
    return api, protocol, batch


def execute_cell(root, rom, game_data, cell_id, resume=False):
    from pokeagent_bench.cli import parser, execute
    from pokeagent_bench.session import replay
    api, protocol, batch = preflight(root, rom, game_data)
    cell = next(c for c in batch['cells'] if c['id'] == cell_id)
    if cell['status'] != 'running':
        raise ValueError('Worker has no reservation')
    target = root / 'runs' / cell_id
    registration = api.read(root / 'fixture-registration.json')
    fixture = registration['fixtures'][cell['task']][cell['variant'] - 1]
    scenario = root / fixture['scenario']
    if api.digest((scenario / 'initial.state').read_bytes()) != fixture['state_sha256']:
        raise ValueError('Starting state changed')
    if api.digest((scenario / 'scenario.json').read_bytes()) != fixture['manifest_sha256']:
        raise ValueError('Scenario manifest changed')
    if resume:
        command = ['resume', '--rom', str(rom), '--run', str(target)]
    else:
        if target.exists():
            raise ValueError('Refusing to replace an existing attempt')
        task = next(t for t in protocol['tasks'] if t['id'] == cell['task'])
        command = ['run', '--rom', str(rom), '--scenario', str(scenario), '--output', str(target),
                   '--provider', cell['provider'], '--model', cell['model'], '--track', 'gameplay',
                   '--codex-policy', 'bounded', '--reasoning-effort', cell['effort'],
                   '--context-turns', '8', '--compact-at', '12000', '--game-data', str(game_data),
                   '--goal', 'challenge']
        for key, value in api.limits(task).items():
            command.extend(['--' + key.replace('_', '-'), str(value)])
    returned = execute(parser().parse_args(command))
    result = api.read(target / 'result.json')
    api.validate_result(returned)
    api.validate_result(result)
    if any(returned.get(k) != result.get(k) for k in ('state', 'stop_reason', 'completed', 'usage')):
        raise ValueError('Persisted result differs')
    proof = replay(rom, target)
    if proof.get('verified') is not True:
        raise ValueError('Replay failed')
    return {'replay': proof, 'result_sha256': api.digest((target / 'result.json').read_bytes())}


def outcomes(root, cells):
    from pokeagent_bench.release import read
    return {c['id']: read(path) for c in cells
            if (path := root / 'runs' / c['id'] / 'result.json').exists()}


def launch(root, rom, game_data, cell, resume=False):
    args = [sys.executable, str(Path(__file__).resolve()), 'worker', '--root', str(root),
            '--rom', str(rom), '--game-data', str(game_data), '--cell', cell['id']]
    if resume:
        args.append('--resume')
    logs = root / 'parallel-logs'
    logs.mkdir(exist_ok=True)
    with (logs / (cell['id'] + '.log')).open('ab') as log:
        return subprocess.Popen(args, stdout=log, stderr=subprocess.STDOUT, env=dict(os.environ))


def coordinate(root, rom, game_data, workers=4, provider_limit=2, quarantine_cells=()):
    from pokeagent_bench.recovery import lock_run
    if not 1 <= workers <= 4 or not 1 <= provider_limit <= workers:
        raise ValueError('At most four workers, with an explicit per-provider limit')
    lease = lock_run(root)
    active = {}
    try:
        api, protocol, batch = preflight(root, rom, game_data)
        amendment_number = len(list(root.glob('execution-amendment-*.json'))) + 1
        amendment_path = root / f'execution-amendment-{amendment_number:03d}.json'
        if amendment_path.exists():
            raise ValueError('Execution amendment sequence is inconsistent')
        if any(c['status'] == 'running' for c in batch['cells']):
            raise ValueError('Drain the serial runner before handoff')
        paused = []
        quarantined = []
        if set(quarantine_cells) - {c['id'] for c in batch['cells'] if c['status'] == 'error'}:
            raise ValueError('Quarantine must name existing failed attempts')
        for cell in batch['cells']:
            if cell['status'] != 'error':
                continue
            target = root / 'runs' / cell['id']
            result = api.read(target / 'result.json')
            if cell['id'] in quarantine_cells:
                hold = max(cell['token_limit'] + protocol['in_flight_reserve'],
                           sum(result.get('usage', {}).get(k, 0) for k in ('input_tokens', 'output_tokens')))
                quarantined.append({'cell': cell['id'], 'budget_hold_tokens': hold,
                    'result_sha256': api.digest((target / 'result.json').read_bytes()),
                    'reason': 'Reviewed failed attempt excluded from scoring. Its full trial allowance plus reserve stays charged to the global ledger. Missing usage remains disclosed and is not presented as measured usage.'})
                cell['budget_hold_tokens'] = hold
                continue
            if cell.get('budget_hold_tokens'):
                continue
            usage = result.get('usage', {})
            if result.get('stop_reason') != 'paused' or usage.get('accounting_complete') is not True:
                raise ValueError('Existing infrastructure failure requires review')
            if not (target / 'recovery.json').exists() or (target / 'pending.json').exists():
                raise ValueError('Paused trial has no unambiguous checkpoint')
            paused.append(cell)
        amendment = {'format': 1, 'protocol_sha256': protocol['sha256'],
            'created_at': datetime.now(timezone.utc).isoformat(),
            'scheduler_sha256': api.digest(Path(__file__).read_bytes()),
            'previous_batch_sha256': api.digest((root / 'batch.json').read_bytes()),
            'workers': workers, 'per_provider_limit': provider_limit,
            'effective_after_finished': sum(c['status'] == 'finished' for c in batch['cells']),
            'resumed_cells': [c['id'] for c in paused], 'quarantined_cells': quarantined,
            'policy': 'One coordinator reserves full per-trial ceilings plus the registered in-flight reserve. Task and variant barriers retain paired coverage. Provider lanes may dispatch out of original model order. Gameplay, scoring and total budget are unchanged.',
            'timing': 'Concurrent trials can encounter shared provider rate limits. Wall times before and after this amendment are not directly comparable.',
            'failure_policy': 'Stop new admissions on any infrastructure error or unknown usage. Already reserved trials drain. No automatic model retries.'}
        amendment['sha256'] = api.digest(api.encoded(amendment))
        api.write_json(amendment_path, amendment)
        batch['execution_amendment_sha256'] = amendment['sha256']
        (root / 'parallel-outcomes').mkdir(exist_ok=True)
        # The old run becomes resumable, preserving its token ledger and conversation.
        for cell in paused:
            cell.pop('error', None)
            cell['status'] = 'running'
            cell['execution_mode'] = 'parallel-resumed'
        spent, reserved = reservation_ledger(batch['cells'], outcomes(root, batch['cells']), protocol['in_flight_reserve'])
        if spent + reserved > protocol['total_token_budget']:
            raise ValueError('Insufficient remaining allowance for paused trials')
        batch['phase'] = 'running'
        api.write_json(root / 'batch.json', batch)
        for cell in paused:
            active[cell['id']] = launch(root, rom, game_data, cell, resume=True)
        stop = None
        while True:
            for cell_id, process in list(active.items()):
                if process.poll() is None:
                    continue
                cell = next(c for c in batch['cells'] if c['id'] == cell_id)
                proof_path = root / 'parallel-outcomes' / (cell_id + '.json')
                proof = api.read(proof_path) if proof_path.exists() else {}
                try:
                    if process.returncode != 0 or proof.get('status') != 'finished':
                        raise ValueError('Worker failed')
                    target = root / 'runs' / cell_id / 'result.json'
                    api.validate_result(api.read(target))
                    if proof['result_sha256'] != api.digest(target.read_bytes()) or proof['replay'].get('verified') is not True:
                        raise ValueError('Worker proof changed')
                    cell.update(status='finished', replay=proof['replay'], result_sha256=proof['result_sha256'])
                except Exception as error:
                    cell.update(status='error', error=type(error).__name__)
                    stop = 'stopped for infrastructure review'
                del active[cell_id]
            try:
                spent, reserved = reservation_ledger(batch['cells'], outcomes(root, batch['cells']), protocol['in_flight_reserve'])
            except ValueError:
                stop = 'stopped for incomplete accounting'
            if stop is None:
                while (cell := next_cell(batch['cells'], workers, provider_limit)) is not None:
                    allowance = cell['token_limit'] + protocol['in_flight_reserve']
                    if spent + reserved + allowance > protocol['total_token_budget']:
                        break
                    cell.update(status='running', execution_mode='parallel')
                    reserved += allowance
                    api.write_json(root / 'batch.json', batch)
                    try:
                        active[cell['id']] = launch(root, rom, game_data, cell)
                    except Exception as error:
                        cell.update(status='error', error=type(error).__name__)
                        stop = 'stopped for infrastructure review'
                        break
            batch['budget_reservations'] = {'completed_tokens': spent, 'reserved_tokens': reserved,
                'active_workers': len(active), 'limit': protocol['total_token_budget']}
            if not active:
                batch['phase'] = stop or ('finished' if all(c['status'] == 'finished' for c in batch['cells']) else 'finished with evaluation errors' if all(c['status'] in ('finished', 'error') for c in batch['cells']) else 'paused at total token budget')
            api.write_json(root / 'batch.json', batch)
            api.report(root)
            if not active:
                return batch['phase']
            time.sleep(5)
    finally:
        # Fail closed if the coordinator itself fails. Workers pause at a decision boundary.
        for cell_id, process in active.items():
            if process.poll() is None:
                target = root / 'runs' / cell_id
                if target.exists():
                    (target / 'pause.request').write_text('Coordinator stopped. Pause at the next decision boundary.\n')
        lease.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('mode', choices=['run', 'worker'])
    parser.add_argument('--root', type=Path, required=True)
    parser.add_argument('--rom', type=Path, required=True)
    parser.add_argument('--game-data', type=Path, required=True)
    parser.add_argument('--workers', type=int, default=4)
    parser.add_argument('--per-provider', type=int, default=2)
    parser.add_argument('--cell')
    parser.add_argument('--resume', action='store_true')
    parser.add_argument('--quarantine-cell', action='append', default=[], help='Reviewed failed trial whose full allowance stays reserved, with no retry')
    args = parser.parse_args()
    args.root = args.root.resolve()
    sys.path.insert(0, str(args.root / 'runtime'))
    from pokeagent_bench import release as api
    if args.mode == 'run':
        print(coordinate(args.root, args.rom, args.game_data, args.workers, args.per_provider, args.quarantine_cell), flush=True)
    else:
        try:
            result = execute_cell(args.root, args.rom, args.game_data, args.cell, args.resume)
            api.write_json(args.root / 'parallel-outcomes' / (args.cell + '.json'), {'status': 'finished', **result})
        except BaseException:
            traceback.print_exc()
            raise


if __name__ == '__main__':
    main()
