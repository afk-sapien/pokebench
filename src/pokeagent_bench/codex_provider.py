"""Subscription-backed decisions through the installed, authenticated Codex CLI."""
import base64
import json
import os
from pathlib import Path
import subprocess
import tempfile

from .providers import SCHEMA, ProviderError
from .rules import NICKNAME_RULE
from .visual_feedback import NOTE_SCHEMA, normalize_notes, public_context


class CodexProvider:
    provider = "codex"
    harness = "codex-cli-visual-feedback-v3"
    max_output_tokens = None
    token_budget_mode = "reported-between-decisions-with-reserve"
    visual_feedback = True
    memory_protocol = "evidence-hypotheses-failures-experiment-v1"
    normalize_notes = staticmethod(normalize_notes)
    prompt = """You are playing Pokemon Red using the actual game screen and controller.
Reach the stated objective. The game pauses while you think. Only your requested
button presses or waits advance time, about 59.73 frames per game second.
The image shows BEFORE followed by AFTER screens for your previous action batch,
in chronological order. The last screen is current. Pixels are enlarged 3x with
no game annotations. Frame numbers and button timings are controller metadata.
Read the current screen before choosing actions. Earlier notes may be wrong.
A fading, blank, or partially redrawn screen may be a transition. If uncertain,
request wait with enough frames to see what happens, such as 30 frames. There
is no automatic waiting, navigation, dialogue advancement, or recovery.
Return actions and notes matching the JSON schema. A hold keeps one button down,
then release_frames advances time with it released. Use short batches near
stairs, doors, dialogue, and menus. Check results before repeating a failed plan.
A 16-frame hold plus 8-frame release is a starting point for walking. Separate
A presses to advance dialogue. One-frame taps may fail to register.
Exact image equality does not prove a wall or a soft lock. Changed pixels do not
prove movement. Interpret the before/after screens, including animations.
Your only memory is your notebook and the last eight controller results. Record
observed evidence separately from hypotheses. Preserve useful discoveries and
unsuccessful attempts. Revise guesses contradicted by the current screen. Set
next_experiment to a concrete test of an uncertain plan. Never record intended
movement as confirmed movement. Return null notes to preserve your notebook.
No external tools, walkthroughs, code execution, or human help are available.
"""
    prompt += "\n" + NICKNAME_RULE + "\n"

    def __init__(self, model, *, executable="codex", reasoning_effort="low"):
        if not isinstance(model, str) or not model.strip():
            raise ValueError("An explicit Codex model ID is required")
        if reasoning_effort not in ("low", "medium", "high", "xhigh"):
            raise ValueError("Unsupported reasoning effort")
        self.next_decision_token_estimate = None
        self.model = model
        self.executable = executable
        self.reasoning_effort = reasoning_effort
        self._initialize_cli()

    def _initialize_cli(self):
        executable = self.executable
        self.env = {key: value for key, value in os.environ.items()
                    if key not in {"OPENAI_API_KEY", "CODEX_API_KEY", "OPENAI_BASE_URL", "CODEX_ACCESS_TOKEN",
                                   "OPENAI_FEDERATION_RULE_ID", "OPENAI_IDENTITY_TOKEN_FILE",
                                   "CODEX_APP_TOOLS_PIPE_PATH", "CODEX_THREAD_ID", "CODEX_SESSION_ID",
                                   "CODEX_INTERNAL_ORIGINATOR_OVERRIDE"}}
        try:
            status = subprocess.run([executable, "-c", 'cli_auth_credentials_store="auto"', "login", "status"], capture_output=True, text=True,
                                    timeout=15, env=self.env)
            if status.returncode or "Logged in using ChatGPT" not in status.stdout + status.stderr:
                raise ValueError("Sign into Codex with ChatGPT before a subscription run")
            result = subprocess.run([executable, "--version"], capture_output=True, text=True,
                                    timeout=15, env=self.env, check=True)
            self.cli_version = result.stdout.strip()
        except (OSError, subprocess.SubprocessError) as error:
            raise ValueError(f"Codex CLI is unavailable: {type(error).__name__}") from None

    def decision_schema(self, limits):
        return {"type": "object", "additionalProperties": False,
                "properties": {"actions": {"type": "array", "minItems": 1,
                    "maxItems": limits.max_actions_per_decision,
                    "items": {"type": "object", "additionalProperties": False,
                              "properties": {key: value for key, value in SCHEMA["properties"].items() if key != "notes"},
                              "required": ["button", "hold_frames", "release_frames"]}},
                    "notes": NOTE_SCHEMA},
                "required": ["actions", "notes"]}

    def decision_context(self, observation, notes, recent):
        public = public_context(observation)
        view = observation.get("controller_view")
        if view:
            public["screens"] = [{"frame": item["frame"]} for item in view["screens"]]
        return {"observation": public, "notes": json.loads(notes) if notes else None, "recent_actions": recent}

    def unpack_decision(self, decision):
        return decision, {}

    def serialize_context(self, payload):
        return json.dumps(payload, sort_keys=True)

    def decide(self, observation, notes, recent, limits, timeout):
        payload = self.decision_context(observation, notes, recent)
        public = payload["observation"]
        view = observation.get("controller_view")
        context = self.serialize_context(payload)
        with tempfile.TemporaryDirectory(prefix="pokeagent-codex-") as temporary:
            directory = Path(temporary)
            image = directory / "screen.png"
            image.write_bytes(base64.b64decode((view or observation["screenshot"])["base64"], validate=True))
            schema = directory / "action.schema.json"
            schema.write_text(json.dumps(self.decision_schema(limits)))
            instructions = directory / "benchmark-instructions.md"
            instructions.write_text(self.prompt)
            command = [self.executable, "exec", "--ignore-user-config", "--ephemeral", "--json",
                       "--skip-git-repo-check", "--sandbox", "read-only", "--disable", "shell_tool",
                       "--disable", "multi_agent", "--disable", "skill_search",
                       "--disable", "plugins", "--disable", "apps", "--disable", "personality",
                       "-c", "model_instructions_file=" + json.dumps(str(instructions)),
                       "-c", 'cli_auth_credentials_store="auto"', "-c", 'web_search="disabled"', "-c", 'approval_policy="never"',
                       "-c", "project_doc_max_bytes=0", "-c", f'model_reasoning_effort="{self.reasoning_effort}"',
                       "--model", self.model, "--image", str(image), "--output-schema", str(schema), "-"]
            try:
                process = subprocess.run(command, input=context, capture_output=True, text=True,
                                         cwd=directory, env=self.env, timeout=max(0.001, min(timeout, 180)))
            except (OSError, subprocess.SubprocessError) as error:
                raise ProviderError(f"Codex process failed: {type(error).__name__}. Usage may be unreported") from None
        if process.returncode:
            raise ProviderError("Codex failed. Check model access and subscription limits. Usage may be unreported")
        try:
            events = [json.loads(line) for line in process.stdout.splitlines() if line.strip()]
            completed = [event for event in events if event.get("type") == "turn.completed"]
            items = [event["item"] for event in events if event.get("type") in ("item.started", "item.completed")]
            if any(item.get("type") not in ("agent_message", "reasoning") for item in items):
                raise ProviderError("Codex attempted an outside tool. This trial cannot be evaluated")
            if len(completed) != 1 or any(event.get("type") in ("error", "turn.failed") for event in events):
                raise ProviderError("Codex did not complete exactly one decision. Usage may be unreported")
            messages = [event["item"]["text"] for event in events if event.get("type") == "item.completed"
                        and event["item"].get("type") == "agent_message"]
            decision, assessment = self.unpack_decision(json.loads(messages[-1]))
            usage = completed[0]["usage"]
            if isinstance(usage, dict) and all(type(usage.get(key)) is int and usage[key] >= 0
                                               for key in ("input_tokens", "output_tokens")):
                self.next_decision_token_estimate = usage["input_tokens"] + usage["output_tokens"] + 512
            # Do not persist reasoning text, process stderr, authentication, or machine paths.
            record = {"cli_version": self.cli_version, "reasoning_effort": self.reasoning_effort,
                      "context": public, "notes": notes, "recent_actions": recent,
                      "assessment": assessment,
                      "presentation": {key: value for key, value in view.items() if key != "base64"} if view else None}
            if getattr(self, "compact_feedback", False):
                record["model_context"] = payload
                record["context_bytes"] = len(context.encode())
            return decision, usage, record
        except (ValueError, KeyError, IndexError, TypeError) as error:
            raise ProviderError(f"Malformed Codex output: {type(error).__name__}. Usage may be unreported") from None

    def close(self):
        pass
