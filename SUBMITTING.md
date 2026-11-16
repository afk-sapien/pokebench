# Submitting a run

Run release `v0.37.2`, installed unchanged. `submit` and `verify` refuse a run from any other code.

Apart from [uv](https://docs.astral.sh/uv/) and the model you want to test, you bring one thing: your own Pokemon Red ROM. The README names the exact file and its hash. PokeBench ships no ROM, save or game table, and `setup` refuses any other ROM. A maintainer checks each result by replay and then decides whether to publish it.

## The three commands

Run these in an empty folder. No clone is needed.

```sh
uvx --from git+https://github.com/afk-sapien/pokebench@v0.37.2 pokebench setup --rom /path/to/red.gb
uvx --from git+https://github.com/afk-sapien/pokebench@v0.37.2 pokebench enter --suite smoke --provider random
uvx --from git+https://github.com/afk-sapien/pokebench@v0.37.2 pokebench enter --suite short --model MODEL --handle YOUR_GITHUB_NAME
```

1. `setup` checks the ROM hash and writes `data/` in the folder.
2. The smoke line is free. A random player plays the three smoke tasks and calls no model. `enter` then packs the bundle and verifies it, which checks the whole path on your machine. The random player runs smoke only, and a smoke bundle is never a leaderboard result, so do not send it.
3. The last line runs your model. It prints the plan, the worst case token use and any published usage for this release, then asks before the first model call. Run the same command again to resume after a stop. When every task has finished it packs the bundle and prints a link to a prefilled "Run submission" issue.

Use `--suite long` for PokeBench Long. For a local or third party model add `--provider openai-compatible` as the README shows. For a Claude model the plan names the Claude Code build. To pin the build this release used, copy it to `data/toolchains/claude-2.1.323/bin/claude` first, as the README explains. `enter` only chains `run --suite` and `submit`, and you can run those two yourself.

Attach the bundle to the issue and fill in its fields. GitHub takes attachments up to 25 MB. A full Short bundle is about 5 MB and a Long bundle about 3 MB.

To work from a clone instead, check out the tag, run `uv sync --locked --extra dev` and use `uv run pokebench` in place of the `uvx` prefix.

## What the bundle holds

`submit` prints the list before it writes anything.

- The task list with its limits and start state hashes.
- For each run: the harness and package versions, the model id, the provider, the settings, every controller input with the game facts read after it, the score, the stop reason, the token counts and any provider errors that came before a model reply, with their time and message.
- Your GitHub name, if you gave one, and the number of attempts you declare with `--attempts`.

It holds no ROM, save state, screenshot, prompt, model reply or note. The endpoint address and the platform string are removed. Add `--include-endpoint-host` if you want the host name of your endpoint recorded.

Before writing, `submit` scans the bundle for absolute paths, key shaped text, the values of secret environment variables, and your user and host names. If it finds any, it stops and writes nothing. If your user name is also a word in the game, add `--skip-name-check`.

## Which versions are accepted

Only a frozen release of the harness is accepted. The list is [accepted_harness.json](src/pokeagent_bench/accepted_harness.json), and the release to run is `v0.37.2`. The `v0.37.1` entry stays listed. Its runs have the limits of `v0.37.2` and are checked on the `v0.37.2` checkout. The `v0.36.0` and `v0.37.0` entries stay listed so their runs keep their labels. Their Short run limits differ from `v0.37.2`, and `v0.36.0` also has a different Short suite and starts, so a bundle from either is checked on its own release's checkout.

Each entry names a harness version, a package version and a hash of the package source. A run must match all three, so a development build that keeps the version name but changes the code is refused. `submit` refuses any other run and names the accepted release. Install that release unchanged with the `uvx` lines above and run again.

Maintainers add an entry at the freeze by following the [release checklist](docs/release-checklist.md).

## How a bundle is checked

```sh
uv run pokebench verify MODEL-SUITE.pokebench.zip
```

Anyone can run this. It needs the ROM and a finished `setup`, calls no model and trusts nothing in the bundle.

- The archive is read in memory. Only known file names are accepted and nothing is extracted.
- The task list must be the complete suite as this checkout defines it, with the same start states, task definitions and limits.
- Each run must use the suite's reasoning effort: low for Short and smoke, medium for Long, as the leaderboard runs did.
- Each run is replayed from the verifier's own start state. The recorded inputs must reproduce the recorded game facts, and the score is recomputed from the replay.
- A run over its decision or token limit fails.
- A run that paused after a provider error with no model reply and was resumed is accepted. Those calls count no tokens, and the report shows how many there were.

One failed run fails the whole bundle. The result is written to `MODEL-SUITE.pokebench.verified.json`.

### How long it takes

Replay is nearly all of the time, and it runs on one CPU core. These were measured on a desktop PC at low priority, by replaying existing private runs the same way `verify` does, from only the manifest, the input log, the result and the start state.

| Suite | Size of the run | Replay time |
| --- | --- | --- |
| Short | 40 gameplay tasks, 31,717 inputs, 0.85 million frames | 16 min 37 s |
| Long | 1 run, 22,645 inputs, 0.6 million frames | 6 min 12 s |

Every run replayed without a mismatch. The time grows with the number of frames played, so a model that uses its whole budget on every task takes longer. The two League battles alone took 4 min 39 s of the Short total. These runs were recorded on the earlier v0.59 harness, so they timed the replay step and not a full `verify` of an accepted bundle. The other checks in `verify` read a few megabytes and take seconds.

## What the check cannot show

- It shows that these inputs, played from the benchmark start, earn this score. It does not show what chose the inputs. A person, a script or a different model could have produced them.
- Model identity, token counts, the number of attempts and the absence of outside help are self reported.
- Nothing stops someone from running many times and sending the best run. Please declare your attempts.

Published community rows carry the label "Community, replay verified, model unverified" for these reasons.

## Publishing

A maintainer runs `verify`, reads the report and publishes by hand. A verified bundle is not published automatically, and a maintainer may decline a row.

For maintainers, `intake` takes a submission issue number and does the reading and checking. It reads the issue with `gh`, downloads the one attached `.pokebench.zip` into a new empty folder, refuses a file over 25 MB or one that is not a zip, runs `verify` and writes a draft reply to `reply.md`. It posts nothing, adds no row and publishes nothing. It prints the two commands to run by hand once you agree with the draft.

```sh
uv run pokebench intake 12
```

One command adds a report from your own `verify` run to the local site data.

```sh
uv run pokebench community-add MODEL-short.pokebench.verified.json --web /path/to/local/site
```

It accepts only verified Short and Long reports from the accepted harness version. The next local site build shows the row on the matching panel with the community label, the submitter's name, the declared attempts and self reported tokens. It has no cost estimate and no replay link, and it stays out of the cost comparison. Putting the row on the live site is a separate step that needs the owner's yes.
