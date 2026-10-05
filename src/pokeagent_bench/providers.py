"""Small, stateless provider adapters with the same observation and action contract."""
from __future__ import annotations

import json
import os
import random

import httpx

from .core import BUTTONS
from .rules import NICKNAME_RULE

PROMPT = """You are playing Pokemon Red in a controlled benchmark.
Reach the stated goal using only controller inputs. Earn unique badges and, for
campaign runs, defeat the Elite Four and Champion and complete the Hall of Fame.
The game pauses while you think. Each action advances the requested number of
frames, about 59.73 frames per game second. A hold keeps one button pressed, then
release_frames advances with that button released. Use wait to advance without
input. Read dialogue from the screenshot. Movement and menus need different timing.
You receive your current observation, the last eight action summaries, and your
notebook. These are your only persistent context. Preserve useful plans, visited
places, and findings by returning updated notes. Return null notes to keep them.
Do not assume that an intended action succeeded. Check the next observation.
Call choose_action exactly once. No external tools, walkthroughs, code, or human help
are available. Stay within the action frame and notebook limits in the observation.
"""
PROMPT += "\n" + NICKNAME_RULE + "\n"


SCHEMA = {
    "type": "object", "additionalProperties": False,
    "properties": {
        "button": {"type": "string", "enum": list(BUTTONS) + ["wait"]},
        "hold_frames": {"type": "integer", "minimum": 1, "maximum": 600},
        "release_frames": {"type": "integer", "minimum": 0, "maximum": 600},
        "notes": {"type": ["string", "null"], "description": "Replace your notebook, or null to preserve it"},
    },
    "required": ["button", "hold_frames", "release_frames", "notes"],
}


class ProviderError(RuntimeError):
    pass


class APIProvider:
    def __init__(self, provider, model, *, max_output_tokens=2048, client=None):
        if provider not in ("openai", "anthropic") or not model:
            raise ValueError("A supported provider and explicit model ID are required")
        self.provider = provider
        self.model = model
        self.max_output_tokens = max_output_tokens
        variable = "OPENAI_API_KEY" if provider == "openai" else "ANTHROPIC_API_KEY"
        self.key = os.environ.get(variable)
        if not self.key:
            raise ValueError(f"Set {variable} before starting a paid run")
        self.client = client or httpx.Client(follow_redirects=False)

    def decide(self, observation, notes, recent, limits, timeout):
        public = {key: value for key, value in observation.items() if key != "screenshot"}
        context = json.dumps({"observation": public, "notes": notes, "recent_actions": recent,
                              "max_action_frames": limits.max_action_frames,
                              "max_note_bytes": limits.max_note_bytes}, sort_keys=True)
        image = observation["screenshot"]["base64"]
        image_url = "data:image/png" + chr(59) + "base64," + image
        if self.provider == "openai":
            url = "https://api.openai.com/v1/responses"
            headers = {"Authorization": f"Bearer {self.key}"}
            body = {"model": self.model, "instructions": PROMPT, "store": False,
                    "max_output_tokens": self.max_output_tokens,
                    "input": [{"role": "user", "content": [
                        {"type": "input_text", "text": context},
                        {"type": "input_image", "image_url": image_url}]}],
                    "tools": [{"type": "function", "name": "choose_action", "strict": True,
                               "description": "Choose the next controller action and update your notebook",
                               "parameters": SCHEMA}],
                    "tool_choice": {"type": "function", "name": "choose_action"},
                    "parallel_tool_calls": False}
        else:
            url = "https://api.anthropic.com/v1/messages"
            headers = {"x-api-key": self.key, "anthropic-version": "2023-06-01"}
            body = {"model": self.model, "system": PROMPT, "max_tokens": self.max_output_tokens,
                    "messages": [{"role": "user", "content": [
                        {"type": "image", "source": {"type": "base64", "media_type": "image/png", "data": image}},
                        {"type": "text", "text": context}]}],
                    "tools": [{"name": "choose_action", "description": "Choose the next controller action and update notes",
                               "input_schema": SCHEMA}],
                    "tool_choice": {"type": "tool", "name": "choose_action", "disable_parallel_tool_use": True}}
        try:
            response = self.client.post(url, headers=headers, json=body, timeout=max(0.001, min(timeout, 180)))
        except httpx.HTTPError as error:
            raise ProviderError(f"{self.provider} transport error: {type(error).__name__}") from None
        if response.status_code >= 400:
            raise ProviderError(f"{self.provider} returned HTTP {response.status_code}")
        try:
            data = response.json()
            usage = data.get("usage", {})
            if self.provider == "openai":
                calls = [item for item in data.get("output", [])
                         if item.get("type") == "function_call" and item.get("name") == "choose_action"]
                decision = json.loads(calls[0]["arguments"]) if len(calls) == 1 else None
            else:
                calls = [item for item in data.get("content", [])
                         if item.get("type") == "tool_use" and item.get("name") == "choose_action"]
                decision = calls[0]["input"] if len(calls) == 1 else None
            return decision, usage, {"response": data, "context": public, "notes": notes, "recent_actions": recent}
        except (ValueError, KeyError, TypeError, AttributeError) as error:
            raise ProviderError(f"Malformed provider response: {type(error).__name__}") from None

    def close(self):
        self.client.close()


class RandomProvider:
    provider = "random"
    model = "random-controller-v1"

    def __init__(self, seed=7):
        self.rng = random.Random(seed)

    def decide(self, observation, notes, recent, limits, timeout):
        button = self.rng.choice(list(BUTTONS) + ["wait"])
        hold = min(8, limits.max_action_frames)
        release = min(2, limits.max_action_frames - hold)
        return {"button": button, "hold_frames": hold, "release_frames": release, "notes": None}, {}, {}

    def close(self):
        pass
