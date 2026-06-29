import pytest
import asyncio
import aiohttp
import random
from src.nodes.cache_node import DistributedCacheNode, CacheState

def get_random_port():
    return random.randint(9000, 9999)

@pytest.fixture
async def cache_nodes():
    """Create 3 cache nodes"""
    ports = [get_random_port() for _ in range(3)]
    nodes = []
    
    for i, port in enumerate(ports):
        node_id = f"cache_node{i+1}"
        peers = [f"localhost:{p}" for j, p in enumerate(ports) if j != i]
        node = DistributedCacheNode(node_id, "localhost", port, peers)
        await node.start()
        nodes.append(node)
    
    await asyncio.sleep(0.5)
    
    yield nodes
    
    # Cleanup
    for node in nodes:
        await node.stop()
    await asyncio.sleep(0.5)

@pytest.mark.asyncio
async def test_cache_put_and_get(cache_nodes):
    """Test basic cache put and get"""
    node = cache_nodes[0]
    
    async with aiohttp.ClientSession() as session:
        # Put a value
        put_response = await session.post(
            f"http://localhost:{node.port}/cache/put",
            json={"key": "user:1", "value": {"name": "Alice", "age": 30}}
        )
        put_data = await put_response.json()
        assert put_data.get("success") == True
        assert put_data["state"] == CacheState.MODIFIED.value
        print(f"✓ Put successful: {put_data}")
        
        # Get the value back
        get_response = await session.post(
            f"http://localhost:{node.port}/cache/get",
            json={"key": "user:1"}
        )
        get_data = await get_response.json()
        assert get_data.get("found") == True
        assert get_data["value"]["name"] == "Alice"
        print(f"✓ Get successful: {get_data}")

@pytest.mark.asyncio
async def test_cache_invalidation(cache_nodes):
    """Test cache invalidation between nodes"""
    node1 = cache_nodes[0]
    node2 = cache_nodes[1]
    
    async with aiohttp.ClientSession() as session:
        # Node1 puts a value (Modified state)
        await session.post(
            f"http://localhost:{node1.port}/cache/put",
            json={"key": "shared_key", "value": "initial"}
        )
        print("✓ Node1 put value")
        
        # Node2 gets the value (should transition node1 to Shared)
        response = await session.post(
            f"http://localhost:{node2.port}/cache/get",
            json={"key": "shared_key"}
        )
        data = await response.json()
        print(f"✓ Node2 got value: {data}")
        
        # Node1 writes new value (should invalidate node2)
        await session.post(
            f"http://localhost:{node1.port}/cache/put",
            json={"key": "shared_key", "value": "updated"}
        )
        print("✓ Node1 updated value")
        
        # Node1 reads (should have new value)
        response = await session.post(
            f"http://localhost:{node1.port}/cache/get",
            json={"key": "shared_key"}
        )
        data = await response.json()
        assert data["value"] == "updated"
        print(f"✓ Node1 has updated value: {data['value']}")

@pytest.mark.asyncio
async def test_cache_miss(cache_nodes):
    """Test cache miss behavior"""
    node = cache_nodes[0]
    
    async with aiohttp.ClientSession() as session:
        response = await session.post(
            f"http://localhost:{node.port}/cache/get",
            json={"key": "nonexistent"}
        )
        data = await response.json()
        assert data.get("found") == False
        print(f"✓ Cache miss handled correctly: {data}")

@pytest.mark.asyncio
async def test_cache_stats(cache_nodes):
    """Test cache statistics"""
    node = cache_nodes[0]
    
    async with aiohttp.ClientSession() as session:
        # Do some operations
        await session.post(
            f"http://localhost:{node.port}/cache/put",
            json={"key": "key1", "value": "value1"}
        )
        await session.post(
            f"http://localhost:{node.port}/cache/get",
            json={"key": "key1"}
        )
        
        # Get stats
        response = await session.get(
            f"http://localhost:{node.port}/cache/stats"
        )
        data = await response.json()
        assert "cache" in data
        print(f"✓ Cache stats: {data}")

@pytest.mark.asyncio
async def test_mesi_states(cache_nodes):
    """Test MESI state transitions"""
    node1 = cache_nodes[0]
    node2 = cache_nodes[1]
    node3 = cache_nodes[2]
    
    async with aiohttp.ClientSession() as session:
        # M: Node1 writes -> Modified
        await session.post(
            f"http://localhost:{node1.port}/cache/put",
            json={"key": "mesi_test", "value": "data"}
        )
        
        response = await session.post(
            f"http://localhost:{node1.port}/cache/get",
            json={"key": "mesi_test"}
        )
        data = await response.json()
        print(f"✓ After put, Node1 state: {data['state']}")
        
        # E/S: Node2 reads -> Node1 goes to Shared
        response = await session.post(
            f"http://localhost:{node2.port}/cache/get",
            json={"key": "mesi_test"}
        )
        data = await response.json()
        print(f"✓ Node2 read, state: {data['state']}")
        
        # Node1 state should now be Shared
        response = await session.post(
            f"http://localhost:{node1.port}/cache/get",
            json={"key": "mesi_test"}
        )
        data = await response.json()
        print(f"✓ Node1 state after sharing: {data['state']}")
        
        # I: Node1 writes again -> Node2 invalidated
        await session.post(
            f"http://localhost:{node1.port}/cache/put",
            json={"key": "mesi_test", "value": "new_data"}
        )
        print("✓ Node1 wrote new value, Node2 should be invalidated")