"""Ctrl-C pauses a run at the next decision boundary, so a stop never scores a partial result.

The first Ctrl-C asks for a pause. The run finishes the decision in progress, saves its checkpoint and
stops, and the same command resumes it. A second Ctrl-C during a model call stops at once. That call's
reply and token use are lost, so the run cannot resume and is never scored. Outside a model call the
decision in progress finishes in moments, so only a third Ctrl-C stops at once there.

Model CLIs run in their own session, so a terminal Ctrl-C reaches only this process.
"""
from contextlib import contextmanager
import signal
import sys
import threading

FIRST = ('\nCtrl-C: pausing after the current decision. The same command resumes the run. '
         'Press Ctrl-C again to stop at once, which loses the decision in progress.')
AGAIN = 'Ctrl-C: still pausing. The controller inputs of this decision finish first. Press Ctrl-C again to stop at once.'


class Guard:
    def __init__(self):
        self.presses = 0
        self.model_call = False

    @property
    def requested(self):
        return self.presses > 0

    def handle(self, signum, frame):
        self.presses += 1
        if self.presses == 1:
            print(FIRST, file=sys.stderr, flush=True)
        elif self.model_call or self.presses >= 3:
            raise KeyboardInterrupt
        else:
            print(AGAIN, file=sys.stderr, flush=True)


_active = None


@contextmanager
def pause_on_interrupt():
    """Install a guard for this block, or share the one a caller installed. Off the main thread yield None."""
    global _active
    if _active is not None:
        yield _active
        return
    if threading.current_thread() is not threading.main_thread():
        yield None
        return
    guard = Guard()
    previous = signal.signal(signal.SIGINT, guard.handle)
    _active = guard
    try:
        yield guard
    finally:
        signal.signal(signal.SIGINT, previous)
        _active = None
