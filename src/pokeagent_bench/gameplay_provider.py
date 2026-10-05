"""Subscription-backed decision benchmark with explicit information assistance."""
from .continuous_provider import ContinuousCodexProvider
from .rules import NICKNAME_RULE


class GameplayCodexProvider(ContinuousCodexProvider):
    allowed_track = "gameplay"
    harness = "codex-app-server-gameplay-menus-v036"
    default_compact_at = 32000
    gameplay_commands = True
    persistent_goal = True
    prompt = """Play Pokemon Red to reach the stated objective. This assisted gameplay track
provides the current screenshot, visible text, local terrain, owned party, moves
and bag. No hidden objectives, unseen terrain, enemy moves or future events.
Coordinates increase east and south. Map rows run north to south. The map legend
identifies confirmed observed exits, not destinations. ? means unseen. Known_map
recalls previously observed terrain only. Recent_movements records actual results.
Working_memory contains the last 50 executed decisions, distinct encountered
conversations and counts of matching action results. These are recorded observations,
not suggested next steps. Encounter text may be truncated or omitted under its
size limit. Inspect memory for a larger selection. Use this history to check
whether a repeated action changed anything before repeating a plan. Your notebook
holds scratch notes. A separate agent_plan retains your current goal, supporting
evidence and observable completion condition. Choose a concrete subgoal spanning
several actions, not just a button press or a restatement of the whole task.
Set goal_plan on the first turn.
Use JSON null for the entire goal_plan to keep it across movement, dialogue and
note changes. Never write the string "null" inside a plan field. Each action should
serve that goal. If completing or abandoning it, explicitly replace goal_plan
and explain the evidence in revision_reason. Do not silently revert to an earlier
plan after an obstruction or map change. Agent plans remain fallible hypotheses.
Use observed changes to revise guesses. Notes and older summaries are fallible.
Objects can block walkable terrain. A blocked move is not evidence of an exit.
Use one explicit command per decision. The controller never chooses a route:
move: direction up/down/left/right, count 1..8 tiles. Stops on obstruction, map
change, dialogue or battle. It handles turning and reports partial movement.
interact: empty argument, count 1. Taps A toward the facing direction. Walking
into an object and interacting with it are different actions.
choose: exact visible option text, count 1. Confirms only that menu choice.
use_move: move slot 1..4 as a string, count 1. Opens FIGHT and selects that move
in one command. Call this directly from the battle menu, without a separate FIGHT.
use_item: argument "Full Restore:1", count 1, uses exactly one named restorative
item on the specified party slot. Handles opening and scrolling the bag, USE,
target selection and closing field menus. Also supports Potions, status cures,
Revive, Max Revive, Elixer and Max Elixer. Spaces or underscores in names work.
Ether, evolution items, TMs and held battle boosts are not supported by this shortcut.
switch_pokemon: party slot 1..6 as a string, count 1. Sends that Pokemon into battle,
including a fainted replacement or the optional change prompt. Outside battle it
swaps that slot with slot 1 to set the lead, then closes menus. Inspect party after
reordering because slot numbers change. These commands never choose a target for you.
Prefer these shortcuts over menu presses. They stop on an unexpected choice,
unavailable item or target, or their 2400-frame navigation limit. Partial progress
is reported. No item is created and no turn cost or opponent response is skipped.
press: up/down/left/right/a/b/start/select, count 1. One short button tap.
wait: empty argument, count 1..600 frames within max_action_frames.
inspect: party/bag/storage/map/memory, count 1. Read-only, no frames pass.
advance_dialogue: empty argument, count 1. Collect an already open conversation.
After actions, the controller passively settles transitions and locked controls,
and advances confirmed continue-only dialogue. Read last_command.dialogue.pages.
It stops at menus, naming, battle choices or stable control, bounded by the run
and max_dialogue_frames limits. It never selects a response or directs movement.
Do not spend turns waiting unless the collection stop reason reports a limit or
an uncertain animation. A missing map can mean the screen is covered.
Move slots and party slots are one-based. Effects describe mechanics, not advice.
Return actions, notes, goal_plan and look_back. Use null notes to retain your notebook. Preserve
useful observations and uncertainties. No shell, walkthrough or human assistance.
""" + NICKNAME_RULE

    def __init__(self, *args, observation_format="json", **kwargs):
        if observation_format not in ("json", "text"):
            raise ValueError("Observation format must be json or text")
        self.observation_format = observation_format
        kwargs.setdefault("compact_at", self.default_compact_at)
        super().__init__(*args, **kwargs)
        self.prompt += ("\nYour conversation is retained between decisions and periodically summarized.\n" if self.continuity else
                        "\nEach decision starts fresh. Your notes, observed exploration memory and recent command results persist.\n")
        self.config_identity.update(observation_format=observation_format,
                                    text_presentation="observed-gameplay-text-v2" if observation_format == "text" else None,
                                    observation_policy="player-information-v036",
                                    controller_timing="bounded-gameplay-menus-v036")

    def decide(self, observation, notes, recent, limits, timeout):
        last = observation.get("game", {}).get("last_command")
        # The same command result is already present in the current observation.
        recent = [entry for entry in recent if entry != last]
        return super().decide(observation, notes, recent, limits, timeout)

    def decision_schema(self, limits):
        from .planning import SCHEMA
        schema = super().decision_schema(limits)
        schema["properties"]["goal_plan"] = SCHEMA
        schema["required"].append("goal_plan")
        schema["properties"]["actions"] = {"type": "array", "minItems": 0, "maxItems": 1,
            "items": {"type": "object", "additionalProperties": False,
                      "properties": {"command": {"type": "string", "enum": ["move", "interact", "choose", "use_move", "use_item", "switch_pokemon", "press", "wait", "inspect", "advance_dialogue"]},
                                     "argument": {"type": "string", "maxLength": 80},
                                     "count": {"type": "integer", "minimum": 1, "maximum": 600}},
                      "required": ["command", "argument", "count"]}}
        return schema
