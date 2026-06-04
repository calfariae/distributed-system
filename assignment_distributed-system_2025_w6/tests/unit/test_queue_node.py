import pytest
import asyncio
import aiohttp
import random
from src.nodes.queue_node import DistributedQueueNode

def get_random_port():
    return random.randint(9000, 9999)

@pytest.fixture
async def queue_nodes():
    """Create 3 queue nodes"""
    ports = [get_random_port() for _ in range(3)]
    nodes = []
    
    for i, port in enumerate(ports):
        node_id = f"queue_node{i+1}"
        # All nodes know about each other
        peers = [f"localhost:{p}" for j, p in enumerate(ports) if j != i]
        node = DistributedQueueNode(node_id, "localhost", port, peers)
        await node.start()
        nodes.append(node)
    
    await asyncio.sleep(1)  # Let nodes initialize
    
    yield nodes
    
    # Cleanup
    for node in nodes:
        await node.stop()
    await asyncio.sleep(0.5)

@pytest.mark.asyncio
async def test_push_message(queue_nodes):
    """Test pushing a message to the queue"""
    node = queue_nodes[0]
    
    async with aiohttp.ClientSession() as session:
        # Push a message
        response = await session.post(
            f"http://localhost:{node.port}/queue/push",
            json={
                "queue_name": "test_queue",
                "data": {"message": "Hello World", "count": 1}
            }
        )
        data = await response.json()
        
        # Check if forwarded or successful
        if data.get("forwarded"):
            # Forward to the correct node
            target = data["target_node"]
            host, port = target.split(":")
            
            response = await session.post(
                f"http://{host}:{port}/queue/push",
                json={
                    "queue_name": "test_queue",
                    "data": {"message": "Hello World", "count": 1}
                }
            )
            data = await response.json()
        
        assert data.get("success") == True
        print(f"✓ Message pushed: {data}")

@pytest.mark.asyncio
async def test_pull_message(queue_nodes):
    """Test pulling a message from the queue"""
    node = queue_nodes[0]
    
    async with aiohttp.ClientSession() as session:
        # First push a message
        push_response = await session.post(
            f"http://localhost:{node.port}/queue/push",
            json={
                "queue_name": "test_queue",
                "data": {"message": "Test Pull"}
            }
        )
        push_data = await push_response.json()
        
        # If forwarded, push to correct node
        if push_data.get("forwarded"):
            target = push_data["target_node"]
            host, port = target.split(":")
            await session.post(
                f"http://{host}:{port}/queue/push",
                json={
                    "queue_name": "test_queue",
                    "data": {"message": "Test Pull"}
                }
            )
        
        await asyncio.sleep(0.5)  # Let message propagate
        
        # Now pull from all nodes until we find it
        for n in queue_nodes:
            response = await session.post(
                f"http://localhost:{n.port}/queue/pull",
                json={
                    "queue_name": "test_queue",
                    "consumer_id": "test_consumer"
                }
            )
            data = await response.json()
            
            if data.get("forwarded"):
                target = data["target_node"]
                host, port = target.split(":")
                response = await session.post(
                    f"http://{host}:{port}/queue/pull",
                    json={
                        "queue_name": "test_queue",
                        "consumer_id": "test_consumer"
                    }
                )
                data = await response.json()
            
            if data.get("message"):
                print(f"✓ Message pulled: {data['message']}")
                assert data["message"]["data"]["message"] == "Test Pull"
                return
        
        # If we get here, message wasn't found
        assert False, "Message not found in any node"

@pytest.mark.asyncio
async def test_message_ack(queue_nodes):
    """Test message acknowledgment"""
    async with aiohttp.ClientSession() as session:
        # Find the node that owns "test_queue"
        # We need to push and pull from the same node that owns the queue
        
        # Try all nodes as they all have the same consistent hash ring
        node = queue_nodes[0]
        
        # Push a message directly - but determine which node owns it first
        # For consistent hashing, we can test all nodes
        msg_id = None
        target_node = None
        
        # Push to all nodes and see which one accepts it
        for n in queue_nodes:
            response = await session.post(
                f"http://localhost:{n.port}/queue/push",
                json={
                    "queue_name": "ack_test_queue",
                    "data": {"message": "Test ACK"}
                }
            )
            data = await response.json()
            
            if data.get("success") and not data.get("forwarded"):
                msg_id = data["msg_id"]
                target_node = n
                print(f"✓ Message pushed to node {n.node_id}: {msg_id}")
                break
            
            if data.get("forwarded"):
                target = data["target_node"]
                host, port = target.split(":")
                # Push to the correct node
                response = await session.post(
                    f"http://{host}:{port}/queue/push",
                    json={
                        "queue_name": "ack_test_queue",
                        "data": {"message": "Test ACK"}
                    }
                )
                data = await response.json()
                if data.get("success"):
                    msg_id = data["msg_id"]
                    # Find the target node object
                    for n in queue_nodes:
                        if f"{n.host}:{n.port}" == target:
                            target_node = n
                            break
                    print(f"✓ Message pushed to correct node: {msg_id}")
                    break
        
        assert msg_id is not None, "Failed to push message"
        assert target_node is not None, "Failed to find target node"
        
        # Now pull from the SAME node
        response = await session.post(
            f"http://localhost:{target_node.port}/queue/pull",
            json={
                "queue_name": "ack_test_queue",
                "consumer_id": "test_consumer"
            }
        )
        data = await response.json()
        
        if data.get("message"):
            pulled_msg_id = data["message"]["msg_id"]
            print(f"✓ Message pulled: {pulled_msg_id}")
            
            # Acknowledge from the SAME node
            ack_response = await session.post(
                f"http://localhost:{target_node.port}/queue/ack",
                json={"msg_id": pulled_msg_id}
            )
            ack_data = await ack_response.json()
            print(f"Ack response: {ack_data}")
            
            assert ack_data.get("success") == True, f"Ack failed: {ack_data}"
            print("✓ Message acknowledged successfully")
        else:
            print(f"No message found to acknowledge. Response: {data}")
            # The message might have been pulled by another consumer in a previous test
            # Let's push a new one and try again
            response = await session.post(
                f"http://localhost:{target_node.port}/queue/push",
                json={
                    "queue_name": "ack_test_queue_2",
                    "data": {"message": "Test ACK 2"}
                }
            )
            data = await response.json()
            
            if data.get("success"):
                msg_id = data["msg_id"]
                
                # Pull it
                response = await session.post(
                    f"http://localhost:{target_node.port}/queue/pull",
                    json={
                        "queue_name": "ack_test_queue_2",
                        "consumer_id": "test_consumer"
                    }
                )
                data = await response.json()
                
                if data.get("message"):
                    pulled_msg_id = data["message"]["msg_id"]
                    
                    # Ack it
                    ack_response = await session.post(
                        f"http://localhost:{target_node.port}/queue/ack",
                        json={"msg_id": pulled_msg_id}
                    )
                    ack_data = await ack_response.json()
                    print(f"Ack response (2nd attempt): {ack_data}")
                    
                    assert ack_data.get("success") == True, f"Ack failed: {ack_data}"
                    print("✓ Message acknowledged successfully")
                else:
                    assert False, "Failed to pull message"
            else:
                assert False, "Failed to push second message"

@pytest.mark.asyncio
async def test_queue_stats(queue_nodes):
    """Test getting queue statistics"""
    node = queue_nodes[0]
    
    async with aiohttp.ClientSession() as session:
        response = await session.get(
            f"http://localhost:{node.port}/queue/stats"
        )
        data = await response.json()
        
        assert "queues" in data
        assert "total_messages" in data
        print(f"✓ Queue stats: {data}")

@pytest.mark.asyncio
async def test_message_persistence(queue_nodes):
    """Test message persistence and recovery"""
    node = queue_nodes[0]
    
    async with aiohttp.ClientSession() as session:
        # Push several messages
        for i in range(5):
            response = await session.post(
                f"http://localhost:{node.port}/queue/push",
                json={
                    "queue_name": "persist_test",
                    "data": {"index": i}
                }
            )
            data = await response.json()
            
            if data.get("forwarded"):
                target = data["target_node"]
                host, port = target.split(":")
                await session.post(
                    f"http://{host}:{port}/queue/push",
                    json={
                        "queue_name": "persist_test",
                        "data": {"index": i}
                    }
                )
        
        await asyncio.sleep(1)  # Wait for persistence
        
        # Trigger recovery
        response = await session.post(
            f"http://localhost:{node.port}/queue/recover",
            json={}
        )
        data = await response.json()
        assert data.get("recovered") == True
        print(f"✓ Messages recovered: {data}")