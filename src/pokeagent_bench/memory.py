"""Bounded agent-authored journal. No evaluator or game-state access."""
from copy import deepcopy
import re

CONFIG = {'entries': 128, 'entry_bytes': 2048, 'total_bytes': 65536, 'retrieval_bytes': 4096, 'results': 5}


def validate(entries, request):
    if not isinstance(request, dict) or set(request) != {'writes', 'delete', 'query'}:
        raise ValueError('Journal needs writes, delete, and query')
    if not isinstance(request['writes'], list) or not isinstance(request['delete'], list):
        raise ValueError('Journal edits must be lists')
    if len(request['writes']) + len(request['delete']) > 8:
        raise ValueError('At most eight journal edits per decision')
    query = request['query']
    if query is not None and (not isinstance(query, str) or len(query.encode()) > 128):
        raise ValueError('Journal query must fit in 128 UTF-8 bytes')
    updated = deepcopy(entries)
    def key_valid(key):
        if not isinstance(key, str) or not re.fullmatch(r'[A-Za-z0-9_.-]{1,64}', key):
            raise ValueError('Journal keys need 1 to 64 letters, digits, dots, underscores, or hyphens')
    for key in request['delete']:
        key_valid(key)
        updated.pop(key, None)
    for item in request['writes']:
        if not isinstance(item, dict) or set(item) != {'key', 'text'}:
            raise ValueError('Journal writes need key and text')
        key_valid(item['key'])
        if not isinstance(item['text'], str) or len(item['text'].encode()) > CONFIG['entry_bytes']:
            raise ValueError('Journal entry exceeds its byte limit')
        updated.pop(item['key'], None)
        updated[item['key']] = item['text']
    if len(updated) > CONFIG['entries'] or sum(len(k.encode()) + len(v.encode()) for k,v in updated.items()) > CONFIG['total_bytes']:
        raise ValueError('Journal full. Delete or shorten entries first')
    return updated


def search(entries, query):
    if query is None:
        return []
    terms = query.casefold().split()
    result = []
    remaining = CONFIG['retrieval_bytes']
    for key, text in reversed(list(entries.items())):
        if not all(term in (key + ' ' + text).casefold() for term in terms):
            continue
        remaining -= len(key.encode())
        if remaining < 1:
            break
        snippet = text.encode()[:remaining].decode('utf-8', errors='ignore')
        result.append({'key': key, 'text': snippet, 'truncated': snippet != text})
        remaining -= len(snippet.encode())
        if remaining < 1 or len(result) == CONFIG['results']:
            break
    return result
