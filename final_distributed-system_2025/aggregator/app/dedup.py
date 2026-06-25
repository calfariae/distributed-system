from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text, select
from sqlalchemy.exc import IntegrityError, OperationalError
from .models import ProcessedEvent, EventStats
from .schemas import Event
import logging
from datetime import datetime, timezone
from typing import Tuple, Optional
import asyncio

logger = logging.getLogger(__name__)

def make_naive(dt: datetime) -> datetime:
    if dt.tzinfo is not None:
        return dt.replace(tzinfo=None)
    return dt

class DedupManager:
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.max_retries = 3
    
    async def process_event(
        self, 
        session: AsyncSession, 
        event: Event,
        atomic_batch: bool = True,
        retry_count: int = 0
    ) -> Tuple[bool, Optional[str]]:
        try:
            stmt = select(ProcessedEvent).where(
                ProcessedEvent.topic == event.topic,
                ProcessedEvent.event_id == event.event_id
            )
            result = await session.execute(stmt)
            existing = result.scalar_one_or_none()
            
            if existing:
                self.logger.info(f"🔄 Duplicate event detected: {event.topic}:{event.event_id}")
                await self._update_stats_atomic(session, event.topic, is_duplicate=True)
                await session.commit()
                return True, "Duplicate event detected"
            
            payload_dict = event.payload if isinstance(event.payload, dict) else event.payload.dict()
            
            timestamp = event.timestamp or datetime.now(timezone.utc)
            processed_at = datetime.now(timezone.utc)
            
            processed_event = ProcessedEvent(
                topic=event.topic,
                event_id=event.event_id,
                source=event.source,
                payload=payload_dict,
                timestamp=make_naive(timestamp),
                processed_at=make_naive(processed_at)
            )
            
            session.add(processed_event)
            await self._update_stats_atomic(session, event.topic, is_duplicate=False)
            await session.commit()
            return False, None
            
        except IntegrityError as e:
            await session.rollback()
            
            if "uq_topic_event" in str(e) or "duplicate key" in str(e).lower():
                self.logger.info(f"🔄 Duplicate event detected (race condition): {event.topic}:{event.event_id}")
                try:
                    await self._update_stats_atomic(session, event.topic, is_duplicate=True)
                    await session.commit()
                except Exception as stats_error:
                    self.logger.error(f"Error updating duplicate stats: {stats_error}")
                    await session.rollback()
                return True, "Duplicate event detected"
            
            return False, f"Database integrity error: {str(e)}"
            
        except OperationalError as e:
            if "could not serialize access" in str(e):
                await session.rollback()
                if retry_count < self.max_retries:
                    self.logger.warning(
                        f"Serialization conflict for {event.topic}:{event.event_id}, "
                        f"retrying ({retry_count + 1}/{self.max_retries})"
                    )
                    await asyncio.sleep(0.1 * (2 ** retry_count))
                    return await self.process_event(
                        session, event, atomic_batch, retry_count + 1
                    )
            raise
            
        except Exception as e:
            await session.rollback()
            self.logger.error(f"Error processing event: {str(e)}")
            return False, f"Processing error: {str(e)}"
    
    async def _update_stats_atomic(self, session: AsyncSession, topic: str, is_duplicate: bool):
        """Atomic stats update using ORM — works with both SQLite and PostgreSQL."""
        now = make_naive(datetime.now(timezone.utc))

        stmt = select(EventStats).where(EventStats.topic == topic)
        result = await session.execute(stmt)
        stats = result.scalar_one_or_none()

        if stats is None:
            stats = EventStats(
                topic=topic,
                received=1,
                unique_processed=0 if is_duplicate else 1,
                duplicate_dropped=1 if is_duplicate else 0,
                last_updated=now,
            )
            session.add(stats)
        else:
            stats.received += 1
            if is_duplicate:
                stats.duplicate_dropped += 1
            else:
                stats.unique_processed += 1
            stats.last_updated = now

        if is_duplicate:
            self.logger.info(f"📊 Duplicate stats updated: topic={topic}, duplicates={stats.duplicate_dropped}")
        else:
            self.logger.info(f"📊 Unique stats updated: topic={topic}, unique={stats.unique_processed}")