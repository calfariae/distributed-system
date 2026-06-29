import pytest
import time
import uuid
from sqlalchemy import select, func
from app.dedup import DedupManager
from app.models import ProcessedEvent, EventStats
from app.schemas import Event

@pytest.mark.asyncio
async def test_batch_stress_timing(db_session):
    """Process 100 unique events and assert completion under 2 seconds."""
    dedup = DedupManager()
    batch_size = 100

    events = [
        Event(
            topic="stress.test",
            event_id=str(uuid.uuid4()),
            source="stress",
            payload={"index": i, "data": "x" * 64}
        )
        for i in range(batch_size)
    ]

    start = time.perf_counter()

    for event in events:
        is_dup, error = await dedup.process_event(db_session, event)
        assert not is_dup
        assert error is None

    elapsed = time.perf_counter() - start

    # Verify all 100 were persisted
    stmt = select(func.count()).where(ProcessedEvent.topic == "stress.test")
    result = await db_session.execute(stmt)
    count = result.scalar()
    assert count == batch_size

    # Verify stats are consistent with processed count
    stmt = select(EventStats).where(EventStats.topic == "stress.test")
    result = await db_session.execute(stmt)
    stats = result.scalar_one()
    assert stats.received == batch_size
    assert stats.unique_processed == batch_size
    assert stats.duplicate_dropped == 0

    assert elapsed < 2.0, f"100 events took {elapsed:.2f}s — expected under 2s"
    print(f"\n⏱ 100 events processed in {elapsed:.3f}s ({batch_size/elapsed:.0f} events/sec)")


@pytest.mark.asyncio
async def test_mixed_batch_stress_timing(db_session):
    """Process 100 events (50 unique + 50 duplicates) and assert completion under 2 seconds."""
    dedup = DedupManager()

    unique_ids = [str(uuid.uuid4()) for _ in range(50)]
    events = []

    # 50 unique events
    for i, eid in enumerate(unique_ids):
        events.append(Event(
            topic="stress.mixed",
            event_id=eid,
            source="stress",
            payload={"index": i}
        ))

    # 50 duplicates (repeat the same IDs)
    for i, eid in enumerate(unique_ids):
        events.append(Event(
            topic="stress.mixed",
            event_id=eid,
            source="stress",
            payload={"index": i, "retry": True}
        ))

    start = time.perf_counter()

    results = [await dedup.process_event(db_session, e) for e in events]

    elapsed = time.perf_counter() - start

    unique_count  = sum(1 for is_dup, _ in results if not is_dup)
    dup_count     = sum(1 for is_dup, _ in results if is_dup)

    assert unique_count == 50
    assert dup_count    == 50

    stmt = select(EventStats).where(EventStats.topic == "stress.mixed")
    result = await db_session.execute(stmt)
    stats = result.scalar_one()
    assert stats.received          == 100
    assert stats.unique_processed  == 50
    assert stats.duplicate_dropped == 50

    assert elapsed < 2.0, f"100 mixed events took {elapsed:.2f}s — expected under 2s"
    print(f"\n⏱ 100 mixed events processed in {elapsed:.3f}s ({100/elapsed:.0f} events/sec)")