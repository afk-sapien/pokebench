"""Bounded mechanical commands. No route finding or gameplay decisions."""
from pokesim_core.gen1_ui import read_screen, read_battler

from .core import BUTTONS
from .gameplay import menu_options, ui_state
from .dialogue import Transcript, settle_dialogue


def validate(command, limits):
    if not isinstance(command, dict) or set(command) != {"command", "argument", "count"}:
        raise ValueError("Expected command, argument and count")
    kind, arg, count = command["command"], command["argument"], command["count"]
    if not isinstance(arg, str) or type(count) is not int or count < 1:
        raise ValueError("Invalid command arguments")
    if kind == "move":
        valid = arg in ("up", "down", "left", "right") and count <= 8
    elif kind == "press":
        valid = arg in BUTTONS and count == 1
    elif kind == "wait":
        valid = arg == "" and count <= limits.max_action_frames
    elif kind in ("interact", "advance_dialogue"):
        valid = arg == "" and count == 1
    elif kind == "choose":
        valid = bool(arg.strip()) and len(arg) <= 80 and count == 1
    elif kind == "use_move":
        valid = arg in ("1", "2", "3", "4") and count == 1
    elif kind == "use_item":
        from .menu_shortcuts import parse_item
        parse_item(arg)
        valid = count == 1
    elif kind == "switch_pokemon":
        valid = arg in ("1", "2", "3", "4", "5", "6") and count == 1
    elif kind == "inspect":
        valid = arg in ("party", "bag", "storage", "map", "memory") and count == 1
    else:
        valid = False
    if not valid:
        raise ValueError("Unsupported command or argument")
    return dict(command)


def execute(session, operation_id, command, on_action=None):
    with session.lock:
        if session.track != "gameplay":
            raise ValueError("Structured commands require the gameplay track")
        command = validate(command, session.limits)
        if operation_id in session.gameplay_operations:
            previous = session.gameplay_operations[operation_id]
            if previous["request"] != command:
                raise ValueError("Operation ID reused with different command")
            return {**previous, "retried": True}
        facing_before = {0: "down", 4: "up", 8: "left", 12: "right"}.get(session.engine.memory[0xC109], "unknown")
        start = session.frame
        raw_count = 0
        phase_end = start + session.limits.max_action_frames
        if command["command"] in ("use_item", "switch_pokemon"):
            phase_end = start + min(2400, session.limits.max_dialogue_frames)
        transcript = Transcript()
        def capture():
            transcript.capture(session.engine.memory)
        capture()
        def position():
            memory = session.engine.memory
            return {"map_id": memory[0xD35E], "x": memory[0xD362], "y": memory[0xD361]}
        result = {"request": command, "start_frame": start, "outcome": "executed", "position_before": position()}
        kind, arg, count = command["command"], command["argument"], command["count"]
        session.gameplay_inspection = None

        def raw_send(button, hold=8, release=24):
            nonlocal raw_count
            remaining = phase_end - session.frame
            if session.reason or remaining <= 0:
                result["outcome"] = "stopped at budget boundary"
                return False
            remaining = min(remaining, session.limits.max_action_frames)
            hold = min(hold, remaining)
            release = min(release, remaining - hold)
            raw = {"button": button, "hold_frames": hold, "release_frames": release}
            before = session.frame
            raw_count += 1
            observed = session.act(f"{operation_id}.{raw_count}", **raw, on_frame=capture)
            if on_action:
                on_action(raw, before, observed)
            return not session.reason

        def send(button, hold=8, release=24):
            ok = raw_send(button, hold, release)
            if not ok or button != "a":
                return ok
            # The requested tap is followed only by released-button frames.
            # Return immediately at a visible menu, otherwise allow text to finish.
            for _ in range(4):
                if ui_state(session.engine.memory)["cursor_tile"]:
                    break
                remaining = phase_end - session.frame
                if remaining <= 0 or not raw_send(None, min(60, remaining), 0):
                    break
            return not session.reason

        def choose(target):
            initial = ui_state(session.engine.memory)
            if not initial["cursor_tile"]:
                result["outcome"] = "No active menu. No input sent."
                return False
            for _ in range(8):
                current = ui_state(session.engine.memory)
                cursor = current["cursor_tile"]
                if current["kind"] != initial["kind"] or not cursor:
                    result["outcome"] = "Menu changed. Stopped before confirming."
                    return False
                if current["kind"] == "battle_menu":
                    destination = {"FIGHT": [9, 14], "PKMN": [15, 14], "ITEM": [9, 16], "RUN": [15, 16]}.get(target.upper())
                else:
                    screen = read_screen(session.engine.memory)
                    matches = [option["cursor"] for option in menu_options(session.engine.memory, screen, current["kind"])
                               if option["text"].upper() == target.upper()]
                    destination = matches[0] if len(matches) == 1 else None
                if destination is None:
                    result["outcome"] = "Requested option is not uniquely visible. No confirmation sent."
                    return False
                if cursor == destination:
                    return send("a")
                button = ("right" if destination[0] > cursor[0] else "left") if destination[0] != cursor[0] else ("down" if destination[1] > cursor[1] else "up")
                if not send(button):
                    return False
            result["outcome"] = "Menu navigation limit reached. No confirmation sent."
            return False

        if kind == "inspect":
            session.gameplay_inspection = arg
            result["outcome"] = "Inspection available in next observation. No frames advanced."
        elif kind == "wait":
            send(None, count, 0)
        elif kind in ("press", "interact"):
            send(arg if kind == "press" else "a")
        elif kind == "choose":
            choose(arg)
        elif kind in ("use_item", "switch_pokemon"):
            from .menu_shortcuts import execute_shortcut
            execute_shortcut(session, command, raw_send, choose, result)
        elif kind == "use_move":
            before = ui_state(session.engine.memory)
            slot = int(arg) - 1
            active = read_battler(session.engine.memory)
            if before["kind"] not in ("battle_menu", "move_menu"):
                result["outcome"] = "Move selection requires a battle or move menu. No input sent."
            elif not active["moves"][slot] or active["pp"][slot] == 0:
                result["outcome"] = "Requested move is empty or has no PP. No input sent."
            else:
                if before["kind"] == "battle_menu":
                    choose("FIGHT")
                for _ in range(3):
                    if ui_state(session.engine.memory)["kind"] == "move_menu" or session.reason:
                        break
                    if not send(None, min(60, session.limits.max_action_frames), 0):
                        break
                for _ in range(4):
                    current = ui_state(session.engine.memory)
                    if current["kind"] != "move_menu":
                        result["outcome"] = "Move menu unavailable. Stopped without selecting a move."
                        break
                    y = current["cursor_tile"][1]
                    if y == 13 + slot:
                        send("a")
                        break
                    if not send("down" if 13 + slot > y else "up"):
                        break
        elif kind == "move":
            completed = 0
            for _ in range(count):
                memory = session.engine.memory
                if ui_state(memory)["kind"] != "overworld" or memory[0xD057]:
                    result["outcome"] = "Stopped at dialogue, menu or battle."
                    break
                location = tuple(memory[a] for a in (0xD35E, 0xD362, 0xD361))
                facing = memory[0xC109]
                continuing = send(arg, 8, 16)
                if continuing and memory[0xC200]:
                    continuing = send(None, 16, 0)
                current = tuple(memory[a] for a in (0xD35E, 0xD362, 0xD361))
                if continuing and current == location and memory[0xC109] != facing and ui_state(memory)["kind"] == "overworld":
                    continuing = send(arg, 8, 16)
                    if continuing and memory[0xC200]:
                        continuing = send(None, 16, 0)
                    current = tuple(memory[a] for a in (0xD35E, 0xD362, 0xD361))
                if current[0] != location[0]:
                    result["outcome"] = "Stopped at map transition."
                    break
                if not continuing:
                    completed += abs(current[1] - location[1]) + abs(current[2] - location[2])
                    result["outcome"] = "stopped at budget boundary"
                    break
                if current == location:
                    result["outcome"] = f"Moved {completed} tiles, then blocked or no further movement."
                    result["blocked_at"] = position()
                    break
                completed += abs(current[1] - location[1]) + abs(current[2] - location[2])
            result["tiles_moved"] = completed
            result["requested_tiles"] = count
            if result["outcome"] == "executed":
                result["outcome"] = f"Moved {completed} tiles."
            result["position_after_input"] = position()
        if (raw_count or kind == "advance_dialogue") and not session.reason:
            phase_end = session.frame + session.limits.max_dialogue_frames
            result["dialogue"] = settle_dialogue(session, raw_send, transcript, phase_end)
        elif kind != "inspect":
            result["dialogue"] = transcript.result("run ended" if session.reason else "command not executed", 0)
        result.update(end_frame=session.frame, raw_actions=raw_count, position_after=position())
        result["map_changed"] = result["position_before"]["map_id"] != result["position_after"]["map_id"]
        if kind == "move":
            movements = session.gameplay_memory.setdefault("movements", [])
            movements.append({key: result[key] for key in ("request", "position_before", "position_after_input", "position_after", "outcome", "tiles_moved", "map_changed")})
            del movements[:-8]
        from .working_memory import record
        record(session.gameplay_memory, session.current_decision or operation_id, result, facing_before, ui_state(session.engine.memory))
        session.gameplay_result = result
        session.gameplay_operations[operation_id] = result
        session.audit_memory("gameplay_command", result)
        return result
