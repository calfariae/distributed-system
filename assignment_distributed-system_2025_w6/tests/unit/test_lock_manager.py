import pytest
import asyncio
import aiohttp
import random
from src.nodes.lock_manager import DistributedLockManager, LockMode, NodeState

def get_random_port():
    return random.randint(9000, 9999)

@pytest.fixture
async def lock_manager_nodes():
    """Create 3 lock manager nodes"""
    ports = [get_random_port() for _ in range(3)]
    nodes = []
    
    for i, port in enumerate(ports):
        node_id = f"node{i+1}"
        # Peers as "localhost:port" format for send_message compatibility
        peers = [f"localhost:{p}" for j, p in enumerate(ports) if j != i]
        node = DistributedLockManager(node_id, "localhost", port, peers)
        await node.start()
        nodes.append(node)
    
    # Wait for leader election
    print("\nWaiting for leader election...")
    await asyncio.sleep(3)
    
    # Print states
    for node in nodes:
        print(f"Node {node.node_id} (port {node.port}): state={node.state.value}, term={node.current_term}, leader={node.leader_id}")
    
    yield nodes
    
    # Cleanup
    for node in nodes:
        await node.stop()
    await asyncio.sleep(0.5)

@pytest.mark.asyncio
async def test_leader_election(lock_manager_nodes):
    """Test that a leader is elected"""
    # Give more time for election if needed
    for _ in range(5):
        leaders = [node for node in lock_manager_nodes if node.state == NodeState.LEADER]
        if len(leaders) == 1:
            break
        await asyncio.sleep(1)
    
    leaders = [node for node in lock_manager_nodes if node.state == NodeState.LEADER]
    
    print(f"\nFound {len(leaders)} leader(s)")
    for node in lock_manager_nodes:
        print(f"Node {node.node_id}: state={node.state.value}, leader={node.leader_id}")
    
    assert len(leaders) == 1, f"Expected 1 leader, got {len(leaders)}"
    print(f"Leader is {leaders[0].node_id}")

@pytest.mark.asyncio
async def test_acquire_lock(lock_manager_nodes):
    """Test lock acquisition"""
    # Find the leader - wait if needed
    leaders = []
    for _ in range(5):
        leaders = [node for node in lock_manager_nodes if node.state == NodeState.LEADER]
        if leaders:
            break
        await asyncio.sleep(1)
    
    if not leaders:
        for node in lock_manager_nodes:
            print(f"Node {node.node_id}: state={node.state.value}")
        assert False, "No leader elected"
    
    leader = leaders[0]
    print(f"\nUsing leader: {leader.node_id}:{leader.port}")
    
    async with aiohttp.ClientSession() as session:
        response = await session.post(
            f"http://localhost:{leader.port}/lock/acquire",
            json={
                "resource_id": "resource1",
                "mode": "exclusive",
                "owner_id": "client1"
            }
        )
        data = await response.json()
        print(f"Lock response: {data}")
        assert data.get("granted") == True, f"Lock not granted: {data}"
        print("Lock acquired successfully")

@pytest.mark.asyncio
async def test_release_lock(lock_manager_nodes):
    """Test lock release"""
    # Find the leader
    leaders = []
    for _ in range(5):
        leaders = [node for node in lock_manager_nodes if node.state == NodeState.LEADER]
        if leaders:
            break
        await asyncio.sleep(1)
    
    if not leaders:
        for node in lock_manager_nodes:
            print(f"Node {node.node_id}: state={node.state.value}")
        assert False, "No leader elected"
    
    leader = leaders[0]
    print(f"\nUsing leader: {leader.node_id}:{leader.port}")
    
    async with aiohttp.ClientSession() as session:
        # First acquire
        response = await session.post(
            f"http://localhost:{leader.port}/lock/acquire",
            json={
                "resource_id": "resource1",
                "mode": "exclusive",
                "owner_id": "client1"
            }
        )
        acquire_data = await response.json()
        assert acquire_data.get("granted") == True, f"Acquire failed: {acquire_data}"
        
        # Then release
        response = await session.post(
            f"http://localhost:{leader.port}/lock/release",
            json={
                "resource_id": "resource1",
                "owner_id": "client1"
            }
        )
        data = await response.json()
        print(f"Release response: {data}")
        assert data.get("released") == True, f"Lock not released: {data}"
        print("Lock released successfully")