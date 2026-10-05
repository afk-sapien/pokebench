import base64
from collections import deque
from io import BytesIO
import json
import time

from PIL import Image
import pytest

from pokeagent_bench.codex_provider import CodexProvider
from pokeagent_bench.continuous_provider import ContinuousCodexProvider
from pokeagent_bench.providers import ProviderError
from pokeagent_bench.visual_feedback import VisualFeedback


@pytest.fixture
def provider(monkeypatch):
    def init(self, model, **kwargs):
        self.model = model
        self.reasoning_effort = kwargs.get("reasoning_effort", "low")
        self.cli_version = "test"
    monkeypatch.setattr(CodexProvider, "__init__", init)
    return ContinuousCodexProvider("explicit-model")


class Server:
    def __init__(self, events):
        self.events = deque(events)
        self.requests = []

    def request(self, method, params, deadline):
        self.requests.append((method, params))
        return {} if method == "thread/compact/start" else {"turn": {"id": "t1"}}

    def event(self, deadline):
        return self.events.popleft()

    def close(self):
        pass


def events(*, compact=False, usage=True, total=100, outside=False):
    thread, turn = "thread", "t1"
    result = [{"method": "turn/started", "params": {"threadId": thread, "turn": {"id": turn}}}]
    item = {"type": "contextCompaction"} if compact else {"type": "agentMessage", "text": json.dumps({
        "actions": [{"button": "wait", "hold_frames": 60, "release_frames": 0}], "notes": None, "look_back": None})}
    if outside:
        item = {"type": "commandExecution"}
    result.append({"method": "item/completed", "params": {"threadId": thread, "turnId": turn, "item": item}})
    if usage:
        result.append({"method": "thread/tokenUsage/updated", "params": {"threadId": thread, "turnId": turn,
            "tokenUsage": {"total": {"inputTokens": total, "outputTokens": 10, "cachedInputTokens": 0},
                           "last": {"inputTokens": 100, "outputTokens": 10}}}})
    result.append({"method": "turn/completed", "params": {"threadId": thread,
                                                           "turn": {"id": turn, "status": "completed"}}})
    return result


def ready(provider, items):
    provider.thread_id = "thread"
    provider.server = Server(items)
    return provider


def test_usage_is_delta_not_recounted_total(provider):
    ready(provider, events(total=300))
    provider.total_usage = {"inputTokens": 200, "outputTokens": 4, "cachedInputTokens": 0}
    _, usage = provider._complete("turn/start", {}, time.monotonic()+10)
    assert usage == {"input_tokens": 100, "output_tokens": 6, "cached_input_tokens": 0}
    assert provider.last_turn_id == "t1"


@pytest.mark.parametrize("settings", [{"usage": False}, {"outside": True}, {"compact": True}])
def test_unaccounted_or_outside_operations_fail_closed(provider, settings):
    ready(provider, events(**settings))
    with pytest.raises(ProviderError):
        provider._complete("turn/start", {}, time.monotonic()+10)


def test_compaction_counted_without_gameplay(provider, session):
    stream = events()
    stream[1]["params"]["item"]["text"] = json.dumps({"summary": "I am still exploring the room. My location is uncertain."})
    ready(provider, stream)
    provider.context_tokens = provider.compact_at
    obs = session.observe()
    obs["status"]["track"] = "visual"
    obs["controller_view"] = VisualFeedback(session.output, current_only=True).prepare(obs, 1)
    decision, usage, record = provider.decide(obs, "", [], session.limits, 20)
    assert decision == {"actions": [], "notes": None}
    assert record["maintenance"] == "compaction"
    assert usage["input_tokens"] == 100
    assert provider.compactions == 1
    assert provider.thread_id is None
    assert provider.pending_summary.startswith("I am still")
    assert session.frame == 0


def test_single_current_frame_is_exact_and_fixed(session):
    feedback = VisualFeedback(session.output, current_only=True)
    first = session.observe()
    feedback.prepare(first, 1)
    session.engine.tick()
    feedback.record({"button": None, "hold_frames": 1, "release_frames": 0}, 0, 1,
                    session.observe()["screenshot"])
    obs = session.observe()
    obs["frame"] = 1
    view = feedback.prepare(obs, 2)
    assert len(view["screens"]) == 1
    im = Image.open(BytesIO(base64.b64decode(view["base64"])))
    original = Image.open(BytesIO(base64.b64decode(obs["screenshot"]["base64"]))).convert("RGB")
    assert im.size == (480, 472)
    assert im.crop((0, 40, 480, 472)).tobytes() == original.resize((480, 432), Image.Resampling.NEAREST).tobytes()


def test_private_evidence_not_in_continuous_payload(provider, session):
    ready(provider, events())
    obs = session.observe()
    obs["status"]["track"] = "visual"
    obs["game"] = {"secret": "NOT_VISIBLE"}
    obs["controller_view"] = VisualFeedback(session.output, current_only=True).prepare(obs, 1)
    _, _, record = provider.decide(obs, "my notes", [], session.limits, 20)
    inputs = provider.server.requests[0][1]["input"]
    assert "NOT_VISIBLE" not in json.dumps(inputs)
    assert record["model_context"]["notes"] == "my notes"
    assert len(provider.history) == 1


def test_schema_has_no_required_object_inventory(provider, session):
    schema = provider.decision_schema(session.limits)
    assert set(schema["required"]) == {"actions", "notes", "look_back"}
    provider.response_contract = "assessment"
    assert set(provider.decision_schema(session.limits)["required"]) == {"assessment", "memory", "plan"}


def test_recall_returns_exact_earlier_image_and_provenance(provider, session):
    ready(provider, events())
    obs = session.observe()
    obs['status']['track'] = 'visual'
    view = VisualFeedback(session.output, current_only=True).prepare(obs, 1)
    obs['controller_view'] = view
    old_view = {k: v for k, v in view.items() if k != 'base64'}
    provider.history.append({'frame': 0, 'image': view['base64'], 'presentation': old_view})
    provider.look_back = 1
    _, _, record = provider.decide(obs, '', [], session.limits, 20)
    inputs = provider.server.requests[0][1]['input']
    images = [item['url'] for item in inputs if item['type'] == 'image']
    assert images == ['data:image/png;base64,' + view['base64']] * 2
    assert record['requested_history_presentation'] == old_view


def test_counter_regression_is_rejected(provider):
    ready(provider, events(total=10))
    provider.total_usage['inputTokens'] = 100
    with pytest.raises(ProviderError, match='cumulative'):
        provider._complete('turn/start', {}, time.monotonic()+10)


def test_summary_sees_latest_controller_result_and_pixels(provider, session):
    stream = events()
    stream[1]['params']['item']['text'] = json.dumps({'summary': 'The last input was rejected.'})
    ready(provider, stream)
    server = provider.server
    provider.context_tokens = provider.compact_at
    obs = session.observe()
    obs['status']['track'] = 'visual'
    obs['controller_view'] = VisualFeedback(session.output, current_only=True).prepare(obs, 1)
    provider.decide(obs, '', [{'error': 'Action exceeds frame limit'}], session.limits, 20)
    inputs = server.requests[0][1]['input']
    assert 'Action exceeds frame limit' in inputs[0]['text']
    assert inputs[1]['type'] == 'image'


def test_maintenance_is_charged_and_checkpointed_without_frames(tmp_path):
    from conftest import FakeEngine
    from pokeagent_bench.core import Limits
    from pokeagent_bench.recovery import unpack
    from pokeagent_bench.runner import run
    from pokeagent_bench.session import Session

    class Maintenance:
        provider = 'codex'
        model = 'test'
        maintenance_decisions = True
        pending_summary = 'Agent-authored memory'
        thread_id = None
        total_usage = {'inputTokens': 0, 'outputTokens': 0, 'cachedInputTokens': 0}

        def decide(self, *args):
            return {'actions': [], 'notes': None}, {'input_tokens': 40, 'output_tokens': 8}, {'maintenance': 'compaction'}

        def close(self):
            pass

    session = Session(FakeEngine(), tmp_path/'maintenance', {}, limits=Limits(max_model_calls=1))
    result = run(session, Maintenance())
    assert result['frames'] == result['actions'] == 0
    assert result['usage']['input_tokens'] + result['usage']['output_tokens'] == 48
    saved = unpack(json.loads((session.output/'recovery.json').read_text())['payload'])
    assert saved['runner']['provider']['pending_summary'] == 'Agent-authored memory'


def test_resume_refuses_a_different_latest_turn(provider, monkeypatch, tmp_path):
    import pokeagent_bench.continuous_provider as module

    class ResumeServer:
        def __init__(self, *args, **kwargs):
            pass

        def request(self, method, params, deadline):
            if method == 'initialize':
                return {}
            if method == 'config/read':
                return {'config': {'mcp_servers': {}}}
            assert method == 'thread/resume'
            return {'thread': {'turns': [{'id': 'uncheckpointed-turn', 'status': 'completed'}]}}

        def send(self, *args):
            pass

        def close(self):
            pass

    monkeypatch.setattr(module, 'AppServer', ResumeServer)
    provider.executable = 'codex'
    provider.env = {}
    provider.thread_id = 'original-session'
    provider.last_turn_id = 'checkpointed-turn'
    try:
        with pytest.raises(ProviderError, match='does not match'):
            provider._start(time.monotonic()+10)
    finally:
        provider.close()


def test_retained_turns_share_session_then_receive_metered_handoff(provider, session):
    obs = session.observe()
    obs['status']['track'] = 'visual'
    obs['controller_view'] = VisualFeedback(session.output, current_only=True).prepare(obs, 1)
    ready(provider, events(total=100))
    server = provider.server
    _, first_usage, first = provider.decide(obs, 'Notebook', [], session.limits, 20)
    server.events.extend(events(total=200))
    _, second_usage, second = provider.decide(obs, 'Notebook', [], session.limits, 20)
    assert first['session_id'] == second['session_id'] == 'thread'
    assert provider.server is server
    assert first_usage['input_tokens'] == second_usage['input_tokens'] == 100
    assert second_usage['output_tokens'] == 0

    stream = events(total=300)
    handoff = 'Observed the same response twice. My next experiment remains uncertain.'
    stream[1]['params']['item']['text'] = json.dumps({'summary': handoff})
    server.events.extend(stream)
    provider.context_tokens = provider.compact_at
    _, summary_usage, summary_record = provider.decide(obs, 'Notebook', [], session.limits, 20)
    assert summary_record['maintenance'] == 'compaction'
    assert summary_usage['input_tokens'] == 100
    assert provider.thread_id is None
    assert provider.server is None
    assert session.frame == 0

    ready(provider, events(total=100))
    _, _, resumed = provider.decide(obs, 'Notebook', [], session.limits, 20)
    assert resumed['model_context']['agent_history_summary'] == handoff
    assert resumed['model_context']['notes'] == 'Notebook'
    assert provider.pending_summary is None
    provider.server.events.extend(events(total=200))
    _, _, later = provider.decide(obs, 'Notebook', [], session.limits, 20)
    assert 'agent_history_summary' not in later['model_context']


def test_gameplay_default_retains_context_with_larger_threshold(provider):
    from pokeagent_bench.gameplay_provider import GameplayCodexProvider
    gameplay = GameplayCodexProvider('explicit-model')
    assert gameplay.continuity is True
    assert gameplay.compact_at == 32000
    assert gameplay.config_identity['continuity'] is True
    assert 'conversation is retained' in gameplay.prompt
    fresh = GameplayCodexProvider('explicit-model', continuity=False)
    assert fresh.continuity is False
    assert 'Each decision starts fresh' in fresh.prompt
