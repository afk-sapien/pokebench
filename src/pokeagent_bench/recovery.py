"""Atomic decision-boundary checkpoints with fail-closed in-flight recovery."""
import base64
from collections import Counter, OrderedDict, deque
from dataclasses import asdict
from datetime import datetime, timezone
import fcntl
import json
import os
from pathlib import Path
import threading
import time

from .core import Limits, core_provenance, digest, encoded, validate_emulator_manifest
from .scoring import Evaluator
from .challenges import ChallengeEvaluator, PreparationEvaluator
from .campaign_runtime import CampaignTracker
from .catalog_runtime import CatalogEvaluator


LOGS = ('actions.jsonl', 'decisions.jsonl', 'memory.jsonl')
FIELDS = ('campaign_tracking', 'frame', 'actions', 'notes', 'reason', 'operation_ids', 'operations', 'trace_head',
          'usage', 'usage_available', 'journal_enabled', 'journal_entries', 'journal_results', 'current_decision',
          'gameplay_catalog', 'gameplay_memory', 'gameplay_inspection', 'gameplay_result', 'gameplay_operations')


def pack(value):
    if isinstance(value, bytes):
        return {'t': 'bytes', 'v': base64.b64encode(value).decode()}
    if isinstance(value, (Evaluator, ChallengeEvaluator, PreparationEvaluator, CatalogEvaluator, CampaignTracker)):
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
    if kind in ('Evaluator', 'ChallengeEvaluator', 'PreparationEvaluator', 'CatalogEvaluator', 'CampaignTracker'):
        result = object.__new__({'Evaluator': Evaluator, 'ChallengeEvaluator': ChallengeEvaluator,
                               'PreparationEvaluator': PreparationEvaluator, 'CatalogEvaluator': CatalogEvaluator,
                               'CampaignTracker': CampaignTracker}[kind])
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
    atomic(session.output / 'pending.json', {'decision': index, 'phase': 'model-or-controller-in-flight'})


def resume(rom, root, *, engine_factory=None, clock=time.monotonic):
    from .game import RedEngine
    from .session import Session
    root = Path(root).resolve()
    lease = lock_run(root)
    engine = None
    try:
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
        pending = root / 'pending.json'
        if pending.exists() and json.loads(pending.read_text())['decision'] > saved['runner']['decision_index']:
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
        session.campaign_tracking = manifest.get('scoring_protocol') == 'campaign-progress-v1'
        from .action_policy import from_manifest, tested_skill
        session.action_policy = from_manifest(manifest)
        session.tested_skill = manifest.get("tested_skill", tested_skill(manifest.get("scenario", {})))
        session.limits, session.evaluator = Limits(**saved['limits']), saved['evaluator']
        session.objective = getattr(session.evaluator, 'objective', None)
        session.score_max = 1 if session.objective else 75 if session.goal == 'first-gym' else 1000
        session.clock, session.started = clock, clock() - saved['elapsed']
        session.ended, session.reason, session.closed = None, None, False
        session.lock, session.run_lease = threading.RLock(), lease
        session.resume_state = saved['runner']
        resumed_at = datetime.now(timezone.utc)
        session.resume_metadata = {'checkpoint_saved_at': saved['saved_at'], 'restored_elapsed': saved['elapsed'],
                                   'resumed_at': resumed_at.isoformat(),
                                   'offline_seconds': max(0, (resumed_at - datetime.fromisoformat(saved['saved_at'])).total_seconds())}
        return session
    except BaseException:
        if engine:
            engine.close()
        lease.close()
        raise
