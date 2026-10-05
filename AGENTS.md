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

## Project conventions

- Keep this project independent of PokeSim. Never modify a sibling checkout or its saves.
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
