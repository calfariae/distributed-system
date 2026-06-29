import asyncio
import logging
from typing import Dict, Set
from collections import defaultdict

logger = logging.getLogger(__name__)

class FailureDetector:
    def __init__(self, timeout: float = 5.0):
        self.timeout = timeout
        self.last_heartbeat: Dict[str, float] = {}
        self.failed_nodes: Set[str] = set()
        self.suspected_nodes: Set[str] = set()
    
    def heartbeat_received(self, node_id: str):
        """Update last heartbeat time for a node"""
        import time
        self.last_heartbeat[node_id] = time.time()
        
        # If node was suspected, remove from suspected list
        if node_id in self.suspected_nodes:
            self.suspected_nodes.remove(node_id)
            logger.info(f"Node {node_id} is back online")
    
    async def monitor(self):
        """Monitor nodes for failures"""
        import time
        while True:
            current_time = time.time()
            
            # Check all known nodes
            for node_id, last_time in self.last_heartbeat.items():
                if current_time - last_time > self.timeout:
                    if node_id not in self.failed_nodes:
                        self.suspected_nodes.add(node_id)
                        logger.warning(f"Node {node_id} is suspected to be down")
                        
                        # After double timeout, mark as failed
                        if current_time - last_time > self.timeout * 2:
                            self.failed_nodes.add(node_id)
                            self.suspected_nodes.remove(node_id)
                            logger.error(f"Node {node_id} is confirmed down")
            
            await asyncio.sleep(1)
    
    def is_node_alive(self, node_id: str) -> bool:
        return node_id not in self.failed_nodes
    
    def get_active_nodes(self) -> Set[str]:
        return {node for node in self.last_heartbeat.keys() 
                if node not in self.failed_nodes}