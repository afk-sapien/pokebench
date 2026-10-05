# Five-task basic suite

This version preserves five easy and medium tasks. An optional sixth task is
available in the separate [League extension](league-suite.md). The rest of the
larger suite proposal remains future work. Package 0.24.0 and benchmark red-v0.34-experimental add this suite
and its healing objective. The bounded model policy remains v033.

| Task | Difficulty | Initial position | Token ceiling |
| --- | --- | --- | ---: |
| Get a starter | Easy | Outside Oak's lab, before his introduction | 1000000 |
| Win a wild battle | Easy | Squirtle versus Rattata, battle menu | 250000 |
| Heal the party | Easy | Outside Viridian Pokemon Center with an injured Squirtle | 500000 |
| Collect and deliver Oak's Parcel | Medium | Immediately after starter acquisition | 1500000 |
| Defeat Brock | Medium | Battle introduction, healthy party including level 12 Squirtle | 500000 |

Difficulty labels and caps are provisional development settings. The full ceiling
is 3750000 tokens per model per sweep. Success stops the run immediately. Reported
input, including cached input, and output count toward budgets. Subscription
usage is not reported as a zero-dollar API bill.

Healing requires the original party at the Viridian Center with full HP, no
status conditions, and control returned. A blackout or party replacement
invalidates that attempt. This basic task does not grade PP restoration. Its
objective text exposes every restriction to the agent. Negative unit tests cover
wrong locations, incomplete healing, party replacement and blackout recovery.

## Prepare local fixtures

The package ships definitions and tools, not ROMs, saves or generated game data.
The current development suite binds local reference-verified checkpoints. This is
not yet a public fixture distribution that can rebuild every checkpoint from a
fresh cartridge. The controller recipes in each prepared suite reproduce the
reference solution from its pinned local starting save.

Create the healing and healthy Brock fixtures from the retained development
controller trace and an isolated PokeSim policy instance:

```sh
PYTHONPATH=src .venv/bin/python scripts/prepare_basic_fixtures.py \
  --rom /path/to/pokered.gb --root /path/to/pokeagent-bench \
  --pokesim /path/to/pokesim --output data/basic-fixtures
```

This requires the existing development wild-battle and Brock-entrance fixtures
and data/pokesim-gym-v015-story/actions.jsonl. It uses the benchmark's compatible
runtime and never writes to PokeSim or its saves. It creates controller-only
references. Those are fixture checks, not AI model results.

Supply a private bindings JSON object with exactly starter, wild-battle, heal,
parcel and brock keys. Each value has scenario and reference absolute paths.
The reference must be a completed controller trace from that same starting save.
The suite builder executes those controllers again, verifies completion and
replays the result. It also checks that waiting alone does not pass any task.
It never trusts a fixture's curation label without running its reference.

```sh
uv run pokeagent suite catalog
uv run pokeagent suite prepare --rom /path/to/pokered.gb \
  --bindings /path/to/bindings.json --output data/red-basic-v1
uv run pokeagent suite validate --rom /path/to/pokered.gb --suite data/red-basic-v1
```

Outputs are immutable snapshots. Preparation refuses to overwrite a directory.
A failed preparation remains available for inspection. Correct the inputs and
use a new destination. States, previews, objectives, references and task limits
are checked before evaluation.

## Run and resume a batch

```sh
uv run pokeagent suite run --suite data/red-basic-v1 \
  --rom /path/to/pokered.gb --game-data /path/to/game-data \
  --models gpt-5.6-sol --repeats 1 --total-token-budget 3750000 \
  --output data/basic-sol-pilot --dry-run
```

Remove --dry-run to execute. The runner resets game state, notes and model context
between every task and repeat. It uses the bounded gameplay track, medium effort,
eight-response segments, a 12000 observed-context threshold and no paid summaries.
No model receives reference controllers or grader evidence. No hints or gameplay
repairs occur during evaluation.

The batch reserves a task's full remaining allowance before starting it. A smaller
batch allowance leaves tasks pending instead of silently lowering their caps.
Actual reported usage, not reservations, is consumed. The adapter uses conservative
preflight estimates, but an in-flight response can still overshoot a reported-token
ceiling. Any such overrun is retained and stops further batch work.

```sh
uv run pokeagent suite resume --suite data/red-basic-v1 \
  --rom /path/to/pokered.gb --game-data /path/to/game-data \
  --total-token-budget 3750000 --output data/basic-sol-pilot
```

Finished cells are not rerun. Resume requires identical source, Core, game data
and suite fingerprints. Only safe decision-boundary recovery is supported.
Infrastructure errors stop the batch and remain visible. They do not receive
automatic replacements or disappear from coverage. A pause or error during an
in-flight request needs inspection under the existing recovery protocol.

Do not enable generic room-duration stops for this development suite. Training,
dialogue and battles can remain in one room legitimately. Token, action, frame
and wall limits still apply.

## Results page and analysis

```sh
uv run pokeagent suite report --suite data/red-basic-v1 \
  --batch data/basic-sol-pilot --output data/reviews/basic-suite.html
```

The self-contained HTML report includes task descriptions, fixture validation,
model/task pass counts, total usage, attempt outcomes and separate decision replay
files. It also writes sanitized JSON and CSV beside the HTML. Serve all of these
files together. Generate again to refresh a running batch. The report is a snapshot,
not a live monitor. Optional --historical-run paths show old pilots separately
without mixing them into the new suite score.

The overall score is the equal-weight mean of five task pass rates. Repeats are
averaged within each task, never selected by best result. The overall score stays
unavailable while any registered cell is pending or has an infrastructure error.
A one-sweep pilot tests the pipeline. Use repeated attempts before drawing model
reliability conclusions. This first release provides descriptive counts, not
confidence intervals or an automatic significance claim.

The existing paper-export workflow remains available for individual run artifacts.
The new report JSON and CSV are analysis inputs. Updating the manuscript's figures
for this five-task suite is separate from collecting or inventing model results.
