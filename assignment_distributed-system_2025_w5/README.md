# Simulasi Sistem Komunikasi Terdistribusi

Aplikasi simulasi interaktif berbasis GUI yang memvisualisasikan dan membandingkan dua model komunikasi sistem terdistribusi: **Request-Response** dan **Publish-Subscribe**.

---

## Daftar Isi

- [Fitur](#fitur)
- [Prasyarat](#prasyarat)
- [Cara Menjalankan](#cara-menjalankan)
- [Struktur Proyek](#struktur-proyek)
- [Arsitektur Kode](#arsitektur-kode)
- [Alur Komunikasi](#alur-komunikasi)
- [Teknik Pemrograman](#teknik-pemrograman)

---

## Fitur

- **Tab Request-Response** — kirim request ke server sinkron, atur delay, dan pantau latency secara real-time
- **Tab Publish-Subscribe** — publish pesan ke broker dan lihat distribusi ke banyak subscriber sekaligus
- **Tab Perbandingan** — grafik batang latency, tabel statistik, dan reset metrik
- Simulasi asinkron menggunakan multi-threading tanpa membekukan GUI
- Visualisasi diagram arsitektur komunikasi pada setiap tab

---

## Prasyarat

- Python **3.7** atau lebih baru
- Tidak memerlukan instalasi library tambahan — semua dependensi sudah tersedia di Python bawaan

---

## Cara Menjalankan

```bash
python main.py
```

---

## Struktur Proyek

```
.
├── main.py       # Seluruh kode simulasi
└── README.md     # Dokumentasi ini
```

---

## Arsitektur Kode

### Class `Message` (dataclass)

Struktur data pesan yang dikirim antar node.

| Field       | Tipe       | Keterangan                        |
|-------------|------------|-----------------------------------|
| `id`        | `str`      | Identifikasi unik pesan           |
| `sender`    | `str`      | Nama pengirim                     |
| `content`   | `str`      | Isi pesan                         |
| `timestamp` | `datetime` | Waktu pesan dibuat                |
| `topic`     | `str`      | Topik (digunakan di Pub-Sub)      |

### Class `RequestResponseNode`

Mensimulasikan server sinkron. Menerima request dan mengembalikan response setelah delay yang dapat dikonfigurasi.

### Class `PubSubBroker`

Broker untuk model Publish-Subscribe. Mengelola daftar subscriber per topik dan mendistribusikan pesan saat ada pesan masuk.

### Class `DistributedCommSimulation`

Class utama yang menangani seluruh GUI dan logika simulasi.

| Method                          | Fungsi                                                    |
|---------------------------------|-----------------------------------------------------------|
| `setup_ui()`                    | Membangun layout utama: header, notebook 3 tab, status bar |
| `setup_request_response_tab()`  | UI tab RR: input teks, slider delay, log, canvas diagram  |
| `setup_publish_subscribe_tab()` | UI tab PS: dropdown topik, log publisher, 3 log subscriber |
| `setup_comparison_tab()`        | UI tab perbandingan: grafik batang, tabel statistik       |
| `send_request_response()`       | Mengirim request secara async dan menghitung latency      |
| `simulate_multiple_requests()`  | Menjalankan 5 request sekaligus untuk uji throughput      |
| `publish_message()`             | Mempublikasikan pesan ke broker dan menghitung latency    |
| `draw_rr_visualization()`       | Menggambar diagram `Client ↔ Server`                      |
| `draw_ps_visualization()`       | Menggambar diagram `Publisher → Broker → Subscribers`     |
| `draw_comparison_chart()`       | Menggambar grafik batang perbandingan latency             |
| `reset_metrics()`               | Mereset semua log dan data statistik                      |
| `process_gui_queue()`           | Memproses update GUI secara thread-safe via queue         |

---

## Alur Komunikasi

### Request-Response

```
Client  ──[REQUEST]──▶  Server
Client  ◀──[RESPONSE]──  Server
```

Komunikasi bersifat **sinkron** dan **satu-ke-satu**. Client menunggu hingga server membalas sebelum melanjutkan.

### Publish-Subscribe

```
Publisher  ──[PUBLISH]──▶  Broker  ──[NOTIFY]──▶  Subscriber A
                                    ──[NOTIFY]──▶  Subscriber B
                                    ──[NOTIFY]──▶  Subscriber C
```

Komunikasi bersifat **asinkron** dan **satu-ke-banyak**. Publisher tidak perlu mengetahui siapa subscribernya.

> Pada inisialisasi, tiga subscriber (Client A, B, C) secara otomatis subscribe ke topik: `berita`, `alert`, dan `info`.

---

## Teknik Pemrograman

| Teknik             | Penerapan                                          |
|--------------------|----------------------------------------------------|
| Multi-threading    | `threading.Thread` untuk simulasi async            |
| Thread-safe GUI    | `queue.Queue` + `root.after()` agar GUI tidak freeze |
| Dataclass          | `@dataclass` pada class `Message`                  |
| OOP dengan Tkinter | Seluruh GUI dienkapsulasi dalam satu class         |

---

## Library yang Digunakan

Semua library merupakan bagian dari **Python Standard Library**:

| Library       | Kegunaan                         |
|---------------|----------------------------------|
| `tkinter`     | Antarmuka grafis (GUI)           |
| `threading`   | Simulasi proses asinkron         |
| `time`        | Delay dan pengukuran latency     |
| `queue`       | Komunikasi thread-safe ke GUI    |
| `dataclasses` | Deklarasi struktur data `Message`|
| `datetime`    | Timestamp pada log pesan         |
| `typing`      | Type hints                       |
| `random`      | Variasi nilai delay              |