"""Read-only detection of continue-only text waits and bounded controller input."""
import re

from pokesim_core.gen1 import decode_text
from pokesim_core.gen1_ui import read_screen

from .gameplay import ui_state


def continue_ready(engine):
    """Recognize the active text wait, never a menu wait or a strategy condition.

    Match the pinned English Red home-bank routine rather than trusting a
    blinking arrow or an unchanged screenshot. Inspect only live stack words.
    No hooks, ROM patches, memory writes or future text reads are performed.
    """
    pb = getattr(engine, "_pb", None)
    if pb is None:
        return False
    addresses = getattr(engine, "_dialogue_wait_returns", None)
    if addresses is None:
        pattern = (rb"\xf0(.)\xf5\xf0(.)\xf5\xaf\xe0\1\x3e\x06\xe0\2"
                   rb"\xe5\xfa..\xa7\x28\x03\xcd..\x21..\xcd..\xe1\xcd.."
                   rb"\x3e\x2d\xcd..\xf0.\xe6\x03\x28\xe1\xf1\xe0\2\xf1\xe0\1\xc9")
        matches = list(re.finditer(pattern, bytes(engine.memory[0:0x4000]), re.DOTALL))
        addresses = {matches[0].start() + offset for offset in (23, 29, 33, 38)} if len(matches) == 1 else set()
        engine._dialogue_wait_returns = addresses
    sp = pb.register_file.SP
    if not 0xC000 <= sp < 0xE000:
        return False
    live = {engine.memory[p] + 256 * engine.memory[p + 1]
            for p in range(sp, min(sp + 80, 0xDFFF), 2)}
    if live & addresses:
        return True
    if ui_state(engine.memory).get("panel") == "pokedex":
        # The visible data card has a separate A/B-only dismissal loop.
        pattern = rb"\xcd..\xf0.\xe6\x03\x28\xf7\xf1\xe0.\xcd..\xcd..\xcd..\xcd..\xcd.."
        addresses = getattr(engine, "_pokedex_wait_returns", None)
        if addresses is None:
            # English Red keeps this routine in bank 16. VBlank can temporarily
            # map another bank, so read the ROM bank without changing emulation.
            try:
                bank = bytes(engine.memory[16, 0x4000:0x7FFF])
            except (TypeError, IndexError):
                return False
            matches = list(re.finditer(pattern, bank, re.DOTALL))
            addresses = {0x4000 + matches[0].start() + 3} if len(matches) == 1 else set()
            engine._pokedex_wait_returns = addresses
        return bool(addresses & live)
    return False


def input_locked(engine):
    """Read the active game's controller lock, without reading its script goal."""
    addresses = getattr(engine, "_input_lock_addresses", None)
    if addresses is None:
        pattern = (rb"\xfa(..)\xcb\x7f\xc8\xf0.\x47\xfa..\xa0\xc0\x21..\x35\x7e\xfe\xff"
                   rb".{0,64}?\xaf\xea..\xea..\xea..\xea(..)\xe0")
        matches = list(re.finditer(pattern, bytes(engine.memory[0:0x4000]), re.DOTALL))
        addresses = tuple(int.from_bytes(group, "little") for group in matches[0].groups()) if len(matches) == 1 else ()
        engine._input_lock_addresses = addresses
    return bool(addresses and (engine.memory[addresses[0]] & 128 or engine.memory[addresses[1]] & 240 == 240))


class Transcript:
    """Retain visible text pages, collapsing incremental typing only."""

    def __init__(self):
        self.pages = []
        self.limited = False

    def capture(self, memory):
        ui = ui_state(memory)
        if self.limited or ui["kind"] != "dialogue":
            return
        screen = read_screen(memory)
        pokedex = ui.get("panel") == "pokedex"
        if not screen["textbox"] and not pokedex:
            return
        # These printed ligatures occupy one tile but represent multiple characters.
        glyphs = {0xBB: "'d", 0xBC: "'l", 0xBD: "'s", 0xBE: "'t", 0xBF: "'v",
                  0xE4: "'r", 0xE5: "'m", 0x9A: "(", 0x9B: ")", 0x9C: ":",
                  0x9D: chr(59), 0x9E: "[", 0x9F: "]", 0xF3: "/", 0x75: "..."}
        def glyph(tile):
            if tile in glyphs:
                return glyphs[tile]
            if tile == 0xE6:
                return "?"
            return decode_text(bytes([tile])).replace("?", " ") or " "
        rows = ["".join(glyph(tile) for tile in screen["tiles"][y * 20:(y + 1) * 20])
                for y in (range(18) if pokedex else range(13, 17))]
        text = " ".join(row.strip() for row in rows if row.strip())
        if not text:
            return
        previous = self.pages[-1] if self.pages else ""
        if previous and (previous.startswith(text) or previous.endswith(text)):
            return
        replacement = bool(previous and text.startswith(previous))
        size = sum(len(p) for p in self.pages) + len(text) - (len(previous) if replacement else 0)
        if size > 16384 or (len(self.pages) >= 128 and not replacement):
            self.limited = True
            return
        if replacement:
            self.pages[-1] = text
        else:
            self.pages.append(text)

    def result(self, reason, frames):
        return {"pages": list(self.pages), "stop_reason": reason, "frames": frames,
                "transcript_limit_reached": self.limited, "format": "screen-text-pages-v1"}


def settle_dialogue(session, send, transcript, deadline):
    start = session.frame
    uncertain = 0
    stable_control = 0
    collecting = bool(transcript.pages)
    while not session.reason and session.frame < deadline:
        ui = ui_state(session.engine.memory)
        transcript.capture(session.engine.memory)
        if transcript.limited:
            return transcript.result("transcript limit", session.frame - start)
        kind = ui["kind"]
        if kind in ("menu", "battle_menu", "move_menu", "naming", "modal"):
            return transcript.result("choice", session.frame - start)
        if kind == "overworld":
            locked = (input_locked(session.engine) or session.engine.memory[0xC200]
                      or session.frame < session.gameplay_memory.get("map_ready_after", 0))
            if locked:
                collecting = True
                stable_control = 0
            if not locked and (not collecting or stable_control >= 120):
                return transcript.result("control returned", session.frame - start)
            before = session.frame
            if not send(None, min(30, deadline - session.frame), 0):
                break
            if not locked:
                stable_control += session.frame - before
            continue
        collecting = True
        stable_control = 0
        if ui["kind"] == "dialogue" and continue_ready(session.engine):
            # A fresh one-frame edge confirms only the observed continue wait.
            if not send("a", 1, 1):
                break
            uncertain = 0
        else:
            uncertain += 1
        if uncertain >= 120:
            return transcript.result("unrecognized or long animation", session.frame - start)
        if session.frame >= deadline or not send(None, min(30, deadline - session.frame), 0):
            break
    return transcript.result("run ended" if session.reason else "dialogue frame limit", session.frame - start)
