import pytest
import json
from sqlalchemy import select
from app.dedup import DedupManager
from app.models import ProcessedEvent, EventStats
from app.schemas import Event

class MockRedis:
    def __init__(self):
        self.queue = []
        self.retry_queue = []
    
    async def rpush(self, key, value):
        if "retry" in key:
            self.retry_queue.append(value)
        else:
            self.queue.append(value)
        return len(self.queue)
    
    async def rpop(self, key):
        if "retry" in key:
            return self.retry_queue.pop(0) if self.retry_queue else None
        return self.queue.pop(0) if self.queue else None
    
    async def ping(self):
        return True
    
    async def close(self):
        pass

@pytest.mark.asyncio
async def test_end_to_end_event_flow(db_session):
    """Test complete flow: publish -> process -> store"""
    dedup = DedupManager()
    
    event = Event(
        topic="e2e.test",
        source="test",
        payload={"data": "test payload"}
    )
    
    is_dup, error = await dedup.process_event(db_session, event)
    assert not is_dup
    assert error is None
    
    stmt = select(ProcessedEvent).where(ProcessedEvent.event_id == event.event_id)
    result = await db_session.execute(stmt)
    saved_event = result.scalar_one()
    assert saved_event.topic == "e2e.test"

@pytest.mark.asyncio
async def test_duplicate_with_retry(db_session):
    """Test duplicate detection with retry logic"""
    dedup = DedupManager()
    
    event = Event(
        topic="retry.test",
        event_id="retry-001",
        source="test",
        payload={"data": "first"}
    )
    
    is_dup, error = await dedup.process_event(db_session, event)
    assert not is_dup
    assert error is None
    
    is_dup, error = await dedup.process_event(db_session, event)
    assert is_dup
    assert error is not None
    
    stmt = select(EventStats).where(EventStats.topic == "retry.test")
    result = await db_session.execute(stmt)
    stats = result.scalar_one()
    assert stats.received == 2
    assert stats.unique_processed == 1
    assert stats.duplicate_dropped == 1

@pytest.mark.asyncio
async def test_persistence_after_restart(db_session):
    """Test data persistence after simulated restart"""
    dedup = DedupManager()
    
    events = [
        Event(topic="persist.test", event_id=f"persist-{i}", source="test", payload={"data": i})
        for i in range(5)
    ]
    
    for event in events:
        is_dup, error = await dedup.process_event(db_session, event)
        assert not is_dup
        assert error is None
    
    stmt = select(ProcessedEvent).where(ProcessedEvent.topic == "persist.test")
    result = await db_session.execute(stmt)
    saved_events = result.scalars().all()
    assert len(saved_events) == 5

@pytest.mark.asyncio
async def test_consumer_processing(db_session):
    """Test consumer processes events from queue"""
    dedup = DedupManager()
    mock_redis = MockRedis()
    
    events = [
        Event(topic="consumer.test", event_id=f"consumer-{i}", source="test", payload={"data": i})
        for i in range(3)
    ]
    
    for event in events:
        is_dup, error = await dedup.process_event(db_session, event)
        assert not is_dup
        assert error is None
        await mock_redis.rpush("events_queue", event.model_dump_json())
    
    assert len(mock_redis.queue) == 3
    
    processed = 0
    for _ in range(3):
        event_data = await mock_redis.rpop("events_queue")
        if event_data:
            processed += 1
            data = json.loads(event_data)
            assert "topic" in data
            assert "event_id" in data
    
    assert processed == 3

@pytest.mark.asyncio
async def test_batch_processing_atomicity(db_session):
    """Test batch processing"""
    dedup = DedupManager()
    
    events = [
        Event(topic="batch.atomic", event_id="batch-001", source="test", payload={"data": 1}),
        Event(topic="batch.atomic", event_id="batch-002", source="test", payload={"data": 2}),
        Event(topic="batch.atomic", event_id="batch-001", source="test", payload={"data": 3}),
        Event(topic="batch.atomic", event_id="batch-003", source="test", payload={"data": 4}),
    ]
    
    results = []
    for event in events:
        is_dup, error = await dedup.process_event(db_session, event)
        results.append(is_dup)
    
    assert results[0] == False
    assert results[1] == False
    assert results[2] == True
    assert results[3] == False
    
    stmt = select(ProcessedEvent).where(ProcessedEvent.topic == "batch.atomic")
    result = await db_session.execute(stmt)
    saved_events = result.scalars().all()
    assert len(saved_events) == 3