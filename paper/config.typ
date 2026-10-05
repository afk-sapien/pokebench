#let paper-title = "PokeBench: Reproducible Decision-Making Benchmarks in Pokemon Red"
#let paper-wordmark = "PokeBench"
#let paper-cover-subtitle = "A technical report on the benchmark and its development evidence"
#let paper-authors = (
  (
    name: "afk-sapien",
    email: "327645577+afk-sapien@users.noreply.github.com",
    affiliation: "Independent project",
  ),
)
#let paper-keywords = (
  "agents",
  "benchmarks",
  "Pokemon",
  "reproducibility",
  "decision making",
)
#let paper-date = "October 2026"
#let paper-institution = "Independent project"
#let paper-bib-style = "american-chemical-society"
#let paper-abstract = [
  PokeBench evaluates language-model agents through reproducible checkpoint
  challenges in Pokemon Red. The gameplay track exposes structured player
  information and controller-backed shortcuts so that item selection, resource
  management, and navigation decisions matter more than repeated menu inputs.
  Private objective checks determine completion, while recorded controller
  traces support deterministic replay. We describe task curation, bounded
  context, usage accounting, paired starting conditions, and release evaluation
  controls. Audited development trials show differences between models, but they
  also show ceiling effects and sensitivity to the surrounding agent framework.
  Historical comparisons are therefore reported as development evidence, not as
  results of a newly frozen release. The report identifies the remaining
  requirements for a fair cross-provider comparison and publishes the analysis
  inputs separately from game assets and private model logs.
]

#let paper-affiliations = {
  let seen = ()
  for a in paper-authors {
    if a.affiliation not in seen { seen.push(a.affiliation) }
  }
  seen
}

// Generational and post-nominal suffixes, so a surname lookup does not return
// "III" for "John R. Yates III". Compared case- and period-insensitively.
#let name-suffixes = (
  "jr",
  "sr",
  "ii",
  "iii",
  "iv",
  "v",
  "phd",
  "md",
  "dphil",
  "dsc",
  "esq",
)

// The family name: the last token that is not a suffix. "John R. Yates III"
// gives "Yates". Used for the audiobook artist tag and the cover art.
#let surname-of(full) = {
  let parts = full.split(" ").filter(p => p.trim() != "")
  let i = parts.len() - 1
  while i > 0 and lower(parts.at(i).replace(".", "")) in name-suffixes {
    i -= 1
  }
  parts.at(i)
}

// "Lovelace, Hopper" -- used as the audiobook artist tag and on the cover.
#let paper-surnames = paper-authors.map(a => surname-of(a.name))

// Restated on the Supporting Information title page.
#let si-authors = paper-authors.map(a => a.name).join(", ")
