import asyncio
from src.models import Event

# Processed events store (in-memory, per topic)
# { "payments": [Event, ...], "auth": [Event, ...] }
processed_events: dict[str, list[Event]] = {}

_queue: asyncio.Queue | None = None


def get_queue() -> asyncio.Queue:
    """
    Return the queue for the current event loop.
    Creates a new one if none exists or if the loop has changed.
    """
    global _queue
    try:
        loop = asyncio.get_event_loop()
        if _queue is None or _queue._loop is not loop:
            _queue = asyncio.Queue()
    except RuntimeError:
        _queue = asyncio.Queue()
    return _queue