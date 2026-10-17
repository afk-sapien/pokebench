# Battle-only pilot v015

Declared before model calls on September 28, 2026.

The task is to win one fixed wild battle, beginning at the battle command menu.
The private checkpoint contains a healthy level 6 Squirtle against a level 3
Rattata. The objective is: "Win this wild Pokemon battle. Defeat the opponent
without fleeing or catching it."

Luna, Terra, Sol and Astra each receive one attempt capped at 100,000 reported
tokens, including cached input. All use Codex CLI 0.157.0, subscription access,
medium reasoning effort, the continuous visual provider, the current image,
the simple response contract, up to two actions per decision, 600 frames per
action, 100 calls, 300 actions, 120,000 game frames and 1,800 wall seconds.
The existing 24,000-token context rotation threshold is unchanged. Native
unmetered compaction remains prohibited. No automatic retries or budget increases.
The package source is frozen and hashed before launch.

The existing controller prompt and timing suggestions remain unchanged.
There are no object labels, decoded stats, move advice, routes or human hints.
The no-nickname rule remains active. The evaluator stays private.

The wild-battle objective is new in red-v0.15-experimental. It requires experience
earned during the initial normal wild encounter, unchanged party species,
no loss or invalid encounter transition, and battle exit with a surviving party
member. Two confirming frames award one point. In Generation I, escape and
capture do not grant battle experience. Later encounters cannot rescue an escape.
This detector is for this low-level, experience-earning fixture. It is not an
appropriate definition for a level-100 party or a multi-enemy trainer battle.

Curation is separate from scoring. The wild checkpoint was prepared with controller
inputs from a verified post-starter save, with private diagnostics available to
the curator. A recorded reference victory and replay verify winnability.
The paired state and screenshot were captured without extra setup advancement.
Its state SHA-256 is e20b2ce22cf070d417fec48c582fe7c631c0b8f304a23e9bb95d75a380aae6e3.
The reference wins in 13 actions and 2,261 frames. Reference actions and private
diagnostics are never supplied to model participants.

Future gym fixtures use PokeSim's strategic policy in an isolated emulator.
That policy is an offline fixture generator, not assistance during scored runs.
It receives read-only game memory and can advance gameplay only through controller
inputs. The live PokeSim process, source and save library remain untouched.
Generated gym fixtures require separate reference validation before model trials.

Report each outcome, decisions, actions, frames, reported tokens, accounting
completeness and replay verification. Export the existing accelerated review UI.
One attempt per model is a diagnostic comparison, not a reliability estimate.
