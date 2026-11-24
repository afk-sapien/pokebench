"""Atomic decision-boundary checkpoints with fail-closed in-flight recovery."""
import base64
from collections import Counter, OrderedDict, deque
from dataclasses import asdict, replace
from datetime import datetime, timezone
import fcntl
import json
import os
from pathlib import Path
import threading
import time

from .core import Limits, core_provenance, digest, encoded, validate_emulator_manifest
from .scoring import Evaluator
from .challenges import ChallengeEvaluator
from .campaign_runtime import CampaignTracker
from .catalog_runtime import CatalogEvaluator
from .milestone_runtime import MilestoneEvaluator

EVALUATORS = {kind.__name__: kind for kind in (Evaluator, ChallengeEvaluator, CatalogEvaluator,
                                                MilestoneEvaluator, CampaignTracker)}


LOGS = ('actions.jsonl', 'decisions.jsonl', 'memory.jsonl')
# Pending phase for a decision whose model call or controller inputs are under way.
IN_FLIGHT = 'model-or-controller-in-flight'
# Pending phase for a decision the provider failed with no model reply. Nothing was spent or played.
NO_REPLY = 'provider-error-no-reply'
# Pending phase for a decision the provider failed after the model may have run. Its usage is unknown, so the
# resumed run counts the failed call and charges it a token reserve. Nothing was played.
UNCERTAIN = 'provider-error-uncertain-usage'
# The reserve for a failed call when the run recorded no estimate, as in the earlier hand recoveries.
DEFAULT_RESERVE = 64000
# Files of a provider error attempt that move into its own folder, so the resumed run writes fresh ones.
SET_ASIDE = ('result.json', 'error.json', 'final.state')
# Pending phase for a decision a second Ctrl-C cut short. Its reply, usage or inputs are unknown.
STOPPED = 'stopped-by-interrupt'
STOPPED_REFUSAL = ('Ctrl-C stopped decision {decision} before it finished, so its token use or controller inputs '
                   'are unknown and this run cannot resume. It is not scored. Delete {folder} to start the task again')
FIELDS = ('campaign_tracking', 'frame', 'actions', 'notes', 'reason', 'operation_ids', 'operations', 'trace_head',
          'usage', 'usage_available', 'journal_enabled', 'journal_entries', 'journal_results', 'current_decision',
          'gameplay_catalog', 'gameplay_memory', 'gameplay_inspection', 'gameplay_result', 'gameplay_operations')


def pack(value):
    if isinstance(value, bytes):
        return {'t': 'bytes', 'v': base64.b64encode(value).decode()}
    if type(value) in EVALUATORS.values():
        return {'t': type(value).__name__, 'v': pack(vars(value))}
    if isinstance(value, dict):
        kind = 'Counter' if isinstance(value, Counter) else 'OrderedDict' if isinstance(value, OrderedDict) else 'dict'
        return {'t': kind, 'v': [[pack(k), pack(v)] for k,v in value.items()]}
    if isinstance(value, (list, tuple, set, deque)):
        return {'t': type(value).__name__, 'v': [pack(x) for x in value], 'maxlen': value.maxlen if isinstance(value, deque) else None}
    return value


def unpack(value):
    if not isinstance(value, dict):
        return value
    kind, content = value['t'], value['v']
    if kind == 'bytes':
        return base64.b64decode(content, validate=True)
    if kind in EVALUATORS:
        result = object.__new__(EVALUATORS[kind])
        result.__dict__.update(unpack(content))
        return result
    if kind in ('dict', 'Counter', 'OrderedDict'):
        return {'dict': dict, 'Counter': Counter, 'OrderedDict': OrderedDict}[kind]({unpack(k): unpack(v) for k,v in content})
    items = [unpack(x) for x in content]
    if kind == 'deque':
        return deque(items, maxlen=value['maxlen'])
    return {'list': list, 'tuple': tuple, 'set': set}[kind](items)


def atomic(path, value):
    temporary = path.with_suffix('.tmp')
    with temporary.open('wb') as stream:
        stream.write(encoded(value))
        stream.flush()
        os.fsync(stream.fileno())
    os.replace(temporary, path)
    descriptor = os.open(path.parent, os.O_RDONLY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def lock_run(root):
    stream = (root / '.run.lock').open('a')
    try:
        fcntl.flock(stream, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        stream.close()
        raise ValueError('This run is already owned by another process') from None
    return stream


def checkpoint(session, state):
    if session.engine is None:
        return
    logs = {}
    for name in LOGS:
        path = session.output / name
        if path.exists():
            with path.open('rb') as stream:
                os.fsync(stream.fileno())
            logs[name] = digest(path.read_bytes())
        else:
            logs[name] = None
    capture = getattr(session.engine, 'checkpoint', None)
    restore = getattr(session.engine, 'restore_checkpoint', None)
    engine_checkpoint = capture() if callable(capture) and callable(restore) else None
    engine_state = engine_checkpoint['state'] if engine_checkpoint is not None else session.engine.save()
    payload = {'format': 1, 'manifest': session.manifest, 'limits': asdict(session.limits),
               'labels': session.labels, 'elapsed': session.elapsed(), 'saved_at': datetime.now(timezone.utc).isoformat(),
               'session': {key: getattr(session, key) for key in FIELDS}, 'evaluator': session.evaluator,
               'engine': engine_state, 'screen': session.engine.screenshot(), 'runner': state, 'logs': logs,
               'pending_button_release': (next(reversed(session.operations.values()))[0]['button']
                                          if session.operations and engine_checkpoint is None else None)}
    if engine_checkpoint is not None:
        payload['engine_checkpoint'] = engine_checkpoint
    data = pack(payload)
    atomic(session.output / 'recovery.json', {'payload': data, 'sha256': digest(encoded(data))})
    (session.output / 'pending.json').unlink(missing_ok=True)


def mark_pending(session, index):
    atomic(session.output / 'pending.json', {'decision': index, 'phase': IN_FLIGHT})


def load_checkpoint(rom, root):
    """The verified checkpoint and manifest of a run, refusing any run this code cannot continue exactly."""
    wrapper = json.loads((root / 'recovery.json').read_text())
    if digest(encoded(wrapper['payload'])) != wrapper['sha256']:
        raise ValueError('Recovery checkpoint checksum mismatch')
    saved = unpack(wrapper['payload'])
    if saved['format'] != 1:
        raise ValueError('Unsupported recovery checkpoint format')
    manifest = json.loads((root / 'manifest.json').read_text())
    source = digest(encoded({p.name: digest(p.read_bytes()) for p in sorted(Path(__file__).parent.glob('*.py'))}))
    if saved['manifest'] != manifest or manifest['source_sha256'] != source:
        raise ValueError('Resume requires the original manifest and exact runtime source')
    from .evaluation_catalog import validate_run_spec
    validate_run_spec(manifest)
    validate_emulator_manifest(manifest)
    if manifest['core'] != core_provenance():
        raise ValueError('Resume requires the original core and emulator versions')
    if digest(Path(rom).read_bytes()) != manifest['scenario']['rom_sha256']:
        raise ValueError('Resume ROM checksum mismatch')
    if saved['session']['reason'] not in (None, 'paused'):
        raise ValueError('Completed, exhausted, or failed runs cannot be resumed')
    for name, expected in saved['logs'].items():
        path = root / name
        actual = digest(path.read_bytes()) if path.exists() else None
        if actual != expected:
            raise ValueError('Uncommitted or changed run log. Refusing rollback or duplicated actions')
    return saved, manifest


def _read_json(path):
    try:
        value = json.loads(path.read_text())
    except (OSError, ValueError):
        return None
    return value if isinstance(value, dict) else None


def _finish_set_aside(root, marker):
    """Move the failed attempt's files into its folder and record it once. Safe to repeat after a crash."""
    attempt = root / marker['set_aside']
    for name in SET_ASIDE:
        if (root / name).exists():
            os.replace(root / name, attempt / name)
    errors = root / 'provider-errors.jsonl'
    rows = [json.loads(line) for line in errors.read_text().splitlines()] if errors.exists() else []
    if not any(row.get('set_aside') == attempt.name for row in rows):
        error = _read_json(attempt / 'error.json') or {}
        details = error.get('details') if isinstance(error.get('details'), dict) else {}
        row = {'at': datetime.now(timezone.utc).isoformat(), 'decision': marker['decision'], 'attempt': None,
               'message': error.get('message'), 'kind': 'provider_error', 'status': details.get('status'),
               'text': details.get('text'), 'seconds': None, 'usage': 'unknown',
               'token_reserve': marker['token_reserve'], 'set_aside': attempt.name}
        with errors.open('a') as stream:
            stream.write(encoded(row).decode() + '\n')
    return attempt


def reopen(rom, root):
    """Set aside a run that a provider error stopped mid decision, so resume runs that decision again.

    The failed call may have spent tokens the provider never reported. Resume counts the call and charges it
    the run's token estimate for the decision, and the run stops that many tokens early, so reported plus
    reserved use stays within the task's cap. The attempt's files are kept in provider-error-NN.
    Return that folder, or None when the run is not such a stop.
    """
    root = Path(root).resolve()
    if not (root / 'recovery.json').is_file() or not (root / 'pending.json').is_file():
        return None
    lease = lock_run(root)
    try:
        marker = _read_json(root / 'pending.json') or {}
        if marker.get('phase') == UNCERTAIN:
            # An earlier reopen stopped part way. Finish it.
            return _finish_set_aside(root, marker)
        result, error = _read_json(root / 'result.json'), _read_json(root / 'error.json')
        if (marker.get('phase') != IN_FLIGHT or result is None or error is None
                or result.get('stop_reason') != 'provider_error' or error.get('kind') != 'provider_error'):
            return None
        saved, _ = load_checkpoint(rom, root)
        if marker.get('decision') != saved['runner']['decision_index'] + 1:
            return None
        reserve = error.get('token_reserve')
        number = 1 + sum(1 for path in root.glob('provider-error-[0-9]*') if path.is_dir())
        attempt = root / f'provider-error-{number:02d}'
        attempt.mkdir()
        (attempt / 'pending.json').write_text(json.dumps(marker) + '\n')
        marker = {'decision': marker['decision'], 'phase': UNCERTAIN, 'set_aside': attempt.name,
                  'token_reserve': reserve if type(reserve) is int and reserve > 0 else DEFAULT_RESERVE}
        # From here a resume charges the reserve, even if the moves below never happen.
        atomic(root / 'pending.json', marker)
        return _finish_set_aside(root, marker)
    finally:
        lease.close()


def resume(rom, root, *, engine_factory=None, clock=time.monotonic):
    from .game import RedEngine
    from .session import Session
    root = Path(root).resolve()
    lease = lock_run(root)
    engine = None
    try:
        saved, manifest = load_checkpoint(rom, root)
        pending = root / 'pending.json'
        in_flight = json.loads(pending.read_text()) if pending.exists() else {}
        uncertain = in_flight.get('phase') == UNCERTAIN
        after_provider_error = in_flight.get('phase') == NO_REPLY or uncertain
        if in_flight.get('phase') == STOPPED:
            raise ValueError(STOPPED_REFUSAL.format(decision=in_flight['decision'], folder=root))
        if uncertain and (in_flight.get('decision') != saved['runner']['decision_index'] + 1
                          or type(in_flight.get('token_reserve')) is not int or in_flight['token_reserve'] <= 0
                          or any((root / name).exists() for name in SET_ASIDE)):
            raise ValueError('Provider error attempt does not match its checkpoint. Automatic retry is unsafe')
        if in_flight.get('decision', 0) > saved['runner']['decision_index'] and not after_provider_error:
            raise ValueError('In-flight decision has uncertain usage or actions. Automatic retry is unsafe')
        engine_checkpoint = saved.get('engine_checkpoint')
        engine = (engine_factory or RedEngine)(Path(rom), None if engine_checkpoint is not None else saved['engine'])
        if engine_checkpoint is not None:
            restore = getattr(engine, 'restore_checkpoint', None)
            if not callable(restore):
                raise ValueError('Recovery requires the original Core checkpoint capability')
            if engine_checkpoint.get('state') != saved['engine']:
                raise ValueError('Recovery raw state and Core checkpoint disagree')
            restore(engine_checkpoint, match='exact')
        elif saved['pending_button_release'] is not None:
            # Legacy raw states omit queued inputs. Restore the final release only.
            engine.release(saved['pending_button_release'])
        engine.initial_screen = saved['screen']
        session = object.__new__(Session)
        session.__dict__.update(saved['session'])
        session.engine, session.output, session.manifest = engine, root, manifest
        session.scenario, session.labels = manifest['scenario'], saved['labels']
        session.track, session.goal = manifest['track'], manifest['goal']
        from .campaign_runtime import VERSIONS
        session.campaign_tracking = manifest.get('scoring_protocol') in VERSIONS
        from .action_policy import from_manifest, tested_skill
        session.action_policy = from_manifest(manifest)
        session.tested_skill = manifest.get("tested_skill", tested_skill(manifest.get("scenario", {})))
        session.limits, session.evaluator = Limits(**saved['limits']), saved['evaluator']
        session.objective = getattr(session.evaluator, 'objective', None)
        session.score_max = (session.evaluator.score_max if isinstance(session.evaluator, MilestoneEvaluator)
                             else 1 if session.objective else 75 if session.goal == 'first-gym' else 1000)
        session.clock, session.started = clock, clock() - saved['elapsed']
        session.ended, session.reason, session.closed = None, None, False
        session.lock, session.run_lease = threading.RLock(), lease
        session.resume_state = saved['runner']
        resumed_at = datetime.now(timezone.utc)
        session.resume_metadata = {'checkpoint_saved_at': saved['saved_at'], 'restored_elapsed': saved['elapsed'],
                                   'resumed_at': resumed_at.isoformat(),
                                   'offline_seconds': max(0, (resumed_at - datetime.fromisoformat(saved['saved_at'])).total_seconds())}
        if after_provider_error:
            session.resume_metadata['after_provider_error'] = in_flight['decision']
        if uncertain:
            # The failed call counts toward the decision cap, and its unknown tokens are charged at the reserve.
            reserve = in_flight['token_reserve']
            session.usage['calls'] += 1
            session.usage['accounting_complete'] = False
            session.usage['unreported_token_reserve'] = session.usage.get('unreported_token_reserve', 0) + reserve
            session.limits = replace(session.limits,
                                     max_total_tokens=max(0, session.limits.max_total_tokens - reserve))
            session.resume_metadata.update(token_reserve=reserve, set_aside=in_flight.get('set_aside'))
        errors = root / 'provider-errors.jsonl'
        session.provider_errors = [json.loads(line) for line in errors.read_text().splitlines()] if errors.exists() else []
        return session
    except BaseException:
        if engine:
            engine.close()
        lease.close()
        raise
