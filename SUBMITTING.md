# Submitting a run

Run release `v0.38.0`, installed unchanged. `submit` and `verify` refuse a run from any other code.

You need [uv](https://docs.astral.sh/uv/), [git](https://git-scm.com/downloads) and the model you want to test. uv fetches the release with git, so without git the first command stops with `Git executable not found`. uv brings its own Python if your machine has none. Beyond those you bring one thing: your own Pokemon Red ROM. The README names the exact file and its hash. PokeBench ships no ROM, save or game table, and `setup` refuses any other ROM. A maintainer checks each result by replay and then decides whether to publish it.

## The three commands

Run these in an empty folder. No clone is needed.

```sh
uvx --from git+https://github.com/afk-sapien/pokebench@v0.38.0 pokebench setup --rom /path/to/red.gb
uvx --from git+https://github.com/afk-sapien/pokebench@v0.38.0 pokebench enter --suite smoke --provider random
uvx --from git+https://github.com/afk-sapien/pokebench@v0.38.0 pokebench enter --suite short --model MODEL --handle YOUR_GITHUB_NAME
```

1. `setup` checks the ROM hash and writes `data/` in the folder.
2. The smoke line is free. A random player plays the three smoke tasks and calls no model. `enter` then packs the bundle and verifies it, which checks the whole path on your machine. The random player runs smoke only, and a smoke bundle is never a leaderboard result, so do not send it.
3. The last line runs your model. Put your model id in place of `MODEL` and your GitHub user name in place of `YOUR_GITHUB_NAME`. The handle goes on the leaderboard row exactly as typed, so leave out `--handle` to stay unnamed. The command prints the plan, the worst case token use and any published usage for this release, then asks before the first model call. Run the same command again to resume after a stop. When every task has finished it packs the bundle and prints a link to a prefilled "Run submission" issue.

A model id starting with `claude` uses your Claude Code login and one starting with `gpt` uses your Codex login. Any other id needs `--provider`, or the command stops with `Suite runs need --provider codex, claude or openai-compatible`.

### A local model

A local or third party model runs through any OpenAI compatible chat endpoint. Point `POKEBENCH_BASE_URL` at it and add `--provider openai-compatible`.

```sh
export POKEBENCH_BASE_URL=http://localhost:11434/v1
uvx --from git+https://github.com/afk-sapien/pokebench@v0.38.0 pokebench enter --suite short --provider openai-compatible --model MODEL --handle YOUR_GITHUB_NAME
```

The model must accept images, and the endpoint must report token usage, or the run cannot be scored. PokeBench asks for JSON output with `response_format` set to a JSON schema. Set `POKEBENCH_API_KEY` only if your server wants a key. It goes to that server and is never written to the run or the bundle. A local model costs nothing but your own compute.

Start the server first and check that it answers, for example with `curl $POKEBENCH_BASE_URL/models`, because the plan does not contact it. Without `POKEBENCH_BASE_URL` the first two tasks fail and the run stops with `Set POKEBENCH_BASE_URL to an OpenAI compatible endpoint`. With the server down the first task fails, the summary says `navigation-forest-crossing failed and is not retried`, and its `error.json` says `Model endpoint failed: ConnectError`. A failed task is never retried and a run that has one cannot be packed. When this happens at the start no tokens were spent, so delete the run folder, for example `runs/short-MODEL`, and start again. Later in a run, delete only the folder the message names.

Use `--suite long` for PokeBench Long. For a Claude model the plan names the Claude Code build. To pin the build this release used, copy it to `data/toolchains/claude-2.1.323/bin/claude` first, as the README explains. `enter` only chains `run --suite` and `submit`, and you can run those two yourself.

`enter` writes the bundle next to the run, as `runs/short-MODEL.pokebench.zip` or `runs/long-MODEL.pokebench.zip`. In those names every character other than a letter, a digit or a dot becomes `-`, so `qwen2.5vl:7b` gives `runs/short-qwen2.5vl-7b`. Attach it to the issue and fill in its fields. GitHub takes attachments up to 25 MB. The Claude Haiku 5.5 bundles on this release are 7.8 MB for Short and 0.5 MB for Long.

To work from a clone instead, check out the tag, run `uv sync --locked --extra dev` and use `uv run pokebench` in place of the `uvx` prefix.

## What the bundle holds

`submit` prints the list before it writes anything.

- The task list with its limits and start state hashes.
- For each run: the harness and package versions, the model id, the provider, the settings, every controller input with the game facts read after it, the score, the stop reason, the token counts and any provider errors that came before a model reply, with their time and message.
- Your GitHub name, if you gave one, and the number of attempts you declare with `--attempts`.

It holds no ROM, save state, screenshot, prompt, model reply or note. The endpoint address, the platform string and the folder a rebuilt start state was copied from are removed. Add `--include-endpoint-host` if you want the host name of your endpoint recorded.

Before writing, `submit` scans the bundle for absolute paths, key shaped text, the values of secret environment variables, and your user and host names. If it finds any, it stops and writes nothing. If your user name is also a word in the game, add `--skip-name-check`.

## Which versions are accepted

Only a frozen release of the harness is accepted. The list is [accepted_harness.json](src/pokeagent_bench/accepted_harness.json), and the release to run is `v0.38.0`, the first release of `red-v0.64-harder-short`. The `v0.37.1` to `v0.37.4` entries stay listed. Their Short bundles hold `red-v0.63-short-guard`, and the `v0.38.0` checkout checks them as that set. A run paused on `v0.37.4` or older must be resumed on that same release, because resume refuses a different emulator, core or harness. The `v0.36.0` and `v0.37.0` entries stay listed so their runs keep their labels. Their Short run limits differ from `v0.37.4`, and `v0.36.0` also has a different Short suite and starts, so a bundle from either is checked on its own release's checkout.

Each entry names a harness version, a package version and a hash of the package source. A run must match all three, so a development build that keeps the version name but changes the code is refused. `submit` refuses any other run and names the accepted release. Install that release unchanged with the `uvx` lines above and run again.

Maintainers add an entry at the freeze by following the [release checklist](docs/release-checklist.md).

### Short suite versions

A Short score belongs to the suite version whose runs it holds exactly, matched by task, variant, task specification digest and start state digest. [short_suites.json](src/pokeagent_bench/short_suites.json) lists every version. The current one is `red-v0.64-harder-short`, 51 runs over 49 tasks. It adds five harder tasks to `red-v0.63-short-guard`, 46 runs over 44 tasks, and keeps those 46 runs unchanged.

Runs made on `red-v0.63-short-guard`, the set behind the Haiku, Terra and Sonnet runs, stay valid for that set and are ranked separately. `verify` on `v0.38.0` checks a bundle of exactly that set as `red-v0.63-short-guard`. Its runs still come from the verifier's own plan, cut to the 46 recorded runs, so the published bundles keep their scores.

A finished `red-v0.63-short-guard` run folder does not have to run again. The same `run --suite short` or `enter --suite short` command on `v0.38.0` keeps its 46 runs in their folders, adds the five new runs after them and runs only those. The older plan is kept as `plan-red-v0.63-short-guard.json`, and the topped-up folder holds `red-v0.64-harder-short`. `verify` matches runs by task, variant and repeat, not by folder, so a topped-up run and a fresh run of the same runs get the same score. A task paused on `v0.37.4` or older is finished on its own release first.

`submit`, `verify` and the run summary each print the suite version with its run count. Runs that match no recorded version print `Suite version: none` and are not a ranked result.

## How a bundle is checked

```sh
uvx --from git+https://github.com/afk-sapien/pokebench@v0.38.0 pokebench verify runs/short-MODEL.pokebench.zip
```

Anyone can run this, in the folder where `setup` ran. It needs the ROM, calls no model and trusts nothing in the bundle. From a clone of the tag, `uv run pokebench verify` does the same. `uv run` outside a clone stops with `Failed to spawn: pokebench`.

- The archive is read in memory. Only known file names are accepted and nothing is extracted.
- The task list must be the complete suite as this checkout defines it, with the same start states, task definitions and limits. For Short it can instead be exactly an older recorded suite version whose runs this checkout still holds unchanged. The report names the suite version from the verifier's own plan, never from the bundle.
- Runs are matched by task, variant and repeat. Each one is read from the folder the bundle plan names for it, and each folder can be named once.
- Each run must use the suite's reasoning effort: low for Short and smoke, medium for Long, as the leaderboard runs did.
- Each run is replayed from the verifier's own start state. The recorded inputs must reproduce the recorded game facts, and the score is recomputed from the replay.
- A run over its decision or token limit fails.
- A run that paused after a provider error with no model reply and was resumed is accepted. Those calls count no tokens, and the report shows how many there were.

One failed run fails the whole bundle. The result is written next to the bundle, as `runs/short-MODEL.pokebench.verified.json`.

### How long it takes

Replay is nearly all of the time, and it runs on one CPU core. These are full `verify` runs of the published Claude Haiku 5.5 bundles on a clean `v0.37.4` checkout, on one core of a desktop PC at low priority.

| Suite | Size of the run | Verify time |
| --- | --- | --- |
| Short, `red-v0.63-short-guard` | 46 runs, 51,008 inputs, 1.37 million frames | 18 min 13 s |
| Long | 1 run, 4,192 inputs, 0.11 million frames | 1 min 3 s |

Both bundles verified with no mismatch. The time grows with the number of frames played, so a model that gets further in Long, or uses its whole budget on every Short task, takes longer.

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
uv run pokebench community-add runs/short-MODEL.pokebench.verified.json --web /path/to/local/site
```

It accepts only verified Short and Long reports from the accepted harness version. The next local site build shows the row on the matching panel with the community label, the submitter's name, the declared attempts and self reported tokens. It has no cost estimate and no replay link, and it stays out of the cost comparison. Putting the row on the live site is a separate step that needs the owner's yes.
