import pytest
from pydantic import ValidationError
from app.dedup import DedupManager
from app.schemas import Event
from sqlalchemy import select
from app.models import ProcessedEvent

@pytest.mark.asyncio
async def test_invalid_and_empty_payload(db_session):
    """Test payload edge cases:
    - None/missing payload defaults to {} and processes successfully
    - Non-dict payload raises ValidationError before reaching dedup
    """
    dedup = DedupManager()

    # Empty payload (omitted) defaults to {} and should process fine
    event_no_payload = Event(topic="payload.test", source="test")
    is_dup, error = await dedup.process_event(db_session, event_no_payload)
    assert not is_dup
    assert error is None

    # Verify it was saved with an empty dict payload
    stmt = select(ProcessedEvent).where(ProcessedEvent.event_id == event_no_payload.event_id)
    result = await db_session.execute(stmt)
    saved = result.scalar_one()
    assert saved.payload == {}

    # Non-dict payload should be rejected by Pydantic before it ever reaches dedup
    with pytest.raises(ValidationError):
        Event(topic="payload.test", source="test", payload="not-a-dict")

    with pytest.raises(ValidationError):
        Event(topic="payload.test", source="test", payload=["a", "list"])