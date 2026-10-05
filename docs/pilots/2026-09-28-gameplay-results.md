# Structured gameplay diagnostic results

All ten started traces replayed exactly. Every recorded structured input and image was verified in the actual client history. All reported usage is accounted for.

Initial v017 usage was 681,011 tokens. Revised v018 usage was 478,644 tokens. Combined usage was 1,159,655, below the original 1,200,000 allocation. No further charged tests were run.

| Revised trial | Tokens | Decisions | Observed outcome |
| --- | ---: | ---: | --- |
| Luna brock | 120,473 | 25 | Defeated Brock and reached badge-receipt text. Formal badge flag remained unset. |
| Terra brock | 119,894 | 15 | Reached Onix and stopped during switching. |
| Luna starter | 117,274 | 28 | Left the bedroom, later returned upstairs. No starter. |
| Terra starter | 121,003 | 21 | Reached Pallet Town. No starter. |

The four revised attempts ended at the prospective token reserve. None completed the unchanged formal objective. Battle victory text is reported separately from the badge event, without rescoring the run.

The initial four Brock attempts ended at their token reserves. The two initial starter attempts were paused after reaching the ground floor. The two remaining starter attempts were cancelled before model calls. Preserve these interrupted diagnostics separately from failures.

The pilot supports further investigation of decision making with structured information. It does not establish full-game performance, a model ranking, or a causal improvement from any single change. Observations, controls, context retention and caps differ from earlier visual trials.

PokeSim Core 0.1.3 supplies read-only primitives. The latest observation policy v018.1 adds a conservative map-transition guard after the charged v018 trials. The original inputs, source snapshots and results remain unchanged.

Local reviews: `http://127.0.0.1:8942/gameplay-v018-review.html` and `http://127.0.0.1:8942/gameplay-v017-review.html`. Raw images, saves, tables and client responses remain private and ignored by Git.
