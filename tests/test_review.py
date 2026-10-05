import base64
from io import BytesIO
import json

from fastapi.testclient import TestClient
from PIL import Image
import pytest

from pokeagent_bench.core import Limits
from pokeagent_bench.dashboard import create_app
from pokeagent_bench.review import build_run, export_review, highlights, review_html
from pokeagent_bench.runner import run
from pokeagent_bench.session import Session


def recorded_run(tmp_path, engine, plan="Test movement"):
    class Provider:
        provider = "fixture"
        model = "review-test"
        visual_feedback = True

        def decide(self, observation, *args):
            view = observation["controller_view"]
            return (
                {
                    "actions": [
                        {"button": "wait", "hold_frames": 2, "release_frames": 0},
                        {"button": "left", "hold_frames": 1, "release_frames": 0},
                    ],
                    "notes": None,
                },
                {"input_tokens": 10, "output_tokens": 2},
                {
                    "presentation": {k: v for k, v in view.items() if k != "base64"},
                    "assessment": {"plan_intent": plan, "scene": {"scene": "room"}},
                    "PRIVATE": "/secret/not-for-export",
                },
            )

        def close(self):
            pass

    session = Session(engine, tmp_path / "run", {}, limits=Limits(max_model_calls=3))
    run(session, Provider())
    return session.output


def color(payload, key):
    raw = base64.b64decode(payload["images"][key].split(",", 1)[1])
    with Image.open(BytesIO(raw)) as image:
        assert image.size == (160, 144)
        return image.getpixel((0, 0))


def test_before_and_after_align_with_executed_batch_including_final_frame(tmp_path, engine):
    path = recorded_run(tmp_path, engine)
    before = {p.relative_to(path): p.read_bytes() for p in path.rglob("*") if p.is_file()}
    result = build_run(path)
    assert [(s["before_frame"], s["after_frame"]) for s in result["steps"]] == [(0, 3), (3, 6), (6, 9)]
    for step in result["steps"]:
        assert color(result, step["before"])[0] == step["before_frame"]
        assert color(result, step["after"])[0] == step["after_frame"]
    assert result["steps"][-1]["cumulative_tokens"] == 36
    assert engine.frame == 9
    assert before == {p.relative_to(path): p.read_bytes() for p in path.rglob("*") if p.is_file()}
    assert "PRIVATE" not in json.dumps(result) and "/secret/" not in json.dumps(result)


def test_repeated_results_are_flagged_without_calling_them_collisions(tmp_path, engine):
    initial = engine.screenshot()
    engine.screenshot = lambda: initial
    result = build_run(recorded_run(tmp_path, engine))
    assert len(result["images"]) == 1
    assert [s["no_new_view_streak"] for s in result["steps"]] == [1, 2, 3]
    assert all(s["unchanged"] for s in result["steps"])
    assert "collision" not in json.dumps(result)


def test_highlights_preserve_endpoints_and_events_under_limit():
    steps = [{"events": [], "no_new_view_streak": 0} for _ in range(120)]
    steps[17]["events"] = [{"kind": "location"}]
    steps[83]["no_new_view_streak"] = 4
    selected = highlights(steps, 20)
    assert len(selected) == 20
    assert selected == sorted(set(selected))
    assert {0, 17, 83, 119}.issubset(selected)


def test_script_injection_is_text_and_export_cannot_overwrite(tmp_path, engine):
    payload = "</script><script>window.BAD=true</script>"
    path = recorded_run(tmp_path, engine, payload)
    html = review_html([path])
    assert payload not in html
    assert "\\u003c/script\\u003e" in html
    output = tmp_path / "review.html"
    export_review([path], output)
    with pytest.raises(ValueError, match="already exists"):
        export_review([path], output)
    with pytest.raises(ValueError, match="duration"):
        review_html([path], 0)


def test_corrupt_or_escaping_image_artifact_is_rejected(tmp_path, engine):
    path = recorded_run(tmp_path, engine)
    decisions = [json.loads(line) for line in (path / "decisions.jsonl").read_text().splitlines()]
    artifact = path / decisions[0]["provider"]["presentation"]["artifact"]
    original = artifact.read_bytes()
    artifact.write_bytes(b"not the recorded screenshot")
    with pytest.raises(ValueError, match="checksum"):
        build_run(path)
    artifact.write_bytes(original)
    decisions[0]["provider"]["presentation"]["artifact"] = "../outside.png"
    (path / "decisions.jsonl").write_text("\n".join(json.dumps(d) for d in decisions))
    with pytest.raises(ValueError, match="inside"):
        build_run(path)


def test_dashboard_review_is_read_only_and_rejects_symlink(tmp_path, engine):
    recorded_run(tmp_path, engine)
    client = TestClient(create_app(tmp_path))
    response = client.get("/api/runs/run/review")
    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]
    assert client.post("/api/runs/run/review").status_code == 405
    (tmp_path / "alias").symlink_to(tmp_path / "run", target_is_directory=True)
    assert client.get("/api/runs/alias/review").status_code == 404
    assert client.get("/api/runs/run/initial.state").status_code == 404


def test_no_action_decision_has_same_before_and_after(tmp_path, engine):
    path = recorded_run(tmp_path, engine)
    ds = [json.loads(line) for line in (path / "decisions.jsonl").read_text().splitlines()]
    ds[0]["frame"] = 3
    actions = [json.loads(line) for line in (path / "actions.jsonl").read_text().splitlines()]
    actions = [a for a in actions if a["operation_id"].split("-")[1] != "1"]
    (path / "actions.jsonl").write_text("\n".join(json.dumps(a) for a in actions))
    (path / "decisions.jsonl").write_text("\n".join(json.dumps(d) for d in ds))
    first = build_run(path)["steps"][0]
    assert first["actions"] == []
    assert first["before"] == first["after"]
