from copy import deepcopy
import json
import shlex

import pytest

from conftest import FakeEngine
from pokeagent_bench import own_release, submission
from pokeagent_bench.core import Limits, core_provenance, digest, emulator_manifest, encoded
from pokeagent_bench.memory import CONFIG, search, validate
from pokeagent_bench.recovery import atomic, lock_run, pack, resume, unpack
from pokeagent_bench.runner import run
from pokeagent_bench.session import Session


EMPTY = {'writes': [], 'delete': [], 'query': None}


class Provider:
    provider = 'codex'
    model = 'test'
    visual_feedback = True
    compact_feedback = True
    prompt = 'test'

    def __init__(self):
        self.contexts = []

    def decide(self, observation, notes, recent, *args):
        self.contexts.append((deepcopy(observation), notes, deepcopy(recent)))
        self.previous_plan = {'expected': 'test'}
        self.next_decision_token_estimate = 15
        return {'actions': [{'button': 'wait', 'hold_frames': 2, 'release_frames': 0}],
                'notes': 'my own memory', 'journal': {'writes': [{'key': 'room', 'text': 'my hypothesis'}],
                                                    'delete': [], 'query': 'room'}}, {
                    'input_tokens': 10, 'output_tokens': 5}, {}

    def close(self):
        pass


def factory(rom, state):
    engine = FakeEngine()
    engine.frame = int(state.decode().split('-')[-1])
    return engine


def setup_run(tmp_path, *, pause=2, clock=lambda: 100):
    rom = tmp_path / 'test.gb'
    rom.write_bytes(b'fake rom')
    session = Session(FakeEngine(), tmp_path / 'run', {'rom_sha256': digest(rom.read_bytes())},
                      track='visual', limits=Limits(max_model_calls=4), journal=True, clock=clock)
    result = run(session, Provider(), pause_after_decisions=pause)
    return session, rom, result


def test_journal_bounds_and_transaction():
    original = {'earlier': 'oak north', 'latest': 'OAK south'}
    assert [x['key'] for x in search(original, 'oak')] == ['latest', 'earlier']
    assert [x['key'] for x in search(original, 'oak north')] == ['earlier']
    assert search(original, None) == []
    assert search(original, 'missing') == []
    bad = {'writes': [{'key': 'x', 'text': '🦊' * 513}], 'delete': ['earlier'], 'query': None}
    with pytest.raises(ValueError):
        validate(original, bad)
    assert original == {'earlier': 'oak north', 'latest': 'OAK south'}
    results = search({str(i): '🦊' * 512 for i in range(8)}, '')
    assert sum(len(x['key'].encode()) + len(x['text'].encode()) for x in results) <= CONFIG['retrieval_bytes']
    assert results[-1]['truncated']
    with pytest.raises(ValueError):
        validate({}, {**EMPTY, 'writes': [{'key': 'bad key', 'text': 'no'}]})
    with pytest.raises(ValueError):
        validate({str(i): 'x' for i in range(128)}, {**EMPTY, 'writes': [{'key': 'new', 'text': 'x'}]})
    with pytest.raises(ValueError):
        validate({str(i): 'x' * 2048 for i in range(32)}, EMPTY)


def test_pause_resume_preserves_context_counters_and_active_time(tmp_path):
    session, rom, result = setup_run(tmp_path)
    assert result['state'] == 'paused'
    assert result['usage']['calls'] == 2
    restored = resume(rom, session.output, engine_factory=factory, clock=lambda: 9999)
    assert restored.elapsed() == result['wall_seconds']
    assert restored.notes == 'my own memory'
    assert restored.journal_entries == {'room': 'my hypothesis'}
    assert restored.trace_head == session.trace_head
    assert restored.operation_ids == session.operation_ids
    assert restored.evaluator.__dict__ == session.evaluator.__dict__
    assert restored.act('decision-2-1', None, 2, 0)['frame'] == 4
    assert restored.actions == 2
    provider = Provider()
    final = run(restored, provider)
    assert final['stop_reason'] == 'model_call_budget'
    assert final['frames'] == 8
    assert final['actions'] == final['usage']['calls'] == 4
    assert final['usage']['input_tokens'] == 40
    observation, notes, recent = provider.contexts[0]
    assert observation['journal']['results'][0]['text'] == 'my hypothesis'
    assert [x['frame'] for x in recent] == [2, 4]
    assert observation['controller_view']['screens'][-1]['frame'] == 4
    rows = [json.loads(x) for x in (session.output / 'decisions.jsonl').read_text().splitlines()]
    assert [x['index'] for x in rows] == [1, 2, 3, 4]
    audits = [json.loads(x) for x in (session.output / 'memory.jsonl').read_text().splitlines()]
    assert sum(x['kind'] == 'resume' for x in audits) == 1
    with pytest.raises(ValueError, match='cannot be resumed'):
        resume(rom, session.output, engine_factory=factory)


@pytest.mark.parametrize('corruption,match', [
    ('checksum', 'checksum'), ('manifest', 'manifest'), ('rom', 'ROM'),
    ('log', 'log'), ('pending', 'uncertain')])
def test_recovery_refuses_unsafe_continuation(tmp_path, corruption, match):
    session, rom, _ = setup_run(tmp_path)
    root = session.output
    if corruption == 'checksum':
        wrapper = json.loads((root / 'recovery.json').read_text())
        wrapper['sha256'] = 'wrong'
        atomic(root / 'recovery.json', wrapper)
    elif corruption == 'manifest':
        value = json.loads((root / 'manifest.json').read_text())
        value['limits']['max_total_tokens'] += 1
        atomic(root / 'manifest.json', value)
    elif corruption == 'rom':
        rom.write_bytes(b'other rom')
    elif corruption == 'log':
        with (root / 'actions.jsonl').open('a') as stream:
            stream.write('{}\n')
    else:
        atomic(root / 'pending.json', {'decision': 3})
    with pytest.raises(ValueError, match=match):
        resume(rom, root, engine_factory=factory)
    lease = lock_run(root)
    lease.close()


def test_source_change_alone_refuses_resume(tmp_path, monkeypatch):
    # A build that is no release records none in its manifest, and no accepted entry matches it.
    monkeypatch.setattr(own_release, 'release', lambda: None)
    session, rom, _ = setup_run(tmp_path)
    assert json.loads((session.output / 'manifest.json').read_text())['release'] is None
    real = submission.this_harness()
    monkeypatch.setattr(submission, 'this_harness', lambda: {**real, 'source_sha256': 'edited'})
    monkeypatch.setattr(submission, 'accepted_harness', lambda: [])
    with pytest.raises(own_release.OtherRelease, match='exact runtime source') as caught:
        resume(rom, session.output, engine_factory=factory)
    assert caught.value.tag is None
    assert 'not a release and differs from this one in its source. Check out that build' in str(caught.value)
    assert 'uvx' not in str(caught.value)
    lease = lock_run(session.output)
    lease.close()


def test_other_release_refusal_names_the_tag(tmp_path, monkeypatch):
    here = {**submission.this_harness(), 'core': core_provenance(), **emulator_manifest()}
    assert own_release.differences(here) == []
    older_core = {**here, 'core': {**here['core'], 'version': '0.11.0'}}
    assert own_release.differences(older_core) == [f'Core (run 0.11.0, here {here["core"]["version"]})']
    older_emulator = {**here, 'emulator': {**here['emulator'], 'version': '0.1.5'}}
    assert own_release.differences(older_emulator) == [
        f'emulator exact runtime fingerprint (run {here["emulator"]["backend"]} 0.1.5, here {here["emulator"]["backend"]} '
        f'{here["emulator"]["version"]})']
    # Runs from before the release field are matched to their accepted entry.
    entry = next(entry for entry in submission.accepted_harness() if entry['package_version'] == '0.37.4')
    assert own_release.run_release(dict(entry)) == 'v0.37.4'
    assert own_release.run_release({**entry, 'source_sha256': 'edited'}) is None

    tag = {'tag': 'v0.37.4', 'install': own_release.install('v0.37.4')}
    monkeypatch.setattr(own_release, 'release', lambda: tag)
    session, rom, _ = setup_run(tmp_path)
    assert json.loads((session.output / 'manifest.json').read_text())['release'] == tag
    real = submission.this_harness()
    monkeypatch.setattr(submission, 'this_harness', lambda: {**real, 'source_sha256': 'newer'})
    words = ['resume', '--rom', str(rom), '--run', str(session.output)]
    monkeypatch.setattr('sys.argv', ['pokebench', *words])
    with pytest.raises(own_release.OtherRelease) as caught:
        resume(rom, session.output, engine_factory=factory)
    assert caught.value.tag == 'v0.37.4'
    assert str(caught.value) == (
        'This run was made by v0.37.4 and differs from this build in its source. A run resumes only on the build '
        'that started it. Run the same command on v0.37.4:\n  '
        + shlex.join(['uvx', '--from', 'git+https://github.com/afk-sapien/pokebench@v0.37.4', 'pokebench', *words]))
    lease = lock_run(session.output)
    lease.close()


def test_resume_names_the_cli_build_the_run_used(tmp_path):
    class Pinned(Provider):
        provider = 'claude-code'
        cli_version = '2.1.300 (Claude Code)'

    class Newer(Pinned):
        cli_version = '2.1.400 (Claude Code)'

    rom = tmp_path / 'test.gb'
    rom.write_bytes(b'fake rom')
    session = Session(FakeEngine(), tmp_path / 'run', {'rom_sha256': digest(rom.read_bytes())},
                      track='visual', limits=Limits(max_model_calls=4), journal=True, clock=lambda: 100)
    assert run(session, Pinned(), pause_after_decisions=2)['state'] == 'paused'
    restored = resume(rom, session.output, engine_factory=factory)
    with pytest.raises(ValueError, match=r'the CLI build this run used, 2\.1\.300 \(Claude Code\), not 2\.1\.400 '
                                         r'\(Claude Code\)\. Copy that build to toolchains/claude-2\.1\.300/bin/claude'):
        run(restored, Newer())
    restored.close()


def test_committed_pending_and_writer_lock(tmp_path):
    session, rom, _ = setup_run(tmp_path)
    atomic(session.output / 'pending.json', {'decision': 2})
    restored = resume(rom, session.output, engine_factory=factory)
    with pytest.raises(ValueError, match='another process'):
        resume(rom, session.output, engine_factory=factory)
    restored.close()


def test_memory_only_costs_tokens_without_advancing_game(tmp_path):
    class MemoryOnly(Provider):
        def decide(self, *args):
            decision, usage, record = super().decide(*args)
            decision['actions'] = []
            return decision, usage, record
    session = Session(FakeEngine(), tmp_path / 'memory-only', {}, journal=True, limits=Limits(max_model_calls=2))
    result = run(session, MemoryOnly())
    assert result['usage']['input_tokens'] == 20
    assert result['frames'] == result['actions'] == 0
    assert session.journal_entries == {'room': 'my hypothesis'}


def test_invalid_action_cannot_mutate_memory(tmp_path):
    class Invalid(Provider):
        def decide(self, *args):
            decision, usage, record = super().decide(*args)
            decision['actions'][0]['button'] = 'teleport'
            return decision, usage, record
    session = Session(FakeEngine(), tmp_path / 'invalid', {}, journal=True)
    result = run(session, Invalid())
    assert result['stop_reason'] == 'invalid_model_response'
    assert session.notes == '' and session.journal_entries == {}
    assert not (session.output / 'memory.jsonl').exists()


def test_tagged_checkpoint_roundtrip_preserves_tuple_counters():
    from collections import Counter, deque
    value = {'counts': Counter({('a', 8, 2): 3}), 'bytes': b'game', 'queue': deque([1, 2], maxlen=3)}
    restored = unpack(json.loads(encoded(pack(value))))
    assert restored == value
    assert restored['queue'].maxlen == 3


def test_journal_provider_schema_and_public_allowlist(session):
    from pokeagent_bench.journal_provider import JournalCodexProvider
    from pokeagent_bench.visual_feedback import VisualFeedback
    provider = object.__new__(JournalCodexProvider)
    schema = provider.decision_schema(session.limits)
    assert schema['properties']['plan']['properties']['actions']['minItems'] == 0
    assert 'journal' in schema['required']
    observation = session.observe()
    observation['status']['track'] = 'visual'
    observation['game'] = {'private': 'HIDDEN_STATE'}
    observation['status']['achievements'] = ['HIDDEN_STATE']
    observation['journal'] = session.journal_context()
    observation['controller_view'] = VisualFeedback(session.output, compact=True).prepare(observation, 1)
    payload = provider.decision_context(observation, '', [])
    assert 'HIDDEN_STATE' not in json.dumps(payload)
    decision, _ = provider.unpack_decision({'assessment': {}, 'memory': None,
        'plan': {'intent': 'remember', 'expected_visible_change': 'none', 'actions': []}, 'journal': EMPTY})
    assert decision == {'actions': [], 'notes': None, 'journal': EMPTY}


def test_resume_restores_final_queued_release_without_ticking(tmp_path):
    class Held(Provider):
        def decide(self, *args):
            decision, usage, record = super().decide(*args)
            decision['actions'][0]['button'] = 'right'
            return decision, usage, record
    rom = tmp_path / 'test.gb'
    rom.write_bytes(b'fake rom')
    session = Session(FakeEngine(), tmp_path / 'held', {'rom_sha256': digest(rom.read_bytes())},
                      journal=True, limits=Limits(max_model_calls=3))
    run(session, Held(), pause_after_decisions=1)
    restored = resume(rom, session.output, engine_factory=factory)
    assert restored.engine.inputs == [('release', 'right', 2)]
    assert restored.frame == restored.engine.frame == 2
    assert restored.actions == 1
    restored.close()


def test_pause_resume_does_not_refill_area_allowance(tmp_path):
    rom = tmp_path / 'test.gb'
    rom.write_bytes(b'fake rom')
    session = Session(FakeEngine(), tmp_path / 'area-resume', {'rom_sha256': digest(rom.read_bytes())},
                      journal=True, limits=Limits(max_area_tokens=45))
    paused = run(session, Provider(), pause_after_decisions=2)
    assert paused['state'] == 'paused'
    restored = resume(rom, session.output, engine_factory=factory)
    final = run(restored, Provider())
    assert final['stop_reason'] == 'area_token_budget'
    assert final['usage']['calls'] == 3
    state = json.loads((session.output / 'area_budget.json').read_text())
    assert state['tokens_in_area'] == 45
    assert state['entry_tokens'] == 0
