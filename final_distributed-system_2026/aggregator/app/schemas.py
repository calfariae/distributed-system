from pydantic import BaseModel, Field, validator
from datetime import datetime, timezone
from typing import Optional, Dict, Any, List
import uuid

class Event(BaseModel):
    topic: str = Field(..., min_length=1, max_length=255)
    event_id: Optional[str] = None
    timestamp: Optional[datetime] = None
    source: str = Field(..., min_length=1)
    payload: Dict[str, Any] = Field(default_factory=dict)
    
    @validator('event_id', pre=True, always=True)
    def set_event_id(cls, v):
        if v is None:
            return str(uuid.uuid4())
        return v
    
    @validator('timestamp', pre=True, always=True)
    def set_timestamp(cls, v):
        if v is None:
            return datetime.now(timezone.utc)
        if isinstance(v, str):
            try:
                # Handle ISO format with Z
                if v.endswith('Z'):
                    v = v[:-1] + '+00:00'
                return datetime.fromisoformat(v)
            except:
                return datetime.now(timezone.utc)
        return v

class EventBatch(BaseModel):
    events: List[Event]
    atomic: bool = True

class StatsResponse(BaseModel):
    total_received: int
    total_unique_processed: int
    total_duplicate_dropped: int
    topics: Dict[str, Dict[str, int]]
    uptime_seconds: float