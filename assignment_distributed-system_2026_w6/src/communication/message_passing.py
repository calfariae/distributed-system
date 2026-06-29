import json
import asyncio
from typing import Dict, Any, Optional
from enum import Enum

class MessageType(Enum):
    REQUEST = "request"
    RESPONSE = "response"
    HEARTBEAT = "heartbeat"
    LOCK_REQUEST = "lock_request"
    LOCK_RELEASE = "lock_release"
    QUEUE_PUSH = "queue_push"
    QUEUE_PULL = "queue_pull"
    CACHE_INVALIDATE = "cache_invalidate"

class Message:
    def __init__(self, msg_type: MessageType, sender: str, 
                 receiver: str, payload: Dict[str, Any], 
                 msg_id: Optional[str] = None):
        self.type = msg_type
        self.sender = sender
        self.receiver = receiver
        self.payload = payload
        self.msg_id = msg_id or str(id(self))
    
    def to_dict(self) -> Dict:
        return {
            "type": self.type.value,
            "sender": self.sender,
            "receiver": self.receiver,
            "payload": self.payload,
            "msg_id": self.msg_id
        }
    
    @classmethod
    def from_dict(cls, data: Dict) -> 'Message':
        return cls(
            msg_type=MessageType(data["type"]),
            sender=data["sender"],
            receiver=data["receiver"],
            payload=data["payload"],
            msg_id=data["msg_id"]
        )

class MessageQueue:
    def __init__(self):
        self.queue: asyncio.Queue = asyncio.Queue()
    
    async def publish(self, message: Message):
        await self.queue.put(message)
    
    async def consume(self) -> Message:
        return await self.queue.get()