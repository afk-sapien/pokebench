# Astra outside-start result

Astra reached Oak's laboratory but did not receive a starter within the
allowance. This is the first lab visit among these outside-start attempts.
It is not task completion or evidence of a stable model ranking.

## Gameplay

The gpt-6-astra gameplay attempt used medium effort, the same outside checkpoint,
visual input, controller semantics and prompt as the previous models. It entered
the laboratory at decision 11 and frame 1,908. It finished at decision 21 after
40 controller actions and 4,452 game frames, stopping on token reservation.
Wall duration was approximately 70 seconds. The party remained empty.

Its final eight decisions each requested two A presses. The final screen still
showed Oak dialogue with the starter balls nearby. Astra did not switch to
movement toward a ball during that stretch. This is an observed repeated-input
pattern, not proof of why the model chose it. The run recorded no explanatory
notes, so no hidden rationale is inferred.

All 40 actions passed deterministic replay. The review exporter verified game
pixels against model-input image records, and the initial image was also
verified byte-for-byte in the actual client conversation history. No hints,
reference actions, object labels or earlier model findings were supplied.

## Compatibility and spending

The first attempt used CLI 0.147.0 and failed with HTTP 400 because Astra required
a newer client. It produced no completed model answer or controller action.
Its missing usage remains unknown, rather than being treated as zero.

Installed the official CLI 0.157.0 into an isolated benchmark toolchain, leaving
the original executable unchanged. A non-generating session-start check passed
before the technical retry. The retry used a 242,000-token limit, reserving
8,000 against the original 250,000 scheduling allowance for the failed request.
This reservation is not measured consumption. Both attempts remain preserved.
The client upgrade follows the
[official release guidance](https://learn.chatgpt.com/docs/changelog).

The gameplay attempt reported 230,169 tokens: 229,020 input and 1,149 output.
Input contains 202,368 cached tokens and 26,652 uncached tokens. Its usage is
fully accounted. The experiment-wide total is not fully accounted because the
first rejected request has unknown usage. No summary or compaction occurred.
No additional attempt or allowance increase was made after gameplay stopped.

Manifest checks confirmed parity with the earlier outside trials apart from
the model ID, CLI version and reduced token cap. Those differences qualify the
comparison. Astra demonstrated farther navigation in this attempt, while
acquisition dialogue and starter selection remained unfinished. The runtime
source and original results remain unchanged.

[Protocol and compatibility amendment](2026-09-28-astra-outside-protocol.md).
[Four-model outside-start review](http://127.0.0.1:8942/starter-outside-v014-astra-review.html).
