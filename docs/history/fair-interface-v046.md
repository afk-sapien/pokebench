# Gen 1 fair interface pilot

This is PokeBench package 0.32.0 and protocol red-v0.46-fair-interface.
Historical results, registered starts and the frozen release runtime remain unchanged.
This update does not enable Gen 2 or replace the main model rankings.

## Changes

The command schema and runtime validator share one Gen 1 contract. Each command
has its actual argument and count constraints. Invalid requests produce specific
feedback before controller input. For example, press requires count 1, while move
permits up to eight tiles. Equivalent integral JSON numbers are normalized without
changing the requested action. Malformed requests are never interpreted as game actions.

Notes and structured plans are optional, including on the first decision. Omission
or null preserves existing notes and plans. Supplied updates remain validated.
Codex strict decoding requires all response keys at its transport boundary. Those
metadata values may be null, and the common validator accepts omission from either
provider. This encoding requirement never requires creating a plan.
Screenshot recall is optional and must reference one of the last eight screenshots.
One controller command is permitted per gameplay decision. Recall-only decisions
advance no frames but consume model usage.

Format corrections use ordinary metered decisions and the same three-consecutive
invalid-response limit. Known usage is retained for rejected responses. Provider
failures with unavailable usage remain infrastructure failures. Transport isolation,
private evaluator state, controller timing and task scoring are unchanged.

New results and historical views distinguish success, gameplay loss, budget
exhaustion, invalid model response and infrastructure failure. Categories describe
stop reasons. They do not change scores, coverage selection or old result files.

## Memory and observations

The default retains the existing deterministic eight-decision segments, 12,000
context-token threshold, persistent notes and observed action/outcome archive.
It makes no paid summarization calls. Context settings and presentation are recorded
in the run identity. A model can inspect memory for the retained observed history.

An explicit --context-detail on-demand option omits move power, accuracy, effect,
identifier and base PP from ordinary party updates. It retains move slot, name,
type and current PP, party HP/status, location, menus and battle information.
Inspect party returns the complete original owned-party information. The default
remains full, allowing observation changes to be evaluated independently of the
interface repair. Every inspection consumes a model decision but no emulator frames.

## Rust core assessment

Core 0.2.0 and PyBoy RS 0.1.1 are available in the local release preparation checkout.
The default remains Core 0.1.4 and PyBoy 2.7.0 for the interface pilot. This avoids
confounding a controller-interface experiment with an emulator replacement.

New manifests record the actual emulator backend and runtime fingerprint. Replay
and resume require matching provenance. A historical PyBoy scenario cannot silently
load under Rust just because the Rust backend supports its raw save format.

scripts/probe_rust_backend.py explicitly compares the same saved bytes and fixed
controller sequence under separate legacy and Rust interpreters. Initial probes
on starter, parcel and Lorelei match WRAM, screenshots and decoded facts at nine
checkpoints each. These are short compatibility tests, not proof of full campaign
parity or a speed benchmark. No models or registered saves are changed by the probe.

Reproduce the local smoke checks with the installed, isolated interpreters:

```bash
cd <repo>
probe_output=<private-data>/fair-interface-v046-pilot-r2/rust-probes
for probe_task in starter parcel lorelei
do
  python3 scripts/probe_rust_backend.py \
    --legacy-python <private-data>/toolchains/release-v1/python \
    --rust-python <pokesim-rust-lab>/release-prep/v2/bin/python \
    --rom <roms>/pokered.gb \
    --scenario <private-data>/pokebench-v1/fixtures/$probe_task/variant-01 \
    --output "$probe_output/$probe_task.json"
done
```

The probe refuses to overwrite existing evidence. Choose a new output directory
when reproducing these checks. The Rust interpreter was installed from these
local release wheels under `<pokesim-rust-lab>/release-prep/findlinks`:

- `pokesim_core-0.2.0-py3-none-any.whl`, SHA-256
  `7834e5b6a92dd5e8b891eb3d4f28896797c2b2cbd819ee8593dade247b371b07`
- `pyboy_rs-0.1.1-cp311-abi3-manylinux_2_17_x86_64.manylinux2014_x86_64.whl`, SHA-256
  `92c09af36cdf3da998428af1f75331f024ca523338163aac46d417123a15ba0b`

These are wheel pins, not just version pins. A different directory contains a
rebuilt PyBoy RS wheel with the same version and a different binary hash.
The legacy launcher keeps its existing pinned Core 0.1.4 and PyBoy 2.7.0 runtime.
A separate `checkpoint.json` in the probe output directory records a real Core
checkpoint test with a pending release and press, exact restore, and matching
state and screenshot after the next frame.

Useful new Core features include exact backend identity, byte reads, checkpointed
pending inputs and atomic failed loads. The optional native decoder is not required.
Raw Core snapshot fields must never be passed wholesale to models because they can
contain hidden event flags and other evaluator information. Gen 2 remains out of scope.

## Pilot and interpretation

Use matched starting saves and identical information, effort and token limits for
each model in this pilot. Keep the full observation profile and original emulator.
Run a small subscription smoke only, with all reported usage and conservative
unknown-usage holds counted within the existing authorization. Preserve every result.

Report stop category, valid controller decisions, rejected responses, replay
verification and token usage. Short pilot caps and one trial per cell do not establish
model rankings or prove a win-rate improvement. A later comparison can vary the
observation profile, memory policy or backend one at a time.

## Completed local smoke

Four gameplay trials used the same 150,000 token cap, medium effort, full
observations and original emulator. The starter fixture begins outside Oak's lab.

| Model | Task | Recorded outcome | Calls | Reported tokens |
| --- | --- | --- | ---: | ---: |
| Sol | starter | success | 12 | 114,463 |
| Sonnet 5 | starter | budget_exhausted | 13 | 131,713 |
| Sol | item-recovery | success | 9 | 100,053 |
| Sonnet 5 | item-recovery | budget_exhausted | 10 | 128,088 |

All four traces passed replay verification and recorded no invalid-response
envelopes. An earlier Sol attempt failed before gameplay because Codex required
nullable metadata keys in its strict wire schema. The transport adapter was fixed,
the failed attempt was retained, and its conservative usage hold was not refunded.

Sonnet restored every party member to full HP and healthy status in the item task.
Its recorded failure reflects the existing evaluator's additional requirement to
return to overworld control. The run stopped during menu cleanup. This is evidence
of remaining menu and completion-contract friction, not inability to select healing
items. Historical scores have not been relabeled. A future task revision should
align visible completion instructions and evaluator requirements explicitly.

The budget guard stops before admitting a call that risks exceeding the cap, so
reported usage can be lower than 150,000. These are smoke results, not an estimate
of improvement or a new model ranking. Evidence and per-trial checksums are saved
in data/fair-interface-v046-pilot-r2/analysis.json in the private artifact repository.
The local replay is at http://127.0.0.1:8942/fair-interface-v046-review.html.
