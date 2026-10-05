# Ability ranking v2

Benchmark `red-v0.43-experimental`, package 0.29.0, introduces the analysis
policy `ability-ranking-v2`. This changes aggregation and presentation only.
The running tactical comparison keeps its frozen v0.42 code, five saves,
500,000-token attempt limits and all seven models.

## Task selection

The main ranking removes five specific original saves: wild battle, first
capture, Brock, Erika and Sabrina. Trace review found that these checkpoints
mostly reward repeating an obvious attack or throwing a ball at an already
weakened opponent. Their exact save hashes and reasons are registered in
`combined_analysis.RETIREMENTS`. Different future saves are not automatically
retired just because their task IDs match.

This is a retrospective change informed by task design and recorded play.
It is not a preregistered claim about model quality. The new percentages are
not directly comparable with earlier rankings on all 27 tasks.

The active catalog now has 22 tasks. Useful basic tests remain, including
healing and several fights passed by every model. Universal success alone is
not a removal rule. The calibrated tactical Lorelei fight stays active and
enters the score once all models have completed matching verified repeats.
Its offline calibration outcomes never count as model results. Future hard
battle replacements should pass the same documented calibration process.

## Reporting

Removed tasks do not contribute to the main success score, cost comparison,
token totals or active attempt counts. All original suites, scores, attempts,
replays and costs remain available in historical comparisons. The main JSON
export includes the ranking version, retirement reasons, exact state hashes
and source links. The page explains the change under Methodology.

The remaining rules are unchanged: equal task weights, repeats averaged within
each task, and matched verified coverage across every model. A pending or
infrastructure-failed task is excluded equally for all models. This remains
an exploratory aggregate with historical differences in harness versions.
