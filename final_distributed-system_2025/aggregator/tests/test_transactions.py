import pytest
from sqlalchemy import select
from app.dedup import DedupManager
from app.models import ProcessedEvent
from app.schemas import Event

@pytest.mark.asyncio
async def test_atomic_batch_transaction(db_session):
    """Test batch transaction works"""
    dedup = DedupManager()
    
    # Process events
    events = [
        Event(topic="batch.topic", event_id=f"batch-{i}", source="test", payload={"data": i})
        for i in range(3)
    ]
    
    for event in events:
        is_dup, error = await dedup.process_event(db_session, event)
        assert not is_dup
        assert error is None
    
    # Verify all events were saved
    stmt = select(ProcessedEvent).where(ProcessedEvent.topic == "batch.topic")
    result = await db_session.execute(stmt)
    saved_events = result.scalars().all()
    assert len(saved_events) == 3

@pytest.mark.asyncio
async def test_transaction_rollback_on_error(db_session):
    """Test that duplicate causes rollback"""
    dedup = DedupManager()
    
    event1 = Event(topic="rollback.topic", event_id="rollback-001", source="test", payload={"data": 1})
    event2 = Event(topic="rollback.topic", event_id="rollback-001", source="test", payload={"data": 2})
    
    # First event succeeds
    is_dup, error = await dedup.process_event(db_session, event1)
    assert not is_dup
    assert error is None
    
    # Second should be duplicate
    is_dup, error = await dedup.process_event(db_session, event2)
    assert is_dup
    assert error is not None
    
    # Verify only one event saved
    stmt = select(ProcessedEvent).where(ProcessedEvent.topic == "rollback.topic")
    result = await db_session.execute(stmt)
    saved_events = result.scalars().all()
    assert len(saved_events) == 1