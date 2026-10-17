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
reports input and output tokens, and both count toward `--max-total-tokens`. A
screenshot decision used about 2,200 tokens in the first trial, so the default
100,000-token budget allows roughly 45 decisions.

## Shortcuts on the gameplay track

By default Jev presses raw buttons. That is a fair comparison only on manual-input
tasks. For decision tasks and campaigns, where Claude and Codex use bounded gameplay
commands, add `--jev-shortcuts`:

```sh
uv run pokebench run --provider jev --jev-shortcuts --jev-observation both \
  --track gameplay --game-data /private/game-data \
  --rom /private/red.gb --scenario /private/validated-fixture \
  --output runs/jev-shortcuts-01 --max-model-calls 100
```

Jev then picks one fixed command per decision from this menu. The runner validates
and executes each one through the same `gameplay_commands` code as other agents.

| Choices | Command |
| --- | --- |
| `move_<direction>`, `move_<direction>_4` | Walk 1 or up to 4 tiles, stopping at obstacles, maps, dialogue and battles |
| `press_<button>` | One tap of any button, for menus |
| `interact`, `advance_dialogue`, `wait` | Tap A at the facing tile, collect open dialogue, wait 60 frames |
| `choose_yes`, `choose_no`, `choose_run` | Select that visible menu option |
| `use_move_1` to `use_move_4` | Fight with that move slot |
| `switch_pokemon_1` to `switch_pokemon_6` | Send in or lead with that party slot |
| `potion_1` and so on to `revive_6` | One Potion, Super Potion, Hyper Potion, Full Restore or Revive on a slot |
| `inspect_party`, `inspect_bag`, `inspect_map`, `inspect_memory` | State and both modes only |

Dialogue collected after a command is returned in the recent action outcomes.
Choice answers come from a fixed list, so free-text `choose` and other items are not
offered. Jev still has no notebook or goal plan. The manifest records
`harness: jev-choice-shortcuts-v1` and `shortcuts: true`, so these runs stay a separate
condition from button runs. The live player below uses buttons only.

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
- Shortcut mode, October 17, 2026: unit tests cover the menu, the request and the
  runner executing shortcuts. A six-command mocked run on the real ROM executed press,
  interact, inspect, dialogue, move and wait, and replay verified it. Not yet run live.
- First live trial, October 17, 2026: 20 screenshot-only decisions from the opening
  save. Jev pressed A and waited through the title screen into Professor Oak's
  introduction. It used 42,747 input and 2,240 output tokens, with a median of about
  0.19 seconds per call. Score 0, as expected for that distance. This shows the
  adapter works live. It is not yet a measure of play quality or the best mode.
