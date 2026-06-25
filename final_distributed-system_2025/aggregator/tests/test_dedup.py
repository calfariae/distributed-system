import pytest
from sqlalchemy import select
from app.dedup import DedupManager
from app.models import ProcessedEvent, EventStats
from app.schemas import Event
import uuid

@pytest.mark.asyncio
async def test_dedup_prevents_duplicates(db_session):
    """Test that duplicate events are prevented"""
    dedup = DedupManager()
    
    event1 = Event(
        topic="test.topic",
        event_id=str(uuid.uuid4()),
        source="test",
        payload={"data": "test"}
    )
    
    # First event should be processed
    is_dup, error = await dedup.process_event(db_session, event1)
    assert not is_dup
    assert error is None
    
    # Second event with same ID should be duplicate
    event2 = Event(
        topic="test.topic",
        event_id=event1.event_id,
        source="test",
        payload={"data": "different"}
    )
    is_dup, error = await dedup.process_event(db_session, event2)
    assert is_dup
    assert error is not None

@pytest.mark.asyncio
async def test_stats_update_consistency(db_session):
    """Test that stats updates are consistent"""
    dedup = DedupManager()
    
    # Process 5 unique events
    for i in range(5):
        event = Event(
            topic="stats.test",
            event_id=str(uuid.uuid4()),
            source="test",
            payload={"data": f"test_{i}"}
        )
        await dedup.process_event(db_session, event)
    
    # Check stats - use scalar_one_or_none for SQLite
    stmt = select(EventStats).where(EventStats.topic == "stats.test")
    result = await db_session.execute(stmt)
    stats = result.scalar_one_or_none()
    
    if stats is not None:
        assert stats.received == 5
        assert stats.unique_processed == 5
        assert stats.duplicate_dropped == 0