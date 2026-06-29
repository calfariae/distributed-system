import asyncio
import json
import logging
from abc import ABC, abstractmethod
from typing import Dict, Any
import aiohttp
from aiohttp import web

from src.utils.config import config
from src.utils.metrics import metrics

logging.basicConfig(level=config.LOG_LEVEL)
logger = logging.getLogger(__name__)

class BaseNode(ABC):
    def __init__(self, node_id: str, host: str, port: int):
        self.node_id = node_id
        self.host = host
        self.port = port
        self.session: aiohttp.ClientSession = None
        self.is_running = False
        
    async def start(self):
        """Start the node"""
        self.session = aiohttp.ClientSession()
        self.is_running = True
        logger.info(f"Node {self.node_id} starting on {self.host}:{self.port}")
        
        # Start HTTP server
        app = web.Application()
        self.setup_routes(app)
        runner = web.AppRunner(app)
        await runner.setup()
        site = web.TCPSite(runner, self.host, self.port)
        await site.start()
        
        # Start background tasks
        asyncio.create_task(self.heartbeat_task())
        
    async def stop(self):
        """Stop the node"""
        self.is_running = False
        if self.session:
            await self.session.close()
        logger.info(f"Node {self.node_id} stopped")
    
    @abstractmethod
    def setup_routes(self, app: web.Application):
        """Setup HTTP routes"""
        pass
    
    async def send_message(self, target_node: str, endpoint: str, data: Dict) -> Dict:
        """Send message to another node"""
        metrics.start_operation("send_message")
        try:
            # Parse target node info
            node_host, node_port = target_node.split(":")
            url = f"http://{node_host}:{node_port}{endpoint}"
            
            async with self.session.post(url, json=data) as resp:
                result = await resp.json()
                metrics.end_operation("send_message")
                return result
        except Exception as e:
            logger.error(f"Failed to send message to {target_node}: {e}")
            metrics.end_operation("send_message")
            return {"error": str(e)}
    
    async def broadcast(self, endpoint: str, data: Dict, exclude_self: bool = True):
        """Broadcast message to all known nodes"""
        tasks = []
        for node in config.CLUSTER_NODES:
            if exclude_self and node.startswith(self.node_id):
                continue
            tasks.append(self.send_message(node, endpoint, data))
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
        return results
    
    async def heartbeat_task(self):
        """Periodic heartbeat to detect node failures"""
        while self.is_running:
            await asyncio.sleep(2)
            for node in config.CLUSTER_NODES:
                if not node.startswith(self.node_id):
                    try:
                        await self.send_message(node, "/health", {"node_id": self.node_id})
                    except Exception:
                        logger.warning(f"Node {node} is unreachable")
    
    async def handle_health(self, request: web.Request) -> web.Response:
        """Health check endpoint"""
        data = await request.json()
        return web.Response(
            text=json.dumps({
                "status": "healthy",
                "node_id": self.node_id,
                "from": data.get("node_id", "unknown")
            }),
            content_type="application/json"
        )