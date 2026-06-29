import asyncio
import logging
from datetime import datetime, timezone

from .dedup_store import DedupStore
from .models import Event
from .stats import StatsCollector
from .queue_manager import get_queue, processed_events

logger = logging.getLogger(__name__)


async def consume(dedup_store: DedupStore, stats: StatsCollector) -> None:
    """
    Background worker that runs for the lifetime of the application.
    Pulls events off the queue one at a time and applies deduplication.
    """
    logger.info("Consumer worker started.")
    queue = get_queue()

    while True:
        event: Event = await queue.get()

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
            queue.task_done()