import asyncio
import logging
from datetime import datetime, timezone

from .dedup_store import DedupStore
from .models import Event
from .stats import StatsCollector

logger = logging.getLogger(__name__)

# ── Shared in-memory queue ────────────────────────────────────────────────────
event_queue: asyncio.Queue[Event] = asyncio.Queue()

# ── Processed events store (in-memory, per topic) ────────────────────────────
# { "payments": [Event, ...], "auth": [Event, ...] }
processed_events: dict[str, list[Event]] = {}


async def consume(dedup_store: DedupStore, stats: StatsCollector) -> None:
    """
    Background worker that runs for the lifetime of the application.
    Pulls events off the queue one at a time and applies deduplication.
    """
    logger.info("Consumer worker started.")

    while True:
        event: Event = await event_queue.get()

        try:
            if dedup_store.is_duplicate(event.topic, event.event_id):
                logger.warning(
                    "[DUPLICATE DROPPED] topic=%s event_id=%s",
                    event.topic,
                    event.event_id,
                )
                stats.increment_duplicate()
            else:
                processed_at = datetime.now(timezone.utc).isoformat()
                dedup_store.mark_processed(event.topic, event.event_id, processed_at)

                if event.topic not in processed_events:
                    processed_events[event.topic] = []
                processed_events[event.topic].append(event)

                stats.add_topic(event.topic)
                stats.increment_unique()

                logger.info(
                    "[PROCESSED] topic=%s event_id=%s",
                    event.topic,
                    event.event_id,
                )
        except Exception:
            logger.exception(
                "Unexpected error processing event_id=%s", event.event_id
            )
        finally:
            event_queue.task_done()