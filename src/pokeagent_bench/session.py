"""One isolated run shared by direct runners and MCP."""
from __future__ import annotations

from .outcomes import outcome_category

import base64
from collections import OrderedDict
from copy import deepcopy
from dataclasses import asdict
from datetime import datetime, timezone
import json
from pathlib import Path
import platform
import threading
import time

from . import BENCHMARK_VERSION, __version__
from .core import FPS, Limits, action, core_provenance, digest, encoded, write_json
from .core import emulator_manifest, validate_emulator_manifest
from .game import RedEngine
from .challenges import create_challenge_evaluator, evidence, validate_objective
from .scoring import Evaluator


def prepare(rom: Path, output: Path):
    if output.exists():
        raise ValueError("Scenario destination already exists")
    engine = RedEngine(rom)
    try:
        for _ in range(1800):
            engine.tick()
        state = engine.save()
        output.mkdir(parents=True)
        (output / "initial.state").write_bytes(state)
        (output / "preview.png").write_bytes(engine.screenshot())
        manifest = {"format": 1, "name": "red-opening-v1", "game": "red",
                    "rom_sha256": engine.rom_sha256, "state_sha256": digest(state),
                    **emulator_manifest(), "core": core_provenance(), "setup_frames": 1800,
                    "preview_sha256": digest(engine.screenshot())}
        write_json(output / "scenario.json", manifest)
        return manifest
    finally:
        engine.close()


def initialize_controls(engine, scenario):
    """New fixtures begin with released buttons without advancing a game frame.

    Raw hardware states cannot retain pending host input releases. Queue the
    registered neutral-input policy before the first evaluated controller tick.
    Historical fixtures without this policy keep their original replay behavior.
    """
    policy = scenario.get('input_policy')
    if policy is None:
        return
    if policy != 'release-all-before-first-tick-v1':
        raise ValueError('Unknown fixture input policy')
    from .core import BUTTONS
    for button in BUTTONS:
        engine.release(button)


def load_engine(rom, scenario):
    manifest = json.loads((scenario / "scenario.json").read_text())
    state = (scenario / "initial.state").read_bytes()
    if manifest.get("format") != 1 or manifest.get("game") != "red":
        raise ValueError("Unsupported scenario format or game")
    validate_emulator_manifest(manifest)
    if manifest["state_sha256"] != digest(state):
        raise ValueError("Scenario state checksum mismatch")
    if manifest["rom_sha256"] != digest(rom.read_bytes()):
        raise ValueError("Scenario ROM checksum mismatch")
    preview = None
    if "preview_sha256" in manifest:
        preview = (scenario / "preview.png").read_bytes()
        if digest(preview) != manifest["preview_sha256"]:
            raise ValueError("Scenario preview checksum mismatch")
    engine = RedEngine(rom, state)
    from .navigation_conditions import install
    try:
        install(engine, manifest)
    except ValueError:
        engine.close()
        raise
    initialize_controls(engine, manifest)
    engine.initial_screen = preview
    return engine, manifest


class Session:
    def __init__(self, engine, output: Path, scenario: dict, *, track="structured", goal="first-gym",
                 limits=None, labels=None, agent=None, clock=time.monotonic, journal=False, gameplay_catalog=None, action_policy=None):
        if track not in ("structured", "visual", "gameplay") or goal not in ("first-gym", "campaign", "challenge"):
            raise ValueError("Unsupported observation track or goal")
        self.engine = engine
        self.output = output
        self.scenario = scenario
        from .action_policy import resolve, tested_skill
        self.tested_skill = tested_skill(scenario)
        self.action_policy = resolve(scenario, action_policy)
        catalog_id = scenario.get('task_id') or scenario.get('objective', {}).get('task_id')
        if catalog_id and (scenario.get('objective', {}).get('kind') in ('catalog-task', 'preparation-submission') or catalog_id == 'campaign-full-game'):
            from .evaluation_catalog import task_definition
            definition = task_definition(catalog_id)
            if self.action_policy != definition['action_policy']:
                raise ValueError('Catalog task controls cannot be overridden')
            if self.tested_skill != definition['tested_skill']:
                raise ValueError('Catalog task skill differs from its registered definition')
            if goal != ('campaign' if catalog_id == 'campaign-full-game' else 'challenge'):
                raise ValueError('Catalog task requires its registered goal')
            if scenario.get('catalog_sha256') and scenario['catalog_sha256'] != digest(encoded(definition)):
                raise ValueError('Catalog fixture specification changed')
        self.track = track
        self.goal = goal
        self.limits = limits or Limits()
        self.labels = labels or {}
        self.gameplay_catalog = gameplay_catalog or {}
        if track == "gameplay" and not self.gameplay_catalog:
            raise ValueError("Gameplay track requires a verified game data catalog")
        self.gameplay_memory = {}
        self.gameplay_inspection = None
        self.gameplay_result = None
        self.gameplay_operations = {}
        self.clock = clock
        self.lock = threading.RLock()
        self.frame = 0
        self.actions = 0
        self.notes = ""
        self.journal_enabled = journal
        self.journal_entries = {}
        self.journal_results = []
        self.current_decision = 0
        self.resume_state = None
        self.resume_metadata = None
        self.started = clock()
        self.ended = None
        self.reason = None
        self.closed = False
        self.operations = OrderedDict()
        self.operation_ids = set()
        self.trace_head = "0" * 64
        self.campaign_tracking = scenario.get('task_id') == 'campaign-full-game'
        if self.campaign_tracking and goal != 'campaign':
            raise ValueError('Full-game catalog campaigns require goal=campaign')
        self.objective = validate_objective(scenario.get("objective")) if goal == "challenge" else None
        self.evaluator = (create_challenge_evaluator(evidence(engine, self.objective), self.objective)
                          if self.objective else Evaluator(engine.evidence()))
        if self.campaign_tracking:
            from .campaign_runtime import CampaignTracker, read_campaign_evidence
            campaign_start = read_campaign_evidence(engine)
            if campaign_start['party'] or campaign_start['badges'] or campaign_start['hall_of_fame'] or campaign_start['map_id'] != 38:
                raise ValueError('Full-game campaigns must start in the bedroom without a starter or badges')
            self.evaluator = CampaignTracker(json.loads(encoded(campaign_start)))
        self.score_max = 1 if self.objective else 75 if goal == "first-gym" else 1000
        if not self.objective and not self.campaign_tracking and (self.evaluator.initial_keys or self.evaluator.baseline["hall_of_fame"]):
            raise ValueError("Scored runs require an opening scenario without earned milestones")
        output.mkdir(parents=True, exist_ok=False)
        from .recovery import lock_run
        self.run_lease = lock_run(output)
        (output / "initial.state").write_bytes(engine.save())
        self.manifest = {"format": 1, "benchmark": BENCHMARK_VERSION, "package_version": __version__,
                         "journal": journal, "recovery_protocol": "decision-boundary-v1",
                         "core": core_provenance(),
                         "python_version": platform.python_version(), "platform": platform.platform(),
                         "source_sha256": digest(encoded({path.name: digest(path.read_bytes())
                                                          for path in sorted(Path(__file__).parent.glob("*.py"))})),
                         "created_at": datetime.now(timezone.utc).isoformat(),
                         "action_policy": self.action_policy, "tested_skill": self.tested_skill,
                         "track": track, "goal": goal, "limits": asdict(self.limits),
                         "scenario": scenario, "labels_sha256": digest(encoded(self.labels)),
                         "agent": agent or {"provider": "external-mcp", "model": "unspecified"},
                         **emulator_manifest(),
                         "initial_sha256": digest((output / "initial.state").read_bytes())}
        if self.campaign_tracking or self.objective and self.objective['kind'] in ('catalog-task', 'preparation-submission'):
            from .evaluation_catalog import task_definition
            task_id = scenario.get('task_id') or self.objective['task_id']
            task = task_definition(task_id)
            self.manifest['evaluation_spec_sha256'] = digest(encoded(task))
            self.manifest['benchmark_track'] = 'pokebench-long' if self.campaign_tracking else 'pokebench'
            self.manifest['scoring_protocol'] = 'campaign-progress-v1' if self.campaign_tracking else 'catalog-tasks-v1'
        if track == "gameplay":
            from .gameplay import POLICY, catalog_hash
            self.manifest["observation_policy"] = POLICY
            self.manifest["catalog_sha256"] = catalog_hash(self.gameplay_catalog)
        write_json(output / "manifest.json", self.manifest)
        self.usage = {"calls": 0, "input_tokens": 0, "output_tokens": 0, "model_seconds": 0.0,
                      "estimated_cost_usd": None, "accounting_complete": True}
        self.usage_available = self.manifest["agent"]["provider"] != "external-mcp"
        self._persist()

    def elapsed(self):
        return max(0, (self.ended if self.ended is not None else self.clock()) - self.started)

    def _budget(self):
        if self.reason:
            return
        if self.elapsed() >= self.limits.max_wall_seconds:
            self.finish("wall_budget")
        elif self.frame >= self.limits.max_frames:
            self.finish("frame_budget")
        elif self.actions >= self.limits.max_actions:
            self.finish("action_budget")

    def finish(self, reason):
        with self.lock:
            if not self.reason:
                self.reason = reason
                self.ended = self.clock()
                self._persist()
                (self.output / "final.state").write_bytes(self.engine.save())

    def status(self):
        with self.lock:
            self._budget()
            return {"state": "paused" if self.reason == "paused" else "finished" if self.reason else "running", "stop_reason": self.reason,
                    "outcome_category": outcome_category(self.reason, state="running" if not self.reason else "finished"),
                    "completed": self.reason == "completed", "goal": self.goal, "track": self.track,
                    "score": self.evaluator.score, "score_max": self.score_max,
                    "achievements": list(self.evaluator.awarded.values()), "frames": self.frame,
                    "emulated_seconds": self.frame / FPS, "wall_seconds": round(self.elapsed(), 6),
                    "actions": self.actions, "usage": self._public_usage(),
                    "remaining": {"frames": max(0, self.limits.max_frames - self.frame),
                                  "actions": max(0, self.limits.max_actions - self.actions),
                                  "wall_seconds": max(0, self.limits.max_wall_seconds - self.elapsed()),
                                  "model_calls": max(0, self.limits.max_model_calls - self.usage["calls"])
                                  if self.usage_available else None},
                    "decision_budget": {"limit": self.limits.max_model_calls,
                                        "used": self.usage["calls"] if self.usage_available else None,
                                        "remaining": max(0, self.limits.max_model_calls - self.usage["calls"])
                                        if self.usage_available else None},
                    "token_budget": {"limit": self.limits.max_total_tokens,
                                     "used": self.usage["input_tokens"] + self.usage["output_tokens"]
                                     if self.usage_available else None,
                                     "enforcement": self.manifest["agent"].get("token_budget_mode", "reported-between-decisions")
                                     if self.usage_available else "unavailable"},
                    "action_policy": self.action_policy, "tested_skill": self.tested_skill,
                    "max_action_frames": self.limits.max_action_frames,
                    "max_dialogue_frames": self.limits.max_dialogue_frames,
                    "max_note_bytes": self.limits.max_note_bytes,
                    "max_actions_per_decision": self.limits.max_actions_per_decision,
                    "objective": self.objective["description"] if self.objective else
                    "Earn the Boulder Badge by defeating Brock." if self.goal == "first-gym" else
                    "Complete Pokemon Red: earn all eight gym badges, defeat the Elite Four and Champion, and enter the Hall of Fame."}

    def _public_usage(self):
        if self.usage_available:
            return {"available": True, **deepcopy(self.usage)}
        return {"available": False, **{key: None for key in self.usage}}

    def _observation(self):
        result = {"frame": self.frame, "status": self.status(),
                  "screenshot": {"mime_type": "image/png",
                                 "base64": base64.b64encode(self.engine.screenshot()).decode()}}
        if self.track == "structured":
            result["game"] = self.engine.structured(self.labels)
        elif self.track == "gameplay":
            from .gameplay import observe_gameplay
            result["game"] = observe_gameplay(self)
        return result

    def observe(self):
        with self.lock:
            return self._observation()

    def read_notes(self):
        with self.lock:
            return {"text": self.notes, "max_bytes": self.limits.max_note_bytes}

    def write_notes(self, text):
        with self.lock:
            self._budget()
            if self.reason:
                raise ValueError(f"Run finished: {self.reason}")
            if not isinstance(text, str) or len(text.encode()) > self.limits.max_note_bytes:
                raise ValueError(f"Notes must fit in {self.limits.max_note_bytes} UTF-8 bytes")
            self.audit_memory("notebook", {"before": self.notes, "after": text})
            self.notes = text
            (self.output / "notes.txt").write_text(text)
            return self.read_notes()

    def audit_memory(self, kind, content):
        row = {"decision": self.current_decision, "frame": self.frame, "kind": kind, **content}
        with (self.output / "memory.jsonl").open("a") as stream:
            stream.write(encoded(row).decode() + "\n")

    def journal_context(self):
        from .memory import CONFIG
        return {"limits": dict(CONFIG), "entry_count": len(self.journal_entries),
                "results": deepcopy(self.journal_results)}

    def update_journal(self, request):
        from .memory import search, validate
        with self.lock:
            if not self.journal_enabled or self.reason:
                raise ValueError("Journal is unavailable")
            updated = validate(self.journal_entries, request)
            results = search(updated, request["query"])
            if request["writes"] or request["delete"] or request["query"] is not None:
                self.audit_memory("journal", {"request": request, "results": results,
                                  "before_sha256": digest(encoded(self.journal_entries)),
                                  "after_sha256": digest(encoded(updated))})
            self.journal_entries, self.journal_results = updated, results

    def act(self, operation_id, button, hold_frames=8, release_frames=2, *, on_frame=None):
        with self.lock:
            if not isinstance(operation_id, str) or not 1 <= len(operation_id) <= 128:
                raise ValueError("An operation_id of 1 to 128 characters is required")
            request = action(button, hold_frames, release_frames, self.limits.max_action_frames)
            if operation_id in self.operations:
                old, result = self.operations[operation_id]
                if old != request:
                    raise ValueError("Operation ID was already used for a different action")
                return deepcopy(result)
            if operation_id in self.operation_ids:
                raise ValueError("Operation already executed but response expired. Use observe()")
            self._budget()
            if self.reason:
                raise ValueError(f"Run finished: {self.reason}")
            self.operation_ids.add(operation_id)
            before = self.frame
            new_awards = []
            started = self.clock()
            try:
                recorder = getattr(self.evaluator, 'observe_input', None)
                if callable(recorder):
                    recorder(button, self._evaluation_evidence())
                if button:
                    self.engine.press(button)
                for index in range(hold_frames + release_frames):
                    if index == hold_frames and button:
                        self.engine.release(button)
                    if self.frame >= self.limits.max_frames or self.elapsed() >= self.limits.max_wall_seconds:
                        break
                    self.engine.tick()
                    self.frame += 1
                    if on_frame is not None:
                        on_frame()
                    new_awards.extend(self._evaluate_frame())
                    if getattr(self.evaluator, 'disqualified', False):
                        break
                    if (self.objective and self.objective['kind'] in ('battle-milestone','guarded-milestones','encounter-capture','resource-route')
                            and self.evaluator.battle_disqualified):
                        break
                    if self.evaluator.complete(self.goal):
                        break
            except Exception:
                self.finish("infrastructure_error")
                raise
            finally:
                if button:
                    self.engine.release(button)
            self.actions += 1
            self._record(operation_id, request, before, new_awards, self.clock() - started)
            if (self.objective and self.objective['kind'] in ('battle-milestone','guarded-milestones','encounter-capture','resource-route')
                    and self.evaluator.battle_disqualified):
                self.finish('battle_loss')
            if getattr(self.evaluator, 'disqualified', False):
                self.finish('challenge_failed')
            if self.evaluator.complete(self.goal):
                self.finish("completed")
            self._budget()
            result = self._observation()
            result["executed_frames"] = self.frame - before
            result["new_achievements"] = new_awards
            self.operations[operation_id] = (request, deepcopy(result))
            if len(self.operations) > 64:
                self.operations.popitem(last=False)
            self._persist()
            return result

    def _evaluation_evidence(self):
        if self.campaign_tracking:
            from .campaign_runtime import read_campaign_evidence
            return json.loads(encoded(read_campaign_evidence(self.engine)))
        state = evidence(self.engine, self.objective)
        return state['catalog'] if self.objective and self.objective['kind'] == 'catalog-task' else state

    def _evaluate_frame(self):
        facts = self._evaluation_evidence()
        if self.campaign_tracking:
            return self.evaluator.observe(facts, self.frame, self.elapsed(), decision=self.current_decision,
                tokens=self.usage['input_tokens'] + self.usage['output_tokens'], actions=self.actions + 1)
        return self.evaluator.observe(facts, self.frame, self.elapsed())

    def wait(self, operation_id, frames):
        return self.act(operation_id, None, frames, 0)

    def _record(self, operation_id, request, before, awards, duration):
        screenshot = self.engine.screenshot()
        row = {"operation_id": operation_id, "action": request, "before_frame": before,
               "frame": self.frame, "executed_frames": self.frame - before,
               "evidence": self._evaluation_evidence(), "screenshot_sha256": digest(screenshot),
               "achievements": awards, "execution_seconds": duration, "previous_hash": self.trace_head}
        self.trace_head = digest(encoded(row))
        row["hash"] = self.trace_head
        with (self.output / "actions.jsonl").open("a") as stream:
            stream.write(encoded(row).decode() + "\n")
        if awards:
            directory = self.output / "milestones"
            directory.mkdir(exist_ok=True)
            stem = directory / f"{self.frame:012d}"
            stem.with_suffix(".png").write_bytes(screenshot)
            saved = self.engine.save()
            stem.with_suffix(".state").write_bytes(saved)
            write_json(stem.with_suffix(".json"), {"frame": self.frame, "state_sha256": digest(saved),
                                                   "trace_head": self.trace_head, "achievements": awards})

    def _persist(self):
        # Build status directly to avoid recursively enforcing budgets while finishing.
        result = {"state": "paused" if self.reason == "paused" else "finished" if self.reason else "running", "stop_reason": self.reason,
                    "outcome_category": outcome_category(self.reason, state="running" if not self.reason else "finished"),
                  "completed": self.reason == "completed", "goal": self.goal, "track": self.track,
                  "score": self.evaluator.score, "score_max": self.score_max,
                  "achievements": list(self.evaluator.awarded.values()), "frames": self.frame,
                  "emulated_seconds": self.frame / FPS, "wall_seconds": round(self.elapsed(), 6),
                  "actions": self.actions, "usage": self._public_usage(), "trace_head": self.trace_head,
                  "updated_at": datetime.now(timezone.utc).isoformat()}
        if self.campaign_tracking:
            from .campaign_report import enrich_current_profile
            result['campaign'] = enrich_current_profile(self.engine, self.evaluator.report())
            write_json(self.output / 'campaign.json', result['campaign'])
        if self.objective and self.objective['kind'] == 'catalog-task':
            result['task_id'] = self.objective['task_id']
            result['failure_reason'] = getattr(self.evaluator, 'disqualification_reason', None)
        write_json(self.output / "result.json", result)
        temporary = self.output / "latest.tmp"
        temporary.write_bytes(self.engine.screenshot())
        temporary.replace(self.output / "latest.png")

    def close(self):
        with self.lock:
            if not self.closed:
                self.finish("interrupted")
                (self.output / "final.state").write_bytes(self.engine.save())
                self.engine.close()
                self.closed = True
                self.run_lease.close()


def replay(rom: Path, run: Path):
    manifest = json.loads((run / "manifest.json").read_text())
    from .evaluation_catalog import validate_run_spec
    validate_run_spec(manifest)
    state = (run / "initial.state").read_bytes()
    validate_emulator_manifest(manifest)
    if digest(state) != manifest["initial_sha256"]:
        raise ValueError("Run state checksum mismatch")
    if digest(rom.read_bytes()) != manifest["scenario"]["rom_sha256"]:
        raise ValueError("ROM checksum mismatch")
    engine = RedEngine(rom, state)
    try:
        from .navigation_conditions import install
        install(engine, manifest["scenario"])
        initialize_controls(engine, manifest["scenario"])
        objective = validate_objective(manifest["scenario"].get("objective")) if manifest["goal"] == "challenge" else None
        campaign_tracking = manifest.get('scoring_protocol') == 'campaign-progress-v1'
        def replay_evidence():
            if campaign_tracking:
                from .campaign_runtime import read_campaign_evidence
                return json.loads(encoded(read_campaign_evidence(engine)))
            state = evidence(engine, objective)
            return state['catalog'] if objective and objective['kind'] == 'catalog-task' else state
        if campaign_tracking:
            from .campaign_runtime import CampaignTracker
            evaluator = CampaignTracker(replay_evidence())
        else:
            evaluator = create_challenge_evaluator(evidence(engine, objective), objective) if objective else Evaluator(engine.evidence())
    except Exception:
        engine.close()
        raise
    head = "0" * 64
    frame = 0
    count = 0
    try:
        path = run / "actions.jsonl"
        for line in path.read_text().splitlines() if path.exists() else []:
            row = json.loads(line)
            claimed = row.pop("hash")
            if row["previous_hash"] != head or digest(encoded(row)) != claimed or row["before_frame"] != frame:
                raise ValueError(f"Broken action log at action {count + 1}")
            head = claimed
            command = row["action"]
            action(**command, maximum=manifest["limits"]["max_action_frames"])
            if not 0 <= row["executed_frames"] <= command["hold_frames"] + command["release_frames"]:
                raise ValueError("Recorded action duration is outside the action request")
            button = command["button"]
            recorder = getattr(evaluator, 'observe_input', None)
            if callable(recorder):
                recorder(button, replay_evidence())
            if button:
                engine.press(button)
            awards = []
            for index in range(row["executed_frames"]):
                if button and index == command["hold_frames"]:
                    engine.release(button)
                engine.tick()
                frame += 1
                awards.extend(evaluator.observe(replay_evidence(), frame, 0))
            if button:
                engine.release(button)
            expected_awards = [(a["id"], a["points"], a["frame"]) for a in row["achievements"]]
            actual_awards = [(a["id"], a["points"], a["frame"]) for a in awards]
            if (frame != row["frame"] or replay_evidence() != row["evidence"]
                    or digest(engine.screenshot()) != row["screenshot_sha256"] or expected_awards != actual_awards):
                raise ValueError(f"Replay diverged at action {count + 1}")
            count += 1
        result = json.loads((run / "result.json").read_text())
        if (head != result["trace_head"] or frame != result["frames"] or evaluator.score != result["score"]
                or count != result["actions"]):
            raise ValueError("Final result differs from replay")
        if result["completed"] and not evaluator.complete(manifest["goal"]):
            raise ValueError("Claimed completion is not supported by replay evidence")
        return {"verified": True, "actions": count, "frames": frame, "score": evaluator.score, "trace_head": head}
    finally:
        engine.close()


def checkpoint(rom: Path, state_path: Path, output: Path, *, name: str, objective: dict):
    """Import a private PyBoy save as a checksum-pinned challenge start."""
    objective = validate_objective(objective)
    if output.exists():
        raise ValueError("Scenario destination already exists")
    if not name or len(name) > 120:
        raise ValueError("A checkpoint needs a short name")
    state = state_path.read_bytes()
    engine = RedEngine(rom, state)
    try:
        # One declared setup wait renders the imported state before capturing the checkpoint.
        # Runs load this new state and its paired image without advancing the game.
        engine.tick()
        initial_state = engine.save()
        preview = engine.screenshot()
        create_challenge_evaluator(evidence(engine, objective), objective)
        manifest = {"format": 1, "name": name, "game": "red", "objective": objective,
                    "rom_sha256": engine.rom_sha256, "state_sha256": digest(initial_state),
                    "preview_sha256": digest(preview), "setup_wait_frames": 1,
                    **emulator_manifest(), "core": core_provenance(),
                    "curation": "unverified", "source_state_sha256": digest(state)}
        output.mkdir(parents=True)
        (output / "initial.state").write_bytes(initial_state)
        (output / "preview.png").write_bytes(preview)
        write_json(output / "scenario.json", manifest)
        return manifest
    finally:
        engine.close()
