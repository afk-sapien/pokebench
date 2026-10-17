# Canonical text field order repair

The v031 text pilot exposed an audit reproducibility defect. Live text rendering
used dictionary insertion order, while the canonical JSON audit log sorts keys.
Regenerating text from a recorded payload therefore changed field order. All
13 v031 text calls had identical line contents and multiplicities, but their
regenerated text was not byte-identical.

Preserve that frozen trial. Its corrected audit matches the exact recorded text
and screenshot in the actual client message, and checks regenerated line content
without claiming the original field order was reproduced. Retain the original
exception, launcher and repair record. Continue the unstarted JSON control with
the same original v031 runtime. Do not restart or extend either model trial.

Version red-v0.32-experimental, package 0.22.1, canonicalizes the public payload
before text rendering. The presentation protocol is observed-gameplay-text-v2
and gameplay harness is codex-app-server-gameplay-v032. Dictionary field order is
now reproducible after audit-log serialization. Array order, including decision
chronology, map rows and dialogue pages, remains unchanged. Add a regression test
for exact byte equality after a sorted JSON roundtrip. No new game information,
hints, action policy, memory capacity or model calls are introduced.

The active comparison remains v031. Do not relabel its performance results as
v032 or attribute gameplay improvement to this audit-only repair.
