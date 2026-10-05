"""Command-line entry points. All generated artifacts live outside tracked source."""
from __future__ import annotations

import argparse
from dataclasses import asdict
import json
import math
from pathlib import Path
import sys

from .core import Limits
from .session import Session, checkpoint, load_engine, prepare, replay


def load_labels(path):
    if path is None:
        return {}
    source = json.loads(path.read_text())
    output = {}
    for kind in ("maps", "species", "items", "moves"):
        output[kind] = {}
        for key, value in source.get(kind, {}).items():
            name = value.get("name") if isinstance(value, dict) else value
            if str(key).isdigit() and isinstance(name, str) and len(name) <= 100:
                output[kind][str(key)] = name
    return output


def parser():
    root = argparse.ArgumentParser(description="Controlled Pokemon Red agent benchmarks")
    sub = root.add_subparsers(dest="command", required=True)
    setup = sub.add_parser("prepare", help="Create a fixed opening scenario using fresh SRAM")
    setup.add_argument("--rom", type=Path, required=True)
    setup.add_argument("--output", type=Path, required=True)
    capture = sub.add_parser("checkpoint", help="Import a private PyBoy save with an explicit challenge objective")
    capture.add_argument("--rom", type=Path, required=True)
    capture.add_argument("--state", type=Path, required=True)
    capture.add_argument("--objective", type=Path, required=True)
    capture.add_argument("--name", required=True)
    capture.add_argument("--output", type=Path, required=True)
    pause = sub.add_parser("pause", help="Request a pause at the next complete decision boundary")
    pause.add_argument("--run", type=Path, required=True)
    resume = sub.add_parser("resume", help="Resume a controlled Codex run with its original settings and budget")
    resume.add_argument("--rom", type=Path, required=True)
    resume.add_argument("--run", type=Path, required=True)
    resume.add_argument("--pause-after-decisions", type=int)
    for name in ("run", "mcp"):
        command = sub.add_parser(name, help="Run a model" if name == "run" else "Expose the controller over stdio MCP")
        command.add_argument("--rom", type=Path, required=True)
        command.add_argument("--scenario", type=Path, required=True)
        command.add_argument("--output", type=Path, required=True)
        command.add_argument("--labels", type=Path)
        command.add_argument("--game-data", type=Path, help="Private verified game data bundle for the gameplay track")
        command.add_argument("--track", choices=("structured", "visual", "gameplay"), default="structured")
        command.add_argument("--goal", choices=("first-gym", "campaign", "challenge"), default="first-gym")
        for key, default in asdict(Limits()).items():
            command.add_argument("--" + key.replace("_", "-"), type=float if isinstance(default, float) else int,
                                 default=default)
        if name == "run":
            command.add_argument("--journal", action="store_true", help="Enable the bounded agent-authored journal for compact Codex")
            command.add_argument("--pause-after-decisions", type=int)
            command.add_argument("--provider", choices=("random", "openai", "anthropic", "codex", "claude"), required=True)
            command.add_argument("--model")
            command.add_argument("--codex-policy", choices=("standard", "grounded", "grounded-motion", "compact", "continuous", "gameplay", "bounded"), default="compact",
                                 help="Compact is the default. Legacy policies remain selectable for comparisons")
            command.add_argument("--context-turns", type=int, default=8, help="Maximum responses per bounded conversation segment")
            command.add_argument("--compact-at", type=int, help="Context threshold, default 12000 for bounded, 32000 for legacy gameplay and 24000 for visual")
            command.add_argument("--observation-format", choices=("json", "text"), default="json",
                                 help="Gameplay input format. Text is an experimental deterministic presentation")
            command.add_argument("--presentation", choices=("current", "strip"), default="current")
            command.add_argument("--response-contract", choices=("simple", "assessment"), default="simple")
            command.add_argument("--fresh-decisions", action="store_true",
                                 help="Comparison mode: restart every decision. Default retains conversation with periodic summaries")
            command.add_argument("--reasoning-effort", choices=("low", "medium", "high", "xhigh"), default="low")
            command.add_argument("--seed", type=int, default=7)
            command.add_argument("--max-output-tokens", type=int, default=2048, help="Per-response API cap, not supported by Codex CLI")
            command.add_argument("--input-price", type=float, help="USD per million input tokens")
            command.add_argument("--output-price", type=float, help="USD per million output tokens")
    check = sub.add_parser("replay", help="Replay actions and verify frame, score, and image evidence")
    check.add_argument("--rom", type=Path, required=True)
    check.add_argument("--run", type=Path, required=True)
    review = sub.add_parser("review", help="Export a short, offline decision slideshow from finished visual runs")
    review.add_argument("--run", type=Path, nargs="+", required=True)
    review.add_argument("--output", type=Path, required=True)
    review.add_argument("--seconds", type=int, help="Optional total playback seconds per run, default is 8 decisions per second")
    view = sub.add_parser("dashboard", help="Serve a local read-only results viewer")
    view.add_argument("--runs", type=Path, default=Path("runs"))
    view.add_argument("--port", type=int, default=8941)
    report = sub.add_parser("report", help="Print comparable trial groups and aggregate results as JSON")
    report.add_argument("--runs", type=Path, default=Path("runs"))
    paper = sub.add_parser("paper-export", help="Freeze sanitized results and provenance for the manuscript")
    paper.add_argument("--runs", type=Path, default=Path("runs"))
    paper.add_argument("--output", type=Path, default=Path("paper/analysis/inputs/benchmark.json"))
    suite = sub.add_parser("suite", help="Prepare, validate and run versioned benchmark suites")
    modes = suite.add_subparsers(dest="suite_command", required=True)
    catalog_suite = modes.add_parser("catalog", help="Show a suite definition without model calls")
    catalog_suite.add_argument("--suite-id", default="red-basic-v1")
    prepare_suite = modes.add_parser("prepare", help="Bind local fixtures and replay-check their references")
    prepare_suite.add_argument("--suite-id", default="red-basic-v1")
    prepare_suite.add_argument("--rom", type=Path, required=True)
    prepare_suite.add_argument("--bindings", type=Path, required=True)
    prepare_suite.add_argument("--output", type=Path, required=True)
    combine_suite = modes.add_parser("combine", help="Assemble unchanged fixtures from verified suites")
    combine_suite.add_argument("--suite-id", required=True)
    combine_suite.add_argument("--sources", type=Path, nargs="+", required=True)
    combine_suite.add_argument("--output", type=Path, required=True)
    revalidate_suite = modes.add_parser("revalidate", help="Rebuild fixture proofs after a Core upgrade")
    revalidate_suite.add_argument("--suite", type=Path, required=True)
    revalidate_suite.add_argument("--rom", type=Path, required=True)
    revalidate_suite.add_argument("--output", type=Path, required=True)
    validate_suite = modes.add_parser("validate")
    validate_suite.add_argument("--suite", type=Path, required=True)
    validate_suite.add_argument("--rom", type=Path, required=True)
    for name in ("run", "resume"):
        batch = modes.add_parser(name)
        batch.add_argument("--suite", type=Path, required=True)
        batch.add_argument("--rom", type=Path, required=True)
        batch.add_argument("--game-data", type=Path, required=True)
        batch.add_argument("--output", type=Path, required=True)
        batch.add_argument("--total-token-budget", type=int, required=True)
        if name == "run":
            batch.add_argument("--models", nargs="+", required=True)
            batch.add_argument("--repeats", type=int, default=1)
            batch.add_argument("--dry-run", action="store_true")
    suite_report = modes.add_parser("report")
    suite_report.add_argument("--suite", type=Path, required=True)
    suite_report.add_argument("--batch", type=Path)
    suite_report.add_argument("--output", type=Path, required=True)
    suite_report.add_argument("--historical-run", type=Path, nargs="*", default=[])
    return root


def execute(args):
    if args.command == "suite":
        from . import suite
        if args.suite_command == "catalog":
            return suite.definition_for(args.suite_id)
        if args.suite_command == "prepare":
            return suite.prepare(args.rom, args.bindings, args.output, args.suite_id)
        if args.suite_command == "combine":
            return suite.combine(args.sources, args.output, args.suite_id)
        if args.suite_command == "revalidate":
            return suite.revalidate(args.suite, args.rom, args.output)
        if args.suite_command == "validate":
            return suite.validate(args.suite, args.rom, replay_references=True)
        if args.suite_command == "report":
            from .suite_report import export_report
            return export_report(args.suite, args.batch, args.output, args.historical_run)
        if args.suite_command == "run" and args.dry_run:
            return suite.plan(args.suite, args.models, args.repeats)
        return suite.run_batch(args.suite, args.rom, args.game_data, args.output,
                               models=getattr(args, "models", None), repeats=getattr(args, "repeats", 1),
                               budget=args.total_token_budget, resume=args.suite_command == "resume")
    if getattr(args, "pause_after_decisions", None) is not None and args.pause_after_decisions < 1:
        raise ValueError("pause-after-decisions must be positive")
    if args.command == "pause":
        result = json.loads((args.run / "result.json").read_text())
        if result["state"] != "running":
            raise ValueError("Only a running run can be paused")
        (args.run / "pause.request").write_text("Pause at the next complete decision boundary\n")
        return {"pause_requested": True, "run": str(args.run)}
    if args.command == "resume":
        from .recovery import resume
        from .runner import run
        from .codex_provider import CodexProvider
        from .compact_provider import CompactCodexProvider
        from .grounded_provider import GroundedCodexProvider, MotionCodexProvider
        from .journal_provider import JournalCodexProvider
        from .continuous_provider import ContinuousCodexProvider
        from .gameplay_provider import GameplayCodexProvider
        from .bounded_provider import BoundedGameplayProvider
        from .claude_provider import ClaudeCodeProvider
        manifest = json.loads((args.run / "manifest.json").read_text())
        agent = manifest["agent"]
        classes = {cls.harness: cls for cls in (CodexProvider, CompactCodexProvider, GroundedCodexProvider,
                                               MotionCodexProvider, JournalCodexProvider, ContinuousCodexProvider, GameplayCodexProvider, BoundedGameplayProvider, ClaudeCodeProvider)}
        if agent["provider"] not in ("codex", "claude-code") or agent.get("harness") not in classes:
            raise ValueError("CLI resume supports controlled Codex and Claude Code runs")
        extra = {}
        if agent["harness"] in (ContinuousCodexProvider.harness, GameplayCodexProvider.harness, BoundedGameplayProvider.harness, ClaudeCodeProvider.harness):
            extra = {k: v for k, v in agent["configuration"].items() if k in ("compact_at", "presentation", "response_contract", "continuity", "observation_format", "context_turns")}
        provider = classes[agent["harness"]](agent["model"], reasoning_effort=agent["reasoning_effort"], **extra)
        session = None
        try:
            session = resume(args.rom, args.run)
            return run(session, provider, pause_after_decisions=args.pause_after_decisions)
        finally:
            if session:
                session.close()
            provider.close()
    if args.command == "review":
        from .review import export_review
        return export_review(args.run, args.output, args.seconds)
    if args.command == "paper-export":
        from .paper_export import export_results
        return export_results(args.runs, args.output)
    if args.command == "checkpoint":
        return checkpoint(args.rom, args.state, args.output, name=args.name,
                          objective=json.loads(args.objective.read_text()))
    if args.command == "prepare":
        return prepare(args.rom, args.output)
    if args.command == "replay":
        return replay(args.rom, args.run)
    if args.command == "report":
        from .report import comparison_report
        return comparison_report(args.runs)
    if args.command == "dashboard":
        import uvicorn
        from .dashboard import create_app
        uvicorn.run(create_app(args.runs), host="127.0.0.1", port=args.port)
        return None
    limits = Limits(**{key: getattr(args, key) for key in asdict(Limits())})
    labels = load_labels(args.labels)
    gameplay_catalog = None
    if args.track == "gameplay":
        if args.game_data is None:
            raise ValueError("Gameplay track requires --game-data")
        from .gameplay import load_catalog
        gameplay_catalog = load_catalog(args.game_data)
        if args.command == "run" and not (args.provider == "claude" or (args.provider == "codex" and args.codex_policy in ("gameplay", "bounded"))):
            raise ValueError("Gameplay runs require --provider codex --codex-policy gameplay")
    provider = None
    agent = None
    if args.command == "run":
        from .providers import APIProvider, RandomProvider
        if args.observation_format != "json" and not (args.provider == "claude" or (args.provider == "codex" and args.codex_policy in ("gameplay", "bounded"))):
            raise ValueError("Text observations require the gameplay Codex policy")
        if args.journal and (args.provider != "codex" or args.codex_policy != "compact"):
            raise ValueError("Journal requires the compact Codex policy")
        if args.max_output_tokens < 1:
            raise ValueError("max-output-tokens must be positive")
        if (args.input_price is None) != (args.output_price is None):
            raise ValueError("Supply both input and output prices, or neither")
        if any(p is not None and (not math.isfinite(p) or p < 0) for p in (args.input_price, args.output_price)):
            raise ValueError("Prices must be nonnegative and finite")
        if args.provider == "claude":
            from .claude_provider import ClaudeCodeProvider
            if args.track != "gameplay" or args.codex_policy != "bounded" or args.presentation != "current" or args.response_contract != "simple" or args.fresh_decisions:
                raise ValueError("Claude requires gameplay track, bounded policy and retained current/simple presentation")
            if args.input_price is not None or args.output_price is not None:
                raise ValueError("Subscription usage is not API-priced")
            provider = ClaudeCodeProvider(args.model, reasoning_effort=args.reasoning_effort,
                context_turns=args.context_turns,
                compact_at=12000 if args.compact_at is None else args.compact_at)
        elif args.provider == "codex":
            from .codex_provider import CodexProvider
            if args.input_price is not None or args.output_price is not None:
                raise ValueError("Subscription usage is not API-priced")
            if args.codex_policy in ("gameplay", "bounded"):
                if args.track != "gameplay" or args.response_contract != "simple" or args.presentation != "current":
                    raise ValueError("Gameplay policy requires gameplay track and current/simple presentation")
                from .gameplay_provider import GameplayCodexProvider
                from .bounded_provider import BoundedGameplayProvider
                cls = BoundedGameplayProvider if args.codex_policy == "bounded" else GameplayCodexProvider
                options = {"context_turns": args.context_turns} if args.codex_policy == "bounded" else {}
                provider = cls(args.model, reasoning_effort=args.reasoning_effort,
                    compact_at=cls.default_compact_at if args.compact_at is None else args.compact_at, continuity=not args.fresh_decisions,
                    observation_format=args.observation_format, **options)
            elif args.codex_policy == "continuous":
                if args.track != "visual":
                    raise ValueError("Continuous gameplay requires --track visual")
                from .continuous_provider import ContinuousCodexProvider
                provider = ContinuousCodexProvider(args.model, reasoning_effort=args.reasoning_effort,
                    compact_at=24000 if args.compact_at is None else args.compact_at, presentation=args.presentation,
                    response_contract=args.response_contract, continuity=not args.fresh_decisions)
            elif args.codex_policy == "compact":
                from .compact_provider import CompactCodexProvider
                from .journal_provider import JournalCodexProvider
                cls = JournalCodexProvider if args.journal else CompactCodexProvider
                provider = cls(args.model, reasoning_effort=args.reasoning_effort)
            elif args.codex_policy == "grounded-motion":
                from .grounded_provider import MotionCodexProvider
                provider = MotionCodexProvider(args.model, reasoning_effort=args.reasoning_effort)
            elif args.codex_policy == "grounded":
                from .grounded_provider import GroundedCodexProvider
                provider = GroundedCodexProvider(args.model, reasoning_effort=args.reasoning_effort)
            else:
                provider = CodexProvider(args.model, reasoning_effort=args.reasoning_effort)
        else:
            provider = RandomProvider(args.seed) if args.provider == "random" else APIProvider(
                args.provider, args.model, max_output_tokens=args.max_output_tokens)
        agent = {"provider": provider.provider, "model": provider.model}
        if args.provider == "random":
            agent["seed"] = args.seed
    engine = None
    session = None
    try:
        engine, manifest = load_engine(args.rom, args.scenario)
        session = Session(engine, args.output, manifest, track=args.track, goal=args.goal,
                          limits=limits, labels=labels, agent=agent, journal=getattr(args, "journal", False), gameplay_catalog=gameplay_catalog)
        if args.command == "mcp":
            from .mcp_server import serve
            serve(session)
            return None
        from .runner import run
        return run(session, provider, input_price=args.input_price, output_price=args.output_price,
                   pause_after_decisions=args.pause_after_decisions)
    finally:
        if session:
            session.close()
        elif engine:
            engine.close()
        if provider:
            provider.close()


def main():
    args = parser().parse_args()
    try:
        result = execute(args)
    except (ValueError, OSError, KeyError) as error:
        print(f"Error: {error}", file=sys.stderr)
        return 2
    if result is not None:
        print(json.dumps(result, indent=2))
        if isinstance(result, dict) and (result.get("stop_reason") in ("provider_error", "infrastructure_error", "usage_unavailable")
                                         or result.get("phase") in ("stopped for error", "stopped after in-flight budget overrun")):
            return 1
    return 0
