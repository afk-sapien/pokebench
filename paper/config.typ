#let paper-title = "PokeBench: Reproducible Decision-Making Benchmarks in Pokemon Red"
#let paper-wordmark = "PokeBench"
#let paper-cover-subtitle = "Focused evaluation, failure review, and matched repeat trials"
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
  PokeBench compares language-model agents on checkpoint tasks in Pokemon Red.
  Tasks cover navigation, battle tactics, manual menu operation, team
  preparation, and quests. Structured player information and mechanical
  shortcuts support strategy tasks, while menu tasks require manual inputs. This
  report presents a completed cross-provider pass, its token usage, a review of
  failure traces, and a targeted repeatability check. Opus obtained the highest
  equal-category score in the initial pass, while category results exposed
  different strengths across models. Many tasks reached a ceiling or floor, and
  response-format failures clustered in the warp-navigation task. The results
  describe agents within this framework, not model ability independent of tools.
  All original attempts remain recorded, including repaired infrastructure
  failures. Repeat outcomes are reported separately so that selected tasks do
  not receive extra weight in the main ranking.
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
