# Jev provider

TypeSafe's Jev chooses one controller input per decision from a fixed menu. PokeBench
runs it through the same session, budgets, scoring and replay checks as other models.
The adapter pins `jev-1.14.0` and uses the documented multipart image API. Sources:
[release announcement](https://typesafe.ai/blog/jev-1-14),
[image protocol](https://docs.typesafe.ai/images) and
[Choice responses](https://docs.typesafe.ai/primitives/choice).

Jev work moved here from the PokeSim checkout on October 16, 2026. The earlier trial
used PokeSim's own RAM readers, terrain patches and damage estimates. Those are not
part of this adapter. Jev now sees only the benchmark's allowlisted observations.

## Set the key

Each Jev call is billed to your TypeSafe account. Read the key without echoing it:

```sh
read -rsp 'TypeSafe API key: ' TYPESAFE_API_KEY
export TYPESAFE_API_KEY
```

The key is sent only to TypeSafe. It is never written to manifests, decisions or saves.

## Run a benchmark task

```sh
uv run pokebench run --provider jev \
  --rom /private/red.gb --scenario /private/validated-fixture \
  --output runs/jev-opening-01 --track visual --max-model-calls 100
```

`--model` defaults to `jev-1.14.0`. Choose what Jev receives with `--jev-observation`:

| Mode | Input | Tracks |
| --- | --- | --- |
| `images` (default) | Current and previous screenshots, scaled to 480 by 432 | Any |
| `state` | The track's allowlisted `game` fields, no images | Structured or gameplay |
| `both` | Screenshots and the allowlisted `game` fields | Structured or gameplay |

Every mode receives the task objective, the action menu and the last eight action
outcomes. Jev has no notebook. Compare modes as separate runs from the same scenario
with the same limits. The manifest records the mode under `agent.configuration`.

## Action menu

| Choice | Controller input |
| --- | --- |
| `up`, `down`, `left`, `right`, `a`, `b`, `start`, `select` | Hold 8 frames, release 16 |
| `up_long`, `down_long`, `left_long`, `right_long` | Hold 32 frames, release 16 |
| `wait` | Advance 60 frames with no button |

Invalid responses, HTTP errors and transport errors stop the run with
`provider_error` before any input. There are no retries or fallback actions. Jev
reports input tokens only, so output tokens are recorded as zero. `--max-total-tokens`
therefore limits reported input tokens.

## Watch it play

The live player is a local toy for watching Jev and taking over. It is not scored.

```sh
uv run pokebench jev-live --rom /private/red.gb
```

Open [the local player](http://127.0.0.1:8931). It starts paused and manual buttons
work immediately. Enter a key in the page or set `TYPESAFE_API_KEY` first, then click
**Start Jev**. Arrow keys move, Z presses A, X presses B and Enter presses Start.
Manual input pauses Jev and discards any in-flight answer. A request already sent can
still be billed.

The player saves `current.state` and `current.json` after each action in
`runs/jev-live/<time>/`. Resume with `--state runs/jev-live/<time>/current.state`.
`decisions.jsonl` separates manual inputs from Jev inputs and records whether each
answer was applied. Defaults are 1,000 calls and 1,000,000 input tokens. Change them
with `--steps` and `--max-input-tokens`. The server binds only to localhost.

## Validation status, October 16, 2026

- Unit tests cover the request format, answer validation, error handling, state mode,
  the runner loop, manual takeover and discarded in-flight answers.
- With the real Red ROM and a mocked Jev API, a five-decision run executed real
  presses and `pokebench replay` verified it. The live player advanced the real game,
  saved, and resumed from that save.
- No live TypeSafe calls have been made from PokeBench. Jev's play quality, latency
  and best observation mode remain unmeasured.
