#!/usr/bin/env python3
"""
Distributed Synchronization System - Main Entry Point
Runs all components: Lock Manager, Queue, Cache, and ML
"""

import asyncio
import argparse
import sys
import os

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.nodes.lock_manager import DistributedLockManager
from src.nodes.queue_node import DistributedQueueNode
from src.nodes.cache_node import DistributedCacheNode
from src.nodes.ml_node import MLNode


async def main():
    parser = argparse.ArgumentParser(description="Distributed Sync System")
    parser.add_argument("--node-type", choices=["lock", "queue", "cache", "ml", "all"], 
                        default="all", help="Type of node to run")
    parser.add_argument("--node-id", default="node1", help="Node ID")
    parser.add_argument("--port", type=int, default=8000, help="Port")
    parser.add_argument("--peers", nargs="*", default=[], help="Peer addresses (host:port)")
    
    args = parser.parse_args()
    
    peers = args.peers if args.peers else ["localhost:8001", "localhost:8002"]
    
    nodes = []
    
    if args.node_type in ["lock", "all"]:
        lock_node = DistributedLockManager(
            f"{args.node_id}_lock", "0.0.0.0", args.port, peers
        )
        await lock_node.start()
        nodes.append(lock_node)
        print(f"Lock Manager running on port {args.port}")
    
    if args.node_type in ["queue", "all"]:
        queue_port = args.port + 1000
        queue_node = DistributedQueueNode(
            f"{args.node_id}_queue", "0.0.0.0", queue_port, 
            [f"localhost:{p+1000}" for p in [args.port, args.port+1, args.port+2] if p != args.port]
        )
        await queue_node.start()
        nodes.append(queue_node)
        print(f"Queue Node running on port {queue_port}")
    
    if args.node_type in ["cache", "all"]:
        cache_port = args.port + 2000
        cache_node = DistributedCacheNode(
            f"{args.node_id}_cache", "0.0.0.0", cache_port,
            [f"localhost:{p+2000}" for p in [args.port, args.port+1, args.port+2] if p != args.port]
        )
        await cache_node.start()
        nodes.append(cache_node)
        print(f"Cache Node running on port {cache_port}")
    
    if args.node_type in ["ml", "all"]:
        ml_port = args.port + 3000
        ml_node = MLNode(
            f"{args.node_id}_ml", "0.0.0.0", ml_port,
            [f"localhost:{p+3000}" for p in [args.port, args.port+1, args.port+2] if p != args.port]
        )
        await ml_node.start()
        nodes.append(ml_node)
        print(f"ML Node running on port {ml_port}")
    
    print(f"\nAll nodes started. Press Ctrl+C to stop.")
    
    try:
        # Keep running
        while True:
            await asyncio.sleep(1)
    except KeyboardInterrupt:
        print("\nShutting down...")
        for node in nodes:
            await node.stop()
        print("All nodes stopped.")


if __name__ == "__main__":
    asyncio.run(main())