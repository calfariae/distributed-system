import datetime
from pydantic import BaseModel, field_validator
from typing import Any


class Event(BaseModel):
    event_id: str
    topic: str
    timestamp: datetime.datetime
    source: str
    payload: dict[str, Any]

    @field_validator("event_id", "topic", "source")
    @classmethod
    def must_not_be_empty(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("field must not be empty or whitespace")
        return v

class BatchPublishRequest(BaseModel):
    events: list[Event]