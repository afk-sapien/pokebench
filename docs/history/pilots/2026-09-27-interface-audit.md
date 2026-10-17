# Starter failure audit and proposed harness changes

Status: offline diagnosis and implementation recommendation. No new model calls
were made for this audit. Proposed changes below are not implemented or measured.
The frozen v0.10 results remain unchanged.

## Finding

The current trials demonstrate failure of the complete model and harness
configuration. They do not isolate model capability. Prioritize a continuous
agent session with controlled compaction, then test presentation and prompt
simplification independently. Additional token budget alone is poorly motivated.

## Evidence from the existing runs

The three trials consumed 2,988,118 reported input plus output tokens. All used
low reasoning effort and a new ephemeral Codex process for every decision.
The model retains its notebook, recent controller metadata, previous plan and
previous-batch screenshots. It does not retain a continuous conversation.

The journal addition did not compensate in these runs. None of the models
requested journal writes, deletions or retrievals. Notebook replacements occurred
113 times for Luna, 130 for Terra and 138 for Sol.

Sol's input at decision 86 contains a notebook claim that Oak's event brought it
into the laboratory. It was actually downstairs at home. Its response describes
home furniture as the starter table and Mom as Oak. The invented event persists
in the notebook at decision 123. By decision 135 it recognizes Mom's dialogue.
This is a concrete belief-correction failure. It is not evidence that every
frame is unreadable or that the emulator lost the controller actions.

Luna stays at the same home tile from decision 62 to the end while repeatedly
attempting to advance an imagined starter introduction. Terra repeatedly probes
an outdoor barrier and sometimes describes animation as scrolling or progress.
These remain model claims in the review portal, not evaluator-verified events.

An offline replay checked every action screenshot against its recorded SHA-256.
Private game coordinates were used only to audit net tile changes. They were
never sent to the models.

| Model | Directional actions | Same map and tile before and after | Same tile with changed screenshot |
|---|---:|---:|---:|
| Luna | 80 | 43 | 30 |
| Terra | 182 | 95 | 86 |
| Sol | 175 | 61 | 36 |

No net tile change does not by itself establish a collision, ignored input or
lack of sub-tile motion. The important limitation is that whole-screen pixel
change cannot serve as a reliable progress signal. The existing prompt already
warns about this, so adding that warning again is not a substantive fix.

Offline neutral-wait branches expose some screenshots captured during game
transitions. After Terra decision 24, 60 neutral frames change about 94.6% of
pixels as the outdoor scene finishes appearing. After Sol decision 77, the
corresponding change is about 94.7%. These were diagnostic branches, not extra
frames added to the actual trials. Settled samples also show wrong scene
interpretations. Timing is therefore a contributor worth testing, not a complete
explanation or proof of a broken renderer.

Current presentation packs one to three unique panels at 2x scale and changes
the current panel's horizontal position with the panel count. Current is labeled
and the pixels are preserved. This is a usability hypothesis, not evidence that
images are missing or corrupted. The current tests verify the bytes supplied to
the CLI, not the service's internal image preprocessing.

## Proposed changes, in priority order

1. **Continuous session and compaction.** Add a provider using a persistent Codex
   conversation for each run. Return controller outcomes as tool results and
   continue the same session. Compact at a declared context threshold rather
   than discarding conversation after every decision. Preserve agent-authored
   notes and references to its own prior observations. Count compaction usage,
   retain audit events and fail closed if usage accounting is unavailable.
   Expose only the game controller, observations and bounded agent memory.
   Keep the existing stateless protocol available as a separately named control.

2. **Simpler response contract.** Test actions plus optional brief notes in place
   of mandatory scene classification, object inventories and repeated notebook
   reconstruction. The model still performs perception and planning. The harness
   should not force every uncertain visual interpretation into a long report.
   Notes remain fallible agent claims, never facts validated by hidden game state.

3. **Consistent visual input.** Test a fixed single current frame at an integer
   enlargement, initially 3x, with recent observations available on request.
   Keep original screenshots and exact frame IDs. Compare this with the existing
   strip under matched budgets. Do not assume a single image or larger scaling
   necessarily costs fewer tokens. Measure reported usage and success.

4. **Explicit controller timing.** Keep hold, release and wait semantics simple
   and deterministic. Calibrate documented tap durations in offline emulator
   checks. Any fixed neutral duration must be part of the agent's requested
   action and count against the frame budget. Intermediate samples can come
   from frames already requested. Do not introduce hidden-state-driven settling,
   automatic dialogue advancement or route-specific macros.

5. **Reasoning effort comparison.** Test medium effort against low with otherwise
   identical settings and total budgets. The million-token cap was an aggregate
   usage limit, not a request for deep reasoning at each decision. More effort
   might improve decisions or merely reduce how many fit. Measure both.

These changes should receive new protocol identifiers and provenance. A useful
interface does not require object labels, player coordinates, collision maps,
NPC identities, route hints or a second model that corrects gameplay.

## Evaluation sequence

First run offline controller and screenshot conformance checks. Reconstruct
transitions and dialogue from existing traces without model calls. Verify action
semantics and human usability of exactly the observations the model receives.
These are interface diagnostics, not new leaderboard achievements.

Next predeclare capped paired development trials at identical failure
checkpoints. Start by isolating continuous versus fresh sessions with the same
images, schema and effort. Then isolate the response schema, image policy and
effort. Use a shared setup across Luna, Terra and Sol. Account for every attempt,
including failed or interrupted calls. Establish a total experiment budget before
launching rather than allocating another million tokens to every combination.

After selecting the common harness on development checkpoints, freeze it and
rerun the actual starter task from the unchanged initial save. Use repeated
trials if making comparative success-rate claims. Report completion, tokens to
completion, decisions, game frames, active wall time and compaction overhead.
Stop immediately when the private evaluator confirms acquisition and completion
of the required dialogue. Preserve failures and compare protocol versions
separately. Diagnostic checkpoint performance must not be presented as full
starter acquisition.

## Sources and reproducibility

- [Frozen trial results](2026-09-27-starter-v010-results.md)
- [Predeclared trial protocol](2026-09-27-starter-v010-protocol.md)
- Provider: `src/pokeagent_bench/codex_provider.py`
- Prompt and schema: `src/pokeagent_bench/compact_provider.py` and
  `src/pokeagent_bench/journal_provider.py`
- Presentation and pixel feedback: `src/pokeagent_bench/visual_feedback.py`
- Local diagnostic script: `/tmp/audit_starter_interface.py`
- Local diagnostic output: `/tmp/pokeagent-interface-audit/audit.json`

The temporary script and screenshots are private diagnostic artifacts and are
not committed. It replays each initial state and logged action, verifies output
image hashes, and branches selected decision boundaries for 8, 16, 32 and 60
neutral frames. It reconstructs the pending button release on each branch.

OpenAI's [Codex harness discussion](https://developers.openai.com/blog/codex-as-a-platform)
describes the importance of retained reasoning and compaction in another
interactive benchmark. This motivates an experiment here, not an expected
Pokemon success rate. The [App Server documentation](https://learn.chatgpt.com/docs/app-server)
provides persistent threads, turn continuation and explicit compaction. The
[reasoning guide](https://developers.openai.com/api/docs/guides/reasoning)
describes the effort tradeoff. Validate the installed subscription client's
capabilities before implementation, and preserve the exact requested model IDs.
