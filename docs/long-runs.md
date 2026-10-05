# Memory and recovery in v0.10

The controlled runner starts a fresh model context for every decision. It sends
the objective, budget, current and previous-batch screenshots, eight recent
controller results, the agent's notebook, and its last executed plan. It never
replays the full conversation. This already prevents context from growing with
campaign length. The agent chooses what to remember and what to replace.

`--journal` adds bounded storage to the compact Codex policy. Every response adds
`journal: {writes: [{key, text}], delete: [key], query: string | null}`. These are
agent-authored claims, not verified facts. There are no automatic summaries,
route hints, object labels, or evaluator facts in memory. The visual observation
allowlist remains unchanged apart from requested journal results.

Limits are 128 entries, 2,048 UTF-8 bytes per entry, 65,536 total key and value
bytes, eight edits per decision, and a 128-byte query. Search matches every
case-insensitive whitespace-separated term in the key and text. Empty query
returns newest entries. Retrieval returns at most five entries and 4,096 key and
text bytes. Snippets may be explicitly truncated. Results appear on the next
call and are replaced by that call's query results. A null query clears them.
The 8,192-byte notebook limit remains separately configurable.

A journal edit or query can use an empty controller batch. This costs a model
call and its reported tokens but advances no game frames. The runner validates
all memory changes and controller actions before applying the decision. Invalid
requests cannot partially update the notebook or journal.

Notebook replacements, journal edits, searches, retrieved text, pauses, and
resumes are recorded in `memory.jsonl`. Decision artifacts retain the exact
model-visible context and usage. Audit artifacts are private and never fed back
to the model. `recovery.json` contains private evaluator and emulator state too.

## Pause and resume

```bash
uv run pokeagent pause --run runs/my-trial
uv run pokeagent resume --rom /absolute/path/red.gb --run runs/my-trial
```

Pause is a request, acknowledged after the current complete decision. Check
`result.json` for `state: paused`. `--pause-after-decisions N` pauses after N new
decisions in the current invocation. It does not change the task budget.
CLI resume supports controlled Codex runs. MCP and arbitrary provider recovery
are not exposed by this interface yet.

The runner commits a checksummed recovery snapshot at each complete decision.
It preserves the emulator state, screenshot, private evaluator, operation IDs,
notebook, journal, retrieval results, recent controller history, visual repeat
counters, last plan, invalid-response count, usage, and provider token reserve.
The snapshot also preserves the final queued controller release, which PyBoy
save files omit. Version 0.10.1 restores that requested release without ticking
the emulator. This prevents a zero-release-frame action from leaving a button
held after resume. The entire run keeps its original budget and action numbering. Active elapsed
time carries over. Time offline is recorded separately and excluded from the
active wall-time budget. Original creation time and resume timestamps remain
available for calendar-time analysis.

Resume requires unchanged logs, manifest, ROM, runtime source, core and emulator
versions, and provider configuration. A process lock prevents concurrent writers.
A completed, budget-exhausted, or failed checkpoint cannot be resumed. Save the
original runtime source when archiving runs so future code edits do not prevent
recovery. Model service revisions cannot be frozen by the local harness.

An in-flight marker is written before the model call. A crash during a call or
uncommitted controller batch leaves uncertain usage or actions. Automatic resume
refuses this case rather than retrying, replaying actions, or resetting usage.
Only a committed complete decision can be recovered. Use the pause command for
planned shutdowns, not Ctrl-C. Provider failures retain incomplete accounting
when usage is unavailable. This is conservative recovery, not arbitrary crash
continuation.

## Benchmark interpretation

v0.10 records the journal and recovery policies in the manifest and comparison
group. Journal-enabled and baseline runs are separate protocols. Memory storage
has bounded capacity and requested retrieval enters the normal token budget.
There are no extra unaccounted summarizer calls. Agent memory quality remains a
measured gameplay skill while transport, storage, and budget enforcement belong
to the harness.

Validation includes memory bounds, transactional rejection, public observations,
checksums, changed logs and manifests, in-flight calls, writer exclusion,
idempotent actions, and cumulative usage. A real-emulator smoke test compared a
paused/resumed run with an uninterrupted run. Both replayed with the same action
trace hash and byte-identical final save states.
