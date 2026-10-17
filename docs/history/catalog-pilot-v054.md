# Catalog pilot and interface fixes v0.54

This small diagnostic uses Sol, Terra and Claude Sonnet 5.5 on five focused tasks.
It is not a full-budget leaderboard comparison. Original attempts and their saved
instructions remain unchanged in the private `catalog-pilot-v053` artifact set.
Targeted follow-ups use `catalog-pilot-v054` and `catalog-v3` fixtures.

## What the pilot exposed

All three initial healing attempts used the Potion on Pikachu correctly. The
private evaluator also required returning to the overworld or pause menu, but the
agent goal did not disclose that condition. The attempts reached the original
100,000-token ceiling while still in the recovery dialogue.

Eight menu task instructions now explicitly disclose the existing end-screen
requirement. The grader and action policy are unchanged. Manual tasks still
require native menu inputs. No item shortcut has been enabled. Follow-up healing
runs use a 200,000-token diagnostic allowance. Because both wording and allowance
changed, improved completion does not isolate the effect of either change.

Saffron Gym navigation exposed misleading action feedback. A delayed warp could
change the position after the input ended, while the command outcome still said
that movement was blocked. The benchmark observation recorder now reconciles the
final position before writing both action feedback and working memory. It reports
the observed transition without supplying a warp destination in advance, a route,
or an automatic decision. Direct input tile counts remain distinct from the
position change that happens during the transition.

The native states in `catalog-v3` are unchanged copies. Eight task specification
hashes changed because their public instructions changed. Existing model results
and old fixture proofs retain their original hashes. The protocol is
`red-v0.54-explicit-menu-finish`.

## Budget and interpretation

The combined diagnostic ceiling is 1,825,000 reported input plus output tokens.
Subscription transports check this between responses, so a single in-flight
response can overshoot its remaining allowance. No automatic paid retry is made
when usage is unknown. The first matrix uses 150,000 tokens each for navigation,
Brock and starter selection, 100,000 for healing and 25,000 for preparation.

Targeted follow-ups use 200,000 for healing, 150,000 for one Sonnet navigation
check, and 90,000 for one Sol Long smoke. The Long smoke only checks execution,
checkpointing and progress reporting. It cannot measure full-game ability.
Preparation assessment uses the same fixed controller over five registered
starts. Its wins are assessment outcomes, not five model-played battles.

Public instructions and visible feedback belong in this benchmark package.
These fixes do not change Core item handling or emulator behavior. Initial pilot
results should be read with the disclosed menu-instruction omission and reduced
budgets. Budget-limited attempts are not evidence that a model cannot solve the
full task.

## Completed pilot

Twenty model attempts used 1,596,918 reported tokens, with complete accounting
and no recorded infrastructure failures. All three models passed Brock and their
submitted preparations won five of five fixed-controller assessments. Terra and
Sonnet obtained a starter. Sol used its small allowance searching for a preferred
starter instead of accepting one already offered.

All three healing follow-ups passed with manual controls. Sol used 128,975 tokens,
Terra used 155,375 and Sonnet used 120,623. The default healing allowance is now
200,000 tokens, based on these observed completions. Current fixtures are in
`catalog-v4`. This revision changes only the healing budget from `catalog-v3`.
Earlier fixture revisions and both pilot phases remain intact.

The native warp replay confirmed that final-position feedback is now accurate.
The Sonnet follow-up still reached its 150,000-token navigation allowance after
13 calls, so this pilot does not establish full-budget navigation performance.
The Sol Long smoke used 80,287 tokens over eight calls, preserved its checkpoint
and finished at the budget boundary with zero milestone points. It does not
validate later campaign milestones.

The full suite passed 751 tests with three skips. The local `pilot-v054.html`
report links every model gameplay replay and includes downloadable results.
No GitHub publication or broad model sweep was performed.
