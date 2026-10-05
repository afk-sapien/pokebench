"""Shared model loop, usage accounting, and explicit termination reasons."""
from __future__ import annotations

from collections import deque
import time

from .core import action, digest, encoded, write_json
from .providers import PROMPT, ProviderError
from .visual_feedback import VisualFeedback
from .recovery import checkpoint, mark_pending
from .memory import validate as validate_journal
from . import loop_budget


def run(session, provider, *, input_price=None, output_price=None, pause_after_decisions=None):
    prompt = getattr(provider, "prompt", PROMPT)
    recent = deque(maxlen=8)
    feedback = VisualFeedback(session.output, with_motion=getattr(provider, "motion_feedback", False), compact=getattr(provider, "compact_feedback", False), current_only=getattr(provider, "current_only", False)) if getattr(provider, "visual_feedback", False) else None
    invalid = 0
    decision_index = 0
    previous_unique_views = 0
    stagnant_decisions = 0
    area_budget = {"map_id": session.engine.evidence()["map_id"], "entry_tokens": 0, "entry_decision": 0}
    loop_state = loop_budget.initial()
    session.usage_available = True
    identity = {"provider": provider.provider, "model": provider.model,
                                      "prompt_sha256": digest(prompt.encode()), "memory": getattr(provider, "memory_protocol", "notebook-and-last-8-actions-v1"),
                                      "harness": getattr(provider, "harness", "direct-controller-v1"),
                                      "stagnation_guard": getattr(provider, "stagnation_guard", False),
                                      "reasoning_effort": getattr(provider, "reasoning_effort", None),
                                      "cli_version": getattr(provider, "cli_version", None),
                                      "configuration": getattr(provider, "config_identity", None),
                                      "token_budget_mode": getattr(provider, "token_budget_mode", "reported-between-decisions"),
                                      "max_output_tokens": getattr(provider, "max_output_tokens", None),
                                      "input_price_per_million": input_price, "output_price_per_million": output_price}
    if session.resume_state:
        if any(session.manifest["agent"].get(key) != value for key, value in identity.items()):
            raise ValueError("Resume requires the original provider configuration")
        saved = session.resume_state
        recent = saved["recent"]
        invalid, decision_index = saved["invalid"], saved["decision_index"]
        previous_unique_views = saved["previous_unique_views"]
        stagnant_decisions = saved["stagnant_decisions"]
        area_budget = saved["area_budget"]
        loop_state = saved["loop_state"]
        if feedback:
            feedback.__dict__.update(saved["feedback"])
        for key, value in saved["provider"].items():
            setattr(provider, key, value)
        session.audit_memory("resume", session.resume_metadata)
    session.manifest["agent"].update(identity)
    invocation_start = decision_index

    def save_boundary():
        if session.limits.max_area_tokens:
            used = session.usage["input_tokens"] + session.usage["output_tokens"]
            map_id = session.engine.evidence()["map_id"]
            if map_id != area_budget["map_id"]:
                session.audit_memory("area_budget_reset", {"decision": decision_index,
                    "previous_map_id": area_budget["map_id"], "map_id": map_id,
                    "tokens_in_previous_area": used - area_budget["entry_tokens"]})
                area_budget.update(map_id=map_id, entry_tokens=used, entry_decision=decision_index)
            spent = used - area_budget["entry_tokens"]
            write_json(session.output / "area_budget.json", {**area_budget,
                       "tokens_in_area": spent, "limit": session.limits.max_area_tokens,
                       "checked_decision": decision_index, "format": "consecutive-map-token-budget-v1"})
            if spent >= session.limits.max_area_tokens and not session.reason:
                session.finish("area_token_budget")
        if session.limits.max_loop_tokens:
            location = session.engine.structured(session.labels)["location"]
            monitored = loop_budget.update(loop_state, location, session.evaluator.awarded,
                session.usage["input_tokens"] + session.usage["output_tokens"], decision_index)
            write_json(session.output / "loop_budget.json", {**monitored, "limit": session.limits.max_loop_tokens})
            if monitored["tokens_without_progress"] >= session.limits.max_loop_tokens and not session.reason:
                session.finish("loop_token_budget")
        state = {"recent": recent, "invalid": invalid, "decision_index": decision_index,
                 "previous_unique_views": previous_unique_views, "stagnant_decisions": stagnant_decisions, "area_budget": area_budget, "loop_state": loop_state,
                 "feedback": {k: v for k, v in vars(feedback).items() if k != "output"} if feedback else None,
                 "provider": {k: getattr(provider, k) for k in ("previous_plan", "next_decision_token_estimate", "thread_id", "last_turn_id",
                              "total_usage", "context_tokens", "history", "look_back", "compactions", "pending_summary", "packet_baseline", "packet_sequence", "segment_turns", "segment_index")
                              if hasattr(provider, k)}}
        checkpoint(session, state)

    write_json(session.output / "manifest.json", session.manifest)
    (session.output / "prompt.txt").write_text(prompt)
    session._persist()
    save_boundary()
    try:
        while session.status()["state"] == "running":
            pause_request = session.output / "pause.request"
            if pause_request.exists() or (pause_after_decisions is not None and decision_index - invocation_start >= pause_after_decisions):
                session.audit_memory("pause", {"active_elapsed": session.elapsed()})
                session.finish("paused")
                save_boundary()
                pause_request.unlink(missing_ok=True)
                break
            if session.usage["calls"] >= session.limits.max_model_calls:
                session.finish("model_call_budget")
                break
            if session.usage["input_tokens"] + session.usage["output_tokens"] >= session.limits.max_total_tokens:
                session.finish("token_budget")
                break
            estimate = getattr(provider, "next_decision_token_estimate", None)
            remaining_tokens = session.limits.max_total_tokens - session.usage["input_tokens"] - session.usage["output_tokens"]
            if not hasattr(provider, "estimate_next_tokens") and type(estimate) is int and estimate > remaining_tokens:
                session.finish("token_budget")
                break
            if feedback and decision_index and getattr(provider, "stagnation_guard", False):
                if len(feedback.visits) > previous_unique_views:
                    stagnant_decisions = 0
                else:
                    stagnant_decisions += 1
                if stagnant_decisions >= session.limits.max_stagnant_decisions:
                    session.finish("observation_stagnation_budget")
                    break
            observation = session.observe()
            if session.journal_enabled:
                observation["journal"] = session.journal_context()
            if feedback:
                observation["controller_view"] = feedback.prepare(observation, decision_index + 1)
                previous_unique_views = len(feedback.visits)
                if getattr(provider, "stagnation_guard", False):
                    observation["controller_view"]["screen_history"]["consecutive_no_new_view_decisions"] = stagnant_decisions
                    observation["controller_view"]["screen_history"]["stagnant_decision_limit"] = session.limits.max_stagnant_decisions
            if hasattr(provider, "estimate_next_tokens"):
                from .bounded_context import ObservationBudgetError
                try:
                    estimate = provider.estimate_next_tokens(observation, session.notes, list(recent), session.limits)
                except ObservationBudgetError as error:
                    write_json(session.output / "error.json", {"kind": "observation_budget", "message": str(error)})
                    session.finish("observation_budget")
                    break
                if estimate > remaining_tokens:
                    session.finish("token_budget")
                    break
            started = time.monotonic()
            if provider.provider != "random":
                session.usage["calls"] += 1
            decision_index += 1
            session.current_decision = decision_index
            mark_pending(session, decision_index)
            try:
                decision, usage, record = provider.decide(
                    observation, session.notes, list(recent), session.limits,
                    session.limits.max_wall_seconds - session.elapsed())
            except ProviderError as error:
                session.usage["accounting_complete"] = False
                session.usage["model_seconds"] += time.monotonic() - started
                write_json(session.output / "error.json", {"kind": "provider_error", "message": str(error)})
                session.finish("provider_error")
                break
            duration = time.monotonic() - started
            if provider.provider != "random":
                session.usage["model_seconds"] += duration
            if provider.provider != "random" and (not isinstance(usage, dict) or any(
                    type(usage.get(key)) is not int or usage[key] < 0 for key in ("input_tokens", "output_tokens"))):
                session.usage["accounting_complete"] = False
                session.finish("usage_unavailable")
                break
            # Cache-specific fields stay in the original response for later billing analysis.
            session.usage["input_tokens"] += int(usage.get("input_tokens", 0))
            session.usage["output_tokens"] += int(usage.get("output_tokens", 0))
            if input_price is not None and output_price is not None:
                session.usage["estimated_cost_usd"] = (
                    session.usage["input_tokens"] * input_price + session.usage["output_tokens"] * output_price) / 1_000_000
            with (session.output / "decisions.jsonl").open("a") as stream:
                row = {"index": decision_index, "frame": session.frame, "decision": decision,
                       "seconds": duration, "usage": usage, "provider": record}
                stream.write(encoded(row).decode() + "\n")
            if session.usage["input_tokens"] + session.usage["output_tokens"] >= session.limits.max_total_tokens:
                session.finish("token_budget")
            if session.status()["state"] != "running":
                break
            if getattr(provider, "maintenance_decisions", False) and record.get("maintenance") in ("compaction", "look_back"):
                if decision.get("actions") != []:
                    raise ValueError("Maintenance cannot execute controller actions")
                if decision.get("notes") is not None:
                    maintenance_notes = provider.normalize_notes(decision["notes"])
                    if not isinstance(maintenance_notes, str) or len(maintenance_notes.encode()) > session.limits.max_note_bytes:
                        raise ValueError("Invalid maintenance notes")
                    session.write_notes(maintenance_notes)
                session.audit_memory(record["maintenance"], {"decision": decision_index, "usage": usage})
                save_boundary()
                continue
            try:
                if not isinstance(decision, dict):
                    raise ValueError("Expected a controller decision")
                planned = getattr(provider, "persistent_goal", False)
                plan = None
                if planned:
                    from .planning import validate as validate_plan
                    if "goal_plan" not in decision:
                        raise ValueError("Missing goal_plan. Use null to retain the existing goal")
                    plan = validate_plan(decision["goal_plan"], session.gameplay_memory.get("agent_plan"))
                    decision = {k: v for k, v in decision.items() if k != "goal_plan"}
                journal_request = None
                if session.journal_enabled:
                    journal_request = decision.get("journal")
                    validate_journal(session.journal_entries, journal_request)
                    decision = {k: v for k, v in decision.items() if k != "journal"}
                if set(decision) == {"actions", "notes"}:
                    raw_commands = decision["actions"]
                elif set(decision) == {"button", "hold_frames", "release_frames", "notes"}:
                    raw_commands = [{key: value for key, value in decision.items() if key != "notes"}]
                else:
                    raise ValueError("Unexpected decision fields")
                memory_only = journal_request is not None and (journal_request["writes"] or journal_request["delete"] or journal_request["query"] is not None)
                minimum = 0 if memory_only else 1
                if not isinstance(raw_commands, list) or not minimum <= len(raw_commands) <= session.limits.max_actions_per_decision:
                    raise ValueError("Invalid controller batch length")
                commands = []
                for raw in raw_commands:
                    if getattr(provider, "gameplay_commands", False):
                        from .gameplay_commands import validate
                        commands.append(validate(raw, session.limits))
                        continue
                    if not isinstance(raw, dict) or set(raw) != {"button", "hold_frames", "release_frames"}:
                        raise ValueError("Invalid controller action fields")
                    button = raw["button"]
                    if not isinstance(button, str):
                        raise ValueError("Invalid button")
                    commands.append(action(None if button == "wait" else button, raw["hold_frames"],
                                           raw["release_frames"], session.limits.max_action_frames))
                notes = decision["notes"]
                if hasattr(provider, "normalize_notes"):
                    notes = provider.normalize_notes(notes)
                if notes is not None and (not isinstance(notes, str) or len(notes.encode()) > session.limits.max_note_bytes):
                    raise ValueError("Notebook exceeds its UTF-8 byte limit")
            except (ValueError, TypeError) as error:
                invalid += 1
                recent.append({"error": str(error)})
                if invalid >= 3:
                    session.finish("invalid_model_response")
                save_boundary()
                continue
            invalid = 0
            if planned:
                from .planning import commit as commit_plan
                commit_plan(session, plan)
            if journal_request is not None:
                session.update_journal(journal_request)
            if notes is not None:
                session.write_notes(notes)
            for action_index, command in enumerate(commands, 1):
                if session.status()["state"] != "running":
                    break
                if getattr(provider, "gameplay_commands", False):
                    from .gameplay_commands import execute
                    def record_action(raw, before, result):
                        if feedback:
                            recent.append(feedback.record(raw, before, result["frame"], result["screenshot"]))
                    outcome = execute(session, f"decision-{decision_index}-{action_index}", command, record_action)
                    recent.append(outcome)
                    continue
                before_frame = session.frame
                result = session.act(f"decision-{decision_index}-{action_index}", **command)
                if feedback:
                    after = session.observe()
                    recent.append(feedback.record(command, before_frame, result["frame"], after["screenshot"]))
                else:
                    recent.append({"action": command, "frame": result["frame"], "new_achievements": result["new_achievements"]})
            if session.frame > observation["frame"] and hasattr(provider, "remember_executed_plan"):
                provider.remember_executed_plan(record, decision_index, session.frame)
            save_boundary()
    except KeyboardInterrupt:
        session.finish("interrupted")
    except Exception as error:
        write_json(session.output / "error.json", {"kind": "infrastructure_error", "type": type(error).__name__})
        session.finish("infrastructure_error")
        raise
    finally:
        if session.usage["accounting_complete"] and session.reason not in ("infrastructure_error", "interrupted"):
            save_boundary()
        provider.close()
        session.close()
    return session.status()
