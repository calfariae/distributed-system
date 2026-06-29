import asyncio
import json
import logging
import time
from enum import Enum
from typing import Dict, Optional, Set, List, Any
from aiohttp import web
from collections import OrderedDict

from src.nodes.base_node import BaseNode
from src.utils.metrics import metrics

logger = logging.getLogger(__name__)

class CacheState(Enum):
    MODIFIED = "M"    # Data is modified, only copy, must write back
    EXCLUSIVE = "E"   # Data is clean, only copy
    SHARED = "S"      # Data is clean, other copies exist
    INVALID = "I"     # Data is invalid

class CacheLine:
    def __init__(self, key: str, value: Any, state: CacheState):
        self.key = key
        self.value = value
        self.state = state
        self.last_access = time.time()

class MESICache:
    def __init__(self, max_size: int = 100):
        self.max_size = max_size
        self.cache: OrderedDict[str, CacheLine] = OrderedDict()
    
    def get(self, key: str) -> Optional[CacheLine]:
        """Get a cache line, update LRU"""
        if key in self.cache:
            line = self.cache[key]
            line.last_access = time.time()
            # Move to end (most recently used)
            self.cache.move_to_end(key)
            return line
        return None
    
    def put(self, key: str, value: Any, state: CacheState):
        """Add or update a cache line"""
        if key in self.cache:
            self.cache[key].value = value
            self.cache[key].state = state
            self.cache[key].last_access = time.time()
            self.cache.move_to_end(key)
        else:
            # Check if we need to evict
            if len(self.cache) >= self.max_size:
                self._evict_lru()
            
            self.cache[key] = CacheLine(key, value, state)
    
    def remove(self, key: str):
        """Remove a cache line"""
        if key in self.cache:
            del self.cache[key]
    
    def _evict_lru(self):
        """Evict the least recently used item"""
        if self.cache:
            # First item is LRU
            key, line = next(iter(self.cache.items()))
            
            # If modified, we'd need to write back (handled by caller)
            del self.cache[key]
            logger.debug(f"Evicted cache line: {key}")
            return line
        return None
    
    def get_stats(self) -> Dict:
        """Get cache statistics"""
        states = {}
        for line in self.cache.values():
            state_name = line.state.value
            states[state_name] = states.get(state_name, 0) + 1
        
        return {
            "size": len(self.cache),
            "max_size": self.max_size,
            "states": states,
            "hit_rate": metrics.get_stats("cache_hit").get("avg", 0) if hasattr(metrics, 'get_stats') else 0
        }

class DistributedCacheNode(BaseNode):
    def __init__(self, node_id: str, host: str, port: int, peers: List[str]):
        super().__init__(node_id, host, port)
        self.peers = peers
        self.cache = MESICache(max_size=100)
        
        # Track which nodes have shared copies of each key
        self.sharing_map: Dict[str, Set[str]] = {}
        
        # Backing store (simulated - in real system would be database)
        self.backing_store: Dict[str, Any] = {}
    
    def setup_routes(self, app: web.Application):
        """Setup HTTP routes for cache management"""
        app.router.add_post('/health', self.handle_health)
        app.router.add_post('/cache/get', self.handle_cache_get)
        app.router.add_post('/cache/put', self.handle_cache_put)
        app.router.add_post('/cache/invalidate', self.handle_invalidate)
        app.router.add_post('/cache/snoop', self.handle_snoop)
        app.router.add_get('/cache/stats', self.handle_cache_stats)
    
    async def start(self):
        """Start cache node"""
        await super().start()
        logger.info(f"Cache node started on {self.host}:{self.port}")
    
    async def handle_cache_get(self, request: web.Request) -> web.Response:
        """Handle cache read request"""
        data = await request.json()
        key = data.get("key")
        
        if not key:
            return web.Response(
                text=json.dumps({"error": "key required"}),
                status=400,
                content_type="application/json"
            )
        
        metrics.record_value("cache_access", 1)
        
        # Check local cache
        cached = self.cache.get(key)
        
        if cached and cached.state != CacheState.INVALID:
            metrics.record_value("cache_hit", 1)
            logger.debug(f"Cache HIT for key '{key}' in state {cached.state.value}")
            
            return web.Response(
                text=json.dumps({
                    "found": True,
                    "key": key,
                    "value": cached.value,
                    "state": cached.state.value,
                    "source": self.node_id
                }),
                content_type="application/json"
            )
        
        metrics.record_value("cache_miss", 1)
        logger.debug(f"Cache MISS for key '{key}'")
        
        # Need to fetch from other nodes or backing store
        # First, snoop other nodes
        value, state = await self.snoop_other_nodes(key)
        
        if value is not None:
            # Found in another node's cache
            self.cache.put(key, value, state)
            
            return web.Response(
                text=json.dumps({
                    "found": True,
                    "key": key,
                    "value": value,
                    "state": state.value,
                    "source": "peer"
                }),
                content_type="application/json"
            )
        
        # Fetch from backing store
        if key in self.backing_store:
            value = self.backing_store[key]
            self.cache.put(key, value, CacheState.EXCLUSIVE)
            
            return web.Response(
                text=json.dumps({
                    "found": True,
                    "key": key,
                    "value": value,
                    "state": CacheState.EXCLUSIVE.value,
                    "source": "store"
                }),
                content_type="application/json"
            )
        
        return web.Response(
            text=json.dumps({
                "found": False,
                "key": key
            }),
            content_type="application/json"
        )
    
    async def handle_cache_put(self, request: web.Request) -> web.Response:
        """Handle cache write request"""
        data = await request.json()
        key = data.get("key")
        value = data.get("value")
        
        if not key or value is None:
            return web.Response(
                text=json.dumps({"error": "key and value required"}),
                status=400,
                content_type="application/json"
            )
        
        # Invalidate other copies first
        await self.invalidate_other_nodes(key)
        
        # Update local cache (Modified state - only copy, dirty)
        self.cache.put(key, value, CacheState.MODIFIED)
        
        # Update backing store
        self.backing_store[key] = value
        
        # Clear sharing map for this key
        self.sharing_map.pop(key, None)
        
        logger.debug(f"Cache PUT key '{key}' in MODIFIED state")
        
        return web.Response(
            text=json.dumps({
                "success": True,
                "key": key,
                "state": CacheState.MODIFIED.value
            }),
            content_type="application/json"
        )
    
    async def handle_invalidate(self, request: web.Request) -> web.Response:
        """Handle invalidation request from another node"""
        data = await request.json()
        key = data.get("key")
        
        if key and key in self.cache.cache:
            line = self.cache.cache[key]
            old_state = line.state
            
            if line.state == CacheState.MODIFIED:
                # Write back to requestor if needed
                pass
            
            line.state = CacheState.INVALID
            logger.debug(f"Invalidated key '{key}' (was {old_state.value})")
        
        return web.Response(
            text=json.dumps({"invalidated": True}),
            content_type="application/json"
        )
    
    async def handle_snoop(self, request: web.Request) -> web.Response:
        """Handle bus snoop request from another node"""
        data = await request.json()
        key = data.get("key")
        request_type = data.get("type", "read")
        
        if key not in self.cache.cache:
            return web.Response(
                text=json.dumps({"found": False}),
                content_type="application/json"
            )
        
        line = self.cache.cache[key]
        
        if request_type == "read":
            if line.state == CacheState.MODIFIED:
                # Transition to Shared (other node will also have copy)
                line.state = CacheState.SHARED
                
                # Track sharing
                requester = data.get("requester")
                if requester:
                    if key not in self.sharing_map:
                        self.sharing_map[key] = set()
                    self.sharing_map[key].add(requester)
                
                return web.Response(
                    text=json.dumps({
                        "found": True,
                        "value": line.value,
                        "state": line.state.value
                    }),
                    content_type="application/json"
                )
            
            elif line.state == CacheState.EXCLUSIVE:
                # Transition to Shared
                line.state = CacheState.SHARED
                
                requester = data.get("requester")
                if requester:
                    if key not in self.sharing_map:
                        self.sharing_map[key] = set()
                    self.sharing_map[key].add(requester)
                
                return web.Response(
                    text=json.dumps({
                        "found": True,
                        "value": line.value,
                        "state": line.state.value
                    }),
                    content_type="application/json"
                )
            
            elif line.state == CacheState.SHARED:
                return web.Response(
                    text=json.dumps({
                        "found": True,
                        "value": line.value,
                        "state": line.state.value
                    }),
                    content_type="application/json"
                )
        
        elif request_type == "write":
            # Invalidate on write
            line.state = CacheState.INVALID
            return web.Response(
                text=json.dumps({"invalidated": True}),
                content_type="application/json"
            )
        
        return web.Response(
            text=json.dumps({"found": False}),
            content_type="application/json"
        )
    
    async def handle_cache_stats(self, request: web.Request) -> web.Response:
        """Get cache statistics"""
        return web.Response(
            text=json.dumps({
                "node_id": self.node_id,
                "cache": self.cache.get_stats(),
                "sharing_map_size": len(self.sharing_map)
            }),
            content_type="application/json"
        )
    
    async def snoop_other_nodes(self, key: str) -> tuple:
        """Snoop other nodes for a cache line"""
        for peer in self.peers:
            try:
                response = await self.send_message(peer, "/cache/snoop", {
                    "key": key,
                    "type": "read",
                    "requester": f"{self.host}:{self.port}"
                })
                
                if response.get("found"):
                    state_str = response.get("state", "S")
                    state = CacheState(state_str)
                    return response["value"], state
            except Exception as e:
                logger.error(f"Error snooping peer {peer}: {e}")
        
        return None, None
    
    async def invalidate_other_nodes(self, key: str):
        """Invalidate key in all other nodes"""
        for peer in self.peers:
            try:
                await self.send_message(peer, "/cache/invalidate", {"key": key})
            except Exception as e:
                logger.error(f"Error invalidating peer {peer}: {e}")