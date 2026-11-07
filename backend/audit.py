"""Append-only audit trail: output/audit_trail.json.

The file is one JSON array. Every agent loop step is appended the moment it
happens (read, append, atomic replace), so a crash mid-run still leaves every
earlier step on disk. Nothing ever truncates the file; if it is unreadable it
is moved aside, never overwritten.
"""

import json
import os
import threading
from datetime import datetime

from .config import AUDIT_FILE

_lock = threading.Lock()
MAX_FIELD_CHARS = 4000  # keep huge tool outputs from bloating the file


def clip(value, limit: int = MAX_FIELD_CHARS):
    """Shorten long strings inside an event so one step can't blow up the file."""
    if isinstance(value, str):
        return value if len(value) <= limit else value[:limit] + f"... [+{len(value) - limit} chars]"
    if isinstance(value, dict):
        return {k: clip(v, limit) for k, v in value.items()}
    if isinstance(value, list):
        return [clip(v, limit) for v in value]
    return value


def append(event: dict) -> None:
    with _lock:
        AUDIT_FILE.parent.mkdir(exist_ok=True)
        entries = []
        if AUDIT_FILE.exists() and AUDIT_FILE.stat().st_size:
            try:
                entries = json.loads(AUDIT_FILE.read_text())
            except json.JSONDecodeError:
                stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
                AUDIT_FILE.rename(AUDIT_FILE.with_suffix(f".corrupt-{stamp}.json"))
                entries = []
        entries.append(clip(event))
        tmp = AUDIT_FILE.with_suffix(".json.tmp")
        tmp.write_text(json.dumps(entries, indent=1, default=str) + "\n")
        os.replace(tmp, AUDIT_FILE)
