"""
publisher.py — standalone publisher for Docker Compose bonus.
Sends 5000 events to the aggregator with ~20% intentional duplicates,
then prints a final stats snapshot.
"""

import time
import uuid
import random
import logging
import httpx
from datetime import datetime, timezone

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger(__name__)

AGGREGATOR_URL = "http://aggregator:8080"
TOTAL_EVENTS   = 5000
DUPLICATE_RATE = 0.20   # 20% of events will be re-sends
BATCH_SIZE     = 100
TOPICS         = ["payments", "auth", "orders", "inventory", "notifications"]


def wait_for_aggregator(retries: int = 15, delay: float = 2.0) -> None:
    """Poll /health until the aggregator is ready."""
    for attempt in range(1, retries + 1):
        try:
            r = httpx.get(f"{AGGREGATOR_URL}/health", timeout=3)
            if r.status_code == 200:
                logger.info("Aggregator is ready.")
                return
        except httpx.ConnectError:
            pass
        logger.info("Waiting for aggregator... (%d/%d)", attempt, retries)
        time.sleep(delay)
    raise RuntimeError("Aggregator did not become ready in time.")


def build_event(event_id: str, topic: str) -> dict:
    return {
        "event_id": event_id,
        "topic": topic,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "source": "publisher-service",
        "payload": {"value": random.randint(1, 1000)},
    }


def main() -> None:
    wait_for_aggregator()

    # Pre-generate unique event IDs
    unique_ids = [(str(uuid.uuid4()), random.choice(TOPICS)) for _ in range(TOTAL_EVENTS)]

    # Build the full send list: unique events + duplicates injected randomly
    send_list = list(unique_ids)
    duplicate_count = int(TOTAL_EVENTS * DUPLICATE_RATE)
    duplicates = random.choices(unique_ids, k=duplicate_count)
    send_list.extend(duplicates)
    random.shuffle(send_list)

    logger.info(
        "Sending %d events (%d unique + %d duplicates) in batches of %d",
        len(send_list), TOTAL_EVENTS, duplicate_count, BATCH_SIZE,
    )

    sent = 0
    with httpx.Client(base_url=AGGREGATOR_URL, timeout=30) as client:
        for i in range(0, len(send_list), BATCH_SIZE):
            batch = send_list[i : i + BATCH_SIZE]
            payload = {"events": [build_event(eid, topic) for eid, topic in batch]}

            try:
                r = client.post("/publish", json=payload)
                r.raise_for_status()
                sent += len(batch)
            except httpx.HTTPError as e:
                logger.error("Batch %d failed: %s", i // BATCH_SIZE, e)

        logger.info("All batches sent (%d total).", sent)

        # Wait briefly for consumer to finish draining the queue
        time.sleep(3)

        stats = client.get("/stats").json()
        logger.info("── Final Stats ──────────────────────────────")
        logger.info("  received:          %d", stats["received"])
        logger.info("  unique_processed:  %d", stats["unique_processed"])
        logger.info("  duplicate_dropped: %d", stats["duplicate_dropped"])
        logger.info("  topics:            %s", stats["topics"])
        logger.info("  uptime_seconds:    %.2f", stats["uptime_seconds"])
        logger.info("─────────────────────────────────────────────")


if __name__ == "__main__":
    main()