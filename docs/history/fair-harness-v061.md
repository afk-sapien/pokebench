# Fair harness red-v0.61

This tag collects fixes for faults that the failure study blamed on the harness,
not on the model. Every change that alters what the model sees lands under this
one tag. The tag is frozen before any leaderboard run. Runs made while it is
still open are tests and are never published as leaderboard rows.

## Move walks the tiles it promises

The move command offers `count 1..8 tiles`. Before this tag the whole command
shared one `max_action_frames` window of 120 frames. One tile takes 24 frames,
so a move stopped after 5 tiles and reported `stopped at budget boundary`.
In the published Short runs, 960 of 1,162 Fable and Astra moves that asked for
6 to 8 tiles stopped at 5. Now each tile gets its own `max_action_frames`
window. An 8-tile move on open ground walks 8 tiles in 192 frames. Obstacles,
map changes, dialogue and battles still stop it as before. The controller
timing label is `core-shortcuts-v061`. Replays of earlier runs are unaffected,
because replay uses the recorded raw inputs.

## Preparation names its items

The preparation turn lists the legal restoratives, the shop and the TMs by id
and name. Before this tag the names came from a helper that was handed the
wrong argument, so every item except TMs and HMs was sent with a null name.
The bag in the same payload was already named. Now both come from the game
data labels, so a Potion in the shop and a Potion in the bag carry the same
name.

## use_item accepts quantity 1

A preparation `use_item` always uses one item. The validator rejected a plan
that also said `quantity: 1`, which zeroed the whole plan. Two Sol plans that
matched the plan most models submitted lost 4.0 points this way. Quantity 1 is
now accepted on `use_item`. Any other quantity is still rejected.

## Choose a party member by name

Party menu options read `1: POLIWRATH`. The `choose` command required that
exact text, so `choose POLIWRATH` was refused. That cost 6 cells one decision
each. Exact text still matches first. If nothing matches exactly, a bare name
matches an option of the form `N: NAME`, and only when exactly one option
matches. Two party members with the same name still need the slot prefix.

## Preparation is shown but not ranked

Preparation scores a team and item plan with a fixed battle controller. It
gives fractional credit, and its result depends on that controller as much as
on the plan. The ranked Short score now averages four categories equally:
navigation, battles, menus and quests. Preparation keeps its own score, which
appears in its own column marked not ranked. The 95% interval, the
cost-per-score comparison and the task-omission rank check use the same four
categories. `pokebench run` prints preparation under "Shown but not ranked".

On the published Short runs, ranks stay the same for six of the eight models.
Haiku and Sonnet swap places 6 and 7. The gap between them is 0.3 points, well
inside both intervals.

## Two Pikachu quests retired

`objectives-find-capture-species` asked the model to find and catch a wild
Pikachu. Pikachu appears in about 5% of Viridian Forest encounters, so the
result depends mostly on encounter luck. Only one of eight published models
passed it. `objectives-capture-pikachu-fixed` had no fixture and was never on
the leaderboard. Both are marked `active: false`. New batches do not run them.
Their old attempts stay on the site, tagged retired, but they are not scored
or counted as planned. Every published score is recomputed without them. The
graders and the fixture stay in the package, so old runs can still be
replayed. The fixture pack needs no rebuild: all 48 active task cases are
runnable from the current pack, and the retired fixture stays in it, as the
two retired navigation fixtures already do.

## Pair collisions on the map

In cave and forest maps the game refuses a step between two particular
walkable tiles, such as raised and low floor in Mt. Moon. The game checks each
pair in both directions (`CheckForTilePairCollisions` in `home/overworld.asm`).
The local map drew both tiles as `.`, so the step looked open. In a Long run at
Mt. Moon 1F (21,25) the map showed open floor below the player and the game
refused the step.

Each tileset's pairs join one hub tile to all of its partners. Among walkable
tiles, cave floor `$05` pairs with three tiles in 19 maps and forest floor
`$2E` with five tiles in 5 maps. No other tileset has pairs. The hub side is
now drawn `:` and the partner side `,`. A step between a `:` cell and a `,` cell
is refused. Every other step between walkable cells is unchanged. The glyph
depends only on the tile, never on where the player stands, so the known map
keeps it too. Because `@` hides the floor under the player, the `@` legend
names that floor. The legend explains `:` and `,` only in maps that use them.
An emulation of the ROM routine over the real ROM bytes matches this rule for
every tileset and tile pair. Three rows of the pair table involve water and
apply only while surfing. They are left out, because a walking step never
reaches a water tile.

A list of blocked steps was the other option. Over 16,685 map windows from
the Long runs in these tilesets, 9,683 had at least one blocked step. The list
would hold 8.2 steps on average when present and up to 17, it would change
with every step the player takes, and the known map would need its own longer
list. The two glyphs add about 45 tokens per decision in these maps and none
elsewhere. The observation policy is `player-information-v063`.

## Prompt and packet trim

The trim deletes text the model does not use. Nothing it can act on is
removed, and the recorded packet keeps every field. Only the rendered text
changes, so the context protocol stays `bounded-gameplay-context-v3`. The text
presentation is `bounded-gameplay-text-v4`.

Removed from every snapshot and update:

- the two header lines, which restate the replace, remove and snapshot rules
  of the system prompt
- protocol, sequence, base sequence, segment and detail policy
- the token budget enforcement mode, the dialogue format tag and the recall
  line that repeats the prompt
- the task goal, track and action policy, which the prompt already states
- the copy of the location inside the replaced game fields. The location is
  shown once at the top of every packet.

The system prompt loses four sentences. Three repeat other sentences: a second
request to preserve discoveries in notes, "use null to keep notes" and a second
"notes and plans are unverified". The fourth, "sequence numbers identify the
previous packet", explained a field the text no longer shows. The action schema drops the description of each argument that
already lists its allowed values. `choose` and `use_item` keep theirs. The
system prompt goes from 5,048 to 4,891 bytes and the schema from 4,648 to
4,277 bytes.

Measured by rendering every recorded packet of four Claude runs both ways:

| Run | Snapshot bytes | Update bytes |
|---|---|---|
| Short, Fable | 10,492 to 9,872 | 2,163 to 1,767 |
| Long, Sonnet | 10,005 to 9,376 | 2,171 to 1,767 |
| Long, Opus | 10,915 to 10,286 | 2,046 to 1,654 |
| Long, Fable | 11,303 to 10,673 | 2,122 to 1,726 |

Snapshots shrink by 6% and updates by 18 to 19%. Cache writes on continued
decisions give about 0.45 tokens per byte, so a snapshot saves about 280
tokens, an update about 180 and the prompt and schema about 240.

A segment ends after eight decisions or once the context reaches the
threshold. A smaller context would reach a 12000 threshold later, and
segments would run longer than in the published runs. The threshold is
lowered by the tokens the trim saves, so segments end where they did. By the
decision that first crossed 12000, the trim had saved a median of 816
tokens. Over 7,470 recorded segments, a threshold of 11,300 ends 94% of them
at the same decision as before. Keeping 12000 would end 52% at the same
decision. 11,300 is the default for every bounded provider. Explicit
`--compact-at` values and the frozen basic and v1 beta protocols are unchanged.

## Prompt field names match the packet

The bounded system prompt is built from the full gameplay prompt, which names
fields of the JSON observation. Three of those names do not exist in the
bounded packet. The prompt told the model to read `last_command.dialogue.pages`,
but the packet shows the result as `last_result`. It named `Recent_movements`,
which the packet replaces with `recent_decisions`, and `agent_plan`, which the
packet shows as `agent.plan`. The bounded prompt now uses the packet names. The
full JSON prompt keeps its own names, which match its observation. A test reads
a recorded Short observation, builds the bounded packet and checks that every
field name in the prompt, under both action policies, is a packet field, a
response field or a command. The text presentation is
`bounded-gameplay-text-v5`.

## Suites use the published effort

Every published Short run used low reasoning effort and every published Long
run used medium. `pokebench run --suite` sent low for every suite, so a new
Long run would have played at a lower effort than the Long rows it is compared
with. Each planned run now records its effort: low for Short and smoke, medium
for Long. `verify` refuses a run whose manifest names another effort.

## Reporting labels

Nothing in this section changes a score or what a model sees. The showcase
now labels each published attempt that ran under conditions the current
version no longer uses. The labels are computed from each attempt's own files
(`src/pokeagent_bench/reporting_labels.py` holds the few facts the files do
not record):

- earlier task version: the attempt's spec hash differs from the current
  task. 18 active Short cells, 6 each in the Mt. Moon, scarce-resource League
  and infeasible-plan tasks. The other 6 old-spec cells belong to the retired
  Pikachu quest, which is already labeled retired.
- earlier start state: 6 scarce-resource League cells started with a level 55
  team. The current fixture has a level 60 team.
- earlier battle controller: 47 preparation cells were scored with
  `fixed-battle-v3` and 10 with `fixed-battle-v2`. The current controller is
  `fixed-battle-v4`.
- no run-ends line: all 240 Original pass prompts lack the sentence saying the
  run ends by itself once the task is complete. Astra and Fable prompts have it.
- harness fault: 7 zeros the failure study traced to the harness. Two Sol
  plans hit the `use_item` quantity check, one Pikachu quest run was stopped
  when the model picked up a free Poke Ball, and four quest-trainer runs met
  spinner tiles the local map drew as floor.

Each task row shows the spec hash, the harness version and, for preparation,
the battle controller version. The ranking shows how many of each model's
counted cells carry each label.

The retry rule is now stated on the page. There are no gameplay retries. An
infrastructure fault resumes the attempt from its last completed decision
with its limits unchanged. Every stopped or replaced copy is kept and listed
in the attempts log under the ranking: 9 replaced, 9 resumed and 1 continued.

Long stays ranked at 2,000 decisions. Extensions past 2,000 are shown but not
ranked, and new models get none. Each Long run card shows how many of its
blocked moves hit a tile pair that the old map drew as floor. Sonnet's
2,000-decision run lost 246 of 434 blocked moves this way and Luna and Haiku
lost none, so older Long rows were hurt unevenly.

## A provider error pauses the run

Two Sonnet test runs on the v0.61 harness stopped on an API error that came
before the model wrote anything. The Short cave task stopped after 333
decisions and the parcel task after 4. Both errors were a Cloudflare 403 page, and
every Claude session on the machine got the same page at those times. The first
outage lasted at least 2 min 47 s. The harness marked the usage as uncertain,
so neither run could be resumed. The model did not end either one.

The Claude adapter now records whether the model replied before an error, and
keeps the error text and its status. When the model did not reply, the call
counts no tokens and the harness tries the same decision again in a fresh
segment, after 15 s, 1 min, 4 min and 10 min. A usage limit is not retried. When the retries run out, the run pauses. The call is not
counted, the checkpoint stays at the last finished decision and
`pending.json` names the phase. `pokebench run --suite` stops at the paused
task, and the same command resumes it from its checkpoint.

Each failed attempt is one row in `provider-errors.jsonl` and in the run
result, with the time, the decision, the attempt, the message, the kind, the
status and the provider's own text. `verify` accepts a resumed run and reports the count. An error
after the model replied, a timeout and a transport error still stop the run
with uncertain usage, because the model may have spent tokens on them.

## A rejected reply says it used a decision

Every rejected reply is a model call, so it uses one decision from the
budget. The feedback said only that no action was executed. In a Sonnet test
run of the warp puzzle, 41 of 200 decisions were empty replies.

Every rejection now opens with `No action was executed and this still used one
decision.` The reason follows. An empty reply reads `Empty actions do nothing.
Send at least one controller action or request look_back from 1 to 8.` Before
this change the Claude feedback said that no action was executed twice. The
correction policy is `three-metered-invalid-decisions-v2` and the Claude
response adapter is `claude-interface-v8`.
