# README.md - Sistem Log Aggregator Pub-Sub Terdistribusi

## Ringkasan

Sistem agregator log terdistribusi dengan consumer idempotent dan deduplikasi kuat. Dibangun menggunakan arsitektur microservices dengan Docker Compose. Sistem ini mampu memproses ribuan event per menit dengan deteksi duplikat yang akurat.

## Arsitektur

```
┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
│   Publisher     │────▶│   Aggregator    │────▶│   PostgreSQL    │
│   (Python)      │     │   (FastAPI)     │     │   (Storage)     │
└─────────────────┘     └────────┬────────┘     └─────────────────┘
                                 │
                                 ▼
                          ┌─────────────────┐
                          │     Redis       │
                          │   (Broker)      │
                          └────────┬────────┘
                                   │
                                   ▼
                          ┌─────────────────┐
                          │   Consumers     │
                          │   (3 Workers)   │
                          └─────────────────┘
```

### Komponen Layanan

| Layanan        | Teknologi        | Fungsi                                           |
| -------------- | ---------------- | ------------------------------------------------ |
| **Aggregator** | FastAPI + Python | Menerima dan memproses event, API gateway        |
| **Publisher**  | Python + aiohttp | Generator event uji dengan duplikasi terkontrol  |
| **PostgreSQL** | PostgreSQL 16    | Penyimpanan persisten dengan constraint unik     |
| **Redis**      | Redis 7          | Message broker untuk pemrosesan asinkron         |
| **Consumer**   | Python async     | 3 worker concurrent memproses event dari antrian |

## Fitur Utama

- ✅ **Idempotent Processing**: Event yang sama tidak diproses ulang
- ✅ **Strong Deduplication**: Constraint database `(topic, event_id)` mencegah duplikat
- ✅ **Transaction Support**: Isolation level SERIALIZABLE untuk konsistensi data
- ✅ **Concurrent Workers**: 3 worker consumer untuk processing paralel
- ✅ **Persistent Storage**: Named volumes untuk data yang aman
- ✅ **Comprehensive Monitoring**: Statistik real-time via API
- ✅ **Health Checks**: Health dan readiness probe untuk orchestration
- ✅ **Batch Processing**: Atomic transaction untuk batch event
- ✅ **High Throughput**: Mampu memproses 30+ events/detik

## Prasyarat

- Docker Engine 20.10+
- Docker Compose 2.0+
- 2GB RAM minimum
- 5GB ruang disk kosong
- curl atau Postman untuk testing API

## Quick Start

### 1. Clone Repository

```bash
git clone <repository-url>
cd final_distributed-system_2025
```

### 2. Build dan Jalankan

```bash
# Build dan start semua services
docker compose up --build

# Atau jalankan di background
docker compose up -d --build
```

### 3. Verifikasi Sistem

```bash
# Cek semua services running
docker compose ps

# Cek health
curl http://localhost:8080/health

# Cek statistik
curl http://localhost:8080/stats | jq

# Cek readiness
curl http://localhost:8080/ready | jq
```

## API Endpoints

### POST /publish

Publikasi event tunggal

```bash
curl -X POST http://localhost:8080/publish \
  -H "Content-Type: application/json" \
  -d '{
    "topic": "system.logs",
    "source": "app-server",
    "payload": {"message": "Hello World"}
  }'
```

Response:

```json
{
  "status": "accepted",
  "event_id": "550e8400-e29b-41d4-a716-446655440000",
  "duplicate": false
}
```

### POST /publish/batch

Publikasi batch event secara atomik

```bash
curl -X POST http://localhost:8080/publish/batch \
  -H "Content-Type: application/json" \
  -d '{
    "events": [
      {"topic":"app.events","event_id":"batch-001","source":"test","payload":{"data":1}},
      {"topic":"app.events","event_id":"batch-002","source":"test","payload":{"data":2}},
      {"topic":"app.events","event_id":"batch-001","source":"test","payload":{"data":3}}
    ],
    "atomic": true
  }'
```

### GET /events

Ambil daftar event yang telah diproses

```bash
curl "http://localhost:8080/events?topic=system.logs&limit=10&offset=0" | jq
```

Parameter:

- `topic`: Filter berdasarkan topik (opsional)
- `limit`: Jumlah data per halaman (default: 100)
- `offset`: Offset untuk paginasi (default: 0)

### GET /stats

Ambil statistik sistem

```bash
curl http://localhost:8080/stats | jq
```

Response:

```json
{
  "total_received": 15934,
  "total_unique_processed": 6550,
  "total_duplicate_dropped": 9384,
  "topics": {
    "system.logs": {
      "received": 3970,
      "unique": 1633,
      "duplicates": 2337
    }
  },
  "uptime_seconds": 414.68
}
```

### GET /health

Health check endpoint untuk monitoring

```bash
curl http://localhost:8080/health
```

### GET /ready

Readiness probe untuk orchestration

```bash
curl http://localhost:8080/ready
```

## Konfigurasi

### Environment Variables

#### Aggregator

| Variable       | Default                                          | Deskripsi             |
| -------------- | ------------------------------------------------ | --------------------- |
| `DATABASE_URL` | `postgresql+asyncpg://user:pass@storage:5432/db` | Koneksi PostgreSQL    |
| `REDIS_URL`    | `redis://broker:6379`                            | Koneksi Redis         |
| `LOG_LEVEL`    | `INFO`                                           | Level logging         |
| `WORKERS`      | `4`                                              | Jumlah worker uvicorn |

#### Publisher

| Variable            | Default                  | Deskripsi                              |
| ------------------- | ------------------------ | -------------------------------------- |
| `TARGET_URL`        | `http://aggregator:8080` | URL aggregator                         |
| `DUPLICATE_RATE`    | `0.3`                    | Probabilitas duplikasi (0-1)           |
| `EVENTS_PER_SECOND` | `50`                     | Rate pengiriman event/detik            |
| `DURATION_SECONDS`  | `300`                    | Durasi pengiriman (detik), 0 = forever |

### Docker Compose Configuration

```yaml
services:
  aggregator:
    build: ./aggregator
    image: final_distributed-system_2025-aggregator:latest
    container_name: final_distributed-system_2025-aggregator
    ports:
      - "8080:8080"
    environment:
      - DATABASE_URL=postgresql+asyncpg://user:pass@storage:5432/db
      - REDIS_URL=redis://broker:6379
    volumes:
      - aggregator_data:/var/lib/aggregator
    depends_on:
      storage:
        condition: service_healthy
      broker:
        condition: service_healthy
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8080/health"]
      interval: 30s
      timeout: 10s
      retries: 3
      start_period: 40s
    restart: unless-stopped

  storage:
    image: postgres:16-alpine
    container_name: final_distributed-system_2025-storage
    environment:
      POSTGRES_DB: db
      POSTGRES_USER: user
      POSTGRES_PASSWORD: pass
    ports:
      - "5432:5432" # Optional untuk debugging
    volumes:
      - pg_data:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U user -d db"]
      interval: 10s
      timeout: 5s
      retries: 5
    command: postgres -c max_connections=100 -c shared_buffers=256MB

  broker:
    image: redis:7-alpine
    container_name: final_distributed-system_2025-broker
    command: redis-server --appendonly yes --maxmemory 256mb
    volumes:
      - broker_data:/data
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 10s
      timeout: 5s
      retries: 5

  publisher:
    build: ./publisher
    image: final_distributed-system_2025-publisher:latest
    container_name: final_distributed-system_2025-publisher
    environment:
      - TARGET_URL=http://aggregator:8080
      - DUPLICATE_RATE=0.3
      - EVENTS_PER_SECOND=50
      - DURATION_SECONDS=300
    depends_on:
      aggregator:
        condition: service_healthy
    restart: on-failure

volumes:
  pg_data:
    name: final_distributed-system_2025_pg_data
  broker_data:
    name: final_distributed-system_2025_broker_data
  aggregator_data:
    name: final_distributed-system_2025_aggregator_data
```

## Testing

### Unit & Integration Tests

```bash
# Jalankan semua test
cd aggregator
pytest tests/ -v

# Jalankan test spesifik
pytest tests/test_dedup.py -v
pytest tests/test_transactions.py -v
pytest tests/test_api.py -v
```

### Cakupan Test (14 Tests)

- ✅ **Deduplikasi**: Kirim duplikat → hanya sekali diproses
- ✅ **Persistensi**: Setelah container recreate, data tetap ada
- ✅ **Transaksi/Konkurensi**: Multi-worker menghasilkan data konsisten
- ✅ **Validasi Skema**: Event validation dengan Pydantic
- ✅ **API Integration**: GET /stats dan GET /events konsisten
- ✅ **Stress Test**: Batch event dengan atomic transaction
- ✅ **Concurrent Processing**: 10 worker paralel tanpa race condition

### Load Test dengan K6

```bash
# Install k6
# https://k6.io/docs/getting-started/installation/

# Jalankan load test
k6 run load-test.js
```

Contoh `load-test.js`:

```javascript
import http from "k6/http";
import { check, sleep } from "k6";

export let options = {
  stages: [
    { duration: "30s", target: 20 },
    { duration: "1m", target: 50 },
    { duration: "30s", target: 0 },
  ],
};

export default function () {
  const event = {
    topic: "load.test",
    event_id: `${__VU}-${__ITER}`,
    source: "k6",
    payload: { data: "load test" },
  };

  const res = http.post(
    "http://localhost:8080/publish",
    JSON.stringify(event),
    {
      headers: { "Content-Type": "application/json" },
    },
  );

  check(res, {
    "status is 202": (r) => r.status === 202,
  });

  sleep(1);
}
```

## Monitoring

### Logging

```bash
# Log semua service
docker compose logs

# Log service spesifik
docker compose logs aggregator
docker compose logs publisher

# Follow log real-time
docker compose logs -f aggregator

# Filter log berdasarkan keyword
docker compose logs aggregator | grep -i duplicate
docker compose logs aggregator | grep -i error
```

### Metrik Sistem

Akses endpoint `/stats` untuk metrik real-time:

- `total_received`: Total event diterima
- `total_unique_processed`: Total event unik
- `total_duplicate_dropped`: Total duplikat yang di-drop
- `topics`: Statistik per topik (received, unique, duplicates)
- `uptime_seconds`: Waktu uptime sistem

### Monitoring dengan watch

```bash
# Monitor stats real-time
watch -n 2 'curl -s http://localhost:8080/stats | jq'

# Monitor total events
watch -n 2 'curl -s http://localhost:8080/stats | jq ".total_received"'

# Monitor duplicate rate
watch -n 2 'curl -s http://localhost:8080/stats | jq "{duplicate_rate: ((.total_duplicate_dropped / .total_received) * 100)}"'
```

## Troubleshooting

### Container Tidak Bisa Start

```bash
# Cek log
docker compose logs aggregator

# Restart dengan rebuild
docker compose down -v
docker compose build --no-cache
docker compose up -d
```

### Database Connection Error

```bash
# Cek konektivitas database
docker exec -it final_distributed-system_2025-storage-1 psql -U user -d db -c "SELECT 1"

# Reset database
docker compose down -v
docker compose up -d
```

### Health Check Gagal

```bash
# Cek health endpoint manual
curl http://localhost:8080/health

# Cek container health
docker inspect final_distributed-system_2025-aggregator-1 --format='{{json .State.Health}}' | jq
```

### Publisher Tidak Mengirim Event

```bash
# Cek log publisher
docker compose logs publisher

# Restart publisher
docker compose restart publisher

# Cek koneksi ke aggregator
docker exec -it final_distributed-system_2025-publisher curl http://aggregator:8080/health
```

### Redis Connection Issues

```bash
# Cek Redis
docker exec -it final_distributed-system_2025-broker redis-cli ping

# Cek antrian
docker exec -it final_distributed-system_2025-broker redis-cli LLEN events_queue

# Cek retry queue
docker exec -it final_distributed-system_2025-broker redis-cli LLEN events_queue:retry
```

## Persistensi Data

Data disimpan dalam named volumes:

- `final_distributed-system_2025_pg_data`: Data PostgreSQL
- `final_distributed-system_2025_broker_data`: Data Redis (persistent)
- `final_distributed-system_2025_aggregator_data`: Data aplikasi (opsional)

Volume tetap ada meskipun container dihapus:

```bash
# Hapus semua data (termasuk volume)
docker compose down -v

# Hapus container tapi pertahankan data
docker compose down
```

## Performance Metrics

Berdasarkan pengujian dengan 15,000+ events:
| Metric | Value |
|--------|-------|
| Total Events Processed | 15,934 |
| Unique Events | 6,550 |
| Duplicates Detected | 9,384 |
| Duplicate Rate | ~59% |
| Publisher Throughput | 31.27 events/sec |
| Publisher Duplicate Rate | 30.20% |
| System Uptime | 414+ seconds |
| Error Rate | 0% |

## Demo Video

Link YouTube: [TBD]

Durasi: 25+ menit

Isi demo:

1. Build image dan jalankan Compose
2. Pengiriman event duplikat
3. Demonstrasi transaksi/konkurensi
4. GET /events dan GET /stats
5. Crash/recreate container dengan persisten data
6. Keamanan jaringan lokal
7. Observability (logging, metrik)

## Repository GitHub

[Link Repository]

Struktur:

```
final_distributed-system_2025/
├── aggregator/
│   ├── Dockerfile
│   ├── requirements.txt
│   └── app/
│       ├── main.py
│       ├── models.py
│       ├── database.py
│       ├── dedup.py
│       ├── consumer.py
│       ├── stats.py
│       └── schemas.py
├── publisher/
│   ├── Dockerfile
│   ├── requirements.txt
│   └── publisher.py
├── tests/
│   ├── pytest.ini
│   ├── conftest.py
│   ├── test_api.py
│   ├── test_intergration.py
│   ├── test_payload.py
│   ├── test_transactions.py
│   └── test_dedup.py
├── docker-compose.yml
└── README.md
```

## Kontribusi

Untuk berkontribusi pada proyek ini:

1. Fork repository
2. Buat branch fitur (`git checkout -b feature/AmazingFeature`)
3. Commit perubahan (`git commit -m 'Add some AmazingFeature'`)
4. Push ke branch (`git push origin feature/AmazingFeature`)
5. Open Pull Request

## Referensi

1. Coulouris, G., Dollimore, J., Kindberg, T., & Blair, G. (2012). _Distributed systems: Concepts and design_ (5th ed.). Addison-Wesley.
2. FastAPI Documentation: https://fastapi.tiangolo.com/
3. PostgreSQL Documentation: https://www.postgresql.org/docs/
4. Redis Documentation: https://redis.io/documentation
5. Docker Compose Documentation: https://docs.docker.com/compose/
6. SQLAlchemy Documentation: https://docs.sqlalchemy.org/
7. Pydantic Documentation: https://docs.pydantic.dev/

---

**Status**: ✅ Production Ready | **Version**: 1.0.0 | **Last Updated**: Juni 2026
