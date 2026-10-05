# Million-token unassisted starter trials

This protocol expands the assessment-first starter budget for Luna, Terra, and
Sol. Each model receives one independent attempt from the same verified opening
checkpoint, using the existing ChatGPT subscription and low reasoning effort.
The objective remains obtaining a starter from Professor Oak. The visual agent
gets no object labels, hints, RAM game facts, reference route, or automatic
navigation. Only its controller requests advance the emulator.

## Protocol declared before results

The benchmark tag is `red-v0.6-1m-experimental`. Runtime source is the archived
assessment-first implementation, with only the benchmark tag changed from the
100k version. Its SHA-256 is
`f5e470cb274f25cae4128c8f83c0e2530f5ee5a8aaa257484a6d14da34b85f6e`.
The prior source SHA-256 was
`c6c7661a50204da01352f93ceb36e781d22aec6585b5ab3e8376ac51dbb05383`.
The prompt, decision schema, image presentation, memory, and controller semantics
are unchanged. The later motion-feedback policy and repeated-view spending guard
are disabled to preserve the earlier interaction protocol.

| Limit | Per model |
| --- | ---: |
| Reported input plus output tokens | 1,000,000 |
| Model decisions | 400 |
| Controller actions | 1,000 |
| Emulator frames | 600,000 |
| Wall seconds | 7,200 |
| Frames per action | 600 |
| Actions per decision | 2 |
| Notebook UTF-8 bytes | 8,192 |

The first five limits replace the short-run limits. The remaining limits are
unchanged. The three models form a new comparison group. They run concurrently
in isolated emulator instances, so wall times include possible host and service
contention and should not be treated as controlled latency comparisons.

Reported tokens include cached input once. The runner estimates the next call
from the last call's input and output plus 512 tokens. It stops before a request
that does not fit this estimate. One in-flight request could still exceed the
threshold. No paid API fallback, automatic retry, or usage reset is authorized
by this protocol. Task completion or the first exhausted limit ends each run.

Local run IDs are `starter-v06-luna-1m-01`, `starter-v06-terra-1m-01`, and
`starter-v06-sol-1m-01`. Exact runtime source is preserved under ignored
`data/source-snapshots/`. The launch script and declared limits are under
`data/million-token-trials/`. ROMs, screenshots, states, and model records remain
private. Completed results were replay-verified and frozen into the paper.


## Verified results

All three runs stopped through token reservation with complete usage accounting.
None exhausted its call, action, frame, or wall limit. There were no retries,
hints, model substitutions, or interventions. Total reported usage was
2,991,870 tokens. All three traces passed deterministic replay. All 433 saved
model-input images matched their recorded hashes, and every source panel matched
the initial preview or controller trace. The sanitized export places the three
runs in comparison group `7518b62d7e77`.

| Model | Reported tokens | Decisions | Actions | Frames | Wall seconds | Formal completion |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Luna | 997,763 | 157 | 192 | 6,635 | 1,557.21 | 0/1 |
| Terra | 996,083 | 138 | 183 | 7,697 | 1,599.24 | 0/1 |
| Sol | 998,024 | 138 | 200 | 9,205 | 1,552.56 | 0/1 |

Luna moved between the bedroom and ground floor but never left the house. It
ended upstairs with an empty party. At decision 99, its plan referred to a sign
and buildings while the saved input image clearly showed the bedroom. This was
an observed interpretation error, not a map-ID change during a fade.

Terra reached Pallet Town, then returned home and continued moving between
floors. It ended on the ground-floor map with an empty party. Neither its outdoor
exploration nor its later return satisfied the starter objective.

Sol reached Pallet Town, triggered Oak's warning, followed the scripted sequence
to the laboratory, selected Bulbasaur, and reached the nickname Yes/No prompt.
The image supplied at decision 133 visibly contained the full receipt message.
The final screenshot shows the nickname question and menu. Sol thus reached a
substantially later stage than the others in this batch. One trial per model does
not establish a reliable model ranking or isolate the causal effect of budget.

### Sol's completion boundary

The existing evaluator requires a valid game state, the starter story flag, one
recognized starter species in the party, and two consecutive confirming frames.
At Sol's stop, the game had displayed receipt of Bulbasaur, but the pending party
entry still decoded as species 0 and the starter story flag was false. The state
was not yet valid under that check. The nickname sequence was unfinished.
Consequently the original score is 0/1, despite the visible receipt message.
No extra button press or wait was applied after the budget stop, and no score was
changed retroactively.

The player-facing objective said to obtain a starter without explicitly naming
the nickname-completion boundary. That mismatch deserves clarification in a
future protocol. The present report preserves both the formal score and the
visible progress. Sol's result should not be summarized as failing to find or
select a starter.

### Token accounting

| Model | Input tokens | Output tokens | Unused threshold |
| --- | ---: | ---: | ---: |
| Luna | 939,639 | 58,124 | 2,237 |
| Terra | 930,566 | 65,517 | 3,917 |
| Sol | 942,359 | 55,665 | 1,976 |

These are reported tokens, including cached input once, not subscription-credit
estimates. Reservation stopped each run when the next estimated request would
not fit. The resulting attempts contain 138 to 157 decisions and 183 to 200
actions, rather than the 13 to 14 decisions in the short assessment-first trials.
Wall time is descriptive because the models ran concurrently.

### Replay evidence

- Luna: `5387bca6512cfcd83ce568219be10673681b7d63d01ad3b508d33ddb694c66d8`
- Terra: `c41aaf92c91d71d49cd2a02ed768897c44e938f19e58ddf4501c4aae38fa33da`
- Sol: `58d5ea3c543a8c93901cef5c37a6125cf938693b59c19e2dfd31896e8638b33d`

The local audit summary and script remain in `data/million-token-trials/`.
ROMs, emulator states, game screenshots, and raw model records are not published.
