# Retained conversation gameplay retest v021

Declared before model calls on 2026-09-28. Use the v020 runtime at commit
6c44b39, package 0.13.0, core 0.1.3 and player-information-v020. The experiment
number does not change the runtime interface. Freeze all Python source and
fixture hashes before launch.

Run one attempt per model for gpt-5.6-luna, gpt-5.6-terra, gpt-5.6-sol and
gpt-6-astra on each original-bedroom starter-v010 and wounded-party
brock-battle-v015 fixture. Use subscription client 0.157.0, medium effort,
one current image, unchanged structured information and 2048-byte notes.
Retain the conversation and use the existing metered agent-summary compaction
at 24000 context tokens. Compaction calls count against the same token and
model-call budgets. Automatic dialogue and corrected menu labels are enabled.
No human guidance, route hints, model substitution or manual recovery is allowed.

Each attempt has the same v019 cap of 250000 reported tokens, 100 model calls,
600 raw actions, 120000 frames and 1800 wall seconds. Action phases allow
600 frames and one command per decision. The additional dialogue phase allows
7200 frames within remaining run budgets. The allocation is 2000000 tokens
across eight attempts, with at most two attempts in flight. No retries.

The runner reserves an estimated next call before dispatch and stops at each
reported limit. The subscription service has no hard aggregate generation cap.
If any attempt exceeds its token cap or ends with incomplete accounting, stop
admitting additional pairs. Preserve failed or incomplete attempts. Do not spend
reset credits or launch a longer campaign run as part of this batch.

Verify text and image delivery in actual client history, same retained thread
between normal decisions, distinct sessions after audited compactions, exact
usage sums, equivalent settings within each task and every raw controller replay.
Formal completion uses the existing starter-acquisition and Boulder Badge
evaluators. Visible combat victory alone is not a pass.

Compare completion, reported tokens, decisions, maintenance calls and controller
actions with v019. This comparison changes dialogue handling, menu parsing and
conversation retention together. It can show whether the revised system works
better, but cannot isolate which change caused the difference. A matched v020
fresh-context ablation would be a separate experiment with a separate allocation.
Report outcomes before considering longer tasks.
