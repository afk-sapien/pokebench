# PokeBench

PokeBench evaluates how AI agents play Pokemon Red. Models choose routes, battles, recovery and resource use in the real game. PokeSim Core decodes observations and executes controller inputs. PokeBench owns the tasks, information boundaries, budgets, scoring and replay checks.

The current catalog has **28 active tasks**. Twenty-two contribute to the development ranking and six tactical candidates remain experimental. Five trivial tasks are retired. Development results are useful evidence, but they used evolving harness versions and are not a controlled release comparison.

A prospective v1 beta evaluates the same three registered starting conditions for every model, with a **50 million reported-token ceiling across the entire evaluation**. This is a staged evaluation. Cells that do not fit the remaining allowance stay pending. A task enters the new aggregate only after every registered model completes all three variants with verified replay. Development results never fill missing release cells.

## Install

```sh
git clone https://github.com/afk-sapien/pokebench.git
cd pokebench
uv sync --locked --extra dev
uv run pokebench --help
```

Python 3.12 is selected for reproducibility. The Python distribution and import remain `pokeagent-bench` and `pokeagent_bench` for compatibility. Both `pokebench` and the older `pokeagent` command work.

Supply your own Pokemon Red ROM and locally prepared fixtures. ROMs, emulator saves and generated game tables are not distributed. PokeSim Core is installed from a versioned, hash-pinned release wheel. A sibling PokeSim checkout is not a runtime dependency.

## What the agent sees and controls

The gameplay track supplies a screenshot, readable dialogue, observed terrain and objects, party health and moves, inventory and recent action outcomes. A notebook and bounded conversation preserve working context. Eight-turn segments reset from deterministic observations and the agent's notes. There are no paid summarization calls.

The agent chooses every route and tactical decision. Item, move and party shortcuts execute real controller input, preserving battle turns and item costs. Continue-only dialogue is collected until an actual decision is needed. The evaluator's hidden completion flags and future game state are not exposed. A separate visual track remains available for perception experiments.

See the [information contract](docs/gameplay-track.md), [bounded context design](docs/design/bounded-gameplay-pipeline.md) and [menu shortcuts](docs/menu-shortcuts.md).

## Models and budgets

The subscription adapters use the official Codex and Claude Code CLIs. Existing CLI login is required. There is no automatic switch to paid API usage. Exact model IDs, requested effort, provider limitations, input/output usage and cache accounting are recorded. Effort names are not equivalent amounts of computation across providers.

```sh
uv run pokebench run \
  --provider claude --model claude-sonnet-5-5 \
  --codex-policy bounded --track gameplay --reasoning-effort medium \
  --rom /private/red.gb --scenario /private/validated-fixture \
  --game-data /private/game-data --goal challenge \
  --max-total-tokens 500000 --output /private/new-run
```

Use `--provider codex` with an available exact Codex model ID for the same gameplay protocol. See [Claude subscription setup and limitations](docs/claude-subscription.md).

Budgets count reported input plus output tokens, including cached input once. They measure inference workload, not the amount billed on a subscription. API-equivalent dollar estimates are estimates, not subscription charges. Admission reserves and between-decision checks limit spending. An in-flight response can exceed a threshold. Missing usage stops the release sweep for review.

## Tasks, results and reproducibility

The catalog includes starter acquisition, parcel delivery, navigation, gym battles, the League, and calibrated tactical battles. Six experimental tasks cover switching out of a bad matchup, healthy capture, team rescue, PP management, adaptive Champion play and a recovery detour. Their selected winning reference traces establish feasibility, not guaranteed success or independence from luck.

- [Release protocol and reproduction](docs/release-v1.md)
- [Task catalog](docs/ability-suite.md)
- [Tactical calibration](docs/tactical-battle.md)
- [Experimental decision tasks](docs/decision-suite.md)
- [Website export and privacy](docs/public-website.md)
- [Technical report source](paper/README.md)

Each local run preserves a manifest, exact starting state, controller trace, observations, usage and results. Offline replay checks the recorded trajectory without another model call. The public website exports allowlisted results and screenshot replays. Private provider logs, model notes, session identifiers, ROMs and saves stay local.

## Development

```sh
uv run --locked --offline pytest -q
uv run --locked --offline ruff check .
```

The source tree retains earlier observation policies so historical traces remain interpretable. They are not interchangeable experimental conditions. See [third-party notices](THIRD_PARTY_NOTICES.md). Pokemon is an unofficial research setting for this project, with no affiliation or endorsement.
