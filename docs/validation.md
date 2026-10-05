# Validation

The automated suite covers milestone confirmation, unique scoring, invalid and
initial state handling, frame and wall limits, terminal clocks, idempotency after
response-cache eviction, observation filtering, note isolation, usage accounting,
provider failure classification, MCP image content, and read-only viewer routes.
Provider HTTP responses are mocked. CI requires neither ROMs nor API keys.

The initial local release passed 39 automated tests and Ruff checks. A real stdio
MCP client negotiated all six tools, received a native image response, and confirmed
that retrying a 30-frame action did not advance another 30 frames. The viewer was
also inspected in the browser. Wheel and source distribution builds succeeded.

## Local real-ROM smoke test

```bash
uv run pokeagent prepare --rom /absolute/path/red.gb --output scenarios/red-opening
uv run pokeagent run --rom /absolute/path/red.gb --scenario scenarios/red-opening \
  --provider random --max-actions 100 --output runs/random-smoke
uv run pokeagent replay --rom /absolute/path/red.gb --run runs/random-smoke
```

Initial validation used clean Pokemon Red (USA, Europe) with isolated SRAM and
PyBoy 2.7.0. A 100-action run advanced 1,000 frames and replayed with identical
screenshots, evaluator evidence, and final score. Two fresh boots produced the
same initial state SHA-256. This smoke test validates emulator and replay wiring,
not first-gym success or campaign completion.

The local test client may require ordinary cross-thread event-loop access.
Restricted process sandboxes that block wakeup sockets can hang a web test while
pure emulator and scoring tests still pass. Run the normal suite in a standard
local environment or CI.

## Shared core migration

Version 0.2.0 passed 43 automated tests and Ruff checks using PokeSim Core 0.1.1.
Integration coverage checks the complete structured observation allowlist, Red-only
ROM policy, core provenance comparison groups, and old manifests without core
metadata. The existing private v0.1 Red smoke trace replayed all 100 actions and
1,000 frames with identical screenshot hashes, evaluator evidence, and final score.
A fresh structured run also completed and replayed 20 actions and 200 frames.
Fresh scenario preparation produced the same initial state hash as v0.1. This
check caught and fixed a shared decoder issue with empty PyBoy bag slices before
release. These checks verify recorded gameplay compatibility, not identical text
decoding for future model requests.

## Remaining validation

- Live paid provider requests with the user's chosen model identifiers.
- Matched first-gym runs and budget calibration.
- Real victory, defeat, blackout, and Hall of Fame fixtures for campaign scoring.
- Provider-specific pricing and reasoning configuration studies.

## Comparison reports

Comparison coverage checks success denominators, completion-only timing, median
gameplay metrics, spend from failed and live trials, missing usage and prices,
experiment boundaries, and equivalent CLI and dashboard JSON exports.
These changes do not alter observations, scoring, prompts, or run budgets.

## Checkpoint and subscription foundation

Mocked Codex processes validate authentication selection, schema and screenshot
arguments, rejection of outside tools, and missing completion handling. Synthetic
emulator tests cover initial badges, exact location targets, trainer flags,
two-frame confirmation, milestone saves, and checkpoint replay. Token threshold
tests include in-flight overshoot and missing accounting. Export tests verify
private-field exclusion and deterministic snapshots.

Live subscription inference, reference solutions, and real trainer victory and
loss fixtures remain pending. No such experiments are implied by these tests.

A local League stress-test save was imported as an unverified checkpoint. A
20-action, 200-frame controller run replayed with identical screenshots, private
evidence, and score. The source save was read without modification. This validates
checkpoint plumbing, not the difficulty or solvability of the fixture.
