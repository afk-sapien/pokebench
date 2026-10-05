"""Continuous subscription play with explicit compaction and private evaluator isolation."""
from collections import deque
import json
import os
import re
from pathlib import Path
import tempfile
import time
import tomllib

from .app_server import AppServer
from .codex_provider import CodexProvider
from .core import digest
from .compact_provider import CompactCodexProvider
from .providers import ProviderError
from .rules import NICKNAME_RULE
from .visual_feedback import public_context


class ContinuousCodexProvider(CodexProvider):
    allowed_track = "visual"
    harness = "codex-app-server-continuous-v1"
    memory_protocol = "continuous-context-metered-summary-v1"
    compact_feedback = False
    current_only = True
    maintenance_decisions = True
    prompt = """Play Pokemon Red using game screenshots and controller inputs. Reach the objective.
The latest image is CURRENT. Earlier images, if attached, are labeled by frame.
The scrolling viewport may show only part of a room. No labels or routes are provided.
Only requested holds, releases and waits advance the game, about 59.73 frames/s.
A hold presses one button, then release_frames advances with it released.
The sum of hold_frames and release_frames must not exceed max_action_frames.
Walking: try hold 16, release 8. Clear walking can use hold 48, release 8.
A or B tap: try hold 8, release 24. Short inputs can occur during animation.
For fading screens or incomplete dialogue, request wait 60, release 0 and inspect.
These are timing suggestions, not automatic actions. Inspect uncertain results.
Animation or facing changes are not proof of movement. Reconsider mistaken beliefs.
You have a continuous conversation, periodically compacted to fit context.
Return actions and optional brief notes. Notes are your fallible claims, not game facts.
Use null notes to retain your notebook. No mandatory scene description is needed.
look_back requests one of the last eight decision screenshots on the NEXT turn:
1 is the screenshot supplied on this turn, 2 the preceding turn, and so on.
Use null unless needed. Empty actions require a look_back request.
Only the controller is available. No external tools, hidden state, walkthroughs,
object labels, automatic navigation or human help are available.
""" + "\n" + NICKNAME_RULE + "\n"
    normalize_notes = staticmethod(lambda notes: notes)

    def __init__(self, model, *, reasoning_effort="low", executable="codex",
                 compact_at=24000, presentation="current", response_contract="simple", continuity=True):
        super().__init__(model, executable=executable, reasoning_effort=reasoning_effort)
        if type(compact_at) is not int or compact_at < 1024:
            raise ValueError("compact_at must be at least 1024 tokens")
        if response_contract == "assessment" and presentation != "strip":
            raise ValueError("Assessment control requires the strip presentation")
        if presentation not in ("current", "strip") or response_contract not in ("simple", "assessment"):
            raise ValueError("Unknown continuous provider policy")
        self.compact_at = compact_at
        self.presentation_policy = presentation
        self.response_contract = response_contract
        self.continuity = continuity
        self.current_only = presentation == "current"
        self.compact_feedback = presentation == "strip"
        self.legacy = object.__new__(CompactCodexProvider)
        if response_contract == "assessment":
            self.normalize_notes = CompactCodexProvider.normalize_notes
            self.prompt = CompactCodexProvider.prompt
            self.prompt += "\nYour conversation is retained until explicit context compaction.\n" if continuity else "\nEach decision starts a fresh conversation.\n"
        elif presentation == "strip":
            self.prompt = self.prompt.replace("The latest image is CURRENT.",
                "The image strip labels the last panel CURRENT. Other panels are earlier.")
        if not continuity:
            self.prompt = self.prompt.replace("You have a continuous conversation, periodically compacted to fit context.",
                                             "Each decision starts fresh. Your notebook and recent controller results persist.")
        self.server = None
        self.temporary = None
        self.thread_id = None
        self.last_turn_id = None
        self.total_usage = {"inputTokens": 0, "outputTokens": 0, "cachedInputTokens": 0}
        self.context_tokens = 0
        self.history = deque(maxlen=8)
        self.look_back = None
        self.next_decision_token_estimate = 8000
        self.compactions = 0
        self.pending_summary = None
        self.config_identity = {"compact_at": compact_at, "presentation": presentation,
                                "response_contract": response_contract, "continuity": continuity,
                                "controller_timing": "explicit-hold-release-v1",
                                "compaction_protocol": "metered-agent-summary-v1",
                                "allowed_writing_policy_sha256": "70a4ca34d487912d4cf511d1033abbce1bce95ab94c305a28912e406c6e4aae3"}

    def decision_schema(self, limits):
        if self.response_contract == "assessment":
            return self.legacy.decision_schema(limits)
        schema = super().decision_schema(limits)
        schema["properties"]["actions"]["minItems"] = 0
        schema["properties"]["notes"] = {"type": ["string", "null"], "maxLength": min(2048, limits.max_note_bytes)}
        schema["properties"]["look_back"] = {"type": ["integer", "null"], "minimum": 1, "maximum": 8}
        schema["required"].append("look_back")
        return schema

    def _start(self, deadline):
        self.temporary = tempfile.TemporaryDirectory(prefix="pokeagent-app-server-")
        directory = self.temporary.name
        instructions = Path(directory) / "instructions.md"
        instructions.write_text(self.prompt)
        disabled = ("shell_tool", "multi_agent", "multi_agent_v2", "skill_search", "plugins", "apps",
                    "personality", "hooks", "memories", "browser_use", "browser_use_external",
                    "computer_use", "image_generation", "in_app_browser", "code_mode", "code_mode_host",
                    "goals", "artifact", "remote_plugin")
        command = [self.executable, "app-server", "--listen", "stdio://"]
        for feature in disabled:
            command.extend(["--disable", feature])
        config = {"web_search": "disabled", "approval_policy": "never", "project_doc_max_bytes": 0,
                  "cli_auth_credentials_store": "auto", "model_provider": "openai",
                  "model_auto_compact_token_limit": 1000000000, "developer_instructions": "",
                  "model_instructions_file": str(instructions)}
        # Disable each configured MCP server without copying credentials or changing user config.
        config_file = Path(os.environ.get("CODEX_HOME", Path.home() / ".codex")) / "config.toml"
        user = tomllib.loads(config_file.read_text()) if config_file.exists() else {}
        for name in user.get("mcp_servers", {}):
            if not re.fullmatch(r"[A-Za-z0-9_-]+", name):
                raise ProviderError("Cannot isolate an unsupported MCP server name")
            config[f"mcp_servers.{name}.enabled"] = False
        for key, value in config.items():
            if value is not None:
                command.extend(["-c", key + "=" + json.dumps(value)])
        self.server = AppServer(command, cwd=directory, env=self.env)
        self.server.request("initialize", {"clientInfo": {"name": "pokeagent_bench", "version": "0.11.0"},
                                          "capabilities": {"experimentalApi": True}}, deadline)
        self.server.send({"method": "initialized", "params": {}})
        effective = self.server.request("config/read", {"includeLayers": False, "cwd": directory}, deadline)["config"]
        if any(server.get("enabled", True) for server in effective.get("mcp_servers", {}).values()):
            raise ProviderError("Outside MCP server remains enabled")
        params = {"model": self.model, "modelProvider": "openai", "cwd": directory,
                  "approvalPolicy": "never", "sandbox": "read-only", "baseInstructions": self.prompt,
                  "developerInstructions": "", "config": {"model_reasoning_effort": self.reasoning_effort},
                  "personality": "none"}
        if self.thread_id:
            params["threadId"] = self.thread_id
            result = self.server.request("thread/resume", params, deadline)
            turns = result["thread"].get("turns", [])
            if not turns or turns[-1]["id"] != self.last_turn_id or turns[-1]["status"] != "completed":
                raise ProviderError("Resumed model history does not match the checkpoint")
        else:
            params.update(ephemeral=False, environments=[], dynamicTools=[], selectedCapabilityRoots=[],
                          allowProviderModelFallback=False)
            result = self.server.request("thread/start", params, deadline)
            self.thread_id = result["thread"]["id"]
        sources = result.get("instructionSources", [])
        for source in sources:
            # The installed client reports the global writing policy even with doc bytes set to zero.
            # Only this audited, gameplay-neutral policy is permitted.
            if digest(Path(source).read_bytes()) != "70a4ca34d487912d4cf511d1033abbce1bce95ab94c305a28912e406c6e4aae3":
                raise ProviderError("Unexpected outside instruction source")
        if result.get("model") != self.model or result.get("reasoningEffort") != self.reasoning_effort:
            raise ProviderError("Unexpected model or reasoning effort")

    def _complete(self, method, params, deadline):
        before = dict(self.total_usage)
        response = self.server.request(method, params, deadline)
        turn_id = response.get("turn", {}).get("id")
        message = None
        usage = None
        compacted = False
        while True:
            event = self.server.event(deadline)
            kind, data = event.get("method"), event.get("params", {})
            if data.get("threadId") not in (None, self.thread_id):
                continue
            if kind == "turn/started" and turn_id is None:
                turn_id = data["turn"]["id"]
            if kind == "thread/tokenUsage/updated" and data.get("turnId") == turn_id:
                usage = data["tokenUsage"]
            if kind in ("item/started", "item/completed") and data.get("turnId") == turn_id:
                item = data["item"]
                if item["type"] not in ("userMessage", "agentMessage", "reasoning", "contextCompaction"):
                    raise ProviderError("Outside tool attempted. Trial is invalid")
                if kind == "item/completed" and item["type"] == "agentMessage":
                    message = item["text"]
                if kind == "item/completed" and item["type"] == "contextCompaction":
                    compacted = True
            if kind == "turn/completed" and data["turn"]["id"] == turn_id:
                if data["turn"]["status"] != "completed":
                    raise ProviderError("App Server turn failed. Usage may be unreported")
                break
        if usage is None:
            raise ProviderError("Missing turn usage, including compaction. Trial stopped")
        total = usage["total"]
        for key in before:
            if type(total.get(key)) is not int or total[key] < before[key]:
                raise ProviderError("Invalid cumulative usage. Trial stopped")
        delta = {"input_tokens": total["inputTokens"] - before["inputTokens"],
                 "output_tokens": total["outputTokens"] - before["outputTokens"],
                 "cached_input_tokens": total["cachedInputTokens"] - before["cachedInputTokens"]}
        if delta["input_tokens"] + delta["output_tokens"] <= 0:
            raise ProviderError("Unaccounted generation or compaction. Trial stopped")
        if method == "thread/compact/start" and not compacted:
            raise ProviderError("Missing compaction completion")
        if method != "thread/compact/start" and compacted:
            raise ProviderError("Unexpected automatic compaction. Usage cannot be isolated")
        self.total_usage = {key: total[key] for key in before}
        self.last_turn_id = turn_id
        self.context_tokens = 0 if compacted else usage["last"]["inputTokens"] + usage["last"]["outputTokens"]
        self.next_decision_token_estimate = max(8000, self.context_tokens + 4096)
        return message, delta

    def decide(self, observation, notes, recent, limits, timeout):
        if observation["status"]["track"] != self.allowed_track:
            raise ProviderError(f"Provider requires the {self.allowed_track} track")
        deadline = time.monotonic() + min(timeout, 180)
        try:
            if self.server is None:
                self._start(deadline)
            view = observation["controller_view"]
            if self.response_contract == "assessment":
                self.legacy.previous_plan = getattr(self, "previous_plan", None)
                payload = self.legacy.decision_context(observation, notes, recent)
            else:
                payload = {"observation": public_context(observation), "notes": notes or None,
                           "controller_results": recent[-2:], "frame": observation["frame"]}
            if self.pending_summary is not None:
                payload["agent_history_summary"] = self.pending_summary
            record = {"cli_version": self.cli_version, "reasoning_effort": self.reasoning_effort,
                      "context": payload["observation"], "model_context": payload,
                      "presentation": {k: v for k, v in view.items() if k != "base64"},
                      "assessment": {}, "session_id": self.thread_id}
            readable_text = None
            if getattr(self, "observation_format", "json") == "text":
                from .readable_context import render
                readable_text = render(payload)
                record["model_input_text"] = readable_text
            if self.continuity and self.context_tokens >= self.compact_at:
                summary_schema = {"type": "object", "additionalProperties": False,
                    "properties": {"summary": {"type": "string", "maxLength": 8000}}, "required": ["summary"]}
                message, usage = self._complete("turn/start", {"threadId": self.thread_id,
                    "effort": self.reasoning_effort, "outputSchema": summary_schema,
                    "input": [{"type": "text", "text": readable_text if readable_text is not None else json.dumps(payload)},
                              {"type": "image", "url": "data:image/png;base64," + view["base64"]},
                              {"type": "text", "text":
                        "Context maintenance only. Write a concise handoff from your own gameplay history. "
                        "Include current objective, observed progress, uncertainties, failed attempts, "
                        "and your next intended experiment. Correct claims contradicted by the screenshots. "
                        "Do not invent events, add outside game knowledge, or issue controller actions. "
                        "This summary and the current screenshot will be supplied to your next session."}]}, deadline)
                summary = json.loads(message)
                if set(summary) != {"summary"} or not isinstance(summary["summary"], str) or len(summary["summary"]) > 8000:
                    raise ValueError("Invalid context summary")
                self.pending_summary = summary["summary"]
                self.compactions += 1
                record.update(maintenance="compaction", compaction_protocol="metered-agent-summary-v1",
                              agent_summary=self.pending_summary, completed_turn_id=self.last_turn_id)
                self.close()
                self.thread_id = self.last_turn_id = None
                self.total_usage = {key: 0 for key in self.total_usage}
                self.context_tokens = 0
                self.next_decision_token_estimate = max(8000, len(self.pending_summary.encode()) + 6000)
                return {"actions": [], "notes": None}, usage, record
            inputs = [{"type": "text", "text": readable_text if readable_text is not None else json.dumps(payload, separators=(",", ":"))}]
            if self.look_back is not None:
                if self.look_back <= len(self.history):
                    old = self.history[-self.look_back]
                    inputs.extend([{"type": "text", "text": f"EARLIER requested screenshot, frame {old['frame']}"},
                                   {"type": "image", "url": "data:image/png;base64," + old["image"]}])
                    record["requested_history_frame"] = old["frame"]
                    record["requested_history_presentation"] = old["presentation"]
                else:
                    inputs.append({"type": "text", "text": "Requested screenshot is outside retained history."})
                self.look_back = None
            inputs.extend([{"type": "text", "text": f"CURRENT frame {observation['frame']}"},
                           {"type": "image", "url": "data:image/png;base64," + view["base64"]}])
            message, usage = self._complete("turn/start", {"threadId": self.thread_id, "input": inputs,
                "effort": self.reasoning_effort, "outputSchema": self.decision_schema(limits)}, deadline)
            self.pending_summary = None
            response = json.loads(message)
            if self.response_contract == "assessment":
                decision, record["assessment"] = self.legacy.unpack_decision(response)
                if response.get("memory") is None:
                    decision["notes"] = None
            else:
                self.look_back = response.pop("look_back")
                if self.look_back is not None and (type(self.look_back) is not int or not 1 <= self.look_back <= 8):
                    raise ValueError("Invalid look_back")
                decision = response
                if not decision["actions"]:
                    if self.look_back is None:
                        raise ValueError("Empty action without an observation request")
                    record["maintenance"] = "look_back"
            self.history.append({"frame": observation["frame"], "image": view["base64"],
                                 "presentation": record["presentation"]})
            if not self.continuity:
                self.close()
                self.thread_id = self.last_turn_id = None
                self.total_usage = {key: 0 for key in self.total_usage}
                self.context_tokens = 0
            return decision, usage, record
        except (KeyError, ValueError, TypeError, OSError) as error:
            raise ProviderError(f"Invalid App Server response: {type(error).__name__}. Usage may be unreported") from None

    remember_executed_plan = CompactCodexProvider.remember_executed_plan

    def close(self):
        if self.server is not None:
            self.server.close()
            self.server = None
        if self.temporary is not None:
            self.temporary.cleanup()
            self.temporary = None
