import json

import pytest

from pokeagent_bench.core import Limits, digest, encoded
from pokeagent_bench.session import Session


def test_observation_pauses_game_and_filters_private_data(session, engine):
    first = session.observe()
    session.observe()
    session.status()
    session.write_notes("Find Oak")
    assert engine.frame == 0
    assert "screenshot" in first and "game" in first
    assert "gym_flags" not in json.dumps(first)
    assert "champion" not in first


def test_visual_track_does_not_return_structured_fields(tmp_path, engine):
    with_session = Session(engine, tmp_path / "visual", {}, track="visual")
    assert set(with_session.observe()) == {"frame", "status", "screenshot"}
    with_session.close()


def test_action_retry_is_idempotent_and_cannot_change_request(session, engine):
    first = session.act("one", "a", 8, 2)
    assert engine.frame == 10
    assert session.act("one", "a", 8, 2) == first
    assert engine.frame == 10
    with pytest.raises(ValueError, match="different"):
        session.act("one", "b", 8, 2)
    first["status"]["score"] = 999
    assert session.act("one", "a", 8, 2)["status"]["score"] == 0


@pytest.mark.parametrize("args", [("bad", 8, 2), ("a", -1, 2), ("a", 1, -1), ("a", 120, 1), ("a", True, 0)])
def test_invalid_action_never_advances(session, engine, args):
    with pytest.raises(ValueError):
        session.act("bad", *args)
    assert engine.frame == 0


def test_frame_budget_truncates_action_exactly(tmp_path, engine):
    session = Session(engine, tmp_path / "budget", {}, limits=Limits(max_frames=3))
    result = session.act("long", "a", 8, 2)
    assert result["executed_frames"] == 3
    assert result["status"]["stop_reason"] == "frame_budget"
    assert engine.frame == 3
    assert session.act("long", "a", 8, 2) == result
    with pytest.raises(ValueError, match="finished"):
        session.wait("new", 1)
    session.close()


def test_wall_budget_does_not_advance_and_terminal_clock_freezes(tmp_path, engine):
    now = [0.0]
    session = Session(engine, tmp_path / "wall", {}, limits=Limits(max_wall_seconds=5), clock=lambda: now[0])
    now[0] = 6
    assert session.status()["stop_reason"] == "wall_budget"
    now[0] = 50
    assert session.status()["wall_seconds"] == 6
    assert engine.frame == 0
    session.close()


def test_success_stops_at_confirming_frame(session, engine):
    def award(emu):
        emu.state["badges"] = 1
        emu.state["gym_flags"][0] = True
    engine.on_tick = award
    result = session.act("win", "a", 20, 0)
    assert result["frame"] == 2
    assert result["status"]["completed"]
    assert result["new_achievements"][0]["frame"] == 2
    assert result["status"]["score"] == 75


def test_old_retry_is_rejected_after_cache_eviction(session, engine):
    for i in range(66):
        session.wait(str(i), 1)
    with pytest.raises(ValueError, match="already executed"):
        session.wait("0", 1)
    assert engine.frame == 66


def test_trace_chain_and_private_evidence_are_recorded(session):
    session.wait("a", 1)
    session.wait("b", 1)
    head = "0" * 64
    for line in (session.output / "actions.jsonl").read_text().splitlines():
        record = json.loads(line)
        claimed = record.pop("hash")
        assert record["previous_hash"] == head
        assert digest(encoded(record)) == claimed
        head = claimed
    assert session.trace_head == head


def test_utf8_notebook_limit_and_isolation(session, tmp_path, engine):
    with pytest.raises(ValueError, match="UTF-8"):
        session.write_notes("é" * 5000)
    session.write_notes("Find Oak")
    other = Session(engine, tmp_path / "other", {})
    assert other.read_notes()["text"] == ""
    other.close()


@pytest.mark.parametrize("kwargs", [{"max_frames": 0}, {"max_actions": True}, {"max_wall_seconds": float("nan")},
                                    {"max_frames": 2.5}, {"max_action_frames": 601}, {"max_area_tokens": -1},
                                    {"max_area_tokens": False}, {"max_area_tokens": 0.0}])
def test_invalid_limits_are_rejected(kwargs):
    with pytest.raises(ValueError):
        Limits(**kwargs)


def test_campaign_goal_overrides_starter_fixture_and_continues_after_brock(tmp_path, engine):
    scenario = {"objective": {"description": "Get a starter"}}
    session = Session(engine, tmp_path / "campaign", scenario, goal="campaign")
    assert "Hall of Fame" in session.status()["objective"]
    assert "Get a starter" not in session.status()["objective"]

    def award(emu):
        emu.state["badges"] = 1
        emu.state["gym_flags"][0] = True

    engine.on_tick = award
    result = session.act("brock", "a", 20, 0)
    assert result["status"]["score"] == 75
    assert result["status"]["score_max"] == 1000
    assert not result["status"]["completed"]
    assert result["status"]["state"] == "running"
    session.close()
