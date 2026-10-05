#import "assets.typ": tbl
= Supporting Information

== Current development catalog

The task inventory appears in @tbl:catalog.

#figure(tbl("tbl.catalog"), caption: [Task inventory at the frozen development
  snapshot. Scored means included in the historical development ranking. It does
  not imply that fresh release trials are complete. Experimental candidates
  remain outside that ranking.]) <tbl:catalog>

== Reproduction and disclosure

The report statistics and tables are generated from sanitized inputs under
`analysis/inputs`. Run `just assets`, `just paper`, and `just verify` from the
manuscript directory. The export script records hashes of its source summaries
and selects an explicit set of public fields. Re-exporting data changes those
hashes and requires a new build.

The archived pre-release manuscript contains earlier observations of visual
perception, navigation, memory, and budget failures. Those studies used
different framework versions and are not pooled into the current pilot. The
upstream Paper Scaffold license and pinned toolchain revision are preserved in
the paper directory. Reported results do not imply endorsement by the game
publisher or model providers.


#pagebreak()

== Registered release models

@tbl:models lists the prospective matrix. Registration is distinct from
completed evaluation and from a successful provider-access smoke test.

#figure(tbl("tbl.models"), caption: [Registered identifiers and effort settings
  in the prospective beta protocol. These are planned participants, not
  results.]) <tbl:models>

The complete frozen protocol is supplied as
`analysis/inputs/pokebench-v1-protocol.json`. Its canonical checksum is #text(
  size: 8pt,
)[`99c4e3a7dfbc0598d2be7c2f75201a08efeb7c63ba7b617da30bc4c7ad2a6d05`]. It
records exact task thresholds, starting-state hashes, runtime identifiers,
transport settings, and scoring rules. The source protocol was checked against
this checksum before inclusion in the public paper inputs.
