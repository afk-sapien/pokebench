# Sol on the matched unassisted starter task

Sol failed to obtain a starter within the same 100,000 reported-token threshold
used for the assessment-first Luna and Terra trials. It stayed in the bedroom.
Unlike those runs, it eventually abandoned the bed-as-exit plan and correctly
identified the visible staircase. This is a qualitative difference in one trial,
not a model ranking or proof that a larger budget would succeed.

## Matched setup

The run used exact archived package source with SHA-256
`c6c7661a50204da01352f93ceb36e781d22aec6585b5ab3e8376ac51dbb05383`.
Before inference, that archive's package fingerprint was verified. The resulting
manifest matched Terra's source, initial state, scenario, ROM, emulator, core,
labels hash, visual track, goal, limits, prompt hash, memory protocol, harness,
CLI version, token reservation policy, and low reasoning effort. Only the model
was changed to `gpt-5.6-sol`. The provider used the existing ChatGPT subscription.

This was `red-v0.6-experimental`, not the later motion-feedback policy. No object
labels, object coordinates, hints, motion estimates, automatic recovery, or
reference route were given to the agent. Only its requested controller inputs
advanced the game. The fixture asked it to obtain its first starter from Oak.

## Results

| Model | Reported tokens | Decisions | Actions | Completed |
| --- | ---: | ---: | ---: | ---: |
| Luna | 94,177 | 14 | 16 | 0/1 |
| Terra | 92,105 | 13 | 13 | 0/1 |
| Sol | 92,051 | 13 | 19 | 0/1 |

Sol used 86,348 input tokens and 5,703 output tokens, with complete accounting.
All reported input counts include cached input once. These are not estimates of
subscription credits. Token reservation stopped the run before another request,
with 7,949 tokens remaining under the threshold. No automatic retry followed.
Wall duration was 166.99 seconds. Emulated duration was 11.25 seconds, or 672
frames. The trial adds 92,051 reported tokens to prior experiment usage.

Sol initially labeled the bed correctly and reported no visible exit. Decisions
3 through 9 then explored that furnishing as a potential staircase or exit.
At decision 10 it abandoned the blocked bed and explored right. At decision 12
it identified a partially visible staircase at the upper right. Its final plan
attempted to approach that staircase. Evaluator evidence recorded only map 38,
the starting bedroom, and an empty party throughout. No hints were introduced
after observing these failures.

The full trace passed deterministic replay. All 13 model-input images matched
their saved hashes, and every panel's frame and screenshot hash matched the
initial preview or controller log. Token sums matched the result file. The trace
head is `253fc57509c354d7d426a9b8482380e0e9c2ab144b87bf75bc65b1663c80f5eb`.
Raw artifacts remain local in `runs/starter-v06-sol-100k-01/`. The sanitized paper
export places all three runs in the same comparison group.

## Scope decision

The benchmark should test the agent's perception as well as gameplay. The
object-label helper remains an unused offline prototype and its expansion is
shelved. A limited hint could be a later experiment if a shared bottleneck
persists across models. That experiment must define its trigger and allowed
content beforehand, record hint timing and count, and report assisted results
separately while preserving the unassisted outcome. No hint system is active.
