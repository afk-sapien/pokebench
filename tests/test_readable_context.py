from copy import deepcopy
import json

import pytest

from pokeagent_bench.codex_provider import CodexProvider
from pokeagent_bench.gameplay_provider import GameplayCodexProvider
from pokeagent_bench.readable_context import render
from pokeagent_bench.visual_feedback import VisualFeedback
from test_continuous import events, ready


def payload():
    entry = {'action': {'command': 'move', 'argument': 'up', 'count': 4},
             'at': {'map_id': 40, 'x': 5, 'y': 11}, 'after': {'map_id': 40, 'x': 5, 'y': 8},
             'facing': 'up', 'outcome': 'Moved 3 tiles, then blocked.', 'encounter_id': 'dialogue-1',
             'same_observed_result_count': 2}
    return {'observation': {'objective': 'Find a new conversation', 'token_budget': {'used': 123, 'limit': 456},
              'game': {'location': entry['after'], 'local_map': {'origin': {'x': 4, 'y': 7}, 'rows': ['.#', '.@']},
                'party': [], 'bag': [], 'battle': {'kind': 'none'},
                'memory': {'agent_plan': {'goal': 'Test a guess', 'evidence': 'An unverified claim'},
                  'working_memory': {'recent_decisions': [{'decision': 9, 'commands': [entry]}],
                    'repeated_results': [entry], 'omitted_encounters': 2,
                    'encounters': [{'id': 'dialogue-1', 'text': 'A person said:\nThe door is closed.',
                                    'truncated': True, 'map_id': 40, 'count': 2}]}}}},
            'notes': 'I think the door opens later.', 'controller_results': [], 'frame': 888}


def test_readable_history_preserves_requested_vs_actual_and_dialogue():
    value = payload()
    before = deepcopy(value)
    text = render(value)
    assert value == before
    assert 'move up (count 4)' in text
    assert 'from map 40 (5, 11), facing up | to map 40 (5, 8)' in text
    assert 'result: "Moved 3 tiles, then blocked."' in text
    assert 'matching-result count: 2' in text
    assert 'A person said:\\nThe door is closed.' in text
    assert '(truncated: yes)' in text
    assert 'Omitted encounters: 2' in text
    assert 'AGENT PLAN (UNVERIFIED)' in text
    assert 'AGENT NOTEBOOK (UNVERIFIED)' in text
    assert '.#\n' in text and '.@\n' in text
    assert 'Used: 123' in text and 'Limit: 456' in text
    assert 'Party:\n  (empty list)' in text
    assert render(value) == text


def test_missing_dialogue_is_not_invented_and_extra_public_fields_survive():
    value = payload()
    command = value['observation']['game']['memory']['working_memory']['recent_decisions'][0]['commands'][0]
    command['encounter_id'] = 'not-retained'
    command['boundary_reason'] = 'transition'
    command['action']['new_public_field'] = 'kept'
    text = render(value)
    assert 'dialogue not-retained: not present in supplied recall' in text
    assert 'Boundary reason: transition' in text
    assert 'New public field: kept' in text


@pytest.mark.parametrize('compacting', [False, True])
def test_exact_text_is_sent_and_recorded_for_actions_and_summaries(monkeypatch, session, compacting):
    def init(self, model, **kwargs):
        self.model = model
        self.reasoning_effort = 'low'
        self.cli_version = 'test'
    monkeypatch.setattr(CodexProvider, '__init__', init)
    provider = GameplayCodexProvider('test-model', observation_format='text')
    stream = events()
    if compacting:
        stream[1]['params']['item']['text'] = json.dumps({'summary': 'An uncertain observation'})
        provider.context_tokens = provider.compact_at
    ready(provider, stream)
    server = provider.server
    observation = session.observe()
    observation['status']['track'] = 'gameplay'
    observation['status']['max_dialogue_frames'] = session.limits.max_dialogue_frames
    observation['game'] = payload()['observation']['game']
    observation['private_evaluator'] = 'NEVER_IN_MODEL_TEXT'
    observation['controller_view'] = VisualFeedback(session.output, current_only=True).prepare(observation, 1)
    _, _, record = provider.decide(observation, 'Agent notes', [], session.limits, 20)
    sent = server.requests[0][1]['input'][0]['text']
    assert sent == record['model_input_text'] == render(record['model_context'])
    assert sent.startswith('GAME OBSERVATION')
    assert 'NEVER_IN_MODEL_TEXT' not in sent
    assert provider.config_identity['observation_format'] == 'text'
    assert provider.config_identity['text_presentation'] == 'observed-gameplay-text-v2'


def test_text_cli_is_explicit_and_json_stays_default():
    from pokeagent_bench.cli import parser
    args = ['run', '--rom', 'x.gb', '--scenario', 'fixture', '--output', 'output', '--provider', 'codex']
    assert parser().parse_args(args).observation_format == 'json'
    assert parser().parse_args(args + ['--observation-format', 'text']).observation_format == 'text'


def test_render_is_stable_after_canonical_audit_log_roundtrip():
    original = payload()
    persisted = json.loads(json.dumps(original, sort_keys=True))
    assert render(original) == render(persisted)
    history = persisted['observation']['game']['memory']['working_memory']['recent_decisions']
    history.append({'decision': 10, 'commands': []})
    text = render(persisted)
    assert text.index('Decision 9:') < text.index('Decision 10:')
