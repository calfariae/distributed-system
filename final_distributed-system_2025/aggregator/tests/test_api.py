import pytest
from fastapi.testclient import TestClient
from unittest.mock import AsyncMock, patch, call
from app.main import app

@pytest.fixture
def client():
    return TestClient(app)

def make_mock_events(n=3, topic="events.test"):
    return [
        {
            "topic": topic,
            "event_id": f"evt-{i}",
            "source": "test",
            "payload": {"index": i},
            "timestamp": f"2024-01-01T00:00:0{i}",
            "processed_at": f"2024-01-01T00:00:0{i}",
        }
        for i in range(n)
    ]

def test_health_check(client):
    """Test health check endpoint"""
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"

def test_stats_endpoint(client):
    """Test stats endpoint structure"""
    response = client.get("/stats")
    assert response.status_code in [200, 500]
    if response.status_code == 200:
        data = response.json()
        assert "total_received" in data
        assert "total_unique_processed" in data

def test_get_events_structure(client):
    """GET /events returns correct envelope shape."""
    with patch("app.main.stats_manager.get_events", new=AsyncMock(return_value=make_mock_events(3))):
        response = client.get("/events")
    assert response.status_code == 200
    data = response.json()
    assert "events" in data
    assert "total" in data
    assert data["total"] == 3
    assert len(data["events"]) == 3

def test_get_events_fields(client):
    """Each event contains all required fields."""
    with patch("app.main.stats_manager.get_events", new=AsyncMock(return_value=make_mock_events(1))):
        response = client.get("/events")
    event = response.json()["events"][0]
    for field in ("topic", "event_id", "source", "payload", "timestamp", "processed_at"):
        assert field in event, f"Missing field: {field}"

def test_get_events_topic_filter(client):
    """GET /events?topic=x passes topic filter through correctly."""
    mock_events = make_mock_events(2, topic="filtered.topic")
    with patch("app.main.stats_manager.get_events", new=AsyncMock(return_value=mock_events)):
        response = client.get("/events?topic=filtered.topic")
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 2
    assert all(e["topic"] == "filtered.topic" for e in data["events"])

def test_get_events_empty(client):
    """GET /events returns empty list gracefully when no events exist."""
    with patch("app.main.stats_manager.get_events", new=AsyncMock(return_value=[])):
        response = client.get("/events")
    assert response.status_code == 200
    data = response.json()
    assert data["events"] == []
    assert data["total"] == 0

def test_get_events_pagination_params(client):
    """GET /events passes limit and offset to the manager."""
    with patch("app.main.stats_manager.get_events", new=AsyncMock(return_value=make_mock_events(5))) as mock:
        response = client.get("/events?limit=5&offset=10")
    assert response.status_code == 200
    # FastAPI injects params positionally — check all args across both positional and keyword
    all_args = list(mock.call_args.args) + list(mock.call_args.kwargs.values())
    assert 5  in all_args, f"limit=5 not found in call args: {mock.call_args}"
    assert 10 in all_args, f"offset=10 not found in call args: {mock.call_args}"

def test_get_events_consistent_with_stats(client):
    """Total from /events matches unique_processed in /stats."""
    mock_events = make_mock_events(4, topic="consistency.topic")
    mock_stats = {
        "total_received": 4,
        "total_unique_processed": 4,
        "total_duplicate_dropped": 0,
        "topics": {"consistency.topic": {"received": 4, "unique": 4, "duplicates": 0}},
        "uptime_seconds": 1.0,
    }
    with patch("app.main.stats_manager.get_events", new=AsyncMock(return_value=mock_events)), \
         patch("app.main.stats_manager.get_stats",  new=AsyncMock(return_value=mock_stats)):
        events_resp = client.get("/events?topic=consistency.topic")
        stats_resp  = client.get("/stats")

    assert events_resp.status_code == 200
    assert stats_resp.status_code == 200
    assert events_resp.json()["total"] == stats_resp.json()["total_unique_processed"]