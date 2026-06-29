import asyncio
import json
import logging
from enum import Enum
from typing import Dict, List, Optional
from dataclasses import dataclass, field
import random

logger = logging.getLogger(__name__)

class NodeState(Enum):
    FOLLOWER = "follower"
    CANDIDATE = "candidate"
    LEADER = "leader"

@dataclass
class LogEntry:
    term: int
    command: Dict
    index: int = 0

@dataclass
class RaftNode:
    node_id: str
    peers: List[str]
    
    # Persistent state
    current_term: int = 0
    voted_for: Optional[str] = None
    log: List[LogEntry] = field(default_factory=list)
    
    # Volatile state
    state: NodeState = NodeState.FOLLOWER
    commit_index: int = 0
    last_applied: int = 0
    
    # Leader state
    next_index: Dict[str, int] = field(default_factory=dict)
    match_index: Dict[str, int] = field(default_factory=dict)
    
    # Election
    election_timeout: float = 0
    last_heartbeat: float = 0
    
    def __post_init__(self):
        self.reset_election_timeout()
    
    def reset_election_timeout(self):
        """Reset election timeout to random value between 150-300ms"""
        import time
        self.election_timeout = time.time() + random.uniform(0.15, 0.3)
    
    def become_follower(self, term: int):
        """Transition to follower state"""
        self.state = NodeState.FOLLOWER
        self.current_term = term
        self.voted_for = None
        logger.info(f"Node {self.node_id} became FOLLOWER for term {term}")
    
    def become_candidate(self):
        """Transition to candidate state"""
        self.state = NodeState.CANDIDATE
        self.current_term += 1
        self.voted_for = self.node_id
        self.reset_election_timeout()
        logger.info(f"Node {self.node_id} became CANDIDATE for term {self.current_term}")
    
    def become_leader(self):
        """Transition to leader state"""
        self.state = NodeState.LEADER
        self.next_index = {peer: len(self.log) for peer in self.peers}
        self.match_index = {peer: 0 for peer in self.peers}
        logger.info(f"Node {self.node_id} became LEADER for term {self.current_term}")
    
    def append_entries(self, entries: List[LogEntry]) -> bool:
        """Append entries to log"""
        for entry in entries:
            entry.index = len(self.log)
            self.log.append(entry)
        return True