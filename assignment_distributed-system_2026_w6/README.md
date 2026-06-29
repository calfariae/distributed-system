# Distributed Synchronization System

Sistem terdistribusi yang mengimplementasikan lock manager, message queue, cache coherence, dan machine learning integration untuk menyimulasikan skenario real-world distributed systems.

---


## Fitur Utama

### Core Requirements (70 poin)

- **Distributed Lock Manager** — Algoritma Raft Consensus, shared & exclusive locks, deadlock detection, network partition handling.
- **Distributed Queue System** — Consistent hashing, multiple producers/consumers, message persistence & recovery, at-least-once delivery.
- **Cache Coherence** — Protokol MESI, snooping-based coherence, cache invalidation & update propagation, LRU replacement.

### Bonus Feature (5 poin)

- **ML Integration** — Adaptive load balancing (RandomForest), anomaly detection (IsolationForest), predictive scaling.

---

## Prasyarat

- Python 3.9+
- Docker & Docker Compose
- Redis

---

## Instalasi

```bash
# Clone repository
git clone https://github.com/[username]/distributed-sync-system.git
cd distributed-sync-system

# Setup virtual environment
python -m venv .venv
source .venv/bin/activate  # Linux/Mac
# .venv\Scripts\activate   # Windows

# Install dependencies
pip install -r requirements.txt

# Konfigurasi environment
cp .env.example .env
```

---

## Menjalankan Sistem

### Dengan Docker (Direkomendasikan)

```bash
# Menjalankan 3 node
docker-compose -f docker/docker-compose.yml up -d

# Scaling node tambahan
docker-compose -f docker/docker-compose.yml up -d --scale node=5

# Melihat status container
docker ps

# Menghentikan sistem
docker-compose -f docker/docker-compose.yml down
```

### Tanpa Docker (3 Terminal Terpisah)

```bash
# Terminal 1 — Node 1
python run_node.py 8000

# Terminal 2 — Node 2
python run_node.py 8001

# Terminal 3 — Node 3
python run_node.py 8002
```

Setelah sistem berjalan, akses endpoint berikut:

| Komponen     | Endpoint                              |
|--------------|---------------------------------------|
| Lock Manager | `http://localhost:8000/lock/status`   |
| Queue Node   | `http://localhost:9000/queue/stats`   |
| Cache Node   | `http://localhost:10000/cache/stats`  |
| ML Node      | `http://localhost:11000/ml/status`    |

---

## Menjalankan Tes

```bash
# Semua unit test
pytest tests/unit/ -v

# Per komponen
pytest tests/unit/test_lock_manager.py -v
pytest tests/unit/test_queue_node.py -v
pytest tests/unit/test_cache_node.py -v
pytest tests/unit/test_ml_node.py -v

# Integration test
pytest tests/unit/test_full_system.py -v
```

Hasil tes terakhir: **20/20 passed**.

---

## Benchmark

```bash
python benchmarks/load_test_scenarios.py
```

Hasil benchmark pada 3-node cluster (localhost):

| Metrik                 | Hasil    |
|------------------------|----------|
| Queue Throughput       | 984 ops/s|
| Queue Latency (avg)    | 1.02 ms  |
| Cache Hit Latency      | 0.37 ms  |
| Cache Miss Latency     | 1.19 ms  |
| Distributed Overhead   | 47.3%    |

---

## Struktur Proyek

```
distributed-sync-system/
├── src/
│   ├── nodes/
│   │   ├── base_node.py          # Base class untuk semua node
│   │   ├── lock_manager.py       # Distributed Lock Manager (Raft)
│   │   ├── queue_node.py         # Distributed Queue (Consistent Hash)
│   │   ├── cache_node.py         # Cache Coherence (MESI)
│   │   └── ml_node.py            # ML Integration Node
│   ├── consensus/
│   │   └── raft.py               # Raft Consensus implementation
│   ├── communication/
│   │   ├── message_passing.py    # Message passing utilities
│   │   └── failure_detector.py   # Node failure detection
│   ├── ml/
│   │   ├── metrics_collector.py  # Metrics collection untuk ML
│   │   ├── load_balancer.py      # Adaptive load balancing
│   │   └── predictive_scaler.py  # Predictive scaling
│   └── utils/
│       ├── config.py             # Konfigurasi environment
│       └── metrics.py            # Performance metrics
├── tests/
│   └── unit/
│       ├── test_lock_manager.py  # Tes Raft & lock
│       ├── test_queue_node.py    # Tes queue
│       ├── test_cache_node.py    # Tes MESI
│       ├── test_ml_node.py       # Tes ML
│       └── test_full_system.py   # Tes integrasi
├── benchmarks/
│   ├── load_test_scenarios.py    # Performance benchmarking
│   └── results/                  # Hasil benchmark (JSON)
├── docker/
│   ├── Dockerfile.node           # Docker image
│   └── docker-compose.yml        # Multi-node orchestration
├── docs/
│   ├── architecture.md           # Dokumentasi arsitektur
│   ├── api_spec.yaml             # API specification (OpenAPI)
│   └── deployment_guide.md       # Panduan deployment
├── run_node.py                   # Script untuk menjalankan single node
├── requirements.txt              # Python dependencies
├── .env.example                  # Contoh environment variables
├── pytest.ini                    # Pytest configuration
└── README.md
```

---

## Arsitektur

```
+------------------------------------------+
|           Client Applications            |
+--------------------+---------------------+
                     |
+--------------------+---------------------+
|           API Gateway / Router           |
+--------------------+---------------------+
                     |
      +--------------+--------------+
      |              |              |
+-----+------+  +----+----+  +-----+------+
|    Lock    |  |  Queue  |  |   Cache    |
|  Manager   |  |  Node   |  |   Node     |
|  (Raft)    |  |(Consist.|  |  (MESI)    |
|            |  |  Hash)  |  |            |
+-----+------+  +----+----+  +-----+------+
      |              |              |
+-----+--------------+--------------+-----+
|          ML Optimization Layer          |
|   (Load Balancing, Anomaly Detection)   |
+-----------------------------------------+
```

---

## Video Demo

https://youtube.com/...

Durasi: 10–15 menit  
Bahasa: Indonesia

---

## Laporan

Laporan lengkap tersedia dalam file PDF:  
https://drive.google.com/drive/folders/1etdhQyvKhb-4kV_ClbcMe-w1QHSLiSqj?usp=drive_link

---

## Teknologi

| Kategori          | Teknologi                                         |
|-------------------|---------------------------------------------------|
| Bahasa            | Python 3.9+                                       |
| Async I/O         | asyncio, aiohttp                                  |
| Containerization  | Docker, Docker Compose                            |
| State Management  | Redis                                             |
| Machine Learning  | scikit-learn (RandomForest, IsolationForest)      |
| Testing           | pytest, pytest-asyncio                            |

---

## Referensi

1. Ongaro, D., & Ousterhout, J. (2014). In search of an understandable consensus algorithm. *USENIX ATC '14*.
2. Karger, D., et al. (1997). Consistent hashing and random trees. *STOC '97*.
3. Papamarcos, M. S., & Patel, J. H. (1984). A low-overhead coherence solution for multiprocessors. *ISCA '84*.
4. Breiman, L. (2001). Random forests. *Machine Learning*, *45*(1), 5–32.
5. Liu, F. T., Ting, K. M., & Zhou, Z. H. (2008). Isolation forest. *ICDM '08*.

---