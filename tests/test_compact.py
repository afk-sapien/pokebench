from io import BytesIO
import json

from PIL import Image

from pokeagent_bench.compact_provider import CompactCodexProvider
from pokeagent_bench.core import Limits
from pokeagent_bench.review import build_run
from pokeagent_bench.runner import run
from pokeagent_bench.session import Session
from pokeagent_bench.visual_feedback import VisualFeedback, pack_screens


def png(color):
    out = BytesIO()
    Image.new('RGB', (160, 144), color).save(out, format='PNG')
    return out.getvalue()


def test_compact_preserves_every_pixel_and_chronological_duplicate_reference():
    samples = [{'frame': i, 'png': png(color)} for i, color in enumerate(['red', 'blue', 'red'])]
    raw, entries, layout = pack_screens(samples, compact=True)
    assert [e['panel'] for e in entries] == [2, 1, 2]
    assert [e['frame'] for e in entries] == [0, 1, 2]
    assert layout['panel_count'] == 2
    assert layout['current_panel'] == entries[-1]['panel'] == 2
    with Image.open(BytesIO(raw)) as image:
        assert image.size == (640, 320)
        for entry, sample in zip(entries, samples):
            x = (entry['panel'] - 1) * 320
            restored = image.crop((x, 32, x + 320, 320)).resize((160, 144), Image.Resampling.NEAREST)
            assert restored.tobytes() == Image.open(BytesIO(sample['png'])).tobytes()
    raw, entries, layout = pack_screens([samples[0]] * 3, compact=True)
    assert layout['panel_count'] == 1
    assert len(entries) == 3


def test_compact_context_allowlist_and_no_memory_truncation(session):
    provider = object.__new__(CompactCodexProvider)
    observation = session.observe()
    observation['status']['track'] = 'visual'
    observation['game'] = {'secret': 'PRIVATE_RAM'}
    observation['controller_view'] = VisualFeedback(session.output, compact=True).prepare(observation, 1)
    notes = {'observed': ['Important discovery'], 'hypotheses': [], 'unsuccessful_attempts': [], 'next_experiment': 'Old plan'}
    recent = [{'frame': i, 'action': {'button': 'left', 'hold_frames': 16, 'release_frames': 8},
               'executed_frames': 24, 'changed_pixel_fraction': 0.1, 'private': 'SECRET'} for i in range(8)]
    payload = provider.decision_context(observation, json.dumps(notes), recent)
    assert len(payload['recent_actions']) == 8
    assert payload['recent_actions'][-1] == [7, 'left', 16, 8, 24, 0.1]
    assert payload['observation']['current_panel'] == 1
    assert payload['previous_plan'] is None
    assert payload['notes']['observed'] == notes['observed']
    assert 'next_experiment' not in payload['notes']
    assert 'SECRET' not in provider.serialize_context(payload)
    assert 'PRIVATE_RAM' not in provider.serialize_context(payload)
    assert session.frame == 0


def test_compact_run_reuses_memory_and_review_understands_shared_panels(tmp_path, engine):
    initial = engine.screenshot()
    engine.screenshot = lambda: initial
    memory = {'observed': ['Keep this fact'], 'hypotheses': [], 'unsuccessful_attempts': []}

    class Provider(CompactCodexProvider):
        def __init__(self):
            self.model = 'fixture'
            self.calls = 0

        def decide(self, observation, notes, *args):
            self.calls += 1
            if self.calls > 1:
                assert json.loads(notes)['observed'] == ['Keep this fact']
                assert self.previous_plan['decision'] == self.calls - 1
                assert self.previous_plan['after_frame'] == observation['frame']
                assert self.previous_plan['expected_visible_change'] == 'None'
            response = {'assessment': {'scene': 'room'}, 'memory': memory if self.calls == 1 else None,
                        'plan': {'intent': 'Wait', 'expected_visible_change': 'None',
                                 'actions': [{'button': 'wait', 'hold_frames': 2, 'release_frames': 0}]}}
            decision, record = self.unpack_decision(response)
            record = {'assessment': record}
            record['presentation'] = {k: v for k, v in observation['controller_view'].items() if k != 'base64'}
            return decision, {'input_tokens': 10, 'output_tokens': 2}, record

    session = Session(engine, tmp_path / 'run', {}, track='visual', limits=Limits(max_model_calls=3))
    result = run(session, Provider())
    assert result['frames'] == 6
    review = build_run(session.output)
    assert len(review['steps']) == 3 and len(review['images']) == 1
    assert review['steps'][-1]['observed'] == ['Keep this fact']
    assert [(s['before_frame'], s['after_frame']) for s in review['steps']] == [(0, 2), (2, 4), (4, 6)]
    manifest = json.loads((session.output / 'manifest.json').read_text())
    assert manifest['agent']['harness'] == CompactCodexProvider.harness
    assert manifest['agent']['stagnation_guard'] is False


def test_rejected_action_can_be_retried_without_losing_executed_plan(tmp_path, engine):
    class Provider(CompactCodexProvider):
        def __init__(self):
            self.model = 'fixture'
            self.calls = 0

        def decide(self, observation, notes, recent, *args):
            self.calls += 1
            payload = self.decision_context(observation, notes, recent)
            if self.calls == 3:
                assert payload['previous_plan']['decision'] == 1
                assert payload['previous_plan']['after_frame'] == 2
                assert payload['previous_plan']['intent'] == 'Plan 1'
                assert payload['recent_actions'][-1] == {'error': 'Unknown controller button'}
            response = {
                'assessment': {'scene': 'uncertain', 'previous_result': 'Uncertain'},
                'memory': None,
                'plan': {'intent': f'Plan {self.calls}', 'expected_visible_change': 'Observe',
                         'actions': [{'button': 'invalid' if self.calls == 2 else 'wait',
                                      'hold_frames': 2, 'release_frames': 0}]},
            }
            decision, assessment = self.unpack_decision(response)
            return decision, {'input_tokens': 1, 'output_tokens': 1}, {'assessment': assessment}

    provider = Provider()
    session = Session(engine, tmp_path / 'retry', {}, track='visual', limits=Limits(max_model_calls=3))
    result = run(session, provider)
    assert result['stop_reason'] == 'model_call_budget'
    assert result['frames'] == 4
    assert provider.previous_plan['decision'] == 3
    assert provider.previous_plan['after_frame'] == 4
