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
