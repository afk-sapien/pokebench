# Core 0.1.4 review and benchmark upgrades

The published PokeSim Core 0.1.4 wheel is pinned by SHA-256 in this package.
The release consolidates the same mechanical item and party commands introduced
for the v036 benchmark. It does not add an autonomous game strategy.

## What the benchmark uses

| Core feature | Benchmark integration | Benefit |
| --- | --- | --- |
| `controls.use_item` and `switch_pokemon` | `menu_shortcuts.ControllerPort` routes inputs through the session | Share fixes with PokeSim while preserving budgets, turn costs and replay logs |
| `menus.menu_options` | The gameplay menu reader delegates to Core | Share party-slot labels and visible-menu parsing |
| Cached screen glyphs | Existing `read_screen` calls use the new implementation | Less repeated decoding work, with the same observation shape |
| Immutable storage decoding and bulk reads | Existing owned-storage inspection uses the new reader | Less repeated CPU work without stale data after loading a save |

These integrations were already present when this release review began.
The benchmark still owns observation filtering, agent prompts, scoring,
controller budgets and action logging. Cached readers do not directly reduce
model input tokens. No additional model success improvement is claimed from
the Core extraction itself.

The release also provides name entry and trusted event-reset helpers. Current
benchmarks use fixed player names and prohibit new Pokemon nicknames, so adding
a naming tool would not help the active suite. Reset helpers mutate memory and
are not exposed to agents or used by the runtime. Future explicitly reset
fixtures would need their own setup provenance and separate task definitions.

## Upgrade issue fixed in package 0.26.1

Previously, generating an archived suite report required the currently installed
Core to match the one used to prepare the suite. A Core upgrade therefore
blocked report regeneration even though that operation runs no emulator.
Reports now validate fixture integrity and the original batch binding without
requiring the old Core installation. Recorded runtime provenance is retained.

New runs, resumed batches, emulator validation and reference replays still
require compatible runtime checks. An old suite is not silently approved for
a new Core. Use the new command to prepare a separate verified bundle:

```sh
uv run pokeagent suite revalidate \
  --suite data/red-basic-v1 \
  --rom /path/to/pokered.gb \
  --output data/red-basic-v1-core014

uv run pokeagent suite revalidate \
  --suite data/red-league-v1 \
  --rom /path/to/pokered.gb \
  --output data/red-league-v1-core014
```

The command copies the exact checkpoint artifacts, reruns each successful
controller reference and its independent replay, and checks the no-input
negative trial. It records the new Core provenance and the old suite hash.
Existing suites and trials remain unchanged. The output directory must be new.
These checks make no model calls.

Benchmark red-v0.36-experimental remains the controller and observation revision.
Package 0.26.1 changes upgrade tooling and reporting, not task scoring or agent
observations. Core provenance and source hashes continue to distinguish runtime
implementations within that revision.

## Local verification results

All five basic tasks and the League task were revalidated on the released
Core 0.1.4 wheel. Initial-state hashes match the original fixtures. Every
positive reference and negative trial passed its exact controller replay.
The historical League comparison also regenerated successfully. The package
suite passed 286 tests with two skipped, lint passed and the wheel built.
No model calls were made for this upgrade review.
