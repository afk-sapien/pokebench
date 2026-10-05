"""Small deadline-bound App Server transport. Model text is never logged here."""
import json
from queue import Queue, Empty
import subprocess
from threading import Thread
import time

from .providers import ProviderError


class AppServer:
    def __init__(self, command, *, cwd, env):
        self.process = subprocess.Popen(command, cwd=cwd, env=env, stdin=subprocess.PIPE,
                                        stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                                        text=True, bufsize=1)
        self.queue = Queue()
        self.pending = []
        self.sequence = 0
        def read():
            try:
                for line in self.process.stdout:
                    self.queue.put(json.loads(line))
            except (ValueError, OSError):
                pass
            finally:
                self.queue.put(None)
        self.reader = Thread(target=read, daemon=True)
        self.reader.start()

    def send(self, value):
        try:
            self.process.stdin.write(json.dumps(value) + "\n")
            self.process.stdin.flush()
        except (OSError, ValueError):
            raise ProviderError("App Server disconnected. Usage may be unreported") from None

    def receive(self, deadline):
        try:
            value = self.queue.get(timeout=max(0.001, deadline - time.monotonic()))
        except Empty:
            raise ProviderError("App Server deadline exceeded. Usage may be unreported") from None
        if value is None:
            raise ProviderError("App Server exited. Usage may be unreported")
        if "id" in value and "method" in value:
            self.send({"id": value["id"], "error": {"code": -32601, "message": "Outside tools are unavailable"}})
            raise ProviderError("App Server requested an outside tool. Trial is invalid")
        return value

    def request(self, method, params, deadline):
        self.sequence += 1
        request_id = self.sequence
        self.send({"id": request_id, "method": method, "params": params})
        while True:
            event = self.receive(deadline)
            if event.get("id") == request_id:
                if "error" in event:
                    raise ProviderError("App Server rejected " + method + ". Usage may be unreported")
                return event["result"]
            self.pending.append(event)

    def event(self, deadline):
        return self.pending.pop(0) if self.pending else self.receive(deadline)

    def close(self):
        if self.process.poll() is None:
            self.process.terminate()
            try:
                self.process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self.process.kill()
                self.process.wait(timeout=5)
        for stream in (self.process.stdin, self.process.stdout):
            stream.close()
        self.reader.join(timeout=1)
