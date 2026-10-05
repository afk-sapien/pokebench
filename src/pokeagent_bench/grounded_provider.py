"""Assess the visible scene before emitting a single controller plan."""

from .codex_provider import CodexProvider
from .rules import NICKNAME_RULE


class GroundedCodexProvider(CodexProvider):
    harness = "codex-cli-grounded-v4"
    memory_protocol = "screen-history-and-evidence-notebook-v2"
    prompt = """Play Pokemon Red from the actual game screen using controller inputs.
Reach the stated objective. Only your requested holds, releases, and waits advance
game time, about 59.73 frames per second. There is no automatic navigation or help.

First assess the CURRENT screen, the last panel in the image strip. Earlier panels
show the results of your last inputs. This is a scrolling camera viewport, not
necessarily the whole room or map. An exit may be off-screen. Do not invent stairs
or a doorway just because you need one. Describe visible objects and uncertainty
before planning. The game image has no route annotations or hidden map data.

Then produce one plan containing its actual controller actions and expected
visible result. Explore unseen parts of the scene when no exit is identifiable.
Reconsider an interpretation after repeated attempts give no supporting visual
evidence. Use screen_history to remember exact repeated views and inputs that
left pixels unchanged, even if your notebook forgot them. An unchanged image is
not proof of collision, and an animation is not proof of movement.

If the screen is fading or partially redrawn, choose wait before interpreting a
new room. A wait of 60 frames is a useful starting point. Near uncertainty, use one
short action then inspect. For clear walking, longer holds such as 48 frames can
explore more ground. A 16-frame hold plus 8-frame release is a short walking input.
Release the button between presses. Dialogue can require time between A presses.

Keep concise evidence and hypotheses in memory. They are your claims, not verified
facts. Correct stale claims when the current image disagrees. The plan is the only
next-action specification. Do not write a separate future action in memory.
No external tools, game-state inspection, walkthroughs, or human help are allowed.
Return the schema's assessment, memory, and plan in that order.
"""
    prompt += "\n" + NICKNAME_RULE + "\n"

    def decision_schema(self, limits):
        base = super().decision_schema(limits)
        text = {"type": "string"}
        memory = {
            "type": "object",
            "additionalProperties": False,
            "properties": {
                key: {"type": "array", "items": text, "maxItems": 6}
                for key in ("observed", "hypotheses", "unsuccessful_attempts")
            },
            "required": ["observed", "hypotheses", "unsuccessful_attempts"],
        }
        assessment = {
            "type": "object",
            "additionalProperties": False,
            "properties": {
                "scene": {
                    "type": "string",
                    "enum": ["room", "outdoors", "battle", "dialogue", "menu", "transition", "uncertain"],
                },
                "player_position": text,
                "visible_objects": {"type": "array", "items": text, "maxItems": 6},
                "visible_exit": {"type": ["string", "null"]},
            },
            "required": ["scene", "player_position", "visible_objects", "visible_exit"],
        }
        plan = {
            "type": "object",
            "additionalProperties": False,
            "properties": {"intent": text, "expected_visible_change": text, "actions": base["properties"]["actions"]},
            "required": ["intent", "expected_visible_change", "actions"],
        }
        return {
            "type": "object",
            "additionalProperties": False,
            "properties": {"assessment": assessment, "memory": memory, "plan": plan},
            "required": ["assessment", "memory", "plan"],
        }

    def decision_context(self, observation, notes, recent):
        payload = super().decision_context(observation, notes, recent)
        view = observation.get("controller_view", {})
        payload["observation"]["screen_history"] = view.get("screen_history", {})
        if payload["notes"]:
            payload["notes"].pop("next_experiment", None)
        return payload

    def unpack_decision(self, response):
        try:
            if set(response) != {"assessment", "memory", "plan"}:
                raise ValueError("Unexpected grounded fields")
            plan = response["plan"]
            memory = response["memory"]
            if set(memory) != {"observed", "hypotheses", "unsuccessful_attempts"}:
                raise ValueError("Unexpected memory fields")
            if set(plan) != {"intent", "expected_visible_change", "actions"}:
                raise ValueError("Unexpected plan fields")
            notes = {**memory, "next_experiment": plan["intent"]}
            self.normalize_notes(notes)
            return {"actions": plan["actions"], "notes": notes}, {
                "scene": response["assessment"],
                "plan_intent": plan["intent"],
                "expected_visible_change": plan["expected_visible_change"],
            }
        except (TypeError, ValueError, KeyError):
            return {"invalid_grounded_decision": response}, {
                "validation_error": "Malformed assessment, memory, or plan"
            }


class MotionCodexProvider(GroundedCodexProvider):
    harness = "codex-cli-grounded-motion-v5"
    memory_protocol = "screen-history-motion-and-evidence-v3"
    motion_feedback = True
    stagnation_guard = True
    prompt = (
        GroundedCodexProvider.prompt
        + """
The camera often follows the player. The player can stay near the screen center
while the background scrolls. Do not decide movement failed from the player's
screen position alone. Controller feedback includes a pixel-derived screen
translation estimate. Positive dx means the scene shifted right, positive dy
means it shifted down. This often opposes player travel, but is not a player
coordinate or proof of collision. Null means alignment was ambiguous.
When repeated directional inputs produce little scene translation and no useful
change, reconsider the route instead of only varying hold duration. Explore a
previously untested direction. Use wait to inspect a transition before moving.
A repeated-view decision budget ends runs that keep revisiting only known images.
"""
    )
