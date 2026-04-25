# Pub-Sub Log Aggregator

A lightweight, local Pub-Sub log aggregation service built with FastAPI and asyncio. Accepts log events from publishers, deduplicates them using a persistent SQLite store, and serves the cleaned event stream via a REST API.

Built as part of UTS Sistem Terdistribusi dan Parallel 2025.

---

## Architecture

```
POST /publish
      │
      ▼
  [ asyncio.Queue ]  ← in-memory
      │
      ▼
  Consumer Worker (background loop)
      │
      ├── duplicate? ── log [DUPLICATE DROPPED] & discard
      │
      └── unique? ───── SQLite dedup store (persistent)
                          + in-memory processed events list
                                │
                          GET /events
                          GET /stats
```

The publisher and aggregator are separated into two Docker Compose services that communicate over an internal network with no external connectivity.

---

## Project Structure

```
.
├── src/
│   ├── __init__.py
│   ├── main.py            # FastAPI app, lifespan, endpoints
│   ├── models.py          # Pydantic Event and BatchPublishRequest models
│   ├── consumer.py        # Background consumer worker
│   ├── queue_manager.py   # asyncio.Queue (lazy, loop-safe)
│   ├── dedup_store.py     # SQLite-backed deduplication store
│   ├── stats.py           # In-memory stats collector
│   └── dependencies.py    # Shared dedup_store and stats singletons
├── tests/
│   └── test_aggregator.py # 10 unit tests (pytest + httpx)
├── data/                  # SQLite dedup DB written here (local dev)
├── publisher.py           # Standalone publisher for Docker Compose
├── requirements.txt
├── Dockerfile             # Aggregator image
├── Dockerfile.publisher   # Publisher image
├── docker-compose.yml     # Bonus: two-service Compose setup
├── pytest.ini
├── conftest.py
└── README.md
```

---

## Requirements

- Docker 20.10+
- Docker Compose v2 (for the Compose bonus)
- Python 3.11+ (for local runs only)

---

## Running with Docker (Single Container)

**Build:**
```bash
docker build -t uts-aggregator .
```

**Run:**
```bash
docker run -p 8080:8080 -v $(pwd)/data:/app/data uts-aggregator
```

The `-v` flag mounts a local `data/` folder so the SQLite dedup store persists across container restarts.

---

## Running with Docker Compose (Bonus)

Starts the aggregator and a publisher service that automatically sends 6,000 events (5,000 unique + 1,000 duplicates):

```bash
docker compose up --build
```

The publisher waits for the aggregator to pass its healthcheck before sending. After all events are sent, the publisher exits and the aggregator keeps running. Check results with:

```bash
curl http://localhost:8080/stats
```

To stop:
```bash
docker compose down
```

To stop and wipe the dedup volume (full reset):
```bash
docker compose down -v
```

---

## Running Locally (Development)

```bash
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

In `src/dedup_store.py`, temporarily set:
```python
DB_PATH = Path("data/dedup.db")
```

Then run:
```bash
python -m uvicorn src.main:app --host 0.0.0.0 --port 8080 --reload
```

> Remember to revert `DB_PATH` back to `Path("/app/data/dedup.db")` before building the Docker image.

---

## API Endpoints

### `POST /publish`
Accepts a single event or a batch.

**Request body:**
```json
{
  "events": [
    {
      "event_id": "abc-001",
      "topic": "payments",
      "timestamp": "2025-01-01T00:00:00Z",
      "source": "service-a",
      "payload": { "amount": 100 }
    }
  ]
}
```

**Response:** `202 Accepted`
```json
{ "queued": 1 }
```

---

### `GET /events?topic=<name>`
Returns processed unique events. Filter by topic using the query parameter.

```bash
curl http://localhost:8080/events?topic=payments
```

Returns `404` if the topic has not been seen yet.

---

### `GET /stats`
Returns aggregator counters and uptime.

```json
{
  "received": 6000,
  "unique_processed": 5000,
  "duplicate_dropped": 1000,
  "topics": ["auth", "inventory", "notifications", "orders", "payments"],
  "uptime_seconds": 42.5
}
```

---

### `GET /health`
Liveness check used by Docker healthcheck.

```json
{ "status": "ok" }
```

---

## Running Tests

```bash
pytest tests/ -v
```

Tests cover:
- Duplicate detection (same `event_id` only processed once)
- Unique events all processed correctly
- Schema validation (missing fields, empty strings)
- `GET /events` topic filtering
- `GET /stats` consistency (`received = unique + dropped`)
- `GET /events` returns 404 for unknown topics
- `DedupStore.mark_processed` idempotency
- Dedup store persistence across simulated restarts
- Stress test: 5,000 events with 20% duplicates under 15 seconds

---

## Event Schema

| Field | Type | Description |
|---|---|---|
| `event_id` | `string` | Unique identifier for the event. Must be non-empty. |
| `topic` | `string` | Category/channel for the event. Must be non-empty. |
| `timestamp` | `string` | ISO 8601 datetime (e.g. `2025-01-01T00:00:00Z`) |
| `source` | `string` | Origin service or publisher name. Must be non-empty. |
| `payload` | `object` | Arbitrary JSON object with event data. |

Deduplication key is the combination of `(topic, event_id)`.

---

## Design Decisions

**Idempotency** — `INSERT OR IGNORE` in SQLite ensures `mark_processed` is safe to call multiple times with no side effects.

**Crash tolerance** — the dedup store is written to disk (`/app/data/dedup.db`) and mounted as a Docker volume. After a container restart, previously processed events are still rejected.

**Ordering** — total ordering is not required for a log aggregator. Events are processed in arrival order within a single queue, which is sufficient for aggregation use cases.

**Queue** — `asyncio.Queue` provides a simple, non-blocking pipeline between the HTTP layer and the consumer without needing a separate message broker.

**At-least-once simulation** — the publisher intentionally resends ~20% of events to simulate real-world duplicate delivery. The dedup store absorbs all duplicates transparently.

---

## Assumptions

- All components run locally inside Docker with no external network access.
- The `data/` directory must exist before running locally (`mkdir -p data`).
- SQLite is sufficient for the dedup store at this scale; a production system would use Redis or a distributed KV store.
- In-memory processed events list is reset on restart — this is expected. Only the dedup store (SQLite) persists.