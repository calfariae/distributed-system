import asyncio
import json
import logging
import time
import random
from enum import Enum
from typing import Dict, Set, Optional, List
from aiohttp import web

from src.nodes.base_node import BaseNode

logger = logging.getLogger(__name__)

class LockMode(Enum):
    SHARED = "shared"
    EXCLUSIVE = "exclusive"

class NodeState(Enum):
    FOLLOWER = "follower"
    CANDIDATE = "candidate"
    LEADER = "leader"

class Lock:
    def __init__(self, resource_id: str, mode: LockMode, owner_id: str):
        self.resource_id = resource_id
        self.mode = mode
        self.owner_id = owner_id
        self.granted_time = time.time()

class DistributedLockManager(BaseNode):
    def __init__(self, node_id: str, host: str, port: int, peers: List[str]):
        super().__init__(node_id, host, port)
        self.peers = peers
        
        # Raft state
        self.current_term = 0
        self.voted_for = None
        self.state = NodeState.FOLLOWER
        self.leader_id = None
        
        # Election
        self.election_timeout = time.time() + random.uniform(1.0, 2.0)
        self.last_heartbeat = time.time()
        
        # Lock state
        self.locks: Dict[str, Lock] = {}
        self.node_locks: Dict[str, Set[str]] = {}
        self.waiting_requests: Dict[str, List[Dict]] = {}
    
    def setup_routes(self, app: web.Application):
        """Setup HTTP routes for lock management"""
        app.router.add_post('/health', self.handle_health)
        app.router.add_post('/raft/request_vote', self.handle_request_vote)
        app.router.add_post('/raft/heartbeat', self.handle_heartbeat)
        app.router.add_post('/lock/acquire', self.handle_acquire_lock)
        app.router.add_post('/lock/release', self.handle_release_lock)
        app.router.add_get('/lock/status', self.handle_lock_status)
    
    async def start(self):
        """Start lock manager with Raft"""
        await super().start()
        
        # Start background tasks
        asyncio.create_task(self.election_loop())
        asyncio.create_task(self.heartbeat_loop())
        
        logger.info(f"Lock manager started on node {self.node_id} at {self.host}:{self.port}")
    
    async def election_loop(self):
        """Main Raft election loop"""
        await asyncio.sleep(random.uniform(0.5, 1.0))  # Initial random delay
        
        while self.is_running:
            try:
                current_time = time.time()
                
                # Only followers and candidates start elections
                if self.state != NodeState.LEADER:
                    if current_time > self.election_timeout:
                        await self.start_election()
                
                await asyncio.sleep(0.1)  # Check every 100ms
            except Exception as e:
                logger.error(f"Error in election loop: {e}")
                await asyncio.sleep(0.5)
    
    async def heartbeat_loop(self):
        """Send heartbeats if leader"""
        await asyncio.sleep(1.0)  # Initial delay
        
        while self.is_running:
            try:
                if self.state == NodeState.LEADER:
                    await self.send_heartbeats()
                    await asyncio.sleep(0.5)  # Heartbeat every 500ms
                else:
                    current_time = time.time()
                    # If no heartbeat received for too long, become candidate
                    if current_time - self.last_heartbeat > 3.0:
                        logger.info(f"Node {self.node_id} - No heartbeat received, starting election")
                        self.state = NodeState.FOLLOWER
                        self.election_timeout = time.time()
                    
                    await asyncio.sleep(0.5)
            except Exception as e:
                logger.error(f"Error in heartbeat loop: {e}")
                await asyncio.sleep(0.5)
    
    async def start_election(self):
        """Start a leader election"""
        self.state = NodeState.CANDIDATE
        self.current_term += 1
        self.voted_for = self.node_id
        
        logger.info(f"Node {self.node_id} starting election for term {self.current_term}")
        print(f"Node {self.node_id} starting election for term {self.current_term}")
        
        votes = 1  # Vote for self
        
        for peer in self.peers:
            try:
                response = await self.send_message(peer, "/raft/request_vote", {
                    "term": self.current_term,
                    "candidate_id": self.node_id
                })
                
                if response.get("vote_granted"):
                    votes += 1
                    logger.info(f"Node {self.node_id} got vote from {peer}")
            except Exception as e:
                logger.error(f"Error requesting vote from {peer}: {e}")
        
        # Need majority (including self)
        majority = (len(self.peers) + 1) // 2 + 1
        
        if votes >= majority:
            logger.info(f"Node {self.node_id} won election with {votes} votes")
            print(f"Node {self.node_id} won election with {votes} votes")
            self.state = NodeState.LEADER
            self.leader_id = self.node_id
            await self.send_heartbeats()  # Immediately send heartbeats
        else:
            logger.info(f"Node {self.node_id} lost election with {votes} votes")
            self.state = NodeState.FOLLOWER
            self.election_timeout = time.time() + random.uniform(1.0, 2.0)
    
    async def send_heartbeats(self):
        """Send heartbeat to all peers"""
        for peer in self.peers:
            try:
                await self.send_message(peer, "/raft/heartbeat", {
                    "term": self.current_term,
                    "leader_id": self.node_id
                })
            except Exception as e:
                logger.error(f"Error sending heartbeat to {peer}: {e}")
    
    async def handle_request_vote(self, request: web.Request) -> web.Response:
        """Handle vote request from candidate"""
        data = await request.json()
        candidate_term = data.get("term", 0)
        candidate_id = data.get("candidate_id")
        
        vote_granted = False
        
        # If candidate's term is higher, update our term and become follower
        if candidate_term > self.current_term:
            self.current_term = candidate_term
            self.voted_for = None
            self.state = NodeState.FOLLOWER
        
        # Grant vote if term matches and we haven't voted
        if candidate_term == self.current_term and self.voted_for is None:
            self.voted_for = candidate_id
            vote_granted = True
            logger.info(f"Node {self.node_id} voted for {candidate_id} in term {candidate_term}")
        
        return web.Response(
            text=json.dumps({
                "term": self.current_term,
                "vote_granted": vote_granted
            }),
            content_type="application/json"
        )
    
    async def handle_heartbeat(self, request: web.Request) -> web.Response:
        """Handle heartbeat from leader"""
        data = await request.json()
        leader_term = data.get("term", 0)
        leader_id = data.get("leader_id")
        
        if leader_term >= self.current_term:
            self.current_term = leader_term
            self.leader_id = leader_id
            self.state = NodeState.FOLLOWER
            self.last_heartbeat = time.time()
            self.voted_for = None  # Reset vote for new term
        
        return web.Response(
            text=json.dumps({
                "term": self.current_term,
                "success": True
            }),
            content_type="application/json"
        )
    
    async def handle_acquire_lock(self, request: web.Request) -> web.Response:
        """Handle lock acquisition request"""
        data = await request.json()
        resource_id = data.get("resource_id")
        mode_str = data.get("mode", "shared")
        owner_id = data.get("owner_id")
        
        if not resource_id or not owner_id:
            return web.Response(
                text=json.dumps({"error": "resource_id and owner_id required"}),
                status=400,
                content_type="application/json"
            )
        
        # Only leader can grant locks
        if self.state != NodeState.LEADER:
            return web.Response(
                text=json.dumps({
                    "error": "Not leader",
                    "leader_id": self.leader_id
                }),
                status=200,  # Don't use 307 to avoid redirect issues
                content_type="application/json"
            )
        
        mode = LockMode.EXCLUSIVE if mode_str == "exclusive" else LockMode.SHARED
        can_grant = self.check_lock_compatibility(resource_id, mode, owner_id)
        
        if can_grant:
            lock = Lock(resource_id, mode, owner_id)
            self.locks[resource_id] = lock
            
            # Track node locks
            if owner_id not in self.node_locks:
                self.node_locks[owner_id] = set()
            self.node_locks[owner_id].add(resource_id)
            
            logger.info(f"Lock granted: {resource_id} ({mode.value}) to {owner_id}")
            
            return web.Response(
                text=json.dumps({
                    "granted": True,
                    "resource_id": resource_id,
                    "mode": mode.value,
                    "owner_id": owner_id
                }),
                content_type="application/json"
            )
        else:
            # Add to waiting queue
            if resource_id not in self.waiting_requests:
                self.waiting_requests[resource_id] = []
            self.waiting_requests[resource_id].append({
                "owner_id": owner_id,
                "mode": mode.value
            })
            
            return web.Response(
                text=json.dumps({
                    "granted": False,
                    "resource_id": resource_id,
                    "waiting": True
                }),
                content_type="application/json"
            )
    
    async def handle_release_lock(self, request: web.Request) -> web.Response:
        """Handle lock release request"""
        data = await request.json()
        resource_id = data.get("resource_id")
        owner_id = data.get("owner_id")
        
        if resource_id in self.locks and self.locks[resource_id].owner_id == owner_id:
            del self.locks[resource_id]
            
            # Remove from node locks
            if owner_id in self.node_locks:
                self.node_locks[owner_id].discard(resource_id)
                if not self.node_locks[owner_id]:
                    del self.node_locks[owner_id]
            
            logger.info(f"Lock released: {resource_id} by {owner_id}")
            
            # Grant waiting requests
            await self.process_waiting_requests(resource_id)
            
            return web.Response(
                text=json.dumps({"released": True}),
                content_type="application/json"
            )
        
        return web.Response(
            text=json.dumps({"error": "Lock not found or not owned"}),
            content_type="application/json"
        )
    
    async def handle_lock_status(self, request: web.Request) -> web.Response:
        """Get status of all locks"""
        locks_status = {}
        for resource_id, lock in self.locks.items():
            locks_status[resource_id] = {
                "mode": lock.mode.value,
                "owner_id": lock.owner_id,
                "granted_time": lock.granted_time
            }
        
        return web.Response(
            text=json.dumps({
                "locks": locks_status,
                "state": self.state.value,
                "leader_id": self.leader_id
            }),
            content_type="application/json"
        )
    
    def check_lock_compatibility(self, resource_id: str, mode: LockMode, owner_id: str) -> bool:
        """Check if lock can be granted"""
        if resource_id not in self.locks:
            return True
        
        existing_lock = self.locks[resource_id]
        
        # Same owner can always reacquire
        if existing_lock.owner_id == owner_id:
            return True
        
        # Shared locks are compatible with other shared locks
        if mode == LockMode.SHARED and existing_lock.mode == LockMode.SHARED:
            return True
        
        # Exclusive locks are incompatible with everything
        return False
    
    async def process_waiting_requests(self, resource_id: str):
        """Process waiting requests for a resource"""
        if resource_id not in self.waiting_requests:
            return
        
        waiting = self.waiting_requests[resource_id]
        granted = []
        
        for req_data in waiting[:]:
            owner_id = req_data["owner_id"]
            mode = LockMode(req_data["mode"])
            
            if self.check_lock_compatibility(resource_id, mode, owner_id):
                lock = Lock(resource_id, mode, owner_id)
                self.locks[resource_id] = lock
                
                if owner_id not in self.node_locks:
                    self.node_locks[owner_id] = set()
                self.node_locks[owner_id].add(resource_id)
                
                granted.append(req_data)
                waiting.remove(req_data)
        
        if not waiting:
            del self.waiting_requests[resource_id]