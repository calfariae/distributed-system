import asyncio
import logging
from datetime import datetime, timezone

from fastapi import FastAPI, HTTPException, Query
from contextlib import asynccontextmanager

from .consumer import consume, event_queue, processed_events
from .dedup_store import DedupStore
from .models import BatchPublishRequest, Event
from .stats import StatsCollector

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

# ── Shared singletons ─────────────────────────────────────────────────────────
dedup_store = DedupStore()
stats = StatsCollector()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Start the consumer worker on startup; cancel it on shutdown."""
    task = asyncio.create_task(consume(dedup_store, stats))
    logger.info("Application started.")
    yield
    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass
    logger.info("Application shut down.")


app = FastAPI(title="Pub-Sub Log Aggregator", lifespan=lifespan)


# ── POST /publish ─────────────────────────────────────────────────────────────
@app.post("/publish", status_code=202)
async def publish(request: BatchPublishRequest):
    """
    Accept a batch of events (or wrap a single event in {"events": [...]}).
    Each event is placed on the internal queue immediately.
    Validation (schema, non-empty fields) is handled by Pydantic automatically.
    """
    for event in request.events:
        await event_queue.put(event)
        stats.increment_received()
        logger.info(
            "[RECEIVED] topic=%s event_id=%s", event.topic, event.event_id
        )

    return {"queued": len(request.events)}


# ── GET /events ───────────────────────────────────────────────────────────────
@app.get("/events")
async def get_events(topic: str = Query(default=None)):
    """
    Return processed unique events.
    If ?topic=<name> is provided, filter to that topic only.
    """
    if topic is not None:
        if topic not in processed_events:
            raise HTTPException(status_code=404, detail=f"Topic '{topic}' not found.")
        return {"topic": topic, "events": processed_events[topic]}

    # Return all topics
    return {"events": processed_events}


# ── GET /stats ────────────────────────────────────────────────────────────────
@app.get("/stats")
async def get_stats():
    return stats.snapshot()


# ── GET /health ───────────────────────────────────────────────────────────────
@app.get("/health")
async def health():
    return {"status": "ok"}