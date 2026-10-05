import base64
from io import BytesIO
import json

from PIL import Image
import pytest

from pokeagent_bench.core import Limits, digest
from pokeagent_bench.runner import run
from pokeagent_bench.session import Session
from pokeagent_bench.visual_feedback import VisualFeedback, change, normalize_notes, public_context


def test_screen_strip_preserves_pixels_and_observing_never_ticks(session):
    feedback = VisualFeedback(session.output)
    first = session.observe()
    view = feedback.prepare(first, 1)
    assert session.frame == 0
    assert len(view["screens"]) == 1
    command = {"button": "right", "hold_frames": 2, "release_frames": 1}
    session.act("test", **command)
    after = session.observe()
    result = feedback.record(command, 0, 3, after["screenshot"])
    strip = feedback.prepare(after, 2)
    assert session.frame == 3
    assert result["executed_frames"] == 3
    assert result["changed_pixel_fraction"] == 1
    assert [item["frame"] for item in strip["screens"]] == [0, 3]
    png = base64.b64decode(strip["base64"])
    assert digest(png) == strip["image_sha256"]
    assert (session.output / strip["artifact"]).read_bytes() == png
    with Image.open(BytesIO(png)) as image:
        assert image.size == (960, 472)
        assert image.getpixel((0, 40)) == (0, 50, 80)
        assert image.getpixel((480, 40)) == (3, 50, 80)
    unchanged = change(base64.b64decode(after["screenshot"]["base64"]),
                       base64.b64decode(after["screenshot"]["base64"]))
    assert unchanged == {"image_changed": False, "changed_pixel_fraction": 0}


def test_visual_context_cannot_leak_ram_evaluator_or_scores(session):
    observation = session.observe()
    observation["status"]["track"] = "visual"
    observation["game"] = {"location": {"map_id": "SECRET"}}
    observation["status"]["achievements"] = ["PRIVATE_EVENT"]
    observation["status"]["score"] = 999
    observation["private"] = "PRIVATE_DATA"
    public = public_context(observation)
    text = json.dumps(public)
    assert all(secret not in text for secret in ("SECRET", "PRIVATE_EVENT", "PRIVATE_DATA", "999"))
    assert "game" not in public and "score" not in public and "achievements" not in public


def test_notebook_rejects_missing_fields_and_keeps_evidence_separate():
    notes = {"observed": ["Room changed"], "hypotheses": ["Maybe downstairs"],
             "unsuccessful_attempts": ["Left did not visibly change the screen"], "next_experiment": "Try down"}
    assert json.loads(normalize_notes(notes)) == notes
    assert normalize_notes(None) is None
    for invalid in ("old prose", {}, {**notes, "observed": "not a list"}, {**notes, "next_experiment": []}):
        with pytest.raises(ValueError):
            normalize_notes(invalid)


def test_controller_feedback_uses_executed_frames_and_null_preserves_notes(tmp_path, engine):
    notes = {"observed": ["Initial room"], "hypotheses": [],
             "unsuccessful_attempts": [], "next_experiment": "Wait"}
    class Provider:
        provider = "test"
        model = "fixture"
        visual_feedback = True
        normalize_notes = staticmethod(normalize_notes)
        calls = 0
        def decide(self, observation, memory, recent, limits, timeout):
            self.calls += 1
            if self.calls == 2:
                assert json.loads(memory) == notes
                assert len(observation["controller_view"]["screens"]) == 3
                assert [r["executed_frames"] for r in recent] == [2, 2]
                assert all("new_achievements" not in r for r in recent)
            return {"actions": [{"button": "wait", "hold_frames": 2, "release_frames": 0}] * 2,
                    "notes": notes if self.calls == 1 else None}, {"input_tokens": 1, "output_tokens": 1}, {}
        def close(self):
            pass
    session = Session(engine, tmp_path / "run", {}, track="visual", limits=Limits(max_frames=5))
    result = run(session, Provider())
    assert result["frames"] == engine.frame == 5
    assert result["actions"] == 3
    assert json.loads(session.notes) == notes
    assert engine.inputs == []


def test_invalid_structured_notebook_rejects_actions_without_ticks(session):
    class Provider:
        provider = "test"
        model = "fixture"
        visual_feedback = True
        normalize_notes = staticmethod(normalize_notes)
        def decide(self, *args):
            return {"actions": [{"button": "right", "hold_frames": 20, "release_frames": 8}],
                    "notes": {"observed": ["Missing required fields"]}}, {"input_tokens": 1, "output_tokens": 1}, {}
        def close(self):
            pass
    result = run(session, Provider())
    assert result["stop_reason"] == "invalid_model_response"
    assert result["frames"] == 0
