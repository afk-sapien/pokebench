# Project rules

## Project identity

All agents and automation acting on the owner's behalf must use only this
identity for this project:

- GitHub account and Git author/committer name: `afk-sapien`
- Git author/committer email: `327645577+afk-sapien@users.noreply.github.com`

Never use a work account, a work email, another saved login, or an agent's
suggested co-author identity for this work. This applies to commits, tags,
co-author and sign-off trailers, pull requests, merges, releases, issues,
comments, package publication, and other authenticated project operations.
Preserve legitimate third-party attribution in upstream code and history.

### Every checkout, clone, and worktree

These rules also apply to temporary clones, isolated checkouts, worktrees,
subprojects, and delegated work, regardless of their filesystem location.
A fresh clone does not inherit the source checkout's local Git configuration.
Before creating commits or tags in each checkout, set repository-local values:

```sh
git config --local user.name afk-sapien
git config --local user.email 327645577+afk-sapien@users.noreply.github.com
git config --local user.useConfigOnly true
```

Verify the effective identity with both `git var GIT_AUTHOR_IDENT` and
`git var GIT_COMMITTER_IDENT`. Both must have the exact name and email above.
Check for environment variables, command options, and worktree configuration
that override local settings. Recheck after changing checkouts or execution
environments. Do not change global Git identity or the global active login.
Other projects may intentionally use a different account.

### Authentication and publication

Git authorship and service authentication are separate checks. Before any
authenticated project operation, verify the actual account used by that CLI,
connector, browser, credential helper, or API client is `afk-sapien`. For GitHub
CLI, `gh api user --jq .login` must return `afk-sapien`. Ensure Git pushes use
that same verified account. A repository URL, a successful push, or a
`github.account` setting alone does not prove the effective identity.
Use credentials scoped to this repository or operation. Never print tokens.

If the required account is unavailable or either identity check fails, stop
the authenticated or history-writing operation and report the mismatch.
Never fall back to another saved account or bypass a project identity guard.

Before pushing, inspect every new commit's author, committer, and attribution
trailers. Before merging or publishing, inspect the final merge or squash
message and tag attribution too. Correct unintended identities before they
become public. Pass these rules explicitly to delegated agents and temporary
checkouts that might not load this file automatically.

## Working agreement: exploratory PokeBench

The owner clarified this on 2026-10-08. PokeBench is an exploratory Pokemon
benchmark and hobby research project. Optimize for useful comparisons, clear
explanations, low token waste and steady progress. Do not impose production
release machinery or publication-grade requirements unless explicitly requested.
A technical report does not by itself change this working mode.

- Fix shared behavior in its owning package. Emulator or shared controller bugs
  belong in PokeSim Core, with a focused regression test and integration into the
  affected consumer. Do not leave a benchmark adapter as the final fix simply
  to avoid updating Core. A temporary workaround must be called temporary, and
  the remaining Core work must be stated plainly.
- Check the actual current Core implementation before duplicating functionality
  or assuming a dependency update is too disruptive. Keep old runs on their
  recorded versions while using appropriate fixes for new work.
- Preserve useful historical results. Routine backend fixes do not invalidate
  all prior evaluations or justify rerunning the whole benchmark. Show existing
  and partial results with concise caveats. Distinguish materially different
  task conditions without hiding the rest of the leaderboard.
- Use proportionate verification. Reproduce the bug, test the relevant behavior,
  satisfy required repository checks and use small model trials when needed.
  Do not build elaborate approval, reservation, release or reporting systems
  for an ordinary repair unless they solve a concrete current problem.
- Catalog entries must describe concrete evaluations, not just task families.
  Name the target species, opponent or location, starting resources, agent goal
  and scored outcome. Separate proposed setup details from verified save facts.
  Do not present a generic placeholder as a completed evaluation specification.
- Match tools to the skill being tested. Menu-operation tasks require manual
  inputs. Decision-making tasks and campaigns can use reliable mechanical
  shortcuts. Record the condition and keep those results distinguishable.
- Continue authorized diagnosis, fixes and verification without repeatedly
  stopping to ask whether to perform the obvious next step. Existing spending
  limits, account identity rules and publication permissions still apply.
- Explain what was actually fixed, where it was fixed and what remains. Do not
  describe a consumer workaround as a Core fix or a small smoke test as proof
  that the entire system is flawless.
- Keep communication simple. Lead with the result and the practical implication.
  Avoid enterprise-style process language and excessive methodological caveats.

## Project conventions

- Keep the benchmark independent of the PokeSim application and never alter its saves.
  Authorized shared-library repairs should be made in PokeSim Core and integrated
  into the benchmark, rather than duplicated in a local adapter.
- Do not use em dashes or semicolons in authored output.
- Never commit ROMs, generated game labels, emulator states, API keys, or private run artifacts.
- Agent observations must use an explicit allowlist. Evaluator flags remain private.
- Only controller actions advance emulation. No automatic gameplay, recovery, or memory writes.
- Run `uv run pytest` and `uv run ruff check .` before shipping code changes.
- Document scoring, observation, prompt, or budget changes as benchmark version changes.

## Benchmark scope

- The primary visual benchmark tests the agent's own perception and gameplay.
  Do not inject object labels, object coordinates, route hints, hidden maps, or
  automatic game decisions into baseline observations.
- The offline pixel-label experiment is shelved. Do not expand it into a live
  observation helper without a new explicit user request.
- If a shared bottleneck later motivates hints, define a limited hint protocol
  before testing. Record exact hint text, trigger, timing, and count. Report
  assisted results separately and preserve the unassisted attempt.
- Compare new models on the same checkpoint, prompt, observation policy, effort,
  and budgets. A failed baseline is a result, not permission to solve gameplay
  for the model.
