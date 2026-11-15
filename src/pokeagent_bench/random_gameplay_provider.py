"""A free random player for the smoke suite. It calls no model and reports no tokens.

It sends one random command per decision through the same bounded gameplay protocol a model uses,
so a smoke run, submit and verify can be checked end to end at no cost. Its runs are never results.
"""
import json
import random

from .bounded_provider import BoundedGameplayProvider


class RandomGameplayProvider(BoundedGameplayProvider):
    provider = 'random-gameplay'
    harness = 'random-gameplay-bounded-v1'

    def __init__(self, model, *, seed=7, **kwargs):
        self.seed = seed
        self.rng = random.Random(seed)
        super().__init__(model, **kwargs)
        self.config_identity.update(transport='none', seed=seed, usage_accounting='no-model-zero-tokens-v1')

    def _initialize_cli(self):
        self.cli_version = None

    def _start(self, deadline):
        self.server = self

    def close(self):
        self.server = None

    def _complete(self, method, params, deadline):
        # Commands with a fixed list of arguments. Free text commands such as choose are left out.
        variants = [variant['properties'] for variant in params['outputSchema']['properties']['actions']['items']['anyOf']
                    if 'enum' in variant['properties']['argument']]
        chosen = self.rng.choice(variants)
        count = chosen['count']
        action = {'command': chosen['command']['enum'][0], 'argument': self.rng.choice(chosen['argument']['enum']),
                  'count': count['enum'][0] if 'enum' in count else self.rng.randint(1, min(4, count['maximum']))}
        self.context_tokens = 0
        return json.dumps({'actions': [action]}), {'input_tokens': 0, 'output_tokens': 0, 'cached_input_tokens': 0}
