# Action grounding results

The proposed observation-first instruction did not pass the engineering gate.
All continuation checks and all six comparison arms completed. No service
failures occurred in this invocation. No starter batch was launched and no
production prompt was changed.

## Continuation

Luna and Terra resumed their recorded conversations after verified replay of
their first action. Sol received the explicitly declared technical replacement
for its earlier capacity failure. All three recognized that no downstairs
transition had occurred. All retained the incorrect staircase interpretation
of the bed. Recognizing a failed transition did not by itself repair the belief
that drove the action. The prior capacity failure and unknown cost remain in
the v012 report, not erased by this successful continuation.

## Controlled comparison

Each arm received four individual actions and a final assessment with the same
save, 3x screenshots, objective, schema, medium effort and controller semantics.
Only the instruction to describe visible evidence before acting differed.
The baseline uses the v012 diagnostic contract, not the production simple
response contract. The initial question for both arms was made neutral about
whether a scene description should be included.

| Model | Baseline unique positions | Observation-first unique positions | Baseline tokens | Observation-first tokens |
| --- | ---: | ---: | ---: | ---: |
| Luna | 4 | 4 | 22,692 | 23,157 |
| Terra | 4 | 7 | 32,149 | 32,992 |
| Sol | 8 | 4 | 31,626 | 30,231 |

Positions count the initial tile and every intermediate tile crossed, sampled
from private emulator state at each frame during offline replay. Earlier
progress updates used action endpoints, which understated longer moves. The
full counts above supersede those preliminary counts. Coverage is descriptive
and is not a task completion score. All arms remained
in the starting room during the four-action diagnostic.

Terra's observation-first arm rejected its downward staircase hypothesis,
recognized the bed, and explored upward. The final screen revealed the actual
stairs, which it cautiously identified. Its baseline kept trying to enter the
bed area. This is an encouraging example, not a reliable treatment effect.

Luna retained the false exit hypothesis in both arms. Its observation-first
arm also reported moving left after an input that only changed facing at the
same tile. Sol's baseline recognized the bed and explored rightward. Sol's
observation-first arm kept trying different approaches to the supposed stairs.
Sol's baseline final assessment also confused a facing change with movement.
The new instruction therefore did not consistently fix either object beliefs
or action-result interpretation.

## Gate and limits

All six arms completed within their caps. The treatment improved visited-tile
coverage for Terra, tied Luna, and reduced it for Sol, failing the declared
requirement of improvement for at least two models without regression in the
third. Luna and Sol also repeatedly acted on a false exit interpretation.
There were no asserted room transitions in the comparison assessments.
The gate failed and the starter rerun was not launched.

Offline grading was performed by one unblinded reviewer using the saved images
and private map/tile evidence. Physical movement assessment was counted
separately from scene interpretation. This is a single trial per arm with only
four actions. It neither establishes statistical significance nor shows that
any model cannot complete the room with more time. No hints, correct labels,
object coordinates, maps or automatic recovery were sent to a model.

## Spending and verification

The continuation used 36,923 reported tokens against a 50,000 cap. The comparison
used 172,847 against its combined 240,000 cap. Every arm stayed below 40,000.
This invocation used 209,770 reported tokens across 37 completed calls and 28
new controller actions. The total contains 202,653 input tokens and 7,117 output
tokens. Input includes 78,080 cached tokens and 124,573 uncached tokens. Accounting
is complete for this invocation. There were no summary or compaction calls.
Prior v012 spending is separate and still has one unknown failed-call cost.

All 37 model-input frames and 28 new action results matched deterministic
replay. The unchanged production runtime hash is
`a7e8e566c89d8a3b5b33ca5ad7b16ac6657bb1a851e820fdf29420b763e74aa1`.
Raw calls, scripts, states and offline grading remain local under
data/action-grounding-v013. Sanitized counts and hashes are exported to the
paper. Neither the production prompt nor its benchmark version was promoted.

## Recommendation

Do not make observation-first mandatory based on this test. It can produce a
more elaborate incorrect description without improving control. A subsequent
experiment should target how an agent revises a hypothesis after a failed
prediction, keeping any new instructions generic and the correct game answer
private. Repeating failed directions, confusing facing with motion, and
retaining a disproved destination should be measured separately. Such an
experiment is not run or claimed successful here.

[Protocol](2026-09-27-action-grounding-protocol.md).
[Visual comparison](http://127.0.0.1:8942/action-grounding-v013-review.html).
