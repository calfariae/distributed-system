"""
tests/test_aggregator.py

Run with:
    pytest tests/ -v

Make sure DB_PATH in dedup_store.py is set to Path("data/dedup.db") for local runs,
or run inside Docker where /app/data/ exists.
"""

import asyncio
import time
import uuid
import pytest
import pytest_asyncio

from httpx import AsyncClient, ASGITransport
from pathlib import Path

from src.main import app
from src.dedup_store import DedupStore
from src.stats import StatsCollector


# ── Helpers ───────────────────────────────────────────────────────────────────

TEST_DB_PATH = Path("data/test_dedup.db")


def make_event(event_id: str = None, topic: str = "test") -> dict:
    """Build a minimal valid event dict."""
    return {
        "event_id": event_id or str(uuid.uuid4()),
        "topic": topic,
        "timestamp": "2025-01-01T00:00:00Z",
        "source": "pytest",
        "payload": {"key": "value"},
    }


def make_batch(*events: dict) -> dict:
    return {"events": list(events)}


@pytest_asyncio.fixture
async def client():
    """Async test client that talks directly to the ASGI app (no real server)."""
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as ac:
        yield ac


@pytest.fixture
def fresh_dedup_store():
    """Provide a clean DedupStore backed by a temp test DB, cleaned up after."""
    if TEST_DB_PATH.exists():
        TEST_DB_PATH.unlink()
    store = DedupStore(db_path=TEST_DB_PATH)
    yield store
    if TEST_DB_PATH.exists():
        TEST_DB_PATH.unlink()


# ── Tests ─────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_duplicate_event_only_processed_once(client):
    """
    Sending the same (topic, event_id) twice must result in:
      - unique_processed incremented by 1
      - duplicate_dropped incremented by 1
    """
    event_id = f"dedup-test-{uuid.uuid4()}"
    event = make_event(event_id=event_id, topic="payments")

    await client.post("/publish", json=make_batch(event))
    await client.post("/publish", json=make_batch(event))

    # Give the consumer a moment to drain the queue
    await asyncio.sleep(1.0)

    stats = (await client.get("/stats")).json()
    assert stats["duplicate_dropped"] >= 1


@pytest.mark.asyncio
async def test_unique_events_all_processed(client):
    """
    10 events with different event_ids must all be processed as unique.
    """
    events = [make_event(topic="auth") for _ in range(10)]
    await client.post("/publish", json=make_batch(*events))

    await asyncio.sleep(1.0)

    stats = (await client.get("/stats")).json()
    assert stats["unique_processed"] >= 10


@pytest.mark.asyncio
async def test_invalid_schema_missing_event_id(client):
    """
    An event missing event_id must return HTTP 422 Unprocessable Entity.
    """
    bad_event = {
        "topic": "payments",
        "timestamp": "2025-01-01T00:00:00Z",
        "source": "pytest",
        "payload": {},
        # event_id intentionally omitted
    }
    response = await client.post("/publish", json=make_batch(bad_event))
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_invalid_schema_empty_topic(client):
    """
    An event with an empty topic string must return HTTP 422.
    """
    bad_event = make_event()
    bad_event["topic"] = "   "  # whitespace only
    response = await client.post("/publish", json=make_batch(bad_event))
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_get_events_filtered_by_topic(client):
    """
    GET /events?topic=X must only return events for topic X.
    """
    event_id = f"topic-filter-{uuid.uuid4()}"
    event = make_event(event_id=event_id, topic="inventory")
    await client.post("/publish", json=make_batch(event))

    await asyncio.sleep(1.0)

    response = await client.get("/events?topic=inventory")
    assert response.status_code == 200
    data = response.json()
    assert "events" in data
    # every returned event must belong to topic "inventory"
    for e in data["events"]:
        assert e["topic"] == "inventory"


@pytest.mark.asyncio
async def test_stats_consistency(client):
    """
    received must always equal unique_processed + duplicate_dropped.
    """
    await asyncio.sleep(1.0)  # let any previous tests drain

    stats_before = (await client.get("/stats")).json()
    before_received = stats_before["received"]

    event_id = f"stats-check-{uuid.uuid4()}"
    event = make_event(event_id=event_id, topic="orders")

    await client.post("/publish", json=make_batch(event))
    await client.post("/publish", json=make_batch(event))  # duplicate

    await asyncio.sleep(1.0)

    stats = (await client.get("/stats")).json()
    assert stats["received"] == stats["unique_processed"] + stats["duplicate_dropped"]


@pytest.mark.asyncio
async def test_get_events_unknown_topic_returns_404(client):
    """
    GET /events?topic=nonexistent must return 404.
    """
    response = await client.get("/events?topic=nonexistent-topic-xyz")
    assert response.status_code == 404


def test_dedup_store_mark_processed_is_idempotent(fresh_dedup_store):
    """
    Calling mark_processed twice on the same pair must not raise
    and must not corrupt the store.
    """
    store = fresh_dedup_store
    store.mark_processed("payments", "evt-001", "2025-01-01T00:00:00Z")
    store.mark_processed("payments", "evt-001", "2025-01-01T00:00:00Z")  # second call

    assert store.is_duplicate("payments", "evt-001") is True


def test_dedup_store_persists_across_reinit(fresh_dedup_store):
    """
    Simulate a restart: re-initialise DedupStore from the same DB file.
    The previously marked event must still be detected as a duplicate.
    """
    store = fresh_dedup_store
    store.mark_processed("auth", "evt-restart-001", "2025-01-01T00:00:00Z")

    # Simulate restart by creating a new instance pointing to the same file
    restarted_store = DedupStore(db_path=TEST_DB_PATH)
    assert restarted_store.is_duplicate("auth", "evt-restart-001") is True


@pytest.mark.asyncio
async def test_stress_batch_5000_events(client):
    """
    Send 5000 events (20% duplicates) and assert it completes within 15 seconds.
    unique_processed should equal ~4000, duplicate_dropped ~1000.
    """
    total = 5000
    duplicate_rate = 0.20

    unique_events = [make_event(topic="stress") for _ in range(total)]
    duplicate_count = int(total * duplicate_rate)
    import random
    duplicates = random.choices(unique_events, k=duplicate_count)
    all_events = unique_events + duplicates
    random.shuffle(all_events)

    batch_size = 100
    start = time.time()

    for i in range(0, len(all_events), batch_size):
        batch = all_events[i : i + batch_size]
        response = await client.post("/publish", json=make_batch(*batch))
        assert response.status_code == 202

    elapsed = time.time() - start
    assert elapsed < 15, f"Batch publish took too long: {elapsed:.2f}s"

    # Allow consumer to drain
    await asyncio.sleep(4)

    stats = (await client.get("/stats")).json()
    assert stats["unique_processed"] >= total * (1 - duplicate_rate) * 0.95