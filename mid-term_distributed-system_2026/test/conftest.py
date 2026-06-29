import asyncio
import pytest
import pytest_asyncio

from src.consumer import consume, processed_events
from src.queue_manager import get_queue
from src.main import dedup_store, stats


@pytest_asyncio.fixture(autouse=True)
async def start_consumer():
    """
    Start a fresh consumer task for each test.
    Resets all in-memory state so tests don't bleed into each other.
    """
    # Reset in-memory state
    processed_events.clear()
    stats._received = 0
    stats._unique_processed = 0
    stats._duplicate_dropped = 0
    stats._topics = set()

    # Force a fresh queue bound to the current event loop
    import src.queue_manager as qm
    qm._queue = asyncio.Queue()

    # Start consumer
    task = asyncio.create_task(consume(dedup_store, stats))

    yield

    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass