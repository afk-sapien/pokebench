# Continuous visual play

Version red-v0.11-experimental adds an opt-in subscription provider with a
continuous conversation, metered context summaries, a simple response contract,
and a fixed current screenshot. Legacy providers remain available.

```sh
uv run pokeagent run \
  --rom /private/pokered.gb --scenario scenarios/starter-v010 \
  --output runs/starter-continuous-example \
  --provider codex --model gpt-5.6-sol --reasoning-effort medium \
  --codex-policy continuous --track visual --goal challenge \
  --presentation current --response-contract simple --compact-at 24000 \
  --max-total-tokens 250000 --max-model-calls 100 \
  --max-actions-per-decision 2 --max-action-frames 600
```

The model returns actions, nullable brief notes and nullable look_back. Each
controller action still specifies button, hold_frames and release_frames.
The sum of hold and release must fit max_action_frames. No movement, waiting or
dialogue advancement happens unless requested. The no-nickname rule remains.

A 3x nearest-neighbor current screenshot stays at a fixed size. look_back=1
requests the screenshot from the current decision on the next call. Values up
to eight select older decision observations. The response may request recall
without controller actions. This still consumes a decision and tokens. Exact
image bytes and source references are retained and checked by the review export.

## Context and cost

Normal turns retain their conversation. At compact_at input plus output context
tokens, the next decision writes an agent-authored summary using a normal,
metered model call. Its latest controller result and current screenshot are
included, so the summary can incorporate an executed or rejected action. No
controller actions execute during maintenance. The provider starts a new session
with the generated summary, notebook and current observation. It does not add
facts or correct gameplay for the model.

Opaque reasoning is retained only within a session. A rotation carries the
agent's explicit summary. The installed client's native compaction did not
report consumption in an engineering test, so that path is not used for scored
trials. Missing or regressing usage stops the run. Summaries and screenshot-only
requests count toward both token and call budgets. Context threshold and total
run budget are different limits.

Cumulative usage is recorded as deltas, including cached input. This is an audit
metric and does not directly equal subscription quota consumption. The client
cannot enforce a hard per-response token ceiling. The runner reserves estimated
room before a call and reports any final-call overrun.

## Recovery and comparison

The normal pause and resume commands support this provider. Checkpoints preserve
session and turn identity, usage, the recall buffer and pending summary. Resume
requires the original source and configuration and matching model history.
Do not move or delete the client's saved conversations before resuming a run.
The existing guard rejects recovery after an uncertain in-flight call.

Provider configuration, compaction protocol, presentation, response contract and
effort are recorded in comparison groups. --fresh-decisions is the stateless
control. --presentation strip restores the compact strip.
--response-contract assessment requires strip and restores the detailed schema.
The old --codex-policy compact provider remains the default for compatibility.

External tools, plugins, hooks and MCP servers are disabled. The installed client
reports the owner's global punctuation policy as an instruction source even
with project document bytes set to zero. Its audited checksum is allowlisted.
Other instruction sources stop the run. Local Codex histories are private run
dependencies. Do not publish histories, screenshots, ROMs or save states.

[Development protocol](pilots/2026-09-27-continuous-protocol.md) records the capped
comparisons and the unmetered native-compaction engineering failure.
