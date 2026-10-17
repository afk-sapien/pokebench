"""Subscription-backed decision benchmark with explicit information assistance."""
from .continuous_provider import ContinuousCodexProvider
from .rules import NICKNAME_RULE


class GameplayCodexProvider(ContinuousCodexProvider):
    allowed_track = "gameplay"
    harness = "codex-app-server-gameplay-fair-v046"
    default_compact_at = 32000
    gameplay_commands = True
    persistent_goal = True
    max_controller_commands = 1
    required_planning_metadata = False
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
holds scratch notes. A separate agent_plan can retain an optional goal, evidence and completion condition.
Use notes or a plan when useful. Neither is required, including on the first turn.
Omit notes and goal_plan, or return null, to retain their current values. Supplied
plans must contain goal, evidence, done_when and revision_reason. Plans and notes
are unverified agent claims. Check observed outcomes before revising a hypothesis.
The task ends automatically when the benchmark confirms success. task_status is
current feedback. If it says not_complete, a note claiming success does not end
the task. Recheck that claim and continue acting. Empty actions do not submit success.
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
target selection and returning to a resting screen. A starting pause menu stays open. Also supports Potions, status cures,
Revive, Max Revive, Elixer and Max Elixer. Spaces or underscores in names work.
Ether, evolution items, TMs and held battle boosts are not supported by this shortcut.
switch_pokemon: party slot 1..6 as a string, count 1. Sends that Pokemon into battle,
including a fainted replacement or the optional change prompt. Outside battle it
swaps that slot with slot 1 to set the lead, then returns to a resting screen. Inspect party after
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
Return actions. notes, goal_plan and look_back are optional. Omission or null
retains notes and plans and makes no screenshot request. Preserve useful discoveries
in notes if needed. No shell, walkthrough or human assistance.
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
                                    observation_policy="player-information-v062",
                                    controller_timing="core-shortcuts-v060",
                                    action_contract="gen1-commands-v2",
                                    planning_policy="optional-planning-v1",
                                    correction_policy="three-metered-invalid-decisions-v1")

    def configure_action_policy(self, policy, *, record=True):
        from .action_policy import MANUAL, description, resolve
        self.action_policy = resolve({}, policy)
        if not hasattr(self, "_unrestricted_prompt"):
            self._unrestricted_prompt = self.prompt
            self._assisted_timing = self.config_identity.get("controller_timing", "core-shortcuts-v060")
        self.prompt = self._unrestricted_prompt
        if policy == MANUAL:
            start = self.prompt.index("Use one explicit command per decision.")
            end = self.prompt.index("Move slots and party slots are one-based.", start)
            self.prompt = self.prompt[:start] + description(policy) + "\n" + self.prompt[end:]
        if record:
            self.config_identity["action_policy"] = policy
            self.config_identity["controller_timing"] = ("manual-tap-8-hold-24-release-v1"
                                                        if policy == MANUAL else self._assisted_timing)

    def decide(self, observation, notes, recent, limits, timeout):
        last = observation.get("game", {}).get("last_command")
        # The same command result is already present in the current observation.
        recent = [entry for entry in recent if entry != last]
        return super().decide(observation, notes, recent, limits, timeout)

    def decision_schema(self, limits):
        from .planning import SCHEMA
        schema = super().decision_schema(limits)
        schema["properties"]["goal_plan"] = SCHEMA
        from .gameplay_contract import action_schema
        schema["required"] = ["actions"]
        schema["properties"]["actions"] = {"type": "array", "minItems": 0, "maxItems": 1,
                                           "items": action_schema(limits, getattr(self, "action_policy", None))}
        return schema
