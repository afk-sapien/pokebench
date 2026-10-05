# Screen feedback protocol, red-v0.5-experimental

The revised Codex harness is `codex-cli-visual-feedback-v3`. It addresses stale
notes, ambiguous screenshots during fades, and repeated unsuccessful inputs.
The actual game, starter checkpoint, scoring, and controller remain unchanged.
This is a new observation and memory protocol, not a retroactive change to prior
results. Changed source, prompt, track, and limits produce separate report groups.

## Agent information

The visual track gives only game pixels, the objective, controller timing,
remaining budgets, and the model's own memory. RAM coordinates, map names, party
facts, scores, achievements, private event flags, geometry, and route instructions
are absent from its context. The structured track remains available separately.

Each decision receives the previous decision's starting screen followed by each
action's resulting screen. The initial decision has only the current screen.
Images use 3x nearest-neighbor enlargement. Labels identify chronological order,
frame, button, and hold/release timing. The exact input image is saved locally as
`observations/NNNNNN.png`. Its hash and the original screenshot hashes are saved
with the decision. This presentation adds no arrows or game interpretation.

The last eight controller results record the command, before/after frames,
executed frames, exact pixel equality, and changed-pixel fraction. Pixel changes
are not labeled as player motion, collision, dialogue, or success. Animations
can change pixels without movement. Images during fades remain valid observations.
The model must explicitly request a wait to finish a transition. Every such wait
counts toward action, frame, token, and wall limits as applicable. Observing or
building the image strip never advances the emulator.

The notebook has four required fields: observed evidence, hypotheses,
unsuccessful attempts, and next experiment. The model authors every entry.
Returning null preserves the prior notebook. Invalid structure or oversized
notes reject the whole decision before its actions execute. Notes remain bounded
by the configured UTF-8 byte limit. No hidden reasoning is recorded.

## Pilot settings

Luna and Terra each receive a 500,000 reported-token threshold, low reasoning
effort, 150 calls, 1,200 actions, 360,000 frames, and 3,600 wall seconds. Each
action allows 600 frames. The new pilot caps each decision at two actions for
frequent feedback. Both use the same verified starter checkpoint as the earlier
runs. The token reserve is unchanged and is not a provider-side hard cap.

This experiment changes several interface features together. It can test the
combined interface but cannot identify which individual change caused an outcome.
No human route guidance, reference solution, retry, API fallback, or subscription
reset is supplied during the model trials.

## Correction to earlier interpretation

A replay inspection found that Terra's earlier decisions 64 and 76 had already
entered map 0 in RAM while their screenshots still showed the house fading out.
Those observations do not independently establish a failure to recognize an
outdoor image. Other decisions, including 69 and 83, clearly showed the ground
floor while Terra's notes described Pallet Town. The broader mismatch is real,
but map IDs alone are insufficient evidence of what was visible during a fade.
