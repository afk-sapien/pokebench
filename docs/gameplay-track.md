# Gameplay information track v023

This experimental track measures decision making with structured perception
assistance. Keep its results separate from the unchanged visual observation and
raw-controller track. It also differs in its action interface, so a comparison
cannot attribute an improvement to text observations alone.

## Information contract

Every decision receives the current screenshot, visible dialogue and menu text,
current cursor, party species, types, HP, status, move slots, PP, move type,
power, nominal accuracy and effect descriptions. The active battle structure
supplies current HP and PP because party memory can lag during combat.
The enemy HUD comes from rendered text and the six visible HP-bar tiles.
Enemy internal statistics, unrevealed moves and future choices are never read
into the agent observation.

The local map is a 10 by 9 tile viewport. It uses live terrain subtiles and the
current tileset's collision list. It marks visible objects, fixed interactables
and exits. Exit destinations and offscreen geometry are withheld. Object names
are generic visual categories, never scripts or starter identities. Textboxes,
menus, fades and moving-player states suppress the map. This is a terrain map,
not a guarantee that every edge can be traversed. Ledges, surf and directional
collision rules still apply.

Bag names, quantities and descriptions for common supplies are included.
Unimplemented item descriptions are explicitly unavailable. Move effect names
are mechanical labels, not full encyclopedic explanations. Owned PC storage,
previously observed tiles and observed dialogue can be inspected without game
time. This is deliberately easier than navigating the in-game inspection menus.
Exploration memory stores at most 4,096 cells per map across 64 maps and 64
observed dialogue samples. Partial dialogue can be recorded while text renders.
No conversation completion or quest progress is inferred. Each observation also
includes a bounded grid of already seen terrain and the last eight movement
results. Unseen cells remain unknown. Historical terrain can become stale.
The grid is withheld while the map is covered or unsettled.

The private catalog is checksum-verified against the pinned local game-data
bundle. No generated game tables are distributed. Only the explicit projection
can reach the model. Evaluator facts remain outside model context. Provenance
records the catalog hash, core wheel and source hashes, observation policy,
prompt, action interface, reasoning setting, usage and budgets.

## Commands and limits

Commands are move, interact, choose, use_move, press, wait, advance_dialogue and
inspect. Each model decision requests one command. Movement accepts a direction
and at most eight tiles. It stops on obstruction, map change, dialogue or battle.
Choice selection requires exact visible text within the active menu border.
Move selection takes an explicit slot. Neither command selects subsequent choices.

Since v020, a successful controller command automatically collects visible dialogue
and advances confirmed continue-only waits. It returns the decoded pages in
`last_command.dialogue`, including text shown during the original command.
An explicit `advance_dialogue` handles an already open conversation. Menus,
naming screens and battle choices remain agent decisions. Inspection is read-only.
Rejected commands do not trigger automatic continuation.

The requested action phase remains bounded by `max_action_frames`. The separate
dialogue phase is bounded by `max_dialogue_frames`, default 7,200, at most 128
text pages or 16,384 characters, and all remaining run budgets. Each raw input
counts against the action budget and is recorded for replay. The collector sends
one-frame A taps only at recognized text waits. Between checks it allows at most
30 passive frames. It waits for 120 passive frames of a settled overworld screen
before treating a gap in dialogue as returned control. Unrecognized waits return
without guessing after a bounded passive wait. Inspect the reported stop reason.

An explicit A tap still has the v018 initial settle of up to 240 released-button
frames, checked for menus every 60 frames, within the requested action phase.
The v017 diagnostic used only a 24-frame release. All previous attempts retain
their original observations, commands and scoring.

No model-generated dialogue summary is used. No memory writes, pathfinding,
battle policy, automatic recovery or goal-directed planning occur. See the
[v020 implementation and offline validation](dialogue-v020.md) for the mechanical
detection contract and comparison limits.

The same commands are exposed through MCP only for the gameplay track.
Repeated command IDs are checked against the original request to avoid duplicate
controller inputs. The run can pause and resume at decision boundaries, including
its catalog, inspection request and observation memory. In-flight recovery remains
fail-closed. The review portal shows the exact structured input and requested
command alongside the screenshots and actual raw controls.

## Navigation corrections in v023

Movement results contain requested and actual tile counts, positions before and
after input, the final settled position, and an explicit map-change indicator.
Partial movement followed by an obstruction no longer claims that nothing moved.
The tile count sums observed same-map displacement. It does not measure distance
across a warp. The requested direction and count always come from the model.

The collector passively waits through detected map transitions and the game's
scripted controller lock. This includes the existing Oak escort sequence. It
never chooses the walk or its destination. Locked scenes remain subject to the
same frame, raw-action and wall limits. No model call is needed just to wait for
a known transition to finish.

The visible Pokedex data card is dialogue, not an overworld map. Its description
is captured, and the recognized A/B-only dismissal can be advanced. The
subsequent starter choice and nickname choice require separate agent decisions.
Unknown modal screens are withheld from movement and never guessed through.
Detection reads the pinned English Red routine and live stack. No ROM, RAM,
register or emulator hook is written.

Gameplay's retained-context threshold defaults to 12000 tokens. The visual
provider keeps 24000. Explicit invalid values are rejected. `--fresh-decisions`
uses a new session for each decision, retaining bounded notes, observed terrain
and recent command results in the supplied state. It makes no summary calls.
The v023 comparison explicitly uses this option. Retained mode remains available
for separate comparisons and longer-task memory experiments.

See [the navigation results](pilots/2026-09-28-navigation-results.md) for model
outcomes and the limits of the engineering comparison.

## Run

Use the existing private fixtures and a locally prepared game-data bundle:

```sh
pokeagent run --rom /path/to/pokered.gb \
  --scenario scenarios/brock-battle-v015 --output runs/gameplay-example \
  --provider codex --model gpt-6-astra --codex-policy gameplay \
  --track gameplay --game-data /path/to/game-data --goal challenge \
  --reasoning-effort medium --fresh-decisions --max-total-tokens 150000 \
  --max-action-frames 600 --max-actions-per-decision 1
```

These are decision-making benchmark results with assistance. They do not establish
visual game-playing ability or full-game reliability.

## Post-pilot visibility guard

Observation policy v018.1 additionally withholds local map annotations for at least
120 frames after detecting a map ID change. The engine can change its map ID
before the new tiles are rendered, so palette checks alone were insufficient.
The reported v018 model trials retain their original source and observations.
This additional guard has synthetic regression coverage and is not represented
as a new charged model trial.
