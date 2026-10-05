# Structured gameplay retest v019

Declared before model calls on 2026-09-28. This experiment uses the unchanged
red-v0.18-experimental runtime at commit 07dced7, core 0.1.3, and observation
policy player-information-v018.1. The experiment number is not a new interface
version. The map-transition guard is new relative to the charged v018 trials.

Run one attempt for each of gpt-5.6-luna, gpt-5.6-terra, gpt-5.6-sol and
gpt-6-astra on each of the original-bedroom starter-v010 and wounded-party
brock-battle-v015 fixtures. Use subscription client 0.157.0, medium effort,
fresh decision contexts, one current image, the same structured information,
2048-byte notes, and the same exploration memory. No human guidance is added.

Each attempt has a 250000 reported-token ceiling, 100 model calls, 600 raw
actions, 120000 frames, 1800 wall seconds and 600 frames per command. Allow one
command per decision. The runner reserves the estimated next call before
starting it. The upstream generation service does not offer a hard aggregate
token cap. Account for actual usage and stop at any limit. The short-test
allocation is 2000000 reported tokens across eight attempts. No retries are
scheduled. Preserve every failed, stopped or incomplete attempt.

Freeze source and fixture hashes before the first call. Verify exact text and
image delivery, usage accounting, matched settings within each task, and raw
controller replay. Completion requires the existing evaluator's confirmed
starter acquisition or Boulder Badge flags. Visible victory alone is not a pass.
The cap differs from v018 and earlier visual trials, so this is a diagnostic
comparison rather than a causal estimate or a reliable model ranking.

Only a model that formally completes both short tests qualifies for one longer
start-to-first-gym attempt. Among qualifiers, select the model with the lowest
combined reported tokens, breaking a tie by the model order above. Start from
the same original bedroom state with goal first-gym. Retain medium effort,
fresh decisions, the same observation and controller policies, and 2048-byte
notes. Cap this attempt at 1000000 reported tokens, 400 model calls, 4000 raw
actions, 1000000 frames, 7200 wall seconds and 600 frames per command. No retries
or manual interventions. This is a separate exploratory long-task result.
If no model qualifies, do not run the longer test. Report the failed gate.
