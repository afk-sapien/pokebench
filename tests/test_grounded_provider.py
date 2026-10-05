import json

from pokeagent_bench.core import Limits
from pokeagent_bench.grounded_provider import GroundedCodexProvider
from pokeagent_bench.runner import run
from pokeagent_bench.session import Session
from pokeagent_bench.visual_feedback import VisualFeedback


def provider_without_auth():
    return object.__new__(GroundedCodexProvider)


def test_assessment_precedes_single_controller_plan_and_memory_cannot_diverge():
    provider = provider_without_auth()
    schema = provider.decision_schema(Limits(max_actions_per_decision=2))
    assert list(schema["properties"]) == ["assessment", "memory", "plan"]
    assert "actions" not in schema["properties"]
    action = {"button": "right", "hold_frames": 16, "release_frames": 8}
    decision, record = provider.unpack_decision(
        {
            "assessment": {"scene": "room"},
            "memory": {"observed": ["An object is visible"], "hypotheses": [], "unsuccessful_attempts": []},
            "plan": {"intent": "Test right", "expected_visible_change": "View changes", "actions": [action]},
        }
    )
    assert decision["actions"] == [action]
    assert decision["notes"]["next_experiment"] == record["plan_intent"] == "Test right"


def test_grounded_invalid_output_is_counted_without_executing_actions(tmp_path, engine):
    class Provider(GroundedCodexProvider):
        def __init__(self):
            self.model = "fixture"
            self.reasoning_effort = "low"
            self.cli_version = "test"

        def decide(self, *args):
            decision, record = self.unpack_decision({"memory": "bad", "plan": {"actions": []}})
            return decision, {"input_tokens": 7, "output_tokens": 3}, record

    session = Session(engine, tmp_path / "run", {}, limits=Limits(max_model_calls=3))
    result = run(session, Provider())
    assert result["stop_reason"] == "invalid_model_response"
    assert result["usage"]["accounting_complete"] is True
    assert result["usage"]["input_tokens"] + result["usage"]["output_tokens"] == 30
    assert result["frames"] == 0


def test_exact_view_retry_history_survives_notebook_reset_and_observation(session):
    initial = session.engine.screenshot()
    session.engine.screenshot = lambda: initial
    feedback = VisualFeedback(session.output)
    feedback.prepare(session.observe(), 1)
    command = {"button": "left", "hold_frames": 16, "release_frames": 8}
    for index in range(4):
        before = session.frame
        session.act(str(index), **command)
        feedback.record(command, before, session.frame, session.observe()["screenshot"])
        feedback.prepare(session.observe(), index + 2)
    observation = session.observe()
    view = feedback.prepare(observation, 6)
    history = view["screen_history"]
    assert history["current_image_occurrences"] == 5
    assert history["unique_images_seen"] == history["recent_unique_images"] == 1
    assert history["unchanged_inputs_from_this_exact_image"] == [{**command, "count": 4}]
    observation["controller_view"] = view
    notes = {"observed": [], "hypotheses": [], "unsuccessful_attempts": [], "next_experiment": "Forgot everything"}
    payload = provider_without_auth().decision_context(observation, json.dumps(notes), [])
    assert payload["observation"]["screen_history"] == history
    assert "next_experiment" not in payload["notes"]
    assert session.frame == 96
    assert "blocked" not in json.dumps(history)
    assert "map_id" not in json.dumps(history)
