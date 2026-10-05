"""Compare saved v0.6 inputs with compact packaging without model calls or emulator ticks."""
import argparse
from io import BytesIO
import json
import math
from pathlib import Path

from PIL import Image

from pokeagent_bench.compact_provider import CompactCodexProvider
from pokeagent_bench.review import build_run, read_artifact, rows
from pokeagent_bench.visual_feedback import pack_screens


def audit(root):
    review = build_run(root)
    steps = {step["decision"]: step for step in review["steps"]}
    provider = object.__new__(CompactCodexProvider)
    totals = dict(decisions=0, old_image_patch_estimate=0, compact_image_patch_estimate=0,
                  old_context_bytes=0, compact_context_bytes=0, original_panels=0, compact_panels=0)
    for decision in rows(root, 'decisions.jsonl'):
        record = decision['provider']
        view = record['presentation']
        if view['scale'] != 3 or view['layout'] != 'chronological-left-to-right-then-next-row':
            raise ValueError('Audit expects legacy 3x strips')
        samples = []
        with Image.open(BytesIO(read_artifact(root, view['artifact']))) as image:
            totals['old_image_patch_estimate'] += math.ceil(image.width / 32) * math.ceil(image.height / 32)
            columns = min(3, len(view['screens']))
            for i, entry in enumerate(view['screens']):
                x, y = i % columns * 480, i // columns * 472 + 40
                restored = image.crop((x, y, x + 480, y + 432)).resize((160, 144), Image.Resampling.NEAREST)
                stream = BytesIO()
                restored.save(stream, format='PNG')
                samples.append({**entry, 'png': stream.getvalue()})
        packed, screens, layout = pack_screens(samples, compact=True)
        with Image.open(BytesIO(packed)) as image:
            totals['compact_image_patch_estimate'] += math.ceil(image.width / 32) * math.ceil(image.height / 32)
        old = {'observation': record['context'], 'notes': json.loads(record['notes']) if record['notes'] else None,
               'recent_actions': record['recent_actions']}
        if old['notes']:
            old['notes'].pop('next_experiment', None)
        observation = {'frame': record['context']['frame'], 'status': record['context'],
                       'controller_view': {**view, **layout, 'screens': screens}}
        if 'game' in record['context']:
            observation['game'] = record['context']['game']
        compact = provider.decision_context(observation, record['notes'], record['recent_actions'])
        totals['old_context_bytes'] += len(json.dumps(old, sort_keys=True).encode())
        totals['compact_context_bytes'] += len(provider.serialize_context(compact).encode())
        totals['decisions'] += 1
        totals['original_panels'] += len(samples)
        totals['compact_panels'] += layout['panel_count']
        step = steps[decision['index']]
        if step['after_frame'] > step['before_frame']:
            provider.remember_executed_plan(record, decision['index'], step['after_frame'])
    return {'run': root.name, 'recorded_prompt_bytes': len(read_artifact(root, 'prompt.txt')), **totals,
            'image_patch_reduction_percent': round(100 * (1 - totals['compact_image_patch_estimate'] / totals['old_image_patch_estimate']), 2),
            'context_byte_reduction_percent': round(100 * (1 - totals['compact_context_bytes'] / totals['old_context_bytes']), 2)}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('runs', nargs='+', type=Path)
    args = parser.parse_args()
    print(json.dumps({'method': '32px patch proxy, no model token measurement. Context bytes exclude prompt and response schema.',
                      'compact_prompt_bytes': len(CompactCodexProvider.prompt.encode()),
                      'runs': [audit(root.resolve()) for root in args.runs]}, indent=2))
