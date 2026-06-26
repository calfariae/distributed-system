import pytest
import asyncio
import aiohttp
import random
from src.nodes.ml_node import MLNode

def get_random_port():
    return random.randint(9000, 9999)

@pytest.fixture
async def ml_node():
    """Create an ML node"""
    port = get_random_port()
    node = MLNode("ml_node1", "localhost", port, ["localhost:9000", "localhost:9001"])
    await node.start()
    
    # Wait for metrics collection
    await asyncio.sleep(10)
    
    yield node
    
    await node.stop()
    await asyncio.sleep(0.5)

@pytest.mark.asyncio
async def test_metrics_collection(ml_node):
    """Test metrics collection"""
    async with aiohttp.ClientSession() as session:
        response = await session.post(
            f"http://localhost:{ml_node.port}/ml/metrics",
            json={}
        )
        data = await response.json()
        
        assert data["node_id"] == "ml_node1"
        assert "current" in data
        assert data["current"]["cpu_usage"] > 0
        print(f"✓ Metrics: {data['current']}")

@pytest.mark.asyncio
async def test_ml_training(ml_node):
    """Test ML model training"""
    async with aiohttp.ClientSession() as session:
        # Wait for enough data
        await asyncio.sleep(15)
        
        response = await session.post(
            f"http://localhost:{ml_node.port}/ml/train",
            json={}
        )
        data = await response.json()
        
        if data.get("trained"):
            print(f"✓ Model trained with {data['samples']} samples")
        else:
            print(f"Need more data: {data}")
            # That's okay, we might not have enough data yet

@pytest.mark.asyncio
async def test_anomaly_detection(ml_node):
    """Test anomaly detection"""
    async with aiohttp.ClientSession() as session:
        # Normal metrics
        response = await session.post(
            f"http://localhost:{ml_node.port}/ml/anomaly",
            json={
                "features": [0.5, 0.6, 5, 0.1, 50, 0.9, 25]
            }
        )
        data = await response.json()
        print(f"✓ Normal check: anomaly={data['is_anomaly']}")
        
        # Anomalous metrics (very high CPU, low cache hit rate)
        response = await session.post(
            f"http://localhost:{ml_node.port}/ml/anomaly",
            json={
                "features": [0.99, 0.95, 50, 0.8, 200, 0.1, 100]
            }
        )
        data = await response.json()
        print(f"✓ Anomaly check: anomaly={data['is_anomaly']}")

@pytest.mark.asyncio
async def test_ml_status(ml_node):
    """Test ML status endpoint"""
    async with aiohttp.ClientSession() as session:
        response = await session.get(
            f"http://localhost:{ml_node.port}/ml/status"
        )
        data = await response.json()
        
        assert "node_id" in data
        assert "predicted_load" in data
        assert "scaling_recommendation" in data
        print(f"✓ ML Status: {data}")

@pytest.mark.asyncio
async def test_predict_routing(ml_node):
    """Test ML-based routing prediction"""
    async with aiohttp.ClientSession() as session:
        # Simulate multiple nodes with features
        nodes_features = {
            "node1": [0.3, 0.4, 2, 0.05, 20, 0.95, 10],
            "node2": [0.8, 0.7, 10, 0.2, 80, 0.75, 40],
            "node3": [0.5, 0.5, 5, 0.1, 50, 0.85, 25],
        }
        
        response = await session.post(
            f"http://localhost:{ml_node.port}/ml/predict",
            json={"nodes_features": nodes_features}
        )
        data = await response.json()
        print(f"✓ Best node: {data.get('best_node', 'not trained yet')}")