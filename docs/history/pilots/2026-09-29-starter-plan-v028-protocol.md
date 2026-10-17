# Luna starter diagnostic with persistent goals and 50-decision recall

Version red-v0.28 retains 50 executed decisions instead of 20 and adds an
agent-authored goal_plan separate from scratch notes. The model must create
an initial concrete subgoal with evidence and an observable done_when condition.
Null preserves the plan. Replacements require a revision_reason. All four
fields are bounded to 400 characters and 2048 total UTF-8 bytes. The previous
four revisions are retained. Plans are hypotheses, not verified game facts.
Invalid actions cannot commit a new plan. Plan state survives pause and resume.
No evaluator writes a goal or supplies a route, prerequisite or solution.

Retain v027 observed dialogue and matching-result memory with the same bounds.
The observation policy is player-information-v028 and decision memory is
observed-decision-memory-v2. Existing visual policies remain unchanged.

Add an optional max_loop_tokens guard, disabled by default. At each complete
decision boundary, track observed player coordinates (map ID, x, y) across the
whole run. A previously unvisited endpoint or a new verified milestone resets
the counter. Revisiting known endpoints on different maps, editing notes or
changing goals cannot reset it. Persist the seen locations, milestones and
counter across pause and resume. Set 1000000 tokens for this diagnostic, in
addition to the existing 1000000-token single-map guard. Stop with reason
loop_token_budget after that many reported tokens without a reset. This is a
conservative spending guard, not a proof of failure. It can stop useful activity
in familiar locations and does not catch wandering that keeps finding new ones.
The final model call can carry usage beyond the threshold. A terminal game
success or an already-triggered limit retains its original termination reason.

Pause starter-memory-v027-luna-10m-01 at a complete decision boundary, preserve
its artifacts, and label it operator-paused for replacement rather than failed.
Verify its replay. Do not silently resume it with a different runtime.

Run one new gpt-5.6-luna trial from the identical starter-outside-lab-v027 state,
with the identical first-starter objective, empty notes and empty observed memory.
Use subscription client 0.157.0, medium effort, fresh decisions and all previous
supporting limits. Total allocation is 10000000 reported input-plus-output
tokens. No hints, manual gameplay, retries, substitute models or usage resets.
This jointly tests larger recall, persistent goals and a new stopping rule.
It does not isolate any one of those changes. The earlier attempt was censored
by the operator, so do not compare its endpoint as an exhausted-budget failure.

Freeze the runtime before launch. Verify actual paired model text/image delivery,
plan fields, the 50-decision bound, usage and stopping counters. Replay the
controller trace and export a private review and sanitized audit at termination.
The observer's live page may display the model's plan, with no feedback from
that page into the model. Keep raw game states and traces private.
