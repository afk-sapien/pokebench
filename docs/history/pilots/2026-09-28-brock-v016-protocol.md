# Brock battle pilot v016

Declared before model calls on September 28, 2026. This is the first model
trial of the PokeSim-generated Brock checkpoint, not an extension of the wild
Rattata runs. Each model receives a fresh attempt with a 250,000-token cap.
The maximum combined allocation is 1,000,000 reported tokens. Cached input
counts toward that cap. Runs stop on completion or the prospective token reserve.
No automatic retries or budget increases are allowed.

Models are gpt-5.6-luna, gpt-5.6-terra, gpt-5.6-sol and gpt-6-astra. All use
subscription access through Codex CLI 0.157.0, medium reasoning effort, continuous
visual context, current-image presentation, the simple response contract and
24,000-token context rotation. Controller settings remain two actions per
decision, 600 frames per action, 300 actions, 100 model calls, 120,000 game frames
and 1,800 wall seconds. The existing frozen v015 runtime is unchanged, with
source SHA-256 48aa73fa58848b6470a564d186e751250cc86f1979fbb5755aaeea0680e4be8a.
The experiment profile is v016 because the task and budget differ from the
wild-battle pilot. This is not a controlled estimate of the budget change alone.

All participants begin at Brock's first battle command menu in the same private
`brock-battle-v015` fixture. State SHA-256:
`79b416afdafa7af103f0fd739f9dbdcb92a51fe8b6a8f079c66f3a9dd0262d18`.
The objective is "Defeat Brock and earn the Boulder Badge." The existing badge
milestone evaluator determines completion. It permits recovery and a later
attempt if the model loses, within its original budget. Report any loss or
recovery separately if observed.

This is a wounded-party checkpoint. Squirtle starts at level 12 with 8/34 HP,
with five other party members. It is not a full-health easy baseline. PokeSim
completed the reference from this state and earned the badge without leaving
the initial battle before victory. Curation and reference runs are not scored.
The actual benchmark core 0.1.1 has already replayed the reference and reproduced
the PokeSim core 0.1.2 checkpoint and screenshot byte-for-byte.

No decoded state, matchup advice, object labels, routes, reference actions or
other participants' findings are supplied to the models. The unchanged
no-nickname rule applies. Only model-requested controller actions advance the
game. The models must select their own moves and waits.

Replay each completed trace, verify settings and client image delivery, preserve
all original wild-battle results, and publish a separate local Brock review.
Report decisions, actions, tokens, outcome and any incomplete usage accounting.
One attempt per model is a diagnostic result, not a reliability estimate.
