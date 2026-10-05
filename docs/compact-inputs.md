# Compact inputs in red-v0.8-experimental

The compact Codex policy is the default for new runs. It changes presentation and
prompting, not scoring, game speed, controller actions, or token budget accounting.
Select `--codex-policy grounded` to retain the previous unassisted assessment-first
policy. Use the frozen source snapshot to reproduce the exact older benchmark.

## Changes

- 2x nearest-neighbor game pixels instead of 3x, preserving every native pixel.
- One copy of each exact RGB screen within a decision image. A chronological list
  maps every frame to its numbered panel. Its final entry is the current view,
  which can refer back to an earlier panel. Distinct screens are never discarded.
- A 32-pixel panel header instead of 40. Button timing remains in controller text.
- All eight recent inputs stay available as rows with explicit column names.
  Executed frames and changed-pixel fractions remain. Redundant start-frame and
  image-changed fields are omitted. These are controller facts, not game labels.
- Compact JSON and a shorter prompt. Notebook contents are never truncated.
  Null memory preserves the existing notebook instead of requiring a rewrite.
  The model still performs its own scene assessment and chooses every action.
- Review exports accept both formats, including repeated current-panel references
  and retained notebook contents. The agent harness and prompt distinguish groups.

No motion estimates, object recognition, route hints, or repeated-view stopping
rule are enabled by this policy. Reasoning effort remains the configured value,
with low as the CLI default. Existing run budgets and scoring are unchanged.

## Offline audit of the three million-token runs

The audit repackaged all 433 saved model inputs without calling a model or ticking
an emulator. Source image checksums were validated. The context comparison retains
the original notebook text, so it assumes no benefit from shorter model responses.

| Model | Decisions | Image patch reduction | Context byte reduction | Panels before / after |
| --- | ---: | ---: | ---: | ---: |
| Luna | 157 | 58.89% | 42.03% | 347 / 321 |
| Terra | 138 | 58.61% | 42.78% | 320 / 298 |
| Sol | 138 | 58.33% | 39.19% | 337 / 316 |

The prompt is 1,675 UTF-8 bytes versus 1,903. Context bytes exclude the prompt and
response schema. These are size measurements, not measured model token savings.
The image proxy counts 32 by 32 pixel patches using the documented
[OpenAI image tokenization rules](https://developers.openai.com/api/docs/guides/images-vision).
The CLI controls actual image processing. Subscription usage must still be measured
from real completion records, and API token estimates are not subscription billing.

The image reduction alone would save about 159,000 input tokens across these runs
under the documented 1.2 multiplier and no resizing. That is only about 5.3% of
their 2.99 million total tokens. Shorter text and avoided notebook rewrites may
save more, but reasoning, model output, and CLI overhead remain. This is not a
claim of 59% lower total usage or improved gameplay success.

Reproduce the audit without model credentials:

```bash
uv run python scripts/audit_compact.py \
  runs/starter-v06-luna-1m-01 \
  runs/starter-v06-terra-1m-01 \
  runs/starter-v06-sol-1m-01
```

Next validation should compare the same checkpoint, model, effort, and small token
budget under grounded and compact policies. Check dialogue reading and navigation
success alongside tokens per decision. No live model trials were run for this change.
