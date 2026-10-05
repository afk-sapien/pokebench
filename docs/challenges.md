# Checkpoint challenge protocol

Full campaigns measure sustained planning. Checkpoint tasks isolate a skill and
prevent an early failure from hiding every later capability.

| Family | Starting fixture | Stop condition | Status |
| --- | --- | --- | --- |
| Campaign | Fresh title screen | First gym or Hall of Fame | Opening fixture available locally |
| Starter acquisition | Bedroom, downstairs, or outside home | Receive the first starter under the existing evaluator | All three fixtures reference-verified locally, results separated by start |
| Parcel roundtrip | After receiving the starter, before collecting the parcel | Collect Oak's Parcel, return it to Oak, receive the Pokedex | v024 checkpoint, Sol completed the million-token trial |
| Gym segment | After one gym, before the next | Newly earned target badge | Evaluator ready, fixtures pending |
| Trainer battle | Before a named trainer | Curated victory flag plus battle exit | Evaluator ready, fixtures pending |
| Weak-party battle | Underleveled or poorly matched party | Same trainer objective | Curated saves pending |
| Resource recovery | Low HP, limited PP or items | Reach a defined safe location | Curated saves pending |
| Navigation recovery | Difficult route or apparent trap | Reach an exact map tile | Evaluator ready, fixtures pending |
| Soft-lock diagnosis | Independently verified unwinnable state | Correct diagnosis under a separate rubric | Planned, not scored by the current evaluator |

Do not call a time-limited failure a soft lock. Recovery and diagnosis are
separate tasks. Do not average campaign points with normalized challenge scores.

## Create a checkpoint

Every run writes `initial.state` and `final.state`. New milestones also write a
PNG, a `.state` snapshot, and checksum metadata under `runs/RUN/milestones/`.
These are local PyBoy emulator states, not cartridge `.sav` files.
The agent cannot load, rewind, create, or choose its own benchmark starting state.

For a segment from Brock to Misty, use this objective JSON:

```json
{
  "kind": "milestone",
  "target": "badge:cascade",
  "description": "Earn the Cascade Badge from this starting position."
}
```

```bash
uv run pokeagent checkpoint --rom /path/to/red.gb \
  --state /path/to/after-brock.state --name after-brock-to-misty \
  --objective examples/objectives/cascade.json --output scenarios/after-brock
uv run pokeagent run --rom /path/to/red.gb --scenario scenarios/after-brock \
  --goal challenge --provider random --max-actions 20 --output runs/checkpoint-smoke
```

Import validates the ROM and save through the emulator, rejects a satisfied
objective, and records checksums and emulator provenance. Imported fixtures are
marked `curation: unverified`. Import alone does not prove reachability or validity.
Existing badges do not score. A challenge has one success point and stops only
after two consecutive game frames confirm its objective.

A location objective uses `kind: location`, integer `map_id`, `x`, and `y`, plus a
player-facing `description`. A trainer objective uses `kind: trainer`, a zero-based
`event_id`, and `description`. The curator must verify that the selected event is
that trainer's victory flag. A generic battle exit cannot distinguish winning,
fleeing, and defeat. The event index is never included in agent observations.

## Fixture acceptance

Before a checkpoint enters a confirmed suite, record its game and emulator
versions, exact starting-state hash, party and resource constraints, target,
construction method, and a successful reference trace. Replay that trace.
Try a losing or incomplete trace and verify that it does not score. Use an
independent reference trace for each weak-party or low-resource variant.
Keep raw saves and ROMs out of Git. Share fixture metadata and hashes separately.

The gym, battle and recovery catalog entries remain proposed tasks. They do not
claim those saves already exist or that any model has completed them. Start with
one trainer and one gym segment, then expand after validation.

## Verified starter segments

The local `starter-v010` checkpoint begins in the bedroom. To isolate later
navigation, derive additional checkpoints from its verified controller trace:

```bash
uv run python scripts/prepare_starter_segments.py \
  --rom /path/to/red.gb \
  --scenario scenarios/starter-v010 \
  --reference scenarios/starter-v010/reference \
  --output scenarios
```

This creates `starter-downstairs-v014` and `starter-outside-v014`. Existing
output directories are never overwritten. The builder checks the original
reference, captures paired states and images at recorded room boundaries, and
verifies that the remaining controller trace still completes from each restored
checkpoint. It adds no setup frames and makes no game-memory writes. Raw assets
remain gitignored. Fixture checksums and verification counts can be exported.

Run a segment with its own scenario path and a unique output directory. Keep
model settings and caps identical within the segment comparison. Success from
outside is success on that segment, not credit for escaping the original room.
The initial live batch tests outside only. The downstairs fixture is prepared
for a separate batch, which must have its own declared allowance.

## Trial design

Choose exact model IDs that the account can access. Start with sequential trials
and a short pilot. A proposed pilot threshold is 25,000 reported input plus output
tokens, 100 model decisions, 10 minutes of wall time, and 10,000 emulator frames.
These settings are provisional, not calibrated fairness claims. Keep model,
reasoning effort, observation track, fixture hash, notebook size, and all budgets
in the experiment record. Repeat each model and fixture combination before
interpreting differences. Report errors alongside scored outcomes.

The subscription adapter and direct API adapter use different harnesses and are
separate comparison groups. The notebook and last eight actions are persistent
context. Each decision receives the current screenshot.

## Battle-only checkpoints (v015)

`wild-battle` starts inside one normal wild encounter and awards one point after
knockout experience is earned and that encounter exits with a surviving party.
Fleeing, capture, loss, invalid transitions and later encounters do not count.
This objective requires a party able to earn experience and is not a level-100
or trainer-battle detector. Use the existing badge milestone for a gym leader.
Only the description is exposed to visual participants. Private evidence includes
party experience and encounter state.

The private `scenarios/wild-battle-v015` checkpoint starts at the command menu.
The fixed matchup is a healthy level 6 Squirtle versus a level 3 Rattata.
Rebuild it from retained private controller records with:

```sh
uv run python scripts/prepare_battle_checkpoint.py \
  --rom /path/to/pokered.gb \
  --source-run scenarios/starter-v010/reference \
  --curation-actions scenarios/wild-battle-v015/curation-actions.json \
  --reference-run scenarios/wild-battle-v015/reference \
  --output data/rebuilt-wild-battle
```

For later checkpoints, use PokeSim's policy as an offline generator:

```sh
PYTHONPATH=src /path/to/pokesim/.venv/bin/python scripts/prepare_pokesim_gym.py \
  --pokesim /path/to/pokesim \
  --rom /path/to/pokered.gb \
  --scenario scenarios/wild-battle-v015 \
  --output data/new-brock-curation --story-only
```

The policy needs its own compatible PokeSim dependencies and local game-data
bundle. The tool records the actual core version and policy source hash, gives
the policy read-only memory, and executes only its controller inputs. It captures
the gym entrance and the first Brock battle command menu. No live simulation
state is changed. Its output is unverified until a separate victory reference
has been replayed. Do not expose policy labels, strategy or curation traces to
benchmark models.

Verify a generated fixture using the same PokeSim runtime:

```sh
PYTHONPATH=src /path/to/pokesim/.venv/bin/python scripts/verify_pokesim_checkpoint.py \
  --pokesim /path/to/pokesim \
  --rom /path/to/pokered.gb \
  --scenario data/new-brock-curation/brock-battle-v015 \
  --output data/new-brock-reference
```

The `--story-only` curation option defers optional collection projects. Story
training and controller-driven catches can still occur. Both PokeSim-generated
v015 fixtures are now available privately under `scenarios/brock-entrance-v015`
and `scenarios/brock-battle-v015`. Both have successful badge references and
replay verification, including under the benchmark's core 0.1.1 runtime.
The battle fixture has a level 12 Squirtle at 8/34 HP plus five other party members.
It is a wounded-party challenge, not an easy full-health baseline. No subscription
model has been evaluated on these gym fixtures yet.


## Parcel collection and return v024

`opening` target `parcel-roundtrip` starts with one valid starter and no parcel
or Pokedex. It requires a recorded parcel pickup during the attempt, followed
by the delivery flag, parcel removal, a Pokedex, and battle exit. The final
condition must hold for two frames. Acquisition alone is diagnostic progress,
not a completed task. Pickup tracking survives decision-boundary recovery.

The older `parcel` target is unchanged and requires the parcel already in the
initial bag. Keep those delivery-only results separate from roundtrip results.
Use [the roundtrip objective](../examples/objectives/parcel-roundtrip.json) with
the existing checkpoint importer:

```sh
uv run pokeagent checkpoint --rom /path/to/pokered.gb \
  --state /path/to/after-starter.state --name parcel-roundtrip \
  --objective examples/objectives/parcel-roundtrip.json \
  --output scenarios/parcel-roundtrip
```

The v024 pilot uses the final state from Sol's verified v023 starter success,
with one declared setup frame. Rival combat, wild encounters and resource
management remain part of the segment. No battle or navigation is skipped.
It uses the v023 gameplay information policy and a new private evaluator target.
See the [pilot protocol](pilots/2026-09-28-parcel-v024-protocol.md) and
[results](pilots/2026-09-28-parcel-v024-results.md).


Sol completed the roundtrip in the subsequent million-token trial. The
[verified result](pilots/2026-09-28-parcel-v024-1m-results.md) preserves the earlier
failure and supplies a successful controller trace from the same checkpoint.
