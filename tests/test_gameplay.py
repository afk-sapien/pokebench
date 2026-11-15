import json
import os
from copy import deepcopy
from pathlib import Path

import pytest

from pokeagent_bench.core import Limits
from pokeagent_bench.gameplay import SPRITE_LOOKS, known_map, local_map, observe_gameplay, pair_floors, ui_state
from pokeagent_bench.gameplay_commands import execute, validate
from pokeagent_bench.session import Session
from pokeagent_bench.visual_feedback import public_context


def catalog():
    return {"labels": {"maps": {"0": "Test"}, "species": {"177": "Squirtle"}, "moves": {}, "items": {}},
            "moves": {}, "world": {"0": {"passable": [1], "warps": [[4, 5, 999, "SECRET_DESTINATION"], [50, 50, 88, 1]],
            "objects": [[4, 3, "SPRITE_POKE_BALL", "STAY", "SECRET_SPECIES"]], "backgrounds": []}}}


def memory():
    mem = bytearray(65536)
    mem[0xC3A0:0xC3A0 + 360] = bytes([1] * 360)
    mem[0xD362] = mem[0xD361] = 4
    mem[0xFF40] = 0x91
    mem[0xFF47] = 0xE4
    return mem


def test_map_filters_hidden_objects_destinations_and_offscreen_cells():
    mem = memory()
    mem[0xC110] = 1
    mem[0xC112] = 255
    mem[0xC214], mem[0xC215] = 7, 8
    cat = catalog()
    view = local_map(mem, cat, ui_state(mem))
    assert view["objects"] == []
    assert view["exits"] == [{"x": 4, "y": 5}]
    assert "SECRET" not in json.dumps(view)
    mem[0xC112] = 4
    assert local_map(mem, cat, ui_state(mem))["objects"][0]["appearance"] == "ball-shaped object"
    mem[0xC3A0 + 240] = 0x79
    assert not local_map(mem, cat, ui_state(mem))["available"]


def test_visible_people_carry_their_sprite_kind_and_never_a_name_or_role():
    mem = memory()
    cat = catalog()
    cat["world"]["0"]["objects"] = [[4, 3, "SPRITE_GIRL", "STAY", "TEXT_SAFFRONGYM_SABRINA"],
                                    [5, 3, "SPRITE_GYM_GUIDE", "STAY", "TEXT_SAFFRONGYM_GYM_GUIDE"],
                                    [6, 3, "SPRITE_KOGA", "STAY", "TEXT_FUCHSIAGYM_KOGA"]]
    for slot, x in ((1, 4), (2, 5), (3, 6)):
        mem[0xC100 + 16 * slot], mem[0xC102 + 16 * slot] = 1, 4
        mem[0xC204 + 16 * slot], mem[0xC205 + 16 * slot] = 3 + 4, x + 4
    # Slot 3 stands inside the viewport but its sprite is off screen, so it is not shown.
    mem[0xC136] = 200
    view = local_map(mem, cat, ui_state(mem))
    assert [(o["x"], o["appearance"]) for o in view["objects"]] == [(4, "girl"), (5, "man")]
    text = json.dumps(view).lower()
    assert all(word not in text for word in ("sabrina", "koga", "guide", "leader", "gym"))
    names = {"oak", "daisy", "mom", "fuji", "giovanni", "koga", "lance", "bruno", "lorelei", "agatha", "red", "blue"}
    roles = {"leader", "gym", "guide", "clerk", "receptionist", "worker", "president", "warden", "captain",
             "rocket", "silph", "safari", "link", "champion", "professor"}
    for look in SPRITE_LOOKS.values():
        assert not set(look.lower().replace("-", " ").split()) & (names | roles), look


@pytest.mark.skipif(not os.environ.get('POKEBENCH_GAME_DATA'), reason='Game data is not distributed')
def test_every_map_sprite_has_a_look():
    from pokeagent_bench.gameplay import load_catalog
    world = load_catalog(Path(os.environ['POKEBENCH_GAME_DATA']))['world']
    sprites = {row[2] for value in world.values() for row in value['objects']}
    assert sprites <= set(SPRITE_LOOKS), sorted(sprites - set(SPRITE_LOOKS))


def setup(tmp_path, engine):
    engine.memory = memory()
    return Session(engine, tmp_path / "run", {}, track="gameplay", gameplay_catalog=catalog(),
                   limits=Limits(max_action_frames=60))


def test_inspection_is_read_only_and_retry_safe(tmp_path, engine):
    session = setup(tmp_path, engine)
    command = {"command": "inspect", "argument": "storage", "count": 1}
    try:
        before = bytes(engine.memory)
        execute(session, "inspect-1", command)
        game = observe_gameplay(session)
        assert game["inspection"]["topic"] == "storage"
        assert session.frame == 0 and bytes(engine.memory) == before
        history_before = deepcopy(session.gameplay_memory["working"])
        assert execute(session, "inspect-1", command)["retried"]
        assert session.gameplay_memory["working"] == history_before
        with pytest.raises(ValueError):
            execute(session, "inspect-1", {**command, "argument": "party"})
        public = public_context(session.observe())
        assert "score" not in public and "evaluator" not in json.dumps(public)
    finally:
        session.close()


def test_visual_observation_remains_unchanged(tmp_path, engine):
    session = Session(engine, tmp_path / "visual", {}, track="visual")
    try:
        assert "game" not in session.observe()
        with pytest.raises(ValueError):
            execute(session, "bad", {"command": "inspect", "argument": "party", "count": 1})
    finally:
        session.close()


def test_unknown_menu_choice_never_sends_input(tmp_path, engine):
    session = setup(tmp_path, engine)
    try:
        result = execute(session, "no-menu", {"command": "choose", "argument": "NO", "count": 1})
        assert "No active menu" in result["outcome"]
        assert not engine.inputs and session.frame == 0
        execute(session, "blocked", {"command": "move", "argument": "up", "count": 4})
        assert session.frame <= 60
        assert session.gameplay_result["tiles_moved"] == 0
    finally:
        session.close()


def test_active_battle_hp_pp_override_lagging_party(tmp_path, engine):
    session = setup(tmp_path, engine)
    mem = engine.memory
    mem[0xD163] = 1
    mem[0xD16B] = mem[0xD014] = 177
    mem[0xD16B + 33] = mem[0xD014 + 14] = 12
    mem[0xD16B + 2] = 34
    mem[0xD016] = 8
    mem[0xD01C] = 33
    mem[0xD02D] = 4
    mem[0xD057] = 2
    try:
        result = observe_gameplay(session)
        assert result["party"][0]["hp"] == 8
        assert result["party"][0]["moves"][0]["pp"] == 4
        before = deepcopy(result)
        mem[0xCFE5:0xCFE5 + 29] = bytes([255] * 29)
        assert observe_gameplay(session) == before
    finally:
        session.close()


def test_invalid_command_rejected_before_input():
    for command in ({"command": "move", "argument": "up", "count": 9},
                    {"command": "wait", "argument": "", "count": 601},
                    {"command": "choose", "argument": "YES", "count": True}):
        with pytest.raises(ValueError):
            validate(command, Limits())


def test_gameplay_runner_and_recovery_preserve_inspection(tmp_path, engine):
    from pokeagent_bench.runner import run
    from pokeagent_bench.recovery import unpack

    class Provider:
        provider = "codex"
        model = "test"
        gameplay_commands = True
        visual_feedback = True
        current_only = True
        prompt = "test only"

        def decide(self, *args):
            return {"actions": [{"command": "inspect", "argument": "map", "count": 1}], "notes": None}, {
                "input_tokens": 10, "output_tokens": 5}, {}

        def close(self):
            pass

    session = setup(tmp_path, engine)
    run(session, Provider(), pause_after_decisions=1)
    saved = unpack(json.loads((session.output / "recovery.json").read_text())["payload"])
    assert saved["session"]["gameplay_inspection"] == "map"
    assert saved["session"]["gameplay_catalog"] == catalog()
    assert saved["session"]["gameplay_memory"]["tiles"]
    assert saved["session"]["gameplay_memory"]["working"]["decisions"][0]["decision"] == 1
    assert session.frame == 0


def test_fade_does_not_expose_map_or_buffered_dialogue():
    mem = memory()
    mem[0xFF47] = 0
    assert ui_state(mem)["kind"] == "transition"
    assert not local_map(mem, catalog(), ui_state(mem))["available"]


def test_a_tap_settles_without_additional_buttons(tmp_path, engine):
    session = setup(tmp_path, engine)
    session.limits = Limits(max_action_frames=600)
    try:
        result = execute(session, "tap", {"command": "press", "argument": "a", "count": 1})
        assert result["end_frame"] == 272
        assert [row for row in engine.inputs if row[0] == "press"] == [("press", "a", 0)]
    finally:
        session.close()


def test_a_settling_stops_at_visible_choice(tmp_path, engine):
    session = setup(tmp_path, engine)
    session.limits = Limits(max_action_frames=600)
    def update(fake):
        if fake.frame == 40:
            fake.memory[0xC3A0 + 261] = 0xED
    engine.on_tick = update
    try:
        execute(session, "tap", {"command": "press", "argument": "a", "count": 1})
        assert session.frame == 92
        assert [row for row in engine.inputs if row[0] == "press"] == [("press", "a", 0)]
    finally:
        session.close()


def test_map_change_withholds_new_objects_until_settled(tmp_path, engine):
    session = setup(tmp_path, engine)
    try:
        observe_gameplay(session)
        session.gameplay_catalog["world"]["1"] = deepcopy(catalog()["world"]["0"])
        session.gameplay_catalog["world"]["1"]["backgrounds"] = [[4, 4, "private-script"]]
        engine.memory[0xD35E] = 1
        assert not observe_gameplay(session)["local_map"]["available"]
        session.frame = 119
        assert not observe_gameplay(session)["local_map"]["available"]
        session.frame = 120
        assert observe_gameplay(session)["local_map"]["objects"][0]["appearance"] == "sign or fixed interactable"
    finally:
        session.close()


@pytest.mark.parametrize("map_id", [0, 5])
def test_delayed_transition_reconciles_movement_feedback(tmp_path, engine, monkeypatch, map_id):
    session = setup(tmp_path, engine)

    def delayed_transition(session, send, transcript, phase_end):
        session.engine.memory[0xD35E] = map_id
        session.engine.memory[0xD362] = 19
        session.engine.memory[0xD361] = 17
        return transcript.result("control returned", 0)

    monkeypatch.setattr("pokeagent_bench.gameplay_commands.settle_dialogue", delayed_transition)
    try:
        result = execute(session, "delayed-warp", {"command": "move", "argument": "up", "count": 1})
        assert result["position_after"] == {"map_id": map_id, "x": 19, "y": 17}
        assert result["tiles_moved"] == 0
        assert "blocked_at" not in result
        assert "blocked" not in result["outcome"]
        assert "Position changed" in result["outcome"]
        assert result["map_changed"] is (map_id != 0)
        assert session.gameplay_memory["movements"][-1]["outcome"] == result["outcome"]
        assert session.gameplay_memory["working"]["decisions"][-1]["commands"][-1]["outcome"] == result["outcome"]
    finally:
        session.close()


def test_object_motion_is_not_reported_as_a_blocked_player_move(tmp_path, engine, monkeypatch):
    session = setup(tmp_path, engine)
    mem = engine.memory
    mem[0xC110], mem[0xC112] = 1, 4
    mem[0xC214], mem[0xC215] = 7, 8

    def object_motion(session, send, transcript, phase_end):
        session.engine.memory[0xC214] = 8
        return transcript.result("control returned", 0)

    monkeypatch.setattr("pokeagent_bench.gameplay_commands.settle_dialogue", object_motion)
    try:
        result = execute(session, "push", {"command": "move", "argument": "up", "count": 1})
        assert result["position_before"] == result["position_after"]
        assert result["tiles_moved"] == 0
        assert "blocked_at" not in result
        assert result["visible_object_changes"] == [
            {"id": "object-1", "from": {"x": 4, "y": 3}, "to": {"x": 4, "y": 4}}]
        assert "Visible objects moved or disappeared" in result["outcome"]
        assert "SECRET" not in json.dumps(result)
        assert session.gameplay_memory["working"]["decisions"][-1]["commands"][-1]["outcome"] == result["outcome"]
    finally:
        session.close()


@pytest.mark.parametrize('player_x, reported', [(4, True), (20, False)])
def test_an_object_gone_from_its_visible_square_is_reported(tmp_path, engine, monkeypatch, player_x, reported):
    # A boulder pushed into a hole leaves the screen while its old square stays in view.
    # An object whose square scrolled out of view is not reported.
    session = setup(tmp_path, engine)
    mem = engine.memory
    mem[0xC110], mem[0xC112] = 1, 4
    mem[0xC214], mem[0xC215] = 7, 8

    def vanish(session, send, transcript, phase_end):
        session.engine.memory[0xC110] = 0
        session.engine.memory[0xD362] = player_x
        return transcript.result("control returned", 0)

    monkeypatch.setattr("pokeagent_bench.gameplay_commands.settle_dialogue", vanish)
    try:
        result = execute(session, "push", {"command": "move", "argument": "up", "count": 1})
        if reported:
            assert result["visible_object_changes"] == [
                {"id": "object-1", "from": {"x": 4, "y": 3}, "to": "no longer visible"}]
            assert "Visible objects moved or disappeared" in result["outcome"]
            assert "blocked_at" not in result
        else:
            assert "visible_object_changes" not in result
    finally:
        session.close()


@pytest.mark.parametrize('tileset,tiles', [
    ('FACILITY', [0x21, 0x20, 0x31, 0x30]), ('GYM', [0x3C, 0x4C, 0x3D, 0x4D])])
def test_live_spinner_arrows_preserve_direction_without_exposing_routes(tileset, tiles):
    mem, cat = memory(), catalog()
    cat['world']['0']['tileset'] = tileset
    cat['world']['0']['forced_moves'] = [[50, 50, 99, 99]]
    for col, tile in enumerate(tiles):
        mem[0xC3A0 + 20 + 2 * col] = tile
    view = local_map(mem, cat, {'kind': 'overworld'})
    assert view['rows'][0].startswith('^v<>')
    assert '99' not in json.dumps(view)
    cat['world']['0']['tileset'] = 'FOREST'
    assert local_map(mem, cat, {'kind': 'overworld'})['rows'][0].startswith('####')


# The CAVERN rows of the game data. (0x14, 0x05) is water and applies only while surfing.
CAVERN_ROWS = [(0x20, 0x05), (0x41, 0x05), (0x2A, 0x05), (0x05, 0x21), (0x14, 0x05)]


def test_pair_floors_split_cavern_pairs_into_two_glyphs_and_skip_surf_rows():
    floors = pair_floors(CAVERN_ROWS, [0x05, 0x20, 0x21, 0x2A, 0x41, 0x60])
    assert floors == {0x05: ':', 0x20: ',', 0x21: ',', 0x2A: ',', 0x41: ','}
    assert pair_floors(CAVERN_ROWS, [0x20, 0x21]) == {}
    assert pair_floors([], [1]) == {}


@pytest.mark.parametrize('rows', [[(1, 2), (3, 4)], [(1, 2), (2, 3), (1, 3)], [(1, 2), (2, 3), (3, 4)]])
def test_pair_floors_refuse_pairs_two_glyphs_cannot_show(rows):
    # Two separate groups, a triangle and a path all have steps two glyphs would misreport.
    with pytest.raises(ValueError, match='two floor glyphs'):
        pair_floors(rows, [1, 2, 3, 4])


def pair_view(mem, cat, cells):
    for (col, row), tile in cells.items():
        mem[0xC3A0 + (2 * row + 1) * 20 + 2 * col] = tile
    return local_map(mem, cat, {'kind': 'overworld'})


def test_local_map_marks_pair_floors_the_same_from_any_position():
    cat = catalog()
    world = cat['world']['0']
    world['tileset'], world['passable'] = 'CAVERN', [1, 0x05, 0x20]
    world['pair_floors'] = pair_floors(CAVERN_ROWS, world['passable'])
    # The player stands on raised floor 0x05 with low floor 0x20 to the east.
    view = pair_view(memory(), cat, {(4, 4): 0x05, (5, 4): 0x20, (6, 4): 0x05, (1, 0): 0x20})
    assert view['rows'][4][3:7] == '.@,:'
    assert view['rows'][0][1] == ','
    assert view['legend'][': ,'].startswith('walkable floor. A step directly between a : cell and a , cell is refused')
    assert view['legend']['@'] == 'you, standing on : floor'
    # One tile further east the same map cells keep the same glyphs.
    moved = pair_view(memory(), cat, {(3, 4): 0x05, (4, 4): 0x20, (5, 4): 0x05, (0, 0): 0x20})
    assert moved['rows'][4][2:6] == '.:@:'
    assert moved['rows'][0][0] == ','
    assert moved['legend']['@'] == 'you, standing on , floor'
    plain = pair_view(memory(), catalog(), {})
    assert ': ,' not in plain['legend'] and plain['legend']['@'] == 'you'


# Victory Road 1F, 2F and 3F draw each boulder switch square with bottom-left tile 0x2D.
CAVERN_SWITCH = 0x2D


def test_local_map_marks_the_visible_cave_floor_switch_like_a_floor_arrow():
    cat = catalog()
    world = cat['world']['0']
    world['tileset'], world['passable'] = 'CAVERN', [1, 0x05, 0x20, CAVERN_SWITCH]
    world['pair_floors'] = pair_floors(CAVERN_ROWS, world['passable'])
    view = pair_view(memory(), cat, {(6, 4): CAVERN_SWITCH, (2, 1): CAVERN_SWITCH})
    assert view['rows'][4][6] == '*' and view['rows'][1][2] == '*'
    assert view['legend']['*'] == 'visible floor switch'
    # Only the cave tileset draws 0x2D as a switch.
    world['tileset'] = 'FOREST'
    other = pair_view(memory(), cat, {(6, 4): CAVERN_SWITCH})
    assert other['rows'][4][6] == '.' and '*' not in other['legend']
    assert '*' not in pair_view(memory(), catalog(), {})['legend']


# Seafoam Islands 1F to B3F and Victory Road 3F draw each hole square with bottom-left tile 0x22.
CAVERN_HOLE = 0x22


def test_local_map_marks_the_visible_cave_hole():
    cat = catalog()
    world = cat['world']['0']
    world['tileset'], world['passable'] = 'CAVERN', [1, 0x05, 0x20, CAVERN_HOLE]
    world['pair_floors'] = pair_floors(CAVERN_ROWS, world['passable'])
    view = pair_view(memory(), cat, {(6, 4): CAVERN_HOLE, (5, 4): 0x05})
    assert view['rows'][4][5:7] == ':o'
    assert view['legend']['o'] == 'visible hole in the floor'
    # Only the cave tileset draws 0x22 as a hole.
    world['tileset'] = 'FOREST'
    assert pair_view(memory(), cat, {(6, 4): CAVERN_HOLE})['rows'][4][6] == '.'
    assert 'o' not in pair_view(memory(), catalog(), {})['legend']


@pytest.mark.parametrize('tileset, tile', [('CAVERN', 0x14), ('OVERWORLD', 0x14), ('OVERWORLD', 0x32),
                                           ('FOREST', 0x48), ('GYM', 0x14), ('FACILITY', 0x14)])
def test_local_map_shows_surfable_water_apart_from_blocked_terrain(tileset, tile):
    cat = catalog()
    cat['world']['0']['tileset'] = tileset
    view = pair_view(memory(), cat, {(6, 4): tile, (2, 4): 0x60})
    assert view['rows'][4][6] == '~' and view['rows'][4][2] == '#'
    assert view['legend']['~'] == 'water. Blocked on foot, crossable with Surf'


@pytest.mark.parametrize('tileset, tile', [('GYM', 0x32), ('SHIP', 0x32), ('SHIP_PORT', 0x32),
                                           ('INTERIOR', 0x14), ('CAVERN', 0x48)])
def test_local_map_keeps_tiles_that_do_not_look_like_water_blocked(tileset, tile):
    # Gym statues, ship walls, the dock platform and non water tilesets keep their old glyph.
    cat = catalog()
    cat['world']['0']['tileset'] = tileset
    view = pair_view(memory(), cat, {(6, 4): tile})
    assert view['rows'][4][6] == '#' and '~' not in view['legend']


def test_local_map_draws_walkable_tiles_as_floor_even_when_they_share_a_water_id():
    cat = catalog()
    cat['world']['0'].update(tileset='SHIP_PORT', passable=[1, 0x32])
    assert pair_view(memory(), cat, {(6, 4): 0x32})['rows'][4][6] == '.'


# The ROM ledge table: overworld tiles 0x36 and 0x37 hop down, 0x27 left, 0x0D and 0x1D right.
@pytest.mark.parametrize('tile, mark', [(0x36, 'v'), (0x37, 'v'), (0x27, '<'), (0x0D, '>'), (0x1D, '>')])
def test_local_map_marks_overworld_ledges_with_their_hop_direction(tile, mark):
    cat = catalog()
    cat['world']['0']['tileset'] = 'OVERWORLD'
    view = pair_view(memory(), cat, {(6, 4): tile})
    assert view['rows'][4][6] == mark
    assert view['legend']['v < >'] == ("ledge. Walking onto it in the arrow's direction hops over it. "
                                       "Other directions are blocked")
    assert '^ v < >' not in view['legend']
    # Only the overworld tileset draws these tiles as ledges.
    cat['world']['0']['tileset'] = 'FOREST'
    other = pair_view(memory(), cat, {(6, 4): tile})
    assert other['rows'][4][6] == '#' and 'v < >' not in other['legend']


def test_local_map_lists_floor_arrows_only_on_tilesets_that_draw_them():
    cat = catalog()
    assert '^ v < >' not in pair_view(memory(), cat, {})['legend']
    cat['world']['0']['tileset'] = 'OVERWORLD'
    assert not {'^ v < >', 'v < >'} & set(pair_view(memory(), cat, {})['legend'])
    for tileset in ('FACILITY', 'GYM'):
        cat['world']['0']['tileset'] = tileset
        legend = pair_view(memory(), cat, {})['legend']
        assert legend['^ v < >'] == 'visible floor arrows pointing up, down, left, right' and 'v < >' not in legend


def test_local_map_marks_the_mansion_3f_floor_gap_as_a_hole():
    # Mansion 3F draws its broken floor as tile 0x11. Its script drops the player from some gap squares.
    view = door_view(215, 'FACILITY', {(6, 4): 0x11, (2, 4): 0x60})
    assert view['rows'][4][6] == 'o' and view['rows'][4][2] == '#'
    assert view['legend']['o'] == 'visible gap in the floor. Some gap squares drop you to a lower floor'
    other = door_view(214, 'FACILITY', {(6, 4): 0x11})
    assert other['rows'][4][6] == '#' and 'o' not in other['legend']


def test_readable_context_keeps_legend_glyphs_as_they_are():
    from pokeagent_bench.readable_context import tree
    lines = tree({'local_map': {'legend': {'o': 'hole', 'O': 'object', 'v < >': 'ledge'}, 'rows': ['o.O']}})
    assert '    o: hole' in lines and '    O: object' in lines and '    v < >: ledge' in lines
    assert 'Local map:' in lines and '  Legend:' in lines


def test_known_map_explains_ledges_arrows_and_the_mansion_gap_by_tileset():
    tiles = {'tiles': {'0': {'4,4': '.', '5,4': 'v'}, '215': {'4,4': '.', '5,4': 'o'}}}
    legend = known_map(tiles, 0, 4, 4, 'OVERWORLD')['legend']
    assert " v < > observed ledge, hopped only in the arrow's direction." in legend and 'floor arrows' not in legend
    legend = known_map(tiles, 0, 4, 4, 'FACILITY')['legend']
    assert ' ^ v < > observed floor arrows,' in legend and 'ledge' not in legend
    legend = known_map(tiles, 0, 4, 4)['legend']
    assert 'floor arrows' not in legend and 'ledge' not in legend
    legend = known_map(tiles, 215, 4, 4, 'FACILITY')['legend']
    assert ' o observed gap in the floor, some squares drop you to a lower floor.' in legend
    assert 'hole' not in legend


def test_known_map_explains_holes_and_water_only_when_it_shows_them():
    legend = known_map({'tiles': {'0': {'4,4': '.', '5,4': 'o', '6,4': '~'}}}, 0, 4, 4)['legend']
    assert ' o observed hole in the floor.' in legend and legend.endswith(' ~ observed water, crossable with Surf.')
    legend = known_map({'tiles': {'0': {'4,4': '.', '5,4': '#'}}}, 0, 4, 4)['legend']
    assert 'hole' not in legend and 'water' not in legend


def door_view(map_id, tileset, cells):
    mem, cat = memory(), catalog()
    mem[0xD35E] = map_id
    cat['world'][str(map_id)] = dict(cat['world']['0'], tileset=tileset)
    return pair_view(mem, cat, cells)


@pytest.mark.parametrize('map_id, tileset, tile', [(207, 'FACILITY', 0x18), (208, 'FACILITY', 0x24),
                                                   (234, 'FACILITY', 0x18), (235, 'INTERIOR', 0x5E)])
def test_local_map_marks_the_visible_card_key_doors_on_silph_co_floors(map_id, tileset, tile):
    view = door_view(map_id, tileset, {(6, 4): tile, (7, 4): tile, (2, 4): 0x60})
    assert view['rows'][4][6:8] == 'DD' and view['rows'][4][2] == '#'
    assert view['legend']['D'] == 'visible closed door'


@pytest.mark.parametrize('map_id, tileset, tile', [(181, 'FACILITY', 0x18), (200, 'FACILITY', 0x24),
                                                   (212, 'FACILITY', 0x5E), (0, 'INTERIOR', 0x5E)])
def test_local_map_keeps_door_tiles_blocked_where_the_card_key_cannot_open_them(map_id, tileset, tile):
    # Silph Co 1F, Rocket Hideout B2F and 0x5E away from 11F are not doors.
    view = door_view(map_id, tileset, {(6, 4): tile})
    assert view['rows'][4][6] == '#' and 'D' not in view['legend']


@pytest.mark.parametrize('map_id, tile', [(165, 0x18), (166, 0x18), (166, 0x24), (216, 0x24),
                                          (199, 0x18), (202, 0x18)])
def test_local_map_marks_the_closed_gates_and_hideout_doors(map_id, tile):
    view = door_view(map_id, 'FACILITY', {(6, 4): tile, (7, 4): tile, (2, 4): 0x60})
    assert view['rows'][4][6:8] == 'DD' and view['rows'][4][2] == '#'
    assert view['legend']['D'] == 'visible closed door'


@pytest.mark.parametrize('map_id, cells', [(165, [(2, 5)]), (214, [(2, 11)]), (215, [(10, 5)]),
                                           (216, [(20, 3), (18, 25)]),
                                           (166, [(15, 7), (10, 1), (9, 7), (9, 13), (1, 13), (1, 7)])])
def test_local_map_marks_the_mansion_switches_and_the_gym_quiz_machines(map_id, cells):
    mem = memory()
    mem[0xD35E] = map_id
    cat = catalog()
    cat['world'][str(map_id)] = dict(cat['world']['0'], tileset='FACILITY')
    for x, y in cells:
        mem[0xD362], mem[0xD361] = x, y + 1
        view = local_map(mem, cat, {'kind': 'overworld'})
        # The player stands just below the statue or machine, which sits one row up at the centre.
        assert view['rows'][3][4] == 'S'
        assert {'id': f'background-{x}-{y}', 'x': x, 'y': y,
                'appearance': 'sign or fixed interactable'} in view['objects']


def test_local_map_leaves_hidden_items_and_other_maps_unmarked():
    mem = memory()
    cat = catalog()
    # Mansion 3F hides a Max Revive at (1, 9), and map 0 has no visible hidden events.
    for map_id, (x, y) in [(215, (1, 9)), (0, (2, 5))]:
        mem[0xD35E] = map_id
        cat['world'][str(map_id)] = dict(cat['world']['0'], tileset='FACILITY')
        mem[0xD362], mem[0xD361] = x, y + 1
        view = local_map(mem, cat, {'kind': 'overworld'})
        assert 'S' not in ''.join(view['rows']) and not view['objects']


def test_known_map_explains_the_closed_door_only_when_it_shows_it():
    assert known_map({'tiles': {'0': {'4,4': '.', '5,4': 'D'}}}, 0, 4, 4)['legend'].endswith(' D observed closed door.')
    assert 'door' not in known_map({'tiles': {'0': {'4,4': '.', '5,4': '#'}}}, 0, 4, 4)['legend']


@pytest.mark.parametrize('tileset, tile', [('OVERWORLD', 0x3D), ('GYM', 0x50)])
def test_local_map_marks_the_visible_cut_trees(tileset, tile):
    cat = catalog()
    cat['world']['0']['tileset'] = tileset
    view = pair_view(memory(), cat, {(6, 4): tile, (2, 4): 0x60})
    assert view['rows'][4][6] == 'T' and view['rows'][4][2] == '#'
    assert view['legend']['T'] == 'small tree. Blocked, Cut clears it'
    assert 'T' not in pair_view(memory(), cat, {})['legend']


@pytest.mark.parametrize('tileset, tile', [('GYM', 0x3D), ('FOREST', 0x3D), ('OVERWORLD', 0x50), ('CAVERN', 0x50)])
def test_local_map_keeps_tiles_that_are_not_cut_trees_as_before(tileset, tile):
    # Gym tile 0x3D is a floor arrow. The other tilesets have no Cut tree tile.
    cat = catalog()
    cat['world']['0']['tileset'] = tileset
    view = pair_view(memory(), cat, {(6, 4): tile})
    assert view['rows'][4][6] != 'T' and 'T' not in view['legend']


def test_local_map_is_hidden_in_a_dark_cave_until_flash():
    # Rock Tunnel sets wMapPalOffset to 6 on entry from outside, and Flash clears it.
    mem = memory()
    mem[0xD35D] = 6
    assert local_map(mem, catalog(), {'kind': 'overworld'}) == {'available': False, 'reason': 'Too dark to see the terrain.'}
    mem[0xD35D] = 0
    assert local_map(mem, catalog(), {'kind': 'overworld'})['available']


def test_known_map_explains_the_cut_tree_only_when_it_shows_it():
    assert known_map({'tiles': {'0': {'4,4': '.', '5,4': 'T'}}}, 0, 4, 4)['legend'].endswith(' T observed small tree, Cut clears it.')
    assert 'tree' not in known_map({'tiles': {'0': {'4,4': '.', '5,4': '#'}}}, 0, 4, 4)['legend']


def test_known_map_explains_the_floor_switch_only_when_it_shows_it():
    history = {'tiles': {'0': {'4,4': '.', '5,4': '*'}}}
    assert known_map(history, 0, 4, 4)['legend'].endswith(' * observed floor switch.')
    history = {'tiles': {'0': {'4,4': '.', '5,4': '.'}}}
    assert 'floor switch' not in known_map(history, 0, 4, 4)['legend']


def test_known_map_explains_pair_floors_only_when_it_shows_them():
    history = {'tiles': {'0': {'4,4': '.', '5,4': ':', '6,4': ','}}}
    assert known_map(history, 0, 4, 4)['legend'].endswith(' : and , walkable floor, no direct step between them.')
    history = {'tiles': {'0': {'4,4': '.', '5,4': '.'}}}
    assert 'direct step' not in known_map(history, 0, 4, 4)['legend']


@pytest.mark.skipif(not all(os.environ.get(name) for name in ('POKEBENCH_ROM', 'POKEBENCH_GAME_DATA', 'POKEBENCH_PAIR_RUN')),
                    reason='Optional local Long replay is not distributed')
def test_native_mt_moon_pair_collision_appears_on_the_local_map():
    """Replay long-v065-sonnet to Mt. Moon 1F (21,25), where the game refuses the step down."""
    from pokecore.gen1 import W_CUR_MAP, W_X, W_Y
    from pokeagent_bench.game import RedEngine
    from pokeagent_bench.gameplay import load_catalog
    from pokeagent_bench.navigation_conditions import install
    from pokeagent_bench.session import initialize_controls
    run = Path(os.environ['POKEBENCH_PAIR_RUN'])
    manifest = json.loads((run / 'manifest.json').read_text())
    engine = RedEngine(Path(os.environ['POKEBENCH_ROM']), (run / 'initial.state').read_bytes())
    try:
        install(engine, manifest['scenario'])
        initialize_controls(engine, manifest['scenario'])
        for line in (run / 'actions.jsonl').read_text().splitlines():
            row = json.loads(line)
            if row['before_frame'] >= 243458:
                break
            action = row['action']
            if action['button']:
                engine.press(action['button'])
            for index in range(row['executed_frames']):
                if action['button'] and index == action['hold_frames']:
                    engine.release(action['button'])
                engine.tick()
            if action['button']:
                engine.release(action['button'])
        memory = engine.memory
        assert (memory[W_CUR_MAP], memory[W_X], memory[W_Y]) == (59, 21, 25)
        view = local_map(memory, load_catalog(Path(os.environ['POKEBENCH_GAME_DATA'])), ui_state(memory))
        standing = view['legend']['@'].removeprefix('you, standing on ').removesuffix(' floor')
        assert {standing, view['rows'][5][4]} == {':', ','}
        engine.press('down')
        for _ in range(24):
            engine.tick()
        engine.release('down')
        for _ in range(24):
            engine.tick()
        assert (memory[W_X], memory[W_Y]) == (21, 25)
    finally:
        engine.close()
