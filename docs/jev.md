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

Each Jev call is billed to your TypeSafe account at $42 per billion input tokens.
Output tokens are free. Save the key once in a file only you can read:

```sh
mkdir -p ~/.config/typesafe && chmod 700 ~/.config/typesafe
read -rsp 'TypeSafe API key: ' K && printf %s "$K" > ~/.config/typesafe/key
chmod 600 ~/.config/typesafe/key
```

`TYPESAFE_API_KEY` overrides the file when set. The key is sent only to TypeSafe. It is
never written to manifests, decisions or saves.

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
  interact, inspect, dialogue, move and wait, and replay verified it.
- First live shortcut trial, October 17, 2026: both mode from the opening save. Jev
  cleared the title and naming screens into the bedroom and walked a few tiles. It then
  alternated START and B for about 50 decisions until the 1,000,000-token cap stopped
  it after 91 calls. Shortcut decisions averaged about 10,500 input tokens, which is
  about $0.0004 each, so the run cost about $0.04. Score 0. Replay verified. Jev
  reported rounded probabilities that sum to 0.99 over the 66 choices, so the check
  now allows rounding error that grows with the menu size.
- First live trial, October 17, 2026: 20 screenshot-only decisions from the opening
  save. Jev pressed A and waited through the title screen into Professor Oak's
  introduction. It used 42,747 input and 2,240 output tokens, with a median of about
  0.19 seconds per call. Score 0, as expected for that distance. This shows the
  adapter works live. It is not yet a measure of play quality or the best mode.

## Full PokeBench pass, October 17, 2026

Jev ran the same 48 tasks, fixtures and limits as the ranked pass, in a copy of the frozen
`main-v067-fable` runtime with this adapter added. It used shortcuts and both mode, with no
notebook. The 10 preparation cells were not run because they need one multi-operation
submission and Jev answers one fixed choice per call. The remaining 40 cells all finished
and accounting is complete. Output is in `pokeagent-bench/data/main-v074-jev`.

On those 40 cells, with the benchmark's usual weighting:

| Model | Score | Battle | Navigation | Objectives | Operations |
| --- | --- | --- | --- | --- | --- |
| Astra | 0.951 | 0.92 | 1.00 | 0.89 | 1.00 |
| Fable 5.1 | 0.889 | 1.00 | 0.67 | 0.89 | 1.00 |
| Luna, the lowest ranked model | 0.497 | 0.47 | 0.33 | 0.33 | 0.85 |
| Jev | 0.225 | 0.39 | 0.00 | 0.11 | 0.40 |

Jev used 99.9 million input tokens, about $4.20. Two attempts stopped early because the
adapter required the chosen option to be the most probable one. Jev may choose otherwise,
so that check was removed and both cells were rerun. The archived attempts' tokens are
counted in the pass budget.

## Jev v2, October 17, 2026

`--provider jev-v2` is a separate harness, `jev-choice-targets-v2`. Never rank it with
the main results. It always uses screenshots and state on the gameplay track, and adds:

- Destination choices built from seen terrain: `goto_exit_X_Y`, `talk_<object>` and
  `explore_<direction>`. Each is a route of up to six tiles per move command.
- A 40-entry progress log, the exits it has learned and the maps visited. These are sent
  as `progress` in the state.
- Masking: a choice that changed nothing is hidden for four decisions. An exit that twice
  fails to change the map is dropped.
- Screen menus: the overworld, battle, dialogue and menu screens each offer only their
  own options, about 6 to 18 instead of 66. Items appear only in battle when owned.
- The planned route stops early on a map change, a blocked move or a stop.

It ran the 16 navigation and objectives tasks with the same fixtures and limits as v1.
`objectives-infeasible-plan-alternate` did not fit the pass's 80M-token ceiling. It ran
on its own with the same limits and scored 0. Output is in
`pokeagent-bench/data/main-v075-jev-v2`.

| Harness | Navigation cells solved | Objectives cells solved | Input tokens | Cost |
| --- | --- | --- | --- | --- |
| v1, shortcuts | 0 of 6 | 1 of 10 | 72.2M | about $3.03 |
| v2, destinations | 0 of 6 | 2 of 10 | 82.7M | about $3.47 |

The extra solve is `objectives-starter-selection`. On navigation, v2 reached a third map
in two cells, but by going back the way it came. Jev's confidence fell from about 0.25 to
about 0.15. With a progress log and routes, it still does not keep heading toward the goal.
