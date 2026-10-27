# PokeBench

PokeBench evaluates how AI agents play Pokemon Red. Models choose routes, battles, recovery and resource use in the real game. PokeSim Core decodes observations and executes controller inputs. PokeBench owns the tasks, information boundaries, budgets, scoring and replay checks.

## Gen 1 task catalog

The current catalog is split into two benchmarks with separate rankings.

- **PokeBench Gen 1 Short** has **48 tasks**: 47 focused tasks plus one inventory variant, across navigation, battle tactics, manual menu operations, preparation and quests. One battle task has three fixed starting variants, so each model plays **50 starts**. Scores are category-balanced.
- **PokeBench Gen 1 Long** is one continuous full-game campaign with 50 scored milestones worth 1,000 points. The comparison budget is 2,000 decisions and 30M tokens per model.

Short and Long scores are never averaged together. Results and replays are on the [public site](https://afk-sapien.github.io/pokebench/). See the [catalog](docs/catalog/README.md) and [long runs](docs/long-runs.md).

`pokebench catalog` and new `catalog-batch` runs default to Short. Use `--benchmark pokebench-long` to inspect or run the campaign separately. Each batch has its own token ceiling. No models are launched by inspecting the catalog. See [the two benchmark tracks](docs/history/benchmark-tracks-v053.md) for execution and scoring and [catalog runtime and commands](docs/history/catalog-runtime-v050.md) for setup, task controls, preparation assessment and result aggregation.

The earlier 28-task development suite and the v1 beta release protocol are kept in [docs/history](docs/history/release-v1-beta.md). They are not the current catalog.

The exploratory leaderboard preserves completed and partial results across framework improvements. Runs record their model, task, starting save, controls and runtime so material differences remain visible. Routine backend fixes do not discard earlier results or require a full rerun.

## Install

```sh
git clone https://github.com/afk-sapien/pokebench.git
cd pokebench
uv sync --locked --extra dev
uv run pokebench --help
```

Python 3.12 is selected for reproducibility. The Python distribution and import remain `pokeagent-bench` and `pokeagent_bench` for compatibility. Both `pokebench` and the older `pokeagent` command work.

Supply your own Pokemon Red ROM and locally prepared fixtures. ROMs, emulator saves and generated game tables are not distributed. PyBoy RS 0.1.1 is installed from hash-pinned wheels. `uv sync` installs PokeSim Core 0.9.0 (the `pokecore` package) from its hash-pinned release wheel. The integration history is in [the integration notes](docs/history/core-integration-v049.md). A sibling PokeSim checkout is not a runtime dependency.

## What the agent sees and controls

The gameplay track supplies a screenshot, readable dialogue, observed terrain and objects, party health and moves, inventory and recent action outcomes. A notebook and bounded conversation preserve working context. Eight-turn segments reset from deterministic observations and the agent's notes. There are no paid summarization calls.

Menu-operation tasks disable shortcuts and require individual button presses. Strategy and navigation tasks retain mechanical shortcuts. The task focus and actual permissions are recorded. Within a conversation segment, party updates send only changed HP, status and move fields. Full state returns at every segment start.

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

- [Earlier v1 beta release protocol](docs/history/release-v1-beta.md)
- [Task catalog](docs/ability-suite.md)
- [Skill categories and one full-game campaign with progress milestones](docs/catalog/README.md)
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

## Screenshot presentation

Model input defaults to the current screenshot with observed action results and optional screenshot recall. The replay separately shows decision start and action result for human review, plus the exact image sent to the model. See [the screenshot comparison](docs/history/image-presentation-v055.md) for the explicit `--presentation before-after` experiment.
