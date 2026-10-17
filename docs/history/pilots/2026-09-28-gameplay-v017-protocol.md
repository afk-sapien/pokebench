# Structured gameplay pilot v017

Declared before model calls. Eight independent trials test Luna, Terra, Sol and
Astra on the original bedroom starter fixture and the wounded-party Brock battle
fixture. The goal is to diagnose the new decision-making interface, not estimate
a reliable success rate. Each trial has a 150,000 reported-token allocation,
including cached input, with no retries or budget increases. Total allocation
is at most 1,200,000 reported tokens, subject to the existing between-turn reserve
rather than an upstream hard generation cap.

Use models gpt-5.6-luna, gpt-5.6-terra, gpt-5.6-sol and gpt-6-astra through the
ChatGPT subscription and isolated Codex CLI 0.157.0, medium effort. No API-priced
calls or external tools. All use the same gameplay observation policy, prompt,
commands, current screenshot and fresh conversation per decision. Notes,
observed exploration memory and the two most recent command results persist.
Fresh conversations avoid resending an ever-growing image and dialogue history.
This changes perception, control and memory together. It is not an ablation of
one variable and must not be pooled with the visual baseline.

Limits are 150,000 tokens, 100 model calls, 600 total frames per command,
1 command per decision, 600 raw controller actions, 120,000 total game frames,
1,800 wall seconds and 2,048 note bytes. Prospective token reserve and completion
can stop earlier. No nickname rule remains in force. Run at most two trials
concurrently. Preserve all attempts, including infrastructure failures.

Fixtures are starter-v010, starting in the bedroom with no starter, and
brock-battle-v015, starting at Brock's first command menu. Both use their existing
validated scenario manifests and objectives. No new game state or strategic
hint is supplied. Catalog, source, core package, prompt and scenario checksums
are recorded before the first model call. Exact structured input is logged for
every decision and included in the review portal. Verify raw controller replay
and the captured input images before interpreting results.

Preflight checks verified that bounded movement can leave the original bedroom
and that a requested Bubble move selects Bubble in the real Brock fixture.
Both raw traces replayed exactly. These are controller validation, not model
successes, and neither action sequence is given to the models.

## Recorded amendment after initial diagnostics

The four Brock attempts exhausted their prospective reserves. Their traces
showed many short A taps returning during partially typed text. Luna and Terra
starter attempts were paused at complete decision boundaries. Sol and Astra
starter attempts were cancelled before process initialization and consumed no
model calls. Preserve these as interrupted diagnostics, not starter failures.
Reported usage before the revision is 681,011 tokens. The remaining allocation
funds a separately declared v018 pacing revision, without exceeding the original
combined allocation. No original run is resumed or relabeled.
