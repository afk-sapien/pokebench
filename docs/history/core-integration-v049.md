# Core 0.6.0 integration and task-specific assistance

PokeBench 0.35.0 uses `red-v0.49-core-shortcuts` for new runs.
It remains a Gen 1 Pokemon Red benchmark.

## Current shared code

The integration uses the Core 0.6.0 wheel referenced by PokeSim's `release/0.5.0`
branch at commit `3fb9eaf233be6d9a542c867b863b3c71e569f043`.
The wheel URL pins that commit and its SHA-256 is
`935660bcc135e2b91ca623f0aea5d52d662f7f62b4011e6dc9212eb825b8cb6e`.
Core main at inspection was `a7091d6d3d82d1ecd97a55d1b55356b376027dd1`.
The default environment now uses PyBoy RS 0.1.1 from pinned platform wheels.
This is a development wheel, since the latest tagged Core release is still 0.3.0.

PokeBench calls Core directly for item use, party switching and move selection.
The benchmark's temporary cursorless-party-screen workaround is removed.
Core now owns screen recognition, effect verification and settling.
Every input still passes through PokeBench's frame limits and action recorder.
The controller never changes HP, inventory or other gameplay memory directly.

A shortcut returns both `completed` and `settled`. The first means the requested
change occurred. The second describes whether the game reached a resting screen.
A starting pause menu may remain open after an item is used. This is a valid
resting screen, not the old unfinished recovery-message bug. Budget-limited
partial results remain visible. Reusing an operation ID cannot consume another item.

## What a task tests

| Task focus | Examples | Controls |
| --- | --- | --- |
| Menu operation | Item recovery, buying Poke Balls | Individual presses, waits and read-only inspections |
| Navigation | Starter, parcel, forest and cave routes | Movement and menu shortcuts, no automatic route planning |
| Battle strategy | Gym leaders, tactical battles | Choose an explicit move, item or party member |
| Resource planning and campaigns | Team rescue, recovery detour, League | Mechanical shortcuts while the agent chooses resource use and strategy |

New `item-recovery` and `buy-pokeballs` runs default to `manual-menu-v1`.
They disable item, move and switching shortcuts, automatic menu choices,
movement macros and automatic dialogue continuation. Restrictions apply to the
provider schema, runtime execution and MCP. A disallowed command sends no input.
Other tasks retain `assisted-gameplay-v1`.

Custom scenarios can declare `tested_skill: menu-operation` to obtain the manual
default, or declare navigation, battle-strategy, resource-planning or campaign.
A task can explicitly declare `action_policy`. Explicit CLI overrides remain
available for deliberate comparisons and are recorded in each run. The agent
cannot change its policy. The manifest and segment snapshot describe the task's
focus and actual permissions. Historical runs retain their recorded conditions.
A standalone menu test is supporting evidence about that capability, not a proof
that it transfers perfectly to every campaign situation.

Core has additional shopping, storage, field-move and move-learning helpers.
They are not automatically exposed to agents. The existing command allowlist
stays small. Adding another shortcut requires assigning it to the appropriate
task conditions and validating its behavior.

## Smaller context without summaries

`bounded-gameplay-context-v2` sends a full allowed state at each segment start.
Within a segment it sends changed party fields and move fields by one-based slot.
An HP change no longer repeats every move's power, accuracy and effect text.
A PP change updates that move's PP while retaining its description.
Roster changes replace the party. Move changes replace the move list.
Removed, empty and null fields remain distinct. Read-only inspection is unchanged.
No model-generated summary or extra model call is used.

Reformatting the exact observations from the four v047 after runs produced:

| Recorded run | Old text bytes | New text bytes | Reduction |
| --- | ---: | ---: | ---: |
| Sol item recovery | 64,068 | 50,260 | 21.6% |
| Sonnet 5 item recovery | 100,546 | 86,707 | 13.8% |
| Sol starter | 28,605 | 28,605 | 0% |
| Sonnet 5 starter | 34,355 | 34,355 | 0% |

These compare UTF-8 observation text, not provider tokens, cache charges or model
success rates. Fresh runs are needed to measure those effects. Reconstruction
tests confirm that the compact updates preserve the full allowed state.

## Saved scenarios and validation

Old runs and registered fixtures are unchanged. They retain their original
emulator identity. To use an old scenario for a new Rust-backed trial, make a copy:

```sh
uv run python scripts/import_scenario.py \
  --rom /private/pokered.gb \
  --source /private/original-scenario \
  --output /private/new-rust-scenario
```

The importer checks source hashes, loads the save through Core, checks a save/load
round trip, preserves starting bytes and preview, and records both runtime identities.
It advances zero frames and refuses to overwrite an existing directory.
This verifies an import, not arbitrary full-game equivalence between emulators.
Use the frozen historical environment when reproducing an original run.

The integration checks used copied healing, Lorelei and starter fixtures.
The bounded emulator comparison matched game memory, decoded facts and screen
hashes at every tested input. All 27 field-healing sequences and three battle
sequences passed and replayed. Battle checks exercise a chosen move, healing and
switching from battle, move and bag menus. The field checks include the previously
failing item order and pause, bag and party starts. No model calls were needed.
Private evidence is stored under `data/core-v049` in the artifact repository.
