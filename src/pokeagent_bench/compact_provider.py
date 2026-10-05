"""Compact unassisted visual policy, with explicit references for reused pixels."""

import json

from .grounded_provider import GroundedCodexProvider
from .rules import NICKNAME_RULE


class CompactCodexProvider(GroundedCodexProvider):
    harness = "codex-cli-current-panel-v7"
    memory_protocol = "current-panel-previous-plan-v5"
    compact_feedback = True
    prompt = """Play Pokemon Red from game pixels and controller inputs. Reach the objective.
Only your requested holds, releases, and waits advance time, about 59.73 frames/s.
No external tools, walkthroughs, hidden state, route hints, or automatic help.

The image contains numbered panels at 2x nearest-neighbor scale. Identical pixels
share one panel. observation.screens lists chronological frame/panel references.
The panel marked CURRENT is the latest view and is always the last panel.
observation.current_panel identifies it explicitly. Other panels are EARLIER.
Earlier entries show the previous batch's starting screen and action results.
Read CURRENT first. Black regions do not mean the entire image is blank.
This scrolling viewport may show only part of a room or map.
Assess visible evidence and uncertainty yourself. Explore when an exit is unseen.
Reconsider unsupported interpretations. Repeated pixels do not prove collision,
and changed pixels do not prove movement. screen_history counts exact repeats.
recent_actions rows follow recent_action_columns, oldest first, up to eight inputs.
An error entry is a rejected request, not an executed controller action.

Wait if a scene is fading or text is incomplete. 60 frames is a starting wait.
Near uncertainty use one short action. Clear walking can use 48-frame holds.
16 hold + 8 release is a short walking input. Release between button presses.
Dialogue needs time between A presses. There is no automatic dialogue advancement.

Return assessment, memory, plan. In assessment.previous_result, briefly compare
the current visible evidence with previous_plan.expected_visible_change. Say
uncertain when the result is unclear, or no previous plan on the first decision.
The previous plan is your prediction, not a verified result. Keep descriptions brief.
Memory contains your fallible evidence, hypotheses, and failed attempts. Use null
when it is unchanged. Otherwise replace it, preserving useful discoveries and
correcting stale claims. Keep each memory item to one short sentence. The plan
contains the only next-action instructions and the expected visible result.
"""
    prompt += "\n" + NICKNAME_RULE + "\n"

    def serialize_context(self, payload):
        return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)

    def decision_context(self, observation, notes, recent):
        payload = super().decision_context(observation, notes, recent)
        view = observation["controller_view"]
        payload["observation"]["screens"] = [
            {"frame": item["frame"], "panel": item["panel"]} for item in view["screens"]
        ]
        payload["observation"]["current_panel"] = view["current_panel"]
        payload["previous_plan"] = getattr(self, "previous_plan", None)
        payload["recent_action_columns"] = [
            "frame", "button", "hold_frames", "release_frames", "executed_frames", "changed_pixel_fraction"
        ]
        payload["recent_actions"] = [
            {"error": item["error"]} if "error" in item else
            [item["frame"], item["action"]["button"] or "wait", item["action"]["hold_frames"],
             item["action"]["release_frames"], item["executed_frames"], item["changed_pixel_fraction"]]
            for item in recent[-8:]
        ]
        return payload

    def decision_schema(self, limits):
        schema = super().decision_schema(limits)
        assessment = schema["properties"]["assessment"]
        assessment["properties"]["previous_result"] = {"type": "string"}
        assessment["required"].append("previous_result")
        memory = schema["properties"]["memory"]
        schema["properties"]["memory"] = {"anyOf": [{"type": "null"}, memory]}
        return schema

    def remember_executed_plan(self, record, decision, after_frame):
        assessment = record.get("assessment", {})
        self.previous_plan = {
            "decision": decision,
            "after_frame": after_frame,
            "intent": assessment.get("plan_intent"),
            "expected_visible_change": assessment.get("expected_visible_change"),
        }

    def unpack_decision(self, response):
        if isinstance(response, dict) and response.get("memory", False) is None:
            replacement = {"observed": [], "hypotheses": [], "unsuccessful_attempts": []}
            decision, record = super().unpack_decision({**response, "memory": replacement})
            if "notes" in decision:
                decision["notes"] = None
            return decision, record
        return super().unpack_decision(response)
