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
