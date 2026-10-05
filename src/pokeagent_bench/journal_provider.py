"""Compact visual decisions with an optional agent-authored long-term journal."""
from .compact_provider import CompactCodexProvider


class JournalCodexProvider(CompactCodexProvider):
    harness = "codex-cli-journal-v8"
    memory_protocol = "bounded-notebook-journal-v6"
    prompt = CompactCodexProvider.prompt + """
Each call has a fresh context. No old conversation is replayed. The short memory
notebook persists until you replace it. A separate journal stores only your own
claims, which may be wrong. It does not contain hidden game facts or advice.
Use journal.writes [{key,text}] to save or replace entries, delete [key] to remove
them, and query to retrieve entries on the NEXT call. Null query retrieves none.
Search is case-insensitive and matches all space-separated terms in key or text.
An empty query retrieves the newest entries. Limits appear in observation.journal.
At most eight edits per decision. Keys use 1-64 letters, digits, dots, underscores,
or hyphens. Query is at most 128 UTF-8 bytes. Results are newest first and may be
truncated. Old results are not carried forward unless requested again. Use
writes:[], delete:[], query:null when no journal work is needed. Empty plan.actions
is allowed only for a journal edit or search. Memory-only decisions still consume
model calls and tokens but do not advance game time. Keep the notebook concise.
"""

    def decision_context(self, observation, notes, recent):
        payload = super().decision_context(observation, notes, recent)
        payload["observation"]["journal"] = observation["journal"]
        return payload

    def decision_schema(self, limits):
        schema = super().decision_schema(limits)
        text = {"type": "string"}
        schema["properties"]["journal"] = {
            "type": "object", "additionalProperties": False,
            "properties": {
                "writes": {"type": "array", "maxItems": 8, "items": {
                    "type": "object", "additionalProperties": False,
                    "properties": {"key": text, "text": text}, "required": ["key", "text"]}},
                "delete": {"type": "array", "items": text, "maxItems": 8},
                "query": {"type": ["string", "null"]}},
            "required": ["writes", "delete", "query"]}
        schema["required"].append("journal")
        schema["properties"]["plan"]["properties"]["actions"]["minItems"] = 0
        return schema

    def unpack_decision(self, response):
        if not isinstance(response, dict) or "journal" not in response:
            return {"invalid_journal_response": response}, {"validation_error": "Missing journal request"}
        decision, record = super().unpack_decision({k: v for k, v in response.items() if k != "journal"})
        decision["journal"] = response["journal"]
        return decision, record
