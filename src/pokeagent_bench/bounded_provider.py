"""Short retained conversations with deterministic handoffs and no summary calls."""
import json
import time

from . import bounded_context
from .gameplay_provider import GameplayCodexProvider
from .providers import ProviderError
from .visual_feedback import public_context


class BoundedGameplayProvider(GameplayCodexProvider):
    harness = 'codex-app-server-gameplay-v036'
    memory_protocol = 'bounded-segments-deltas-v1'
    default_compact_at = 12000

    def __init__(self, *args, context_turns=8, **kwargs):
        if type(context_turns) is not int or not 2 <= context_turns <= 32:
            raise ValueError('context_turns must be between 2 and 32')
        if kwargs.get('continuity', True) is not True:
            raise ValueError('Bounded gameplay requires retained conversation segments')
        kwargs['continuity'] = True
        kwargs['observation_format'] = 'text'
        super().__init__(*args, **kwargs)
        self.context_turns = context_turns
        self.packet_baseline = None
        self.packet_sequence = 0
        self.segment_turns = 0
        self.segment_index = 0
        start = self.prompt.index('Working_memory contains')
        end = self.prompt.index('A separate agent_plan')
        self.prompt = self.prompt[:start] + '''The full observed action and dialogue archive stays outside this conversation.
Inspect memory to recall it. Your notebook holds persistent agent-authored notes.
''' + self.prompt[end:]
        self.prompt = self.prompt.replace('Your conversation is retained between decisions and periodically summarized.', '''Your conversation is retained for short segments. No model-generated summary is made.
Each new segment starts with a snapshot, your saved notebook and goal, and bounded
exact observed history. Preserve important discoveries and uncertainties in notes
during normal decisions. Use null to keep notes. Segment boundaries do not advance
the game. They do discard earlier conversational guesses not saved in your notes.
Updates name fields to replace and paths to remove. Omitted fields are unchanged
within this segment. A snapshot replaces all previous state. Sequence numbers
identify the previous packet. Current location, result and screenshot are current.
Agent notes and plans are unverified. Do not confuse a requested action with its result.''')
        self.config_identity.update(context_turns=context_turns, compaction_protocol='deterministic-checkpoint-no-summary-v1',
                                    text_presentation='bounded-gameplay-context-v1',
                                    ordinary_packet_bytes=bounded_context.PACKET_BYTES,
                                    inspection_packet_bytes=bounded_context.INSPECTION_BYTES)

    def prepare_packet(self, observation, notes, recent):
        rotate = (self.packet_baseline is None or self.segment_turns >= self.context_turns or
                  self.context_tokens >= self.compact_at)
        segment = self.segment_index + 1 if rotate else self.segment_index
        public = public_context(observation)
        packet, baseline = bounded_context.build(public, notes, recent,
            None if rotate else self.packet_baseline, self.packet_sequence + 1, segment)
        text = bounded_context.render(packet)
        bounded_context.check_size(packet, text)
        return public, packet, baseline, text, rotate

    def estimate_next_tokens(self, observation, notes, recent, limits):
        _, _, _, text, rotate = self.prepare_packet(observation, notes, recent)
        history = len(self.prompt.encode()) if rotate else self.context_tokens
        images = 2 if self.look_back is not None else 1
        output_allowance = max(4096, self.max_output_tokens or 0)
        return max(8000, history + len(text.encode()) + 2048 * images + output_allowance)

    def decide(self, observation, notes, recent, limits, timeout):
        if observation['status']['track'] != self.allowed_track:
            raise ProviderError('Bounded provider requires the gameplay track')
        deadline = time.monotonic() + min(timeout, 180)
        public, packet, baseline, text, rotate = self.prepare_packet(observation, notes, recent)
        if rotate:
            self.close()
            self.thread_id = self.last_turn_id = None
            self.total_usage = {key: 0 for key in self.total_usage}
            self.context_tokens = 0
            self.segment_turns = 0
        try:
            if self.server is None:
                self._start(deadline)
            view = observation['controller_view']
            record = {'cli_version': self.cli_version, 'reasoning_effort': self.reasoning_effort,
                      'context': public, 'model_context': packet, 'model_input_text': text,
                      'presentation': {key: value for key, value in view.items() if key != 'base64'},
                      'assessment': {}, 'session_id': self.thread_id,
                      'segment_start': rotate, 'segment': packet['segment'],
                      'input_text_bytes': len(text.encode())}
            inputs = [{'type': 'text', 'text': text}]
            if self.look_back is not None:
                if self.look_back <= len(self.history):
                    old = self.history[-self.look_back]
                    inputs.extend([{'type': 'text', 'text': f"EARLIER requested screenshot, frame {old['frame']}"},
                                   {'type': 'image', 'url': 'data:image/png;base64,' + old['image']}])
                    record['requested_history_frame'] = old['frame']
                    record['requested_history_presentation'] = old['presentation']
                else:
                    inputs.append({'type': 'text', 'text': 'Requested screenshot is outside retained history.'})
            inputs.extend([{'type': 'text', 'text': f"CURRENT frame {observation['frame']}"},
                           {'type': 'image', 'url': 'data:image/png;base64,' + view['base64']}])
            message, usage = self._complete('turn/start', {'threadId': self.thread_id, 'input': inputs,
                'effort': self.reasoning_effort, 'outputSchema': self.decision_schema(limits)}, deadline)
            response = json.loads(message)
            look_back = response.pop('look_back')
            if look_back is not None and (type(look_back) is not int or not 1 <= look_back <= 8):
                raise ValueError('Invalid look_back')
            if not response['actions'] and look_back is not None:
                record['maintenance'] = 'look_back'
            # The runner accounts for empty decisions and applies its invalid-response limit.
            self.look_back = look_back
            self.packet_baseline = baseline
            self.packet_sequence = packet['sequence']
            self.segment_index = packet['segment']
            self.segment_turns += 1
            self.history.append({'frame': observation['frame'], 'image': view['base64'],
                                 'presentation': record['presentation']})
            return response, usage, record
        except (KeyError, ValueError, TypeError, OSError) as error:
            raise ProviderError(f'Invalid bounded provider response: {type(error).__name__}. Usage may be unreported') from None
