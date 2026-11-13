# Submitting a run

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

Only the harness version the leaderboard uses is accepted. It is listed in [accepted_harness.json](src/pokeagent_bench/accepted_harness.json). `submit` refuses a run from any other version and names the accepted one. Check out that release, run `uv sync --locked --extra dev` and run again.

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

## What the check cannot show

- It shows that these inputs, played from the benchmark start, earn this score. It does not show what chose the inputs. A person, a script or a different model could have produced them.
- Model identity, token counts, the number of attempts and the absence of outside help are self reported.
- Preparation tasks are not replay verified. They are listed as such in the report and are not part of the ranked score.
- Nothing stops someone from running many times and sending the best run. Please declare your attempts.

Published community rows carry the label "Community, replay verified, model unverified" for these reasons.

## Publishing

A maintainer runs `verify`, reads the report and publishes by hand. A verified bundle is not published automatically, and a maintainer may decline a row.
