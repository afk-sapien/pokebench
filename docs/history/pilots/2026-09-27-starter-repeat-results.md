# Starter baseline repeat results

All three explicitly requested baseline repeats finished without obtaining a
starter. They stopped at token reservation limits with complete usage
accounting. These are unchanged v0.11 baseline settings, not the rejected
observation-first treatment.

| Model | Decisions | Actions | Reported tokens | Progress |
| --- | ---: | ---: | ---: | --- |
| Luna | 21 | 32 | 241,297 | Remained in the bedroom |
| Terra | 20 | 28 | 234,921 | Reached the ground floor at decision 11 |
| Sol | 19 | 38 | 231,122 | Reached the ground floor at decision 5 |

No model reached outdoors or Oak's laboratory in these repeats. Relative to the
original run, Terra reached the ground floor earlier, at decision 11 instead of
13. Sol reached it at decision 5 instead of 11, but did not reproduce its earlier
outdoor visit at decision 16. Luna remained in the bedroom in both attempts.
Faster early progress did not imply better eventual progress.

## Accounting and validation

The repeats used 707,340 reported tokens against the combined 750,000 allowance.
That includes 694,209 input tokens and 13,131 output tokens. Input contains
560,768 cached tokens and 133,441 uncached tokens. There were 60 recorded model
calls and 98 controller actions. Every run stayed below its 250,000 cap, and
there were no service failures or replacement attempts.

No summary rotation occurred. The runs again exhausted the total allowance
before reaching the 24,000-token context threshold. These results do not test
long-horizon memory management, and 19 to 21 decisions is not evidence of the
models' maximum ability with a different allowance.

Manifest comparisons confirmed equality with each corresponding original run
for the agent configuration, prompt hash, model effort, limits, starting save,
core, source hash, benchmark and visual track. Model sampling and remote
backend behavior are not fixed by those manifest checks. Deterministic replay
verified all 98 actions, game screenshots and evaluator evidence. The review
export also verified recorded model-input image hashes and their game pixels.

## Interpretation

There is still no validated framework improvement to promote. The repeated
baseline failures support investigating persistent false visual beliefs and
weak correction after feedback, but these results cannot isolate a cause.
The change in Sol's progress also shows why one successful intermediate step
or one run should not determine model rankings or prompt selection.

Production code and defaults remain unchanged. The paper contains these
results as a separate repeat batch. Raw run artifacts remain local, and the
paper audit contains sanitized counts and source hashes.

[Protocol](2026-09-27-starter-repeat-protocol.md).
[Original and repeat review](http://127.0.0.1:8942/starter-v011-repeat-review.html).
