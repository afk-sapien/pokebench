# Task-specific controls and shortcut repair

Historical v048 note. [Core integration v049](core-integration-v049.md) replaces
the temporary benchmark workaround with Core 0.6.0 controller behavior.

PokeBench 0.34.0 uses protocol `red-v0.48-task-controls` for new runs.
This update distinguishes menu operation from gameplay decision making.

## Menu operation

New `item-recovery` runs use `manual-menu-v1`. Models receive only `press`, `wait`
and `inspect` in the gameplay command schema. They must choose every menu button
and confirmation. Item, move and party shortcuts, automatic option selection,
movement macros and automatic dialogue advancement are disabled.

A press holds one button for eight frames and releases it for 24 frames, subject
to the remaining budget. It does not send additional A presses or hidden settling
frames. The model chooses waits for animations. Inspection remains read-only and
provides the existing allowed owned-party and menu information.

The restriction is enforced before controller input, including direct commands
and MCP requests. It is not just a prompt instruction. Healing still scores actual
full HP and cleared status without requiring unrelated menu cleanup.

## Assisted gameplay

Decision-making tasks, battles and campaigns keep `assisted-gameplay-v1`.
The model selects the item, target, move or party member. Controller shortcuts
execute that explicit choice through recorded, bounded Game Boy inputs.
`heal`, `recovery-detour` and `team-rescue` retain their existing assisted settings.
Their navigation or resource decisions are separate from this menu-operation task.

A scenario can declare `action_policy`. A new run can explicitly select a policy
with `--action-policy manual-menu-v1` or `--action-policy assisted-gameplay-v1`.
The resolved policy is fixed in the manifest and result, supplied in observations,
included in provider configuration, and restored on resume. Policy is not an
agent-controlled runtime tool. Old manifests default to their original assisted
behavior, even when the scenario name is item-recovery.

## Reproduced controller bug

The item controller detected consumption before the recovery dialogue appeared.
It returned during a one-frame cursorless party transition. A subsequent request
then classified the unfinished screen as an unsupported starting menu.

The benchmark adapter now recognizes that observed party transition and lets the
controller wait through it using released-button frames. Confirmed continue-only
dialogue and menu cleanup remain inside the same assisted action. Unknown modal
screens are not blindly confirmed. Existing input budgets and item-consumption
checks still prevent repeating the requested effect.

The repair passed 27 deterministic field cases from a real Gen 1 save. These cover
24 valid item orders and starts in the pause, bag and party menus. Every item used
exactly one unit on the specified target, preserved other party members, returned
to overworld control and remained idempotent on retry. All traces replayed.
Three additional real battle cases covered item use and switching from the battle,
move and bag menus. They also replayed correctly. These checks cover the reproduced
failure and sampled supported paths, not every possible game state.

The field regression can be reproduced without model calls:

```bash
uv run python scripts/validate_shortcut_controller.py \
  --rom /path/to/pokered.gb \
  --scenario /path/to/item-recovery/variant-01 \
  --game-data /path/to/game-data \
  --output /path/to/new-controller-regression.json
```

The script refuses to overwrite evidence. It uses an isolated emulator and does
not modify the fixture. Local evidence is saved in the private artifact repository
under `data/menu-policy-v048`. No model tokens were used for this validation.

## Reporting and historical evidence

Action policy is included in comparison metadata, paper exports and replay details.
Manual and assisted attempts are different experimental conditions. If both occur
for one task in the exploratory page, historical assisted results remain intact
and a separate manual-menu row shows the new trials. They are not silently averaged
into the historical assisted score. Existing results are neither relabeled nor
rerun by this change. GitHub publication is unchanged.
