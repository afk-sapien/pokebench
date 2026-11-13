# Submitting a run

Submissions are not open yet. They open with the frozen v0.61 release. Until then `submit` and `verify` refuse every run and say so. The rest of this page describes how it works once they open.

Anyone with the required Pokemon Red ROM and a model can send a result. A maintainer checks it by replay and then decides whether to publish it.

## The three commands

```sh
uv run pokebench setup --rom /path/to/red.gb
uv run pokebench run --model MODEL --suite short
uv run pokebench submit runs/short-MODEL --handle YOUR_GITHUB_NAME
```

Use `--suite long` for PokeBench Long. For a local or third party model add `--provider openai-compatible` as the README shows. Try `--suite smoke` first. A smoke bundle checks the whole path and is never a leaderboard result.

`submit` writes one file, `MODEL-SUITE.pokebench.zip`. Open a "Run submission" issue and attach it. GitHub takes attachments up to 25 MB. A full Short bundle is about 5 MB and a Long bundle about 3 MB.

## What the bundle holds

`submit` prints the list before it writes anything.

- The task list with its limits and start state hashes.
- For each run: the harness and package versions, the model id, the provider, the settings, every controller input with the game facts read after it, the score, the stop reason and the token counts.
- Your GitHub name, if you gave one, and the number of attempts you declare with `--attempts`.

It holds no ROM, save state, screenshot, prompt, model reply or note. The endpoint address and the platform string are removed. Add `--include-endpoint-host` if you want the host name of your endpoint recorded.

Before writing, `submit` scans the bundle for absolute paths, key shaped text, the values of secret environment variables, and your user and host names. If it finds any, it stops and writes nothing. If your user name is also a word in the game, add `--skip-name-check`.

## Which versions are accepted

Only a frozen release of the harness is accepted. The list is [accepted_harness.json](src/pokeagent_bench/accepted_harness.json). It is empty today, because the v0.61 harness is still changing, so nothing is accepted yet.

Each entry names a harness version, a package version and a hash of the package source. A run must match all three, so a development build that keeps the version name but changes the code is refused. `submit` refuses any other run and names the accepted release. Check out that release unchanged, run `uv sync --locked --extra dev` and run again.

Maintainers add an entry at the freeze by following the [release checklist](docs/release-checklist.md).

## How a bundle is checked

```sh
uv run pokebench verify MODEL-SUITE.pokebench.zip
```

Anyone can run this. It needs the ROM and a finished `setup`, calls no model and trusts nothing in the bundle.

- The archive is read in memory. Only known file names are accepted and nothing is extracted.
- The task list must be the complete suite as this checkout defines it, with the same start states, task definitions and limits.
- Each run is replayed from the verifier's own start state. The recorded inputs must reproduce the recorded game facts, and the score is recomputed from the replay.
- A run over its decision or token limit fails.

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
- Preparation tasks are not replay verified. They are listed as such in the report and are not part of the ranked score.
- Nothing stops someone from running many times and sending the best run. Please declare your attempts.

Published community rows carry the label "Community, replay verified, model unverified" for these reasons.

## Publishing

A maintainer runs `verify`, reads the report and publishes by hand. A verified bundle is not published automatically, and a maintainer may decline a row.

For maintainers, one command adds a report from your own `verify` run to the local site data.

```sh
uv run pokebench community-add MODEL-short.pokebench.verified.json --web /path/to/local/site
```

It accepts only verified Short reports from the accepted harness version. The next local site build shows the row with the community label, the submitter's name, the declared attempts and self reported tokens. It has no cost estimate and no replay link. The site has no community rows for Long yet. Putting the row on the live site is a separate step that needs the owner's yes.
