"""Thin stdio MCP adapter. No emulator, scoring, or lifecycle admin tools are exposed."""
from __future__ import annotations

import json
import threading

from mcp.server.fastmcp import FastMCP
from mcp.types import ImageContent, TextContent

from .rules import NICKNAME_RULE


def content(observation):
    data = dict(observation)
    screenshot = data.pop("screenshot")
    if observation["status"]["track"] == "gameplay":
        from .visual_feedback import public_context
        data = public_context(observation)
    return [TextContent(type="text", text=json.dumps(data)),
            ImageContent(type="image", data=screenshot["base64"], mimeType="image/png")]


def create_server(session):
    server = FastMCP("PokeAgent Bench", instructions=(
        "Play Pokemon Red using only these tools. Actions advance bounded frames and return the screen. "
        "Use a unique operation_id per new action and reuse it only for a retry. "
        "The game pauses between actions. Store lasting plans in notes. "
        "Use status to read the goal and remaining budgets. There are no reset or memory editing tools. "
        + NICKNAME_RULE))

    @server.tool()
    def observe() -> list[TextContent | ImageContent]:
        """Read the current screenshot and allowlisted observation without advancing frames."""
        return content(session.observe())

    @server.tool()
    def act(operation_id: str, button: str, hold_frames: int = 8, release_frames: int = 2) -> list[TextContent | ImageContent]:
        """Hold one Game Boy button, release it, and return the resulting screen. At most 120 total frames by default."""
        return content(session.act(operation_id, button, hold_frames, release_frames))

    @server.tool()
    def wait(operation_id: str, frames: int = 30) -> list[TextContent | ImageContent]:
        """Advance a bounded number of frames with no button held."""
        return content(session.wait(operation_id, frames))

    @server.tool()
    def status() -> dict:
        """Read score, achieved milestones, clocks, and remaining budgets."""
        if session.track == "gameplay":
            from .visual_feedback import public_context
            return {key: value for key, value in public_context(session.observe()).items() if key != "game"}
        return session.status()

    @server.tool()
    def read_notes() -> dict:
        """Read this run's private agent notebook."""
        return session.read_notes()

    @server.tool()
    def write_notes(text: str) -> dict:
        """Replace the notebook, up to 8192 UTF-8 bytes by default."""
        return session.write_notes(text)

    if session.track == "gameplay":
        @server.tool()
        def gameplay_command(operation_id: str, command: str, argument: str = "", count: int = 1) -> list[TextContent | ImageContent]:
            """Execute move, interact, choose, use_move, use_item, switch_pokemon, press, wait, advance_dialogue or inspect. Slots are one-based.

            Move takes a direction and 1..8 tiles. Choose takes exact visible text.
            Use_move takes a move slot and opens FIGHT automatically. Use_item takes
            "Full Restore:1" for an item name and party slot. Switch_pokemon takes a
            party slot, switching in battle or setting the lead outside battle.
            Menu shortcuts have a 2400-frame navigation ceiling, capped by
            max_dialogue_frames. Inspect takes party, bag, storage, map or memory.
            Action frames are bounded by max_action_frames. Automatic dialogue has
            its own max_dialogue_frames limit and returns a transcript before choices.
            Advance_dialogue continues an already open conversation without choosing.
            """
            from .gameplay_commands import execute
            execute(session, operation_id, {"command": command, "argument": argument, "count": count})
            return content(session.observe())

    return server


def serve(session):
    stopped = threading.Event()

    def watch_budget():
        while not stopped.wait(1):
            if session.status()["state"] == "finished":
                return

    watcher = threading.Thread(target=watch_budget, daemon=True)
    watcher.start()
    try:
        create_server(session).run(transport="stdio")
    finally:
        stopped.set()
        watcher.join(timeout=2)
        session.close()
