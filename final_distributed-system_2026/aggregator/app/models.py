from sqlalchemy import Column, Integer, String, DateTime, JSON, Index, UniqueConstraint, text
from sqlalchemy.ext.declarative import declarative_base
from datetime import datetime, timezone


duplicate_dropped = Column(Integer, nullable=False, server_default=text("0"))

Base = declarative_base()

class ProcessedEvent(Base):
    __tablename__ = "processed_events"
    
    id = Column(Integer, primary_key=True, index=True)
    topic = Column(String(255), nullable=False)
    event_id = Column(String(255), nullable=False)
    source = Column(String(255))
    payload = Column(JSON)
    timestamp = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    processed_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    
    __table_args__ = (
        UniqueConstraint('topic', 'event_id', name='uq_topic_event'),
        Index('idx_topic_event', 'topic', 'event_id'),
    )

class EventStats(Base):
    __tablename__ = "event_stats"
    
    id = Column(Integer, primary_key=True)
    topic = Column(String(255), unique=True, nullable=False)
    received = Column(Integer, default=0, nullable=False)
    unique_processed = Column(Integer, default=0, nullable=False)
    duplicate_dropped = Column(Integer, nullable=False, server_default=text("0"))
    last_updated = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))