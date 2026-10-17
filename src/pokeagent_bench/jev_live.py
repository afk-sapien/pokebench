"""Watch Jev play locally, pause it, and take over the controller. Not a scored benchmark run."""
from __future__ import annotations

from collections import deque
from concurrent.futures import ThreadPoolExecutor
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import secrets
import threading
import time

from .core import BUTTONS
from .jev_provider import ACTIONS, MODEL, ask, client_for, request_body, screen_png
from .providers import ProviderError


def execute(engine, choice):
    """Press, hold, release and wait. The button is released even if emulation fails."""
    button, hold, gap = ACTIONS[choice]
    if button == "wait":
        engine.tick(hold)
        return hold
    engine.press(button)
    try:
        engine.tick(hold)
    finally:
        engine.release(button)
    engine.tick(gap)
    return hold + gap


def atomic_write(path, data):
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_bytes(data)
    temporary.replace(path)


class LiveSession:
    """The worker alone reads and advances the emulator. HTTP only queues commands."""

    def __init__(self, engine, output, *, frame=0, labels=None, key="", steps=1000, max_input_tokens=1_000_000):
        self.engine = engine
        self.output = output
        self.labels = labels or {}
        self.key = key
        self.steps = steps
        self.max_input_tokens = max_input_tokens
        self.lock = threading.Lock()
        self.commands = deque(maxlen=32)
        self.halt = threading.Event()
        self.epoch = 0
        self.running = False
        self.mode = "both"
        self.goal = "Explore, collect Pokemon, earn badges, and become Champion. Start with the next reachable objective."
        self.history = deque(maxlen=8)
        self.frame = frame
        self.calls = self.tokens = self.actions = 0
        self.error = ""
        self.last_action = "Ready"
        self.last_latency = None
        self.png = b""
        self.observation = None
        self.thread = threading.Thread(target=self.run, daemon=True, name="jev-player")

    def command(self, data):
        with self.lock:
            kind = data.get("command")
            if kind == "start":
                goal = data.get("goal", self.goal)
                mode = data.get("mode", self.mode)
                key = data.get("key", "")
                if not isinstance(goal, str) or not goal.strip() or len(goal) > 2000:
                    raise ValueError("Enter a goal of 1 to 2000 characters")
                if mode not in ("images", "state", "both") or not isinstance(key, str) or len(key) > 4096:
                    raise ValueError("Invalid mode or key")
                if not (key.strip() or self.key):
                    raise ValueError("A TypeSafe API key is required for Jev. Manual controls work without one.")
                if self.calls >= self.steps or self.tokens >= self.max_input_tokens:
                    raise ValueError("This run has reached its configured limit")
                self.key = key.strip() or self.key
                self.goal, self.mode = goal.strip(), mode
                self.commands.append(("reset_history", None))
                self.running = True
                self.error = ""
            elif kind == "pause":
                self.running = False
            elif kind == "action" and data.get("action") in ACTIONS:
                self.running = False
                self.commands.append(("action", data["action"]))
            else:
                raise ValueError("Unknown command")
            self.epoch += 1

    def status(self):
        with self.lock:
            return {"running": self.running, "key_configured": bool(self.key), "mode": self.mode,
                    "goal": self.goal, "calls": self.calls, "input_tokens": self.tokens,
                    "actions": self.actions, "frame": self.frame, "last_action": self.last_action,
                    "latency_seconds": self.last_latency, "error": self.error,
                    "game_state": self.observation, "model": MODEL, "stopped": self.halt.is_set()}

    def publish(self):
        png = screen_png(self.engine.screenshot())
        # The benchmark's structured allowlist. No hidden flags, routes or damage estimates.
        observation = self.engine.structured(self.labels)
        with self.lock:
            self.png, self.observation = png, observation
        atomic_write(self.output / "latest.png", png)
        atomic_write(self.output / "status.json", json.dumps(self.status(), indent=2).encode())

    def save(self):
        atomic_write(self.output / "current.state", self.engine.save())
        atomic_write(self.output / "current.json", json.dumps({
            "rom_sha256": self.engine.rom_sha256, "frame": self.frame, "observation": self.mode,
            "recent_actions": list(self.history)}, indent=2).encode())

    @staticmethod
    def evaluate(body, current, previous, key):
        with client_for(key) as client:
            return ask(client, body, current, previous)

    def run(self):
        pending = None
        previous = previous_state = None
        executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="jev-request")
        try:
            self.publish()
            self.save()
            with (self.output / "decisions.jsonl").open("a") as log:
                while not self.halt.is_set():
                    with self.lock:
                        commands = list(self.commands)
                        self.commands.clear()
                    for kind, value in commands:
                        self.history.clear()
                        previous = previous_state = None
                        if kind == "action":
                            self.frame += execute(self.engine, value)
                            self.actions += 1
                            self.last_action = f"Manual: {value}"
                            log.write(json.dumps({"source": "manual", "choice": value, "frame": self.frame}) + "\n")
                            log.flush()
                            self.publish()
                            self.save()
                    if pending is not None and pending[0].done():
                        future, epoch, body, current, state, started = pending
                        pending = None
                        try:
                            result = future.result()
                            self.tokens += result["usage"]["input_tokens"]
                            self.last_latency = time.monotonic() - started
                            with self.lock:
                                # Pause or manual input after the request makes its answer stale.
                                apply = epoch == self.epoch and self.running
                            row = {"source": "jev", "request": body, "response": result,
                                   "applied": apply, "frame": self.frame, "latency_seconds": self.last_latency}
                            log.write(json.dumps(row) + "\n")
                            log.flush()
                            if apply:
                                choice = result["answers"]["action"]["choice"]
                                self.frame += execute(self.engine, choice)
                                self.actions += 1
                                self.last_action = choice
                                self.publish()
                                changed = self.observation != state if self.mode == "state" else self.png != current
                                self.history.append({"action": choice, "observation_changed": changed})
                                previous, previous_state = current, state
                                self.save()
                        except Exception as error:
                            with self.lock:
                                self.running = False
                                self.error = str(error) if isinstance(error, (ValueError, ProviderError)) else type(error).__name__
                            log.write(json.dumps({"source": "jev", "error": self.error, "frame": self.frame}) + "\n")
                            log.flush()
                    with self.lock:
                        if pending is None and (self.calls >= self.steps or self.tokens >= self.max_input_tokens):
                            self.running = False
                        running, epoch, mode, goal, key = self.running, self.epoch, self.mode, self.goal, self.key
                    if running and pending is None:
                        images = mode != "state"
                        body = request_body(goal, self.history, previous=images and previous is not None,
                                            game_state=self.observation if mode != "images" else None, images=images)
                        if mode != "images" and previous_state is not None:
                            body["state"]["previous_game_state"] = previous_state
                        current = self.png
                        (self.output / f"screen-{self.calls:05d}.png").write_bytes(current)
                        self.calls += 1
                        future = executor.submit(self.evaluate, body, current, previous if images else None, key)
                        pending = (future, epoch, body, current, self.observation, time.monotonic())
                    self.halt.wait(0.025)
        except Exception as error:
            with self.lock:
                self.running = False
                self.error = f"Emulator stopped: {type(error).__name__}"
            self.halt.set()
        finally:
            try:
                self.save()
                self.publish()
            finally:
                self.engine.close()
                executor.shutdown(wait=True, cancel_futures=True)


PAGE = """<!doctype html>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Jev plays Pokemon</title>
<style>
body { background: #111925 }
body { color: #e8eff7 }
body { font: 16px system-ui }
body { margin: 24px auto }
body { max-width: 1050px }
body { padding: 0 16px }
main { display: flex }
main { gap: 24px }
main { flex-wrap: wrap }
section { flex: 1 1 320px }
img { width: 100% }
img { image-rendering: pixelated }
img { background: #243144 }
button, input, select, textarea { font: inherit }
button, input, select, textarea { padding: 10px }
button { margin: 4px }
button { cursor: pointer }
textarea, input { box-sizing: border-box }
textarea, input { width: 100% }
label { display: block }
label { margin-top: 16px }
pre { white-space: pre-wrap }
.muted { color: #a9bed3 }
</style>
<h1>Jev plays Pokemon</h1>
<p class="muted">Live emulator · __MODEL__ · Automatic play with manual takeover · Not a scored run</p>
<main><section>
<img id="screen" src="/screen.png" alt="Live Pokemon game screen">
<p id="status">Loading game...</p>
<div id="buttons"></div>
<p class="muted">Arrow keys move. Z confirms, X cancels, Enter opens the menu. Manual input pauses Jev.</p>
</section><section>
<label for="goal">Goal</label>
<textarea id="goal" rows="3">Explore, collect Pokemon, earn badges, and become Champion. Start with the next reachable objective.</textarea>
<label for="mode">What Jev sees</label>
<select id="mode"><option value="both">Screenshots + game state</option><option value="state">Game state only</option><option value="images">Screenshots only</option></select>
<label for="key">TypeSafe API key</label>
<input id="key" type="password" autocomplete="off" placeholder="Optional if the TypeSafe key is saved">
<p class="muted">The key stays in this process and is sent only to TypeSafe. It is not saved to disk.</p>
<button id="start">Start Jev</button><button id="pause">Pause</button>
<p id="message" role="status"></p>
<pre id="stats"></pre>
<details><summary>Game state</summary><pre id="state"></pre></details>
</section></main>
<script>
const token = '__TOKEN__'
const get = id => document.getElementById(id)
async function command(data) {
  const response = await fetch('/command', {method: 'POST', headers: {'Content-Type': 'application/json', 'X-Jev-Token': token}, body: JSON.stringify(data)})
  const result = await response.json()
  get('message').textContent = result.error || ''
  return response.ok
}
get('start').onclick = async () => {
  if (await command({command: 'start', goal: get('goal').value, mode: get('mode').value, key: get('key').value})) get('key').value = ''
}
get('pause').onclick = () => command({command: 'pause'})
for (const action of ['up', 'left', 'down', 'right', 'a', 'b', 'start', 'select', 'wait']) {
  const button = document.createElement('button')
  button.textContent = action.toUpperCase()
  button.onclick = () => command({command: 'action', action})
  get('buttons').appendChild(button)
}
document.addEventListener('keydown', event => {
  if (['INPUT', 'TEXTAREA', 'SELECT'].includes(event.target.tagName) || event.repeat) return
  const action = {ArrowUp: 'up', ArrowDown: 'down', ArrowLeft: 'left', ArrowRight: 'right', z: 'a', x: 'b', Enter: 'start'}[event.key]
  if (action) {
    event.preventDefault()
    command({command: 'action', action})
  }
})
async function refresh() {
  try {
    const state = await (await fetch('/status')).json()
    get('screen').src = '/screen.png?t=' + Date.now()
    get('status').textContent = state.stopped ? 'Emulator stopped' : state.running ? 'Jev is playing' : 'Paused · Manual controls available'
    get('stats').textContent = 'Last action: ' + state.last_action + '\\nJev calls: ' + state.calls + '\\nInput tokens: ' + state.input_tokens + '\\n' + (state.key_configured ? 'TypeSafe key configured' : 'No TypeSafe key configured')
    get('state').textContent = JSON.stringify(state.game_state, null, 2)
    if (state.error) get('message').textContent = state.error
  } catch { get('status').textContent = 'Disconnected from the local player' }
  setTimeout(refresh, 500)
}
refresh()
</script>"""


def server_for(session, port):
    token = secrets.token_urlsafe(32)

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def local(self):
            port = self.server.server_port
            return self.headers.get("Host") in (f"127.0.0.1:{port}", f"localhost:{port}")

        def reply(self, status, content, kind="application/json"):
            data = content if isinstance(content, bytes) else content.encode()
            self.send_response(status)
            self.send_header("Content-Type", kind)
            self.send_header("Content-Length", str(len(data)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.end_headers()
            self.wfile.write(data)

        def do_GET(self):
            if not self.local():
                self.reply(403, "{}")
            elif self.path == "/":
                self.reply(200, PAGE.replace("__TOKEN__", token).replace("__MODEL__", MODEL), "text/html")
            elif self.path == "/status":
                self.reply(200, json.dumps(session.status()))
            elif self.path.split("?")[0] == "/screen.png":
                with session.lock:
                    png = session.png
                self.reply(200, png, "image/png")
            else:
                self.reply(404, "{}")

        def do_POST(self):
            if not self.local() or self.path != "/command" or self.headers.get("X-Jev-Token") != token:
                self.reply(403, '{"error":"Invalid command token"}')
                return
            try:
                length = int(self.headers.get("Content-Length", "0"))
                if not 0 < length <= 16384:
                    raise ValueError("Invalid request size")
                data = json.loads(self.rfile.read(length))
                if not isinstance(data, dict):
                    raise ValueError("Expected an object")
                session.command(data)
                self.reply(200, "{}")
            except (ValueError, TypeError) as error:
                self.reply(400, json.dumps({"error": str(error)}))

    return ThreadingHTTPServer(("127.0.0.1", port), Handler)


def serve(rom: Path, output: Path, *, state: Path | None = None, labels=None, port=8931, steps=1000,
          max_input_tokens=1_000_000, key=""):
    from .game import RedEngine
    frame = 0
    saved = None
    if state:
        sidecar = state.with_suffix(".json")
        saved = json.loads(sidecar.read_text()) if sidecar.is_file() else None
    output.mkdir(parents=True, exist_ok=False)
    engine = RedEngine(rom, state.read_bytes() if state else None)
    try:
        if saved:
            if saved.get("rom_sha256") != engine.rom_sha256:
                raise ValueError("Saved Jev state was made with a different ROM")
            frame = saved.get("frame", 0)
        for button in BUTTONS:
            engine.release(button)
        # Render the first screen with no input, including after a state load.
        engine.tick(1)
        session = LiveSession(engine, output, frame=frame + 1, labels=labels, key=key,
                              steps=steps, max_input_tokens=max_input_tokens)
        server = server_for(session, port)
    except BaseException:
        engine.close()
        raise
    session.thread.start()
    print(f"Jev player: http://127.0.0.1:{server.server_port}  Saves: {output}", flush=True)
    try:
        server.serve_forever(poll_interval=0.2)
    except KeyboardInterrupt:
        pass
    finally:
        session.halt.set()
        session.thread.join()
        server.server_close()
