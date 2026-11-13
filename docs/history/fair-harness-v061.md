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
