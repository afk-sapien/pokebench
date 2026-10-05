> This page records the v0.4 pilot. See the [v0.5 visual protocol](visual-feedback-v05.md) for the current Codex interface.

# Gameplay pilot protocol

The one-tile and menu trials were software smoke tests. They are not the intended
level of benchmark difficulty. The first gameplay task is obtaining a starter
from a fresh bedroom checkpoint. The controller reference leaves home, finds Oak,
and obtains a Pokemon. It completes in 67 actions and 9,621 emulator frames,
about 161 game seconds. Its complete trace passed deterministic replay.

## Task readiness

| Task | Success criterion | Readiness |
| --- | --- | --- |
| Get a starter | Starter story flag and one valid starter in the party | Reproducible fresh-game fixture and verified reference |
| Deliver Oak's parcel | Delivery flag, parcel consumed, and Pokedex received | Evaluator tested, curated start and reference still needed |
| Catch a first wild Pokemon | New owned species enters the party during a real wild encounter, then battle exits | Evaluator tested, curated start and reference still needed |

Gift Pokemon and the old man's capture demonstration cannot satisfy the capture
evaluator. Pending nickname entry and partially written party data cannot score.
All objectives require consecutive confirming frames.

Prepare the starter task without any model requests:

```bash
uv run python scripts/prepare_opening_fixture.py \
  --rom /path/to/pokered.gb \
  --output scenarios/starter-v04
```

The fixture definition contains setup and reference controller inputs. It uses no
memory writes. The ROM and generated states remain private and gitignored.
Only the goal, observations, and controller interface are given to a model.

## Subscription overhead correction

The old adapter started a full Codex coding context for each button press. Sol's
adjacent-tile trial reported 23,581 input tokens and 175 output tokens across two
calls. That overhead was a harness mistake, not meaningful reasoning required to
walk one tile.

Harness `codex-cli-cooperative-v2` replaces the coding template with the gameplay
prompt using the supported `model_instructions_file` option. It disables apps,
plugins, personality, shell, search, and subagents. Parent app and task connection
variables are removed. Authentication and the read-only sandbox remain intact.
The prompt is supplied once as instructions, rather than duplicated in user input.

A decision may contain up to eight model-chosen controller actions. The entire
batch is validated before any action runs. Each action still gets its own trace,
screenshot hash, evaluator checks, and budget checks. Success stops the batch
immediately. The next model observation follows the batch, so the model should
choose shorter batches when feedback matters.

Before another Codex call, the runner reserves the previous call's reported input
and output tokens plus 512. If the remaining threshold cannot cover that estimate,
it stops without making another request. This is an estimate, not a hard provider
output limit. An unusually large response or growing context can still exceed the
threshold. Token usage remains reported input plus output, including cached input
once. Subscription usage percentages are a different, shared account measure.

Inspect the local prompt without requesting inference:

```bash
uv run python scripts/audit_codex_prompt.py --model gpt-5.6-sol
```

On the installed CLI, the cached coding instruction template contains 17,730
characters. The replacement gameplay instructions contain 1,610 characters. The
local debug context contains another 6,574 characters. These are character
counts, not measured token savings. The debug command does not support exec's
user-config exclusion and omits image tokenization, tool schemas, server additions,
and the actual game payload. The audit itself made no model calls.

A subsequent user-authorized live calibration tested Sol and Luna on the starter
fixture. Both stopped below the 30,000-token threshold without leaving the bedroom.
The runs used 54,434 reported tokens total. See the
[starter pilot results](pilots/2026-09-26-starter-v04.md) for exact usage and outcomes.
Increasing the token allowance is not the fix for the old one-call-per-button design.

Official configuration reference:
[model_instructions_file](https://learn.chatgpt.com/docs/config-file/config-reference).

## Benchmark version

`red-v0.4-experimental` changes the Codex prompt, action batching, request budget
reservation, and supported objectives. Compare it separately from the control
smoke tests. Existing traces remain local and replayable. The manuscript separates the old
control smoke tests from the revised starter pilot.

The [extended Luna trial](pilots/2026-09-26-luna-500k.md) used 499,402 of a
500,000-token threshold and remained in the bedroom. Its full trace passed replay.

The matched [Terra trial](pilots/2026-09-27-terra-500k.md) used 496,641 tokens,
reached Pallet Town, and failed to obtain a starter. Its full replay passed.

The [visual-feedback pilot](pilots/2026-09-27-visual-v05.md) reran Luna and
Terra with game-only screenshots and structured memory. Neither obtained a starter.
