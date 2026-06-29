# Pub-Sub Log Aggregator

Layanan agregasi log berbasis arsitektur *publish-subscribe* yang dibangun menggunakan FastAPI dan asyncio. Layanan ini menerima *event* log dari *publisher*, melakukan deduplikasi menggunakan penyimpanan SQLite yang persisten, serta menyajikan kembali *event* unik melalui REST API.

Dikembangkan sebagai bagian dari **UTS Mata Kuliah Sistem Terdistribusi dan Parallel 2025**.

---

## Arsitektur Sistem

```
POST /publish
      │
      ▼
  [ asyncio.Queue ]  ← antrian in-memory
      │
      ▼
  Consumer Worker (loop background)
      │
      ├── duplikat? ──→ catat [DUPLICATE DROPPED] & buang
      │
      └── unik? ──────→ SQLite dedup store (persisten)
                         + daftar event in-memory (per topik)
                               │
                         GET /events
                         GET /stats
```

*Publisher* dan *aggregator* dijalankan sebagai dua layanan terpisah di dalam Docker Compose dan berkomunikasi melalui jaringan internal tanpa koneksi eksternal.

---

## Struktur Proyek

```
.
├── src/
│   ├── __init__.py
│   ├── main.py            # Aplikasi FastAPI, lifespan, dan endpoint
│   ├── models.py          # Model Pydantic: Event dan BatchPublishRequest
│   ├── consumer.py        # Worker consumer (loop background)
│   ├── queue_manager.py   # asyncio.Queue (lazy, aman antar event loop)
│   ├── dedup_store.py     # Dedup store berbasis SQLite
│   ├── stats.py           # Pengumpul statistik in-memory
│   └── dependencies.py    # Singleton bersama: dedup_store dan stats
├── tests/
│   ├── conftest.py
│   └── test_aggregator.py # 10 unit test (pytest + httpx)
├── data/                  # Lokasi file SQLite saat pengembangan lokal
├── publisher.py           # Skrip publisher untuk Docker Compose
├── requirements.txt
├── Dockerfile             # Image aggregator
├── Dockerfile.publisher   # Image publisher
├── docker-compose.yml     # Konfigurasi dua layanan (bonus)
├── pytest.ini
└── README.md
```

---

## Prasyarat

- Docker 20.10 atau lebih baru
- Docker Compose v2 (untuk menjalankan konfigurasi bonus)
- Python 3.11+ (hanya untuk pengembangan lokal)

---

## Cara Menjalankan

### Menggunakan Docker (Satu Container)

**Build image:**
```bash
docker build -t uts-aggregator .
```

**Jalankan container:**
```bash
docker run -p 8080:8080 -v $(pwd)/data:/app/data uts-aggregator
```

Flag `-v` digunakan untuk me-mount direktori `data/` lokal ke dalam container, sehingga dedup store SQLite tetap persisten meskipun container di-restart.

---

### Menggunakan Docker Compose (Bonus)

Menjalankan dua layanan sekaligus: *aggregator* dan *publisher*. Publisher secara otomatis mengirim 6.000 *event* (5.000 unik + 1.000 duplikat) setelah *aggregator* siap.

**Jalankan:**
```bash
docker compose up --build
```

Publisher akan menunggu hingga *aggregator* lolos *healthcheck* sebelum mulai mengirim *event*. Setelah selesai, publisher berhenti otomatis dan *aggregator* tetap berjalan.

**Periksa hasil:**
```bash
curl http://localhost:8080/stats
```

**Hentikan layanan:**
```bash
docker compose down
```

**Hentikan dan hapus volume (reset penuh):**
```bash
docker compose down -v
```

---

### Pengembangan Lokal (Tanpa Docker)

```bash
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

Ubah sementara `DB_PATH` di `src/dedup_store.py` menjadi:
```python
DB_PATH = Path("data/dedup.db")
```

Buat direktori data dan jalankan server:
```bash
mkdir -p data
python -m uvicorn src.main:app --host 0.0.0.0 --port 8080 --reload
```

> **Perhatian:** Kembalikan `DB_PATH` ke `Path("/app/data/dedup.db")` sebelum melakukan build Docker image.

---

## Dokumentasi API

### `POST /publish`

Menerima satu *event* atau sekumpulan *event* dalam satu permintaan (*batch*).

**Contoh request body:**
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

### `GET /events?topic=<nama_topik>`

Mengembalikan daftar *event* unik yang telah diproses. Parameter `topic` bersifat opsional; jika tidak disertakan, seluruh *event* dari semua topik dikembalikan.

```bash
curl http://localhost:8080/events?topic=payments
```

Mengembalikan `404 Not Found` apabila topik belum pernah diterima.

---

### `GET /stats`

Mengembalikan statistik agregator secara keseluruhan.

**Contoh response:**
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

*Liveness check* yang digunakan oleh Docker *healthcheck*.

```json
{ "status": "ok" }
```

---

## Skema Event

| Field | Tipe | Keterangan |
|---|---|---|
| `event_id` | `string` | Pengenal unik untuk setiap *event*. Tidak boleh kosong. |
| `topic` | `string` | Kategori atau saluran *event*. Tidak boleh kosong. |
| `timestamp` | `string` | Waktu kejadian dalam format ISO 8601 (contoh: `2025-01-01T00:00:00Z`). |
| `source` | `string` | Nama layanan atau *publisher* asal. Tidak boleh kosong. |
| `payload` | `object` | Objek JSON arbitrer yang memuat data *event*. |

Kunci deduplikasi adalah kombinasi dari `(topic, event_id)`.

---

## Menjalankan Unit Test

```bash
pytest tests/ -v
```

Cakupan pengujian meliputi:

| No | Nama Test | Yang Diverifikasi |
|---|---|---|
| 1 | `test_duplicate_event_only_processed_once` | *Event* duplikat hanya diproses satu kali |
| 2 | `test_unique_events_all_processed` | Seluruh *event* unik berhasil diproses |
| 3 | `test_invalid_schema_missing_event_id` | Validasi skema: `event_id` wajib ada |
| 4 | `test_invalid_schema_empty_topic` | Validasi skema: `topic` tidak boleh whitespace |
| 5 | `test_get_events_filtered_by_topic` | Filter `GET /events?topic=` berfungsi benar |
| 6 | `test_stats_consistency` | `received = unique_processed + duplicate_dropped` selalu terpenuhi |
| 7 | `test_get_events_unknown_topic_returns_404` | Topik tidak dikenal mengembalikan 404 |
| 8 | `test_dedup_store_mark_processed_is_idempotent` | Pemanggilan ganda `mark_processed` aman |
| 9 | `test_dedup_store_persists_across_reinit` | Dedup store tetap efektif setelah simulasi restart |
| 10 | `test_stress_batch_5000_events` | 5.000 *event* dengan 20% duplikat selesai dalam 15 detik |

---

## Keputusan Desain

**Idempotency** — Penggunaan `INSERT OR IGNORE` pada SQLite memastikan bahwa pemanggilan `mark_processed` berkali-kali dengan pasangan `(topic, event_id)` yang sama tidak menghasilkan efek samping maupun galat.

**Toleransi Crash** — Dedup store ditulis ke disk (`/app/data/dedup.db`) dan di-mount sebagai Docker volume. Setelah container di-restart, *event* yang sebelumnya telah diproses tetap ditolak sebagai duplikat.

**Ordering** — *Total ordering* tidak diperlukan dalam konteks agregator log. *Event* diproses sesuai urutan kedatangan dalam antrian tunggal, yang sudah memadai untuk tujuan agregasi.

**Antrian Internal** — `asyncio.Queue` menyediakan pipeline non-blocking antara lapisan HTTP dan worker *consumer* tanpa memerlukan *message broker* eksternal.

**Simulasi At-Least-Once Delivery** — Publisher secara sengaja mengirim ulang sekitar 20% *event* untuk mensimulasikan pengiriman duplikat di dunia nyata. Dedup store menyerap seluruh duplikat secara transparan.

---

## Dokumentasi

Laporan:
<br>https://drive.google.com/drive/folders/1XrmdkRbrjFngOyJx-TOZUjsP-_HsNf6-?usp=drive_link

Video Demo:
<br>https://youtu.be/lnygm35w7mE

---

## Referensi

Tanenbaum, A. S., & Van Steen, M. (2007). *Distributed systems: Principles and paradigms* (2nd ed.). Pearson Prentice Hall.