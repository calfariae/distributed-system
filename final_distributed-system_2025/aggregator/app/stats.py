from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from .models import ProcessedEvent, EventStats
from typing import Dict, List, Any

class StatsManager:
    async def get_stats(self, session: AsyncSession) -> Dict[str, Any]:
        # Get aggregated stats
        total_received = await session.scalar(select(func.sum(EventStats.received)))
        total_unique = await session.scalar(select(func.sum(EventStats.unique_processed)))
        total_duplicates = await session.scalar(select(func.sum(EventStats.duplicate_dropped)))
        
        # Get per-topic stats
        topic_stats = {}
        result = await session.execute(select(EventStats))
        for stat in result.scalars().all():
            topic_stats[stat.topic] = {
                "received": stat.received or 0,
                "unique": stat.unique_processed or 0,
                "duplicates": stat.duplicate_dropped or 0  # Ensure 0 instead of None
            }
        
        return {
            "total_received": total_received or 0,
            "total_unique_processed": total_unique or 0,
            "total_duplicate_dropped": total_duplicates or 0,
            "topics": topic_stats
        }
    
    async def get_events(self, session: AsyncSession, topic: str = None, limit: int = 100, offset: int = 0):
        stmt = select(ProcessedEvent)
        if topic:
            stmt = stmt.where(ProcessedEvent.topic == topic)
        stmt = stmt.order_by(ProcessedEvent.processed_at.desc()).limit(limit).offset(offset)
        
        result = await session.execute(stmt)
        events = []
        for event in result.scalars().all():
            events.append({
                "topic": event.topic,
                "event_id": event.event_id,
                "source": event.source,
                "payload": event.payload,
                "timestamp": event.timestamp.isoformat() if event.timestamp else None,
                "processed_at": event.processed_at.isoformat() if event.processed_at else None
            })
        return events