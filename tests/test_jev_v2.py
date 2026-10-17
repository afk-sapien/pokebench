import json
from collections import Counter

import httpx

from pokeagent_bench.core import Limits
from pokeagent_bench.jev_v2 import JevTargetsProvider, fits, moves, targets
from pokeagent_bench.runner import run
from test_jev_provider import client, shortcut_answer


def room():
    return {"location": {"map_id": 1, "map_name": "Room", "x": 1, "y": 3, "facing": "up"},
            "screen": {"kind": "overworld"}, "battle": {"kind": "none"}, "party": [{}], "bag": [],
            "local_map": {"available": True, "origin": {"x": 0, "y": 0},
                          "rows": ["#E###", "#...#", "#...#", "#...?"], "objects": [], "exits": [{"x": 1, "y": 0}]}}


def test_moves_fit_one_command_frame_budget():
    assert moves(["up"] * 8 + ["left"], 4) == [
        {"command": "move", "argument": "up", "count": 6}, {"command": "move", "argument": "up", "count": 2},
        {"command": "move", "argument": "left", "count": 1}]


def test_exit_target_walks_through_the_door_and_reports_where_it_led():
    found = targets(room(), {"1:1,0": "Hall"}, Counter(), 8)
    commands, description = found["goto_exit_1_0"]
    assert commands == [{"command": "move", "argument": "up", "count": 3},
                        {"command": "move", "argument": "up", "count": 1}]
    assert "Leads to Hall" in description and "explore_east" in found


def test_menus_follow_the_screen():
    game = room()
    assert fits("move_up", game) and fits("goto_exit_1_0", game)
    assert not fits("use_move_1", game) and not fits("potion_1", game)
    battle = {**game, "battle": {"kind": "wild"}, "screen": {"kind": "battle_menu"}, "bag": [{"name": "Potion"}]}
    assert fits("use_move_1", battle) and fits("potion_1", battle) and not fits("potion_2", battle)
    assert not fits("move_up", battle) and not fits("super_potion_1", battle)
    dialogue = {**game, "screen": {"kind": "dialogue"}}
    assert fits("advance_dialogue", dialogue) and not fits("move_up", dialogue)


def test_runner_plays_v2_with_progress_log(tmp_path, engine):
    from test_gameplay import setup
    session = setup(tmp_path, engine)
    session.limits = Limits(max_action_frames=60, max_model_calls=2)
    bodies = []

    def handle(request):
        data = request.read()
        part = data[data.index(b'name="request"'):]
        body = json.loads(part[part.index(b"\r\n\r\n") + 4:part.index(b"\r\n--")])
        bodies.append(body)
        menu = body["questions"]["action"]["criteria"]
        return httpx.Response(200, json=shortcut_answer("wait", menu))
    provider = JevTargetsProvider(client=client(handle))
    result = run(session, provider)
    assert result["stop_reason"] == "model_call_budget"
    progress = bodies[1]["state"]["game_state"]["progress"]
    assert progress["log"][0]["choice"] == "wait"
    manifest = json.loads((session.output / "manifest.json").read_text())
    assert manifest["agent"]["harness"] == "jev-choice-targets-v2"
