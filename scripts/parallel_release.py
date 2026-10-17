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


def execution_budget(root, protocol):
    """Read the user's explicit budget amendment without changing old results."""
    from pokeagent_bench import release as api
    path = root / 'budget-authorization.json'
    if not path.exists():
        return protocol['total_token_budget']
    record = api.read(path)
    payload = {k:v for k,v in record.items() if k != 'sha256'}
    limit = record.get('total_token_budget')
    if (api.digest(api.encoded(payload)) != record.get('sha256')
            or record.get('protocol_sha256') != protocol['sha256']
            or type(limit) is not int or limit < protocol['total_token_budget']):
        raise ValueError('Invalid budget authorization')
    return limit



def diagnostic_holds(root, protocol):
    """Keep separately logged provider diagnostics inside the same token ceiling."""
    from pokeagent_bench import release as api
    path = root / 'diagnostic-reservations.json'
    if not path.exists():
        return 0
    record = api.read(path)
    payload = {k:v for k,v in record.items() if k != 'sha256'}
    if api.digest(api.encoded(payload)) != record.get('sha256') or record.get('protocol_sha256') != protocol['sha256']:
        raise ValueError('Invalid diagnostic reservations checksum')
    holds = record.get('holds')
    if not isinstance(holds, list):
        raise ValueError('Invalid diagnostic reservation list')
    seen = set()
    total = 0
    for hold in holds:
        key = hold.get('id')
        amount = hold.get('token_hold')
        if not isinstance(key, str) or not key or key in seen or type(amount) is not int or amount <= 0:
            raise ValueError('Invalid diagnostic reservation')
        seen.add(key)
        total += amount
    return total


def progress_report(api, root, protocol, limit):
    summary = api.report(root)
    summary['diagnostic_token_holds'] = diagnostic_holds(root, protocol)
    summary['registered_token_budget'] = protocol['total_token_budget']
    summary['total_token_budget'] = limit
    if (root / 'budget-authorization.json').exists():
        summary['budget_authorization_sha256'] = api.read(root / 'budget-authorization.json')['sha256']
    api.write_json(root / 'release-summary.json', summary)
    return summary


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


def next_cell(cells, workers, provider_limit, selection='registered', only_cell=None):
    """Keep a task and starting-variant barrier, then admit earliest eligible models."""
    if selection == 'claude-missing':
        running = [c for c in cells if c['status'] == 'running']
        if len(running) >= workers or sum(c['provider'] == 'claude' for c in running) >= provider_limit:
            return None
        covered = {(c['model'], c['task']) for c in cells if c['status'] in ('finished', 'running')
                   or (c['status'] == 'error' and not c.get('budget_hold_tokens'))}
        candidates = [c for c in cells if c['provider'] == 'claude' and c['status'] == 'pending'
                      and (c['model'], c['task']) not in covered and (only_cell is None or c['id'] == only_cell)]
        # Cover new model and task pairs before spending tokens on repeated starts.
        return min(candidates, key=lambda c: (c['token_limit'], c['variant'], cells.index(c))) if candidates else None
    if only_cell is not None:
        raise ValueError('A named trial requires Claude missing selection')
    if selection != 'registered':
        raise ValueError('Unknown selection policy')
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



def install_recovery_validation(root, api):
    """Load the checksummed validator without editing the frozen gameplay source."""
    if getattr(api.validate_batch, 'recovery_aware', False):
        return
    import importlib.util
    path = root / 'execution-schedulers' / 'replacement-722cb45eac3ce075bfb51c7ffc35d9febf585c739bbd787bdeb58b4da12ce9dd.py'
    if api.digest(path.read_bytes()) != '722cb45eac3ce075bfb51c7ffc35d9febf585c739bbd787bdeb58b4da12ce9dd':
        raise ValueError('Recovery validator checksum mismatch')
    spec = importlib.util.spec_from_file_location('pokebench_replacement_validation', path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    original = api.validate_batch
    def validate(protocol, batch):
        module.validate_extended_batch(protocol, batch, original)
    validate.recovery_aware = True
    api.validate_batch = validate


def preflight(root, rom, game_data):
    from pokeagent_bench import release as api
    from pokeagent_bench.gameplay import load_catalog, catalog_hash
    install_recovery_validation(root, api)
    protocol = api.read(root / 'protocol.json')
    batch = api.read(root / 'batch.json')
    api.validate_batch(protocol, batch)
    for record in batch.get('recovery_attempts', []):
        original = root / 'runs' / record['source_cell']
        if any(api.digest((original / name).read_bytes()) != record[key] for name, key in
               [('error.json', 'original_error_sha256'), ('result.json', 'original_result_sha256')]):
            raise ValueError('Original recovery failure changed')
        message = api.read(original / 'error.json').get('message', '').lower()
        if record.get('failure_kind') == 'interface_v4':
            if not any(text in message for text in ('attempted an outside tool', 'did not complete a decision')):
                raise ValueError('Recovery source is not a reviewed interface failure')
            adapter_path = root / 'execution-schedulers' / ('interface-' + record['adapter_source_sha256'] + '.py')
            if api.digest(adapter_path.read_bytes()) != record['adapter_source_sha256']:
                raise ValueError('Interface adapter changed')
        elif 'timed out' not in message:
            raise ValueError('Recovery source is not a provider timeout')
        if record.get('failure_kind') in ('response_truncation', 'response_budget_v3'):
            proof_path = root / 'diagnostics' / record['diagnostic_id'] / 'result.json'
            if api.digest(proof_path.read_bytes()) != record['diagnostic_result_sha256']:
                raise ValueError('Response headroom diagnostic changed')
            proof = api.read(proof_path)
            if (proof.get('status') != 'valid_structured_response' or proof.get('accounting_complete') is not True
                    or proof.get('model') != 'claude-sonnet-4-6' or proof.get('max_output_tokens') != record['adapter']['max_output_tokens']
                    or proof.get('actions_executed') is not False or proof.get('scored') is not False):
                raise ValueError('Response headroom diagnostic is not valid')
            if record.get('failure_kind') == 'response_budget_v3' and (
                    proof.get('deadline_seconds') != 600 or proof.get('original_conversation_unchanged') is not True):
                raise ValueError('V3 diagnostic conditions do not match')
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


def install_storage_read_fix():
    """Avoid emulator slices for empty boxes without changing nonempty reads."""
    from pokesim_core import gen1_ui, storage
    def memory_bytes(memory, bank, start, size):
        if size == 0:
            return b''
        return storage.memory_bytes(memory, bank, start, size)
    gen1_ui.memory_bytes = memory_bytes



def install_response_headroom():
    """Apply the diagnosed response allowance only to an authorized v2 recovery."""
    from pokeagent_bench import claude_provider
    cls = claude_provider.ClaudeCodeProvider
    if cls.harness == 'claude-code-bounded-gameplay-v2':
        return
    original_environment = claude_provider.subscription_environment
    def environment():
        result = original_environment()
        result['CLAUDE_CODE_MAX_OUTPUT_TOKENS'] = '8192'
        return result
    original_estimate = cls.estimate_next_tokens
    def estimate(self, *args, **kwargs):
        return original_estimate(self, *args, **kwargs) + 4096
    claude_provider.subscription_environment = environment
    cls.max_output_tokens = 8192
    cls.harness = 'claude-code-bounded-gameplay-v2'
    cls.estimate_next_tokens = estimate



def install_response_budget_v3():
    """Allow a validated long response while respecting the remaining trial wall time."""
    from pokeagent_bench import claude_provider
    cls = claude_provider.ClaudeCodeProvider
    if cls.harness == 'claude-code-bounded-gameplay-v3':
        return
    install_response_headroom()
    original_environment = claude_provider.subscription_environment
    original_init = cls.__init__
    original_estimate = cls.estimate_next_tokens
    original_decide = cls.decide
    original_complete = cls._complete
    def environment():
        result = original_environment()
        result['CLAUDE_CODE_MAX_OUTPUT_TOKENS'] = '32000'
        return result
    def initialize(self, *args, **kwargs):
        original_init(self, *args, **kwargs)
        self.config_identity.update(max_response_tokens=32000, max_decision_seconds=600)
    def estimate(self, *args, **kwargs):
        return original_estimate(self, *args, **kwargs) + 23808
    def decide(self, observation, notes, recent, limits, timeout):
        self.response_deadline = time.monotonic() + min(timeout, 600)
        return original_decide(self, observation, notes, recent, limits, timeout)
    def complete(self, method, params, deadline):
        return original_complete(self, method, params, self.response_deadline)
    claude_provider.subscription_environment = environment
    cls.max_output_tokens = 32000
    cls.harness = 'claude-code-bounded-gameplay-v3'
    cls.__init__ = initialize
    cls.estimate_next_tokens = estimate
    cls.decide = decide
    cls._complete = complete


def install_interface_v4(root, record):
    """Load only the reviewed response boundary, leaving game code frozen."""
    import importlib.util
    from pokeagent_bench import claude_provider, release as api
    expected = 'cabab8d0e530944c38db724b6bf394e5e9b808533abb76328503e5b52797b544'
    if record['adapter_source_sha256'] != expected:
        raise ValueError('Unreviewed interface adapter')
    path = root / 'execution-schedulers' / ('interface-' + expected + '.py')
    if api.digest(path.read_bytes()) != expected:
        raise ValueError('Interface adapter checksum mismatch')
    spec = importlib.util.spec_from_file_location('pokebench_interface_v4', path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    module.install(claude_provider)


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
    install_storage_read_fix()
    recovery_record = next((r for r in batch.get('recovery_attempts', []) if r['id'] == cell_id), None)
    if recovery_record and recovery_record.get('failure_kind') == 'response_truncation':
        install_response_headroom()
    if recovery_record and recovery_record.get('failure_kind') == 'response_budget_v3':
        install_response_budget_v3()
    if recovery_record and recovery_record.get('failure_kind') == 'interface_v4':
        install_interface_v4(root, recovery_record)
    try:
        returned = execute(parser().parse_args(command))
    finally:
        if target.exists():
            recovery = next((r for r in batch.get('recovery_attempts', []) if r['id'] == cell_id), None)
            if recovery:
                api.write_json(target / 'recovery-attempt.json', recovery)
            api.write_json(target / 'runtime-adapter.json', {
                'id': 'empty-storage-read-v1',
                'response_adapter': recovery_record.get('adapter') if recovery_record else None,
                'scheduler_sha256': api.digest(Path(__file__).read_bytes()),
                'description': 'Empty box storage reads return empty bytes without querying an invalid zero-length emulator slice. Nonempty reads, gameplay and scoring are unchanged.'})
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


def coordinate(root, rom, game_data, workers=4, provider_limit=2, quarantine_cells=(), selection='registered', only_cell=None):
    from pokeagent_bench.recovery import lock_run
    if not 1 <= workers <= 4 or not 1 <= provider_limit <= workers:
        raise ValueError('At most four workers, with an explicit per-provider limit')
    lease = lock_run(root)
    active = {}
    try:
        api, protocol, batch = preflight(root, rom, game_data)
        limit = execution_budget(root, protocol)
        if only_cell is not None:
            if workers != 1 or provider_limit != 1 or selection != 'claude-missing':
                raise ValueError('A named recovery must use one Claude worker')
            if only_cell not in {r['id'] for r in batch.get('recovery_attempts', [])}:
                raise ValueError('Named trial must have a recovery authorization')
            if any(c['status'] == 'error' and not c.get('budget_hold_tokens') for c in batch['cells']):
                raise ValueError('Named recovery requires all previous errors held')
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
            'policy': ('Exploratory collection prioritizes missing Claude pairs, lowest token ceilings first, with no OpenAI reruns or retries of scored gameplay losses. Reviewed infrastructure errors may use a remaining start while retaining the failed attempt and its token hold. Existing development evidence remains usable. ' if selection == 'claude-missing' else 'Task and variant barriers retain paired coverage. ') + f'One coordinator reserves full per-trial ceilings plus the registered in-flight reserve against the user-authorized total of {limit} tokens. Gameplay is unchanged. Original full-suite scoring stays separate from exploratory reporting.',
            'timing': 'Concurrent trials can encounter shared provider rate limits. Wall times before and after this amendment are not directly comparable. Runtime adapter empty-storage-read-v1 fixes zero-length storage reads. Each affected run records the adapter and scheduler checksum.',
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
        spent += diagnostic_holds(root, protocol)
        if spent + reserved > limit:
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
                spent += diagnostic_holds(root, protocol)
            except ValueError:
                stop = 'stopped for incomplete accounting'
            if stop is None:
                while (cell := next_cell(batch['cells'], workers, provider_limit, selection, only_cell)) is not None:
                    allowance = cell['token_limit'] + protocol['in_flight_reserve']
                    if spent + reserved + allowance > limit:
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
                'active_workers': len(active), 'limit': limit}
            if not active:
                batch['phase'] = stop or ('finished' if all(c['status'] == 'finished' for c in batch['cells']) else 'finished with evaluation errors' if all(c['status'] in ('finished', 'error') for c in batch['cells']) else 'paused at total token budget')
                if not stop and selection == 'claude-missing' and next_cell(batch['cells'], workers, provider_limit, selection, only_cell) is None:
                    expected = {(c['model'], c['task']) for c in batch['cells'] if c['provider'] == 'claude'}
                    done = {(c['model'], c['task']) for c in batch['cells'] if c['provider'] == 'claude' and c['status'] == 'finished'}
                    batch['phase'] = 'completed Claude coverage' if expected <= done else 'stopped with unresolved Claude errors'
            api.write_json(root / 'batch.json', batch)
            progress_report(api, root, protocol, limit)
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
    parser.add_argument('--only-cell', help='Restrict collection to one authorized recovery trial')
    parser.add_argument('--selection', choices=['registered', 'claude-missing'], default='registered')
    parser.add_argument('--quarantine-cell', action='append', default=[], help='Reviewed failed trial whose full allowance stays reserved, with no retry')
    args = parser.parse_args()
    args.root = args.root.resolve()
    sys.path.insert(0, str(args.root / 'runtime'))
    from pokeagent_bench import release as api
    if args.mode == 'run':
        print(coordinate(args.root, args.rom, args.game_data, args.workers, args.per_provider, args.quarantine_cell, args.selection, args.only_cell), flush=True)
    else:
        try:
            result = execute_cell(args.root, args.rom, args.game_data, args.cell, args.resume)
            api.write_json(args.root / 'parallel-outcomes' / (args.cell + '.json'), {'status': 'finished', **result})
        except BaseException:
            traceback.print_exc()
            raise


if __name__ == '__main__':
    main()
