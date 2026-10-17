# Astra outside-start extension

The user requested Astra on the current outside-start benchmark. Run exactly
`gpt-6-astra` using the existing subscription adapter. Keep scenario protocol
starter-segments-v014 and frozen runtime v0.11 unchanged. This is an additional
model in the outside-start comparison, not a new task or prompt treatment.

Use starter-outside-v014, medium effort, current 3x screenshots, the simple
response contract, continuous history and the 24,000-token metered summary
threshold. Retain the no-nickname rule. Provide no labels, routes, hints,
reference actions or earlier model findings.

Copy all limits from the prior outside runs: 250,000 reported input plus output
tokens with reservation, 100 model calls, 300 actions, two actions per decision,
600 frames per action, 120,000 total frames and 1,800 seconds. Stop on objective
completion or limits. Do not retry, substitute models or increase the allowance
automatically. Preserve errors and unknown usage. The final response may exceed
a reservation because the subscription client has no hard per-response ceiling.

Verify settings and prompt parity except for the model ID, then replay the
controller trace and validate image evidence. Report token usage, cached input,
actions, decisions, progress and evaluator completion. Keep the earlier three
attempts intact. A single trial does not establish a stable model ranking.

## Compatibility amendment before the technical retry

The first attempt used CLI 0.147.0 and was rejected with HTTP 400 before any
controller action or completed model answer. The service explicitly required
a newer Codex version for gpt-6-astra. Usage was not reported. Preserve this
attempt as a compatibility failure, not a gameplay failure.

To carry out the user's Astra request, install the official CLI 0.157.0 in an
isolated local toolchain. The globally selected CLI remains unchanged. A
non-generating session-start check must confirm the exact model, medium effort,
expected instruction sources and disabled outside tools before proceeding.
The check passed. Version 0.157.0 is documented in the
[official Codex changelog](https://learn.chatgpt.com/docs/changelog).

This amendment permits one technical retry after the identified compatibility
repair. It supersedes the original no-retry sentence only for that repair.
Reserve 8,000 tokens for scheduling against the first call's unknown usage,
leaving a 242,000 reported-token cap for the gameplay attempt. Do not relabel
that reservation as measured consumption. All other game settings remain
unchanged. The new CLI version and smaller cap are explicit comparison
qualifications. Preserve both attempts, and do not retry another failure.
