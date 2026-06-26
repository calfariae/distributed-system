
"""
Full integration test - runs all components together
"""
import pytest
import asyncio
import aiohttp
import random
import time

def get_random_port():
    return random.randint(9000, 9999)

@pytest.fixture
async def full_system():
    """Create full system with all components"""
    from src.nodes.lock_manager import DistributedLockManager
    from src.nodes.queue_node import DistributedQueueNode
    from src.nodes.cache_node import DistributedCacheNode
    from src.nodes.ml_node import MLNode
    
    # Generate ports for 3 nodes
    base_ports = [get_random_port() for _ in range(3)]
    
    lock_nodes = []
    queue_nodes = []
    cache_nodes = []
    ml_nodes = []
    
    for i, base_port in enumerate(base_ports):
        node_id = f"node{i+1}"
        peers = [f"localhost:{p}" for j, p in enumerate(base_ports) if j != i]
        
        # Lock Manager
        lock = DistributedLockManager(f"{node_id}_lock", "localhost", base_port, peers)
        await lock.start()
        lock_nodes.append(lock)
        
        # Queue Node
        queue = DistributedQueueNode(f"{node_id}_queue", "localhost", base_port + 1000, peers)
        await queue.start()
        queue_nodes.append(queue)
        
        # Cache Node
        cache = DistributedCacheNode(f"{node_id}_cache", "localhost", base_port + 2000, peers)
        await cache.start()
        cache_nodes.append(cache)
        
        # ML Node
        ml = MLNode(f"{node_id}_ml", "localhost", base_port + 3000, peers)
        await ml.start()
        ml_nodes.append(ml)
    
    # Wait for initialization
    await asyncio.sleep(3)
    
    yield {
        "locks": lock_nodes,
        "queues": queue_nodes,
        "caches": cache_nodes,
        "ml": ml_nodes
    }
    
    # Cleanup
    for node in lock_nodes + queue_nodes + cache_nodes + ml_nodes:
        await node.stop()
    await asyncio.sleep(0.5)

@pytest.mark.asyncio
async def test_full_system_startup(full_system):
    """Test that all components start"""
    assert len(full_system["locks"]) == 3
    assert len(full_system["queues"]) == 3
    assert len(full_system["caches"]) == 3
    assert len(full_system["ml"]) == 3
    
    for lock in full_system["locks"]:
        assert lock.is_running
    
    for queue in full_system["queues"]:
        assert queue.is_running
    
    for cache in full_system["caches"]:
        assert cache.is_running
    
    print("✓ All components started successfully")

@pytest.mark.asyncio
async def test_cross_component_workflow(full_system):
    """Test a workflow that uses all components"""
    lock_nodes = full_system["locks"]
    queue = full_system["queues"][0]
    cache = full_system["caches"][0]
    ml = full_system["ml"][0]
    
    async with aiohttp.ClientSession() as session:
        # Find the lock leader
        leader = None
        for lock in lock_nodes:
            resp = await session.get(f"http://localhost:{lock.port}/lock/status")
            data = await resp.json()
            if data.get("state") == "leader":
                leader = lock
                break
        
        if not leader:
            print("Waiting for leader election...")
            await asyncio.sleep(2)
            for lock in lock_nodes:
                resp = await session.get(f"http://localhost:{lock.port}/lock/status")
                data = await resp.json()
                if data.get("state") == "leader":
                    leader = lock
                    break
        
        assert leader is not None, "No leader elected!"
        print(f"1. Leader: {leader.node_id} on port {leader.port}")
        
        # 1. Acquire a lock from the leader
        lock_resp = await session.post(
            f"http://localhost:{leader.port}/lock/acquire",
            json={"resource_id": "workflow_test", "mode": "exclusive", "owner_id": "workflow"}
        )
        lock_data = await lock_resp.json()
        print(f"2. Lock acquired: {lock_data.get('granted', lock_data)}")
        
        # 2. Cache some data
        cache_resp = await session.post(
            f"http://localhost:{cache.port}/cache/put",
            json={"key": "workflow_data", "value": "processed"}
        )
        cache_data = await cache_resp.json()
        print(f"3. Cache put: {cache_data}")
        
        # 3. Push to queue
        queue_resp = await session.post(
            f"http://localhost:{queue.port}/queue/push",
            json={"queue_name": "results", "data": {"status": "done"}}
        )
        queue_data = await queue_resp.json()
        print(f"4. Queue push: {queue_data}")
        
        # 4. Release lock via leader
        release_resp = await session.post(
            f"http://localhost:{leader.port}/lock/release",
            json={"resource_id": "workflow_test", "owner_id": "workflow"}
        )
        release_data = await release_resp.json()
        print(f"5. Lock released: {release_data}")
        
        # 5. Check ML status
        ml_resp = await session.get(f"http://localhost:{ml.port}/ml/status")
        ml_data = await ml_resp.json()
        print(f"6. ML Status: {ml_data}")
        
        print("✓ Cross-component workflow completed successfully!")