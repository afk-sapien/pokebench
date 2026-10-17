#import "assets.typ": tbl
= Supporting Information

== Recorded model identifiers

@tbl:focused-identifiers lists provider identifiers saved with these runs.
Leaderboard display names are shorthand for these identifiers.

#figure(tbl("tbl.focused-identifiers"), caption: [Provider identifiers recorded
  for models in the focused pass.]) <tbl:focused-identifiers>

== Task inventory and budgets

Navigation appears in @tbl:focused-navigation, battle in @tbl:focused-battle,
manual operations in @tbl:focused-operations, preparation in
@tbl:focused-preparation, and objectives in @tbl:focused-objectives.

These tables list tasks represented in the focused pass, not every proposed or
historical task. Token limits are expressed in millions per attempt. Preparation
uses a constrained submission followed by offline battle grading.

#figure(tbl("tbl.focused-navigation"), caption: [Navigation tasks and
  budgets.]) <tbl:focused-navigation>
#figure(tbl("tbl.focused-battle"), caption: [Battle tasks and
  budgets.]) <tbl:focused-battle>
#figure(tbl("tbl.focused-operations"), caption: [Manual menu tasks and
  budgets.]) <tbl:focused-operations>
#figure(tbl("tbl.focused-preparation"), caption: [Preparation tasks and
  budgets.]) <tbl:focused-preparation>
#figure(tbl("tbl.focused-objectives"), caption: [Quest and combined-objective
  tasks and budgets.]) <tbl:focused-objectives>

== Reproduction

The snapshot is `analysis/inputs/focused-v060.json`. It records aggregate
scores, selected attempts, starting-state checksums, budgets, usage, audit
counts, and repeat outcomes. Replay paths are relative to the local preview
site. They do not imply that private game assets are publicly distributable.

Run `scripts/export_focused_analysis.py` with the initial directory as `--run`,
the local website as `--web`, and the repeat directory as `--repeats`. The
`--paper-input` option refreshes this report's input. From the manuscript
directory, run `just assets`, `just paper`, and `just verify`. Numeric prose and
tables are generated through the existing Paper Scaffold.

Earlier report sources and historical analysis inputs remain archived. Future
publication can reuse this comparison with its evaluation conditions stated.
This report implies no endorsement by the game publisher or model providers.
