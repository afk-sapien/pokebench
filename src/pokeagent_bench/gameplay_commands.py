"""Bounded mechanical commands. No route finding or gameplay decisions."""
from pokecore.gen1_ui import read_screen

from .gameplay_contract import validate_command
from .gameplay import local_map, menu_options, ui_state
from .dialogue import Transcript, settle_dialogue


def validate(command, limits, policy=None):
    return validate_command(command, limits, policy)


def execute(session, operation_id, command, on_action=None):
    with session.lock:
        if session.track != "gameplay":
            raise ValueError("Structured commands require the gameplay track")
        from .action_policy import ASSISTED, MANUAL
        policy = getattr(session, "action_policy", ASSISTED)
        command = validate(command, session.limits, policy)
        if operation_id in session.gameplay_operations:
            previous = session.gameplay_operations[operation_id]
            if previous["request"] != command:
                raise ValueError("Operation ID reused with different command")
            return {**previous, "retried": True}
        facing_before = {0: "down", 4: "up", 8: "left", 12: "right"}.get(session.engine.memory[0xC109], "unknown")
        start = session.frame
        raw_count = 0
        phase_end = start + session.limits.max_action_frames
        if command["command"] in ("use_item", "switch_pokemon", "use_move"):
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
        visible_before = (local_map(session.engine.memory, session.gameplay_catalog,
                                    ui_state(session.engine.memory)) if kind == "move" else {})

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
            if not ok or button != "a" or policy == MANUAL:
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
        elif kind in ("use_item", "switch_pokemon", "use_move"):
            from .menu_shortcuts import execute_shortcut
            execute_shortcut(session, command, raw_send, choose, result)
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
        if policy != MANUAL and (raw_count or kind == "advance_dialogue") and not session.reason:
            phase_end = session.frame + session.limits.max_dialogue_frames
            result["dialogue"] = settle_dialogue(session, raw_send, transcript, phase_end)
        elif kind != "inspect":
            result["dialogue"] = transcript.result("run ended" if session.reason else "manual input complete" if raw_count and policy == MANUAL else "command not executed", 0)
        result.update(end_frame=session.frame, raw_actions=raw_count, position_after=position())
        result["map_changed"] = result["position_before"]["map_id"] != result["position_after"]["map_id"]
        if kind == "move":
            if result["position_after"] != result["position_after_input"]:
                # Reconcile delayed transitions before writing the observed history.
                result.pop("blocked_at", None)
                destination = result["position_after"]
                result["outcome"] = (
                    f"Moved {result['tiles_moved']} tiles during input. Position changed while the game settled. "
                    f"Now at map {destination['map_id']}, ({destination['x']}, {destination['y']})."
                )
            if not result["map_changed"]:
                visible_after = local_map(session.engine.memory, session.gameplay_catalog,
                                          ui_state(session.engine.memory))
                before_objects = {item["id"]: item for item in visible_before.get("objects", [])}
                changes = []
                for item in visible_after.get("objects", []):
                    old = before_objects.get(item["id"])
                    if old and (old["x"], old["y"]) != (item["x"], item["y"]):
                        changes.append({"id": item["id"], "from": {"x": old["x"], "y": old["y"]},
                                        "to": {"x": item["x"], "y": item["y"]}})
                if changes:
                    result["visible_object_changes"] = changes
                    if result["position_before"] == result["position_after"]:
                        result.pop("blocked_at", None)
                        result["outcome"] = ("Player position unchanged. Visible object positions changed. "
                                             "Check the updated map before treating the move as blocked.")
            movements = session.gameplay_memory.setdefault("movements", [])
            movements.append({key: result[key] for key in ("request", "position_before", "position_after_input", "position_after", "outcome", "tiles_moved", "map_changed")})
            del movements[:-8]
        from .working_memory import record
        record(session.gameplay_memory, session.current_decision or operation_id, result, facing_before, ui_state(session.engine.memory))
        session.gameplay_result = result
        session.gameplay_operations[operation_id] = result
        session.audit_memory("gameplay_command", result)
        return result
