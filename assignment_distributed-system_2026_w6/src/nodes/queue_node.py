import asyncio
import json
import logging
import hashlib
import time
import os
from typing import Dict, List, Optional, Any
from aiohttp import web
from collections import defaultdict

from src.nodes.base_node import BaseNode

logger = logging.getLogger(__name__)

class ConsistentHash:
    """Simple consistent hashing implementation"""
    def __init__(self, nodes: List[str], virtual_nodes: int = 3):
        self.virtual_nodes = virtual_nodes
        self.ring: Dict[int, str] = {}
        self.sorted_keys: List[int] = []
        self.nodes = nodes
        
        for node in nodes:
            self._add_node(node)
    
    def _hash(self, key: str) -> int:
        """Hash a key to an integer"""
        return int(hashlib.md5(key.encode()).hexdigest(), 16)
    
    def _add_node(self, node: str):
        """Add a node with virtual nodes"""
        for i in range(self.virtual_nodes):
            key = self._hash(f"{node}:{i}")
            self.ring[key] = node
            self.sorted_keys.append(key)
        self.sorted_keys.sort()
    
    def get_node(self, key: str) -> str:
        """Get the node responsible for a key"""
        if not self.ring:
            return None
        
        hash_key = self._hash(key)
        
        for node_key in self.sorted_keys:
            if hash_key <= node_key:
                return self.ring[node_key]
        
        # Wrap around to first node
        return self.ring[self.sorted_keys[0]]

class Message:
    """Represents a message in the queue"""
    def __init__(self, msg_id: str, data: Dict, timestamp: float = None):
        self.msg_id = msg_id
        self.data = data
        self.timestamp = timestamp or time.time()
        self.delivered = False
        self.delivery_count = 0
    
    def to_dict(self) -> Dict:
        return {
            "msg_id": self.msg_id,
            "data": self.data,
            "timestamp": self.timestamp,
            "delivered": self.delivered,
            "delivery_count": self.delivery_count
        }
    
    @classmethod
    def from_dict(cls, data: Dict) -> 'Message':
        msg = cls(
            msg_id=data["msg_id"],
            data=data["data"],
            timestamp=data["timestamp"]
        )
        msg.delivered = data.get("delivered", False)
        msg.delivery_count = data.get("delivery_count", 0)
        return msg

class DistributedQueueNode(BaseNode):
    def __init__(self, node_id: str, host: str, port: int, peers: List[str]):
        super().__init__(node_id, host, port)
        self.peers = peers
        
        # Queue storage
        self.queues: Dict[str, List[Message]] = defaultdict(list)
        
        # Message tracking
        self.processing_messages: Dict[str, Message] = {}  # Messages being processed
        self.delivered_messages: Dict[str, float] = {}  # Track delivery for at-least-once
        
        # Consistent hashing
        all_nodes = peers + [f"{host}:{port}"]
        self.hash_ring = ConsistentHash(all_nodes)
        
        # Persistence directory
        self.persistence_dir = f"/tmp/queue_data_{node_id}"
        os.makedirs(self.persistence_dir, exist_ok=True)
        
        # Recovery flag
        self.recovered = False
    
    def setup_routes(self, app: web.Application):
        """Setup HTTP routes for queue management"""
        app.router.add_post('/health', self.handle_health)
        app.router.add_post('/queue/push', self.handle_push)
        app.router.add_post('/queue/pull', self.handle_pull)
        app.router.add_post('/queue/ack', self.handle_ack)
        app.router.add_get('/queue/stats', self.handle_stats)
        app.router.add_post('/queue/recover', self.handle_recover)
    
    async def start(self):
        """Start queue node with recovery"""
        await super().start()
        
        # Recover persisted messages
        await self.recover_messages()
        self.recovered = True
        
        # Start background tasks
        asyncio.create_task(self.redelivery_task())
        asyncio.create_task(self.persistence_task())
        
        logger.info(f"Queue node started on {self.host}:{self.port}")
    
    async def handle_push(self, request: web.Request) -> web.Response:
        """Push a message to the queue"""
        data = await request.json()
        
        queue_name = data.get("queue_name", "default")
        message_data = data.get("data")
        msg_id = data.get("msg_id", self.generate_msg_id())
        
        if not message_data:
            return web.Response(
                text=json.dumps({"error": "message data required"}),
                status=400,
                content_type="application/json"
            )
        
        # Determine which node owns this queue
        target_node = self.hash_ring.get_node(queue_name)
        
        # If message belongs to another node, forward it
        if target_node != f"{self.host}:{self.port}":
            return web.Response(
                text=json.dumps({
                    "forwarded": True,
                    "target_node": target_node
                }),
                status=200,
                content_type="application/json"
            )
        
        # Create and store message
        message = Message(msg_id, message_data)
        self.queues[queue_name].append(message)
        
        logger.info(f"Message {msg_id} pushed to queue {queue_name}")
        
        return web.Response(
            text=json.dumps({
                "success": True,
                "msg_id": msg_id,
                "queue_name": queue_name
            }),
            content_type="application/json"
        )
    
    async def handle_pull(self, request: web.Request) -> web.Response:
        """Pull a message from the queue"""
        data = await request.json()
        queue_name = data.get("queue_name", "default")
        consumer_id = data.get("consumer_id", "unknown")
        
        # Determine which node owns this queue
        target_node = self.hash_ring.get_node(queue_name)
        
        # If queue belongs to another node, forward request
        if target_node != f"{self.host}:{self.port}":
            return web.Response(
                text=json.dumps({
                    "forwarded": True,
                    "target_node": target_node
                }),
                status=200,
                content_type="application/json"
            )
        
        # Check if queue exists and has messages
        if queue_name not in self.queues or not self.queues[queue_name]:
            return web.Response(
                text=json.dumps({
                    "success": True,
                    "message": None,
                    "queue_name": queue_name
                }),
                content_type="application/json"
            )
        
        # Get next message
        message = self.queues[queue_name].pop(0)
        message.delivery_count += 1
        
        # Track as processing
        self.processing_messages[message.msg_id] = message
        self.delivered_messages[message.msg_id] = time.time()
        
        logger.info(f"Message {message.msg_id} pulled from queue {queue_name} by {consumer_id}")
        
        return web.Response(
            text=json.dumps({
                "success": True,
                "message": message.to_dict(),
                "queue_name": queue_name
            }),
            content_type="application/json"
        )
    
    async def handle_ack(self, request: web.Request) -> web.Response:
        """Acknowledge message processing"""
        data = await request.json()
        msg_id = data.get("msg_id")
        
        if not msg_id:
            return web.Response(
                text=json.dumps({"error": "msg_id required"}),
                status=400,
                content_type="application/json"
            )
        
        # Remove from processing
        if msg_id in self.processing_messages:
            message = self.processing_messages.pop(msg_id)
            message.delivered = True
            
            # Remove from delivered tracking
            self.delivered_messages.pop(msg_id, None)
            
            logger.info(f"Message {msg_id} acknowledged")
            
            return web.Response(
                text=json.dumps({"success": True, "msg_id": msg_id}),
                content_type="application/json"
            )
        
        return web.Response(
            text=json.dumps({"error": "Message not found in processing"}),
            status=404,
            content_type="application/json"
        )
    
    async def handle_stats(self, request: web.Request) -> web.Response:
        """Get queue statistics"""
        stats = {
            "node_id": self.node_id,
            "host": f"{self.host}:{self.port}",
            "queues": {}
        }
        
        for queue_name, messages in self.queues.items():
            stats["queues"][queue_name] = {
                "message_count": len(messages),
                "oldest_message": messages[0].timestamp if messages else None,
                "newest_message": messages[-1].timestamp if messages else None
            }
        
        stats["processing_count"] = len(self.processing_messages)
        stats["total_messages"] = sum(len(q) for q in self.queues.values())
        
        return web.Response(
            text=json.dumps(stats),
            content_type="application/json"
        )
    
    async def handle_recover(self, request: web.Request) -> web.Response:
        """Handle recovery request - redistribute messages after node failure"""
        # Recover from persistence
        await self.recover_messages()
        
        return web.Response(
            text=json.dumps({
                "recovered": True,
                "total_messages": sum(len(q) for q in self.queues.values())
            }),
            content_type="application/json"
        )
    
    def generate_msg_id(self) -> str:
        """Generate a unique message ID"""
        import uuid
        return f"{self.node_id}_{uuid.uuid4().hex[:8]}"
    
    async def redelivery_task(self):
        """Redeliver messages that haven't been acknowledged"""
        redelivery_timeout = 10  # seconds
        
        while self.is_running:
            await asyncio.sleep(5)  # Check every 5 seconds
            
            current_time = time.time()
            messages_to_redeliver = []
            
            # Find messages that haven't been acknowledged
            for msg_id, message in list(self.processing_messages.items()):
                delivery_time = self.delivered_messages.get(msg_id, 0)
                
                if current_time - delivery_time > redelivery_timeout:
                    messages_to_redeliver.append((msg_id, message))
            
            # Redeliver failed messages
            for msg_id, message in messages_to_redeliver:
                logger.warning(f"Redelivering message {msg_id} (attempt {message.delivery_count + 1})")
                
                # Remove from processing
                self.processing_messages.pop(msg_id, None)
                self.delivered_messages.pop(msg_id, None)
                
                # Put back in appropriate queue (find which queue it belongs to)
                for queue_name, queue in self.queues.items():
                    # We need to determine which queue this message was from
                    # In a real implementation, we'd track this
                    pass
                
                # For simplicity, add to a redelivery queue
                if message.delivery_count < 3:  # Max 3 attempts
                    message.delivery_count += 1
                    self.queues["redelivery"].append(message)
    
    async def persistence_task(self):
        """Periodically persist messages to disk"""
        while self.is_running:
            await asyncio.sleep(10)  # Persist every 10 seconds
            
            try:
                await self.persist_messages()
            except Exception as e:
                logger.error(f"Error persisting messages: {e}")
    
    async def persist_messages(self):
        """Save messages to disk for recovery"""
        data = {
            "node_id": self.node_id,
            "timestamp": time.time(),
            "queues": {},
            "processing": {}
        }
        
        # Save queue messages
        for queue_name, messages in self.queues.items():
            data["queues"][queue_name] = [msg.to_dict() for msg in messages]
        
        # Save processing messages
        data["processing"] = {
            msg_id: msg.to_dict() for msg_id, msg in self.processing_messages.items()
        }
        
        # Write to file
        filename = os.path.join(self.persistence_dir, "queue_state.json")
        with open(filename, 'w') as f:
            json.dump(data, f, indent=2)
        
        logger.debug(f"Persisted {sum(len(q) for q in self.queues.values())} messages")
    
    async def recover_messages(self):
        """Recover messages from disk after failure"""
        filename = os.path.join(self.persistence_dir, "queue_state.json")
        
        if not os.path.exists(filename):
            logger.info(f"No recovery file found for node {self.node_id}")
            return
        
        try:
            with open(filename, 'r') as f:
                data = json.load(f)
            
            recovered_count = 0
            
            # Recover queue messages
            for queue_name, messages in data.get("queues", {}).items():
                for msg_data in messages:
                    message = Message.from_dict(msg_data)
                    if not message.delivered:
                        self.queues[queue_name].append(message)
                        recovered_count += 1
            
            # Recover processing messages
            for msg_id, msg_data in data.get("processing", {}).items():
                message = Message.from_dict(msg_data)
                if not message.delivered:
                    self.processing_messages[msg_id] = message
                    recovered_count += 1
            
            logger.info(f"Recovered {recovered_count} messages for node {self.node_id}")
            
        except Exception as e:
            logger.error(f"Error recovering messages: {e}")