"""Decide whether a frequent GitHub schedule is due for a user-selected JST time."""

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

from state import atomic_write_json

ROOT = Path(__file__).parent.parent
STATE_FILE = ROOT / "data" / "schedule_state.json"
JST = timezone(timedelta(hours=9), name="JST")


def due_slot(times: list[str], now: datetime | None = None) -> str | None:
    """Return one unprocessed slot within 12 minutes, otherwise None."""
    now = (now or datetime.now(JST)).astimezone(JST)
    try:
        saved = json.loads(STATE_FILE.read_text(encoding="utf-8"))
        completed = set(saved.get("completed_slots", []))
    except (OSError, ValueError, TypeError):
        completed = set()
    for value in sorted(set(times), reverse=True):
        hour, minute = map(int, value.split(":"))
        slot = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
        if slot > now:
            slot -= timedelta(days=1)
        key = slot.isoformat()
        if timedelta(0) <= now - slot <= timedelta(minutes=12) and key not in completed:
            return key
    return None


def complete_slot(slot: str) -> None:
    try:
        saved = json.loads(STATE_FILE.read_text(encoding="utf-8"))
    except (OSError, ValueError, TypeError):
        saved = {}
    values = [value for value in saved.get("completed_slots", []) if isinstance(value, str)]
    atomic_write_json(STATE_FILE, {"completed_slots": [slot, *[value for value in values if value != slot]][:90]})
