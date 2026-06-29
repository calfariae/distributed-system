import tkinter as tk
from tkinter import ttk, scrolledtext, messagebox
import threading
import time
import queue
from dataclasses import dataclass
from datetime import datetime
from typing import List, Dict
import random

# ============================================
# KOMPONEN SISTEM TERDISTRIBUSI
# ============================================

@dataclass
class Message:
    """Representasi pesan dalam sistem"""
    id: int
    sender: str
    content: str
    timestamp: float
    topic: str = None  # Untuk pub-sub

class RequestResponseNode:
    """Node untuk model Request-Response (sinkron)"""
    def __init__(self, name: str, response_time: float = 0.5):
        self.name = name
        self.response_time = response_time
        self.requests_handled = 0
        
    def handle_request(self, request: Message) -> Message:
        """Memproses request dan mengembalikan response"""
        self.requests_handled += 1
        time.sleep(self.response_time)  # Simulasi processing delay
        return Message(
            id=request.id,
            sender=self.name,
            content=f"Response to: {request.content}",
            timestamp=time.time()
        )

class PubSubBroker:
    """Broker untuk model Publish-Subscribe (asinkron)"""
    def __init__(self):
        self.subscribers: Dict[str, List[str]] = {}  # topic -> list of subscribers
        self.message_history: List[Message] = []
        
    def subscribe(self, topic: str, subscriber_name: str):
        if topic not in self.subscribers:
            self.subscribers[topic] = []
        if subscriber_name not in self.subscribers[topic]:
            self.subscribers[topic].append(subscriber_name)
            
    def publish(self, message: Message) -> List[str]:
        """Mengirim pesan ke semua subscriber topik"""
        if message.topic not in self.subscribers:
            return []
        self.message_history.append(message)
        return self.subscribers[message.topic]

# ============================================
# SIMULASI INTERAKTIF
# ============================================

class DistributedCommSimulation:
    def __init__(self, root):
        self.root = root
        self.root.title("Simulasi Interaktif Model Komunikasi Sistem Terdistribusi")
        self.root.geometry("1300x750")
        self.root.configure(bg='#f0f0f0')
        
        # Komponen sistem
        self.request_node = RequestResponseNode("Server-1")
        self.pubsub_broker = PubSubBroker()
        self.pubsub_subscribers = ["Client A", "Client B", "Client C"]
        
        # Inisialisasi subscribers untuk topik yang berbeda
        for sub in self.pubsub_subscribers:
            self.pubsub_broker.subscribe("berita", sub)
            self.pubsub_broker.subscribe("alert", sub)
            self.pubsub_broker.subscribe("info", sub)
        
        # Metrik kinerja
        self.message_count = 0
        self.latency_records = []  # (model, latency_ms)
        
        # Queue untuk thread-safe GUI update
        self.gui_queue = queue.Queue()
        
        self.setup_ui()
        self.process_gui_queue()
        
    def setup_ui(self):
        """Membangun antarmuka pengguna"""
        # Header
        header_frame = tk.Frame(self.root, bg='#2c3e50', height=60)
        header_frame.pack(fill=tk.X)
        tk.Label(header_frame, text="Simulasi Interaktif Model Komunikasi Sistem Terdistribusi",
                font=('Arial', 16, 'bold'), fg='white', bg='#2c3e50').pack(pady=15)
        
        # Notebook untuk tab model komunikasi
        self.notebook = ttk.Notebook(self.root)
        self.notebook.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # Tab 1: Request-Response
        self.rr_frame = ttk.Frame(self.notebook)
        self.notebook.add(self.rr_frame, text="📡 Request-Response")
        self.setup_request_response_tab()
        
        # Tab 2: Publish-Subscribe
        self.ps_frame = ttk.Frame(self.notebook)
        self.notebook.add(self.ps_frame, text="📢 Publish-Subscribe")
        self.setup_publish_subscribe_tab()
        
        # Tab 3: Perbandingan Metrik
        self.comp_frame = ttk.Frame(self.notebook)
        self.notebook.add(self.comp_frame, text="📊 Perbandingan Metrik")
        self.setup_comparison_tab()
        
        # Status bar
        self.status_bar = tk.Label(self.root, text="✅ Siap | Pilih model komunikasi untuk memulai simulasi",
                                   relief=tk.SUNKEN, anchor=tk.W, bg='#ecf0f1', fg='#2c3e50')
        self.status_bar.pack(side=tk.BOTTOM, fill=tk.X)
        
    def setup_request_response_tab(self):
        """Membangun UI untuk model Request-Response"""
        # Frame utama split
        main_panel = ttk.Frame(self.rr_frame)
        main_panel.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # Frame kiri: Kontrol
        left_frame = ttk.LabelFrame(main_panel, text="🎮 Kontrol Request", padding=15)
        left_frame.pack(side=tk.LEFT, fill=tk.Y, padx=5, pady=5)
        
        ttk.Label(left_frame, text="📝 Request Message:", font=('Arial', 10, 'bold')).pack(anchor=tk.W)
        self.rr_request_text = tk.Text(left_frame, height=6, width=45, font=('Arial', 10))
        self.rr_request_text.pack(pady=5)
        self.rr_request_text.insert(tk.END, "Halo Server, berapa waktu sekarang?")
        
        ttk.Label(left_frame, text="⏱️ Simulasi Delay Server (detik):", font=('Arial', 10, 'bold')).pack(anchor=tk.W, pady=(10,0))
        self.rr_delay_var = tk.DoubleVar(value=0.5)
        delay_slider = ttk.Scale(left_frame, from_=0.1, to=2.0, variable=self.rr_delay_var, orient=tk.HORIZONTAL)
        delay_slider.pack(fill=tk.X, pady=5)
        self.rr_delay_label = ttk.Label(left_frame, text=f"{self.rr_delay_var.get():.2f} detik", font=('Arial', 9))
        self.rr_delay_label.pack()
        
        def update_delay_label(*args):
            self.rr_delay_label.config(text=f"{self.rr_delay_var.get():.2f} detik")
        self.rr_delay_var.trace('w', update_delay_label)
        
        ttk.Button(left_frame, text="🚀 Kirim Request", command=self.send_request_response,
                   width=35).pack(pady=15)
        
        ttk.Button(left_frame, text="🔄 Simulasi Multi-Request (5x)", 
                   command=self.simulate_multiple_requests, width=35).pack(pady=5)
        
        # Frame kanan: Log dan Visualisasi
        right_frame = ttk.Frame(main_panel)
        right_frame.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        # Visualisasi
        viz_frame = ttk.LabelFrame(right_frame, text="📊 Visualisasi Aliran Data", padding=10)
        viz_frame.pack(fill=tk.X, pady=5)
        
        self.rr_canvas = tk.Canvas(viz_frame, height=150, bg='white', relief=tk.RAISED, borderwidth=1)
        self.rr_canvas.pack(fill=tk.X)
        self.draw_rr_visualization()
        
        # Log
        log_frame = ttk.LabelFrame(right_frame, text="📋 Log Komunikasi", padding=10)
        log_frame.pack(fill=tk.BOTH, expand=True, pady=5)
        
        self.rr_log = scrolledtext.ScrolledText(log_frame, height=18, width=60, font=('Consolas', 9))
        self.rr_log.pack(fill=tk.BOTH, expand=True)
        
    def setup_publish_subscribe_tab(self):
        """Membangun UI untuk model Publish-Subscribe"""
        # Frame kontrol
        control_frame = ttk.LabelFrame(self.ps_frame, text="🎮 Kontrol Publisher", padding=15)
        control_frame.pack(fill=tk.X, padx=10, pady=10)
        
        control_grid = ttk.Frame(control_frame)
        control_grid.pack(fill=tk.X)
        
        ttk.Label(control_grid, text="📢 Topik:", font=('Arial', 10, 'bold')).grid(row=0, column=0, padx=5, pady=5)
        self.ps_topic_var = tk.StringVar(value="berita")
        topic_combo = ttk.Combobox(control_grid, textvariable=self.ps_topic_var, 
                                   values=["berita", "alert", "info"], width=15, font=('Arial', 10))
        topic_combo.grid(row=0, column=1, padx=5, pady=5)
        
        ttk.Label(control_grid, text="💬 Pesan:", font=('Arial', 10, 'bold')).grid(row=0, column=2, padx=5, pady=5)
        self.ps_message_entry = ttk.Entry(control_grid, width=45, font=('Arial', 10))
        self.ps_message_entry.grid(row=0, column=3, padx=5, pady=5)
        self.ps_message_entry.insert(0, "Pesan baru dari publisher!")
        
        ttk.Button(control_grid, text="📤 PUBLISH", command=self.publish_message,
                   width=15).grid(row=0, column=4, padx=10, pady=5)
        
        # Publisher Log Frame
        pub_frame = ttk.LabelFrame(self.ps_frame, text="📝 Publisher Log", padding=10)
        pub_frame.pack(fill=tk.X, padx=10, pady=5)
        
        self.publisher_log = scrolledtext.ScrolledText(pub_frame, height=6, width=80, font=('Consolas', 9))
        self.publisher_log.pack(fill=tk.BOTH, expand=True)
        
        # Subscribers frame
        subs_frame = ttk.LabelFrame(self.ps_frame, text="👥 Subscribers & Log", padding=10)
        subs_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)
        
        # Visualisasi
        self.ps_canvas = tk.Canvas(subs_frame, height=150, bg='lightyellow', relief=tk.RAISED, borderwidth=1)
        self.ps_canvas.pack(fill=tk.X, pady=5)
        self.draw_ps_visualization()
        
        # Text log untuk masing-masing subscriber
        log_container = ttk.Frame(subs_frame)
        log_container.pack(fill=tk.BOTH, expand=True, pady=5)
        
        self.subscriber_logs = {}
        colors = ['#ffcccc', '#ccffcc', '#ccccff']
        for i, sub in enumerate(self.pubsub_subscribers):
            frame = ttk.LabelFrame(log_container, text=f"📱 {sub}", padding=5)
            frame.grid(row=0, column=i, padx=5, pady=5, sticky="nsew")
            log_text = scrolledtext.ScrolledText(frame, height=12, width=35, font=('Consolas', 8))
            log_text.pack(fill=tk.BOTH, expand=True)
            self.subscriber_logs[sub] = log_text
            
        log_container.grid_columnconfigure(list(range(3)), weight=1)
        
    def setup_comparison_tab(self):
        """Membangun UI untuk perbandingan metrik"""
        # Frame utama
        main_frame = ttk.Frame(self.comp_frame)
        main_frame.pack(fill=tk.BOTH, expand=True, padx=15, pady=15)
        
        # Canvas untuk grafik
        chart_frame = ttk.LabelFrame(main_frame, text="📊 Grafik Perbandingan Latency", padding=10)
        chart_frame.pack(fill=tk.BOTH, expand=True, pady=5)
        
        self.comp_canvas = tk.Canvas(chart_frame, height=300, bg='white', relief=tk.RAISED, borderwidth=1)
        self.comp_canvas.pack(fill=tk.BOTH, expand=True)
        
        # Tabel perbandingan
        table_frame = ttk.LabelFrame(main_frame, text="📈 Statistik Kinerja", padding=10)
        table_frame.pack(fill=tk.X, pady=10)
        
        # Header tabel
        headers = ["Model Komunikasi", "Jumlah Pesan", "Rata-rata Latency (ms)", "Total Pesan"]
        for col, header in enumerate(headers):
            ttk.Label(table_frame, text=header, font=('Arial', 11, 'bold')).grid(row=0, column=col, padx=20, pady=5)
        
        ttk.Separator(table_frame, orient='horizontal').grid(row=1, column=0, columnspan=4, sticky='ew', pady=5)
        
        self.rr_stats_label = ttk.Label(table_frame, text="Request-Response", font=('Arial', 10))
        self.rr_stats_label.grid(row=2, column=0, padx=20, pady=5)
        
        self.rr_count_label = ttk.Label(table_frame, text="0", font=('Arial', 10))
        self.rr_count_label.grid(row=2, column=1, padx=20, pady=5)
        
        self.rr_latency_label = ttk.Label(table_frame, text="0.00", font=('Arial', 10))
        self.rr_latency_label.grid(row=2, column=2, padx=20, pady=5)
        
        self.ps_stats_label = ttk.Label(table_frame, text="Publish-Subscribe", font=('Arial', 10))
        self.ps_stats_label.grid(row=3, column=0, padx=20, pady=5)
        
        self.ps_count_label = ttk.Label(table_frame, text="0", font=('Arial', 10))
        self.ps_count_label.grid(row=3, column=1, padx=20, pady=5)
        
        self.ps_latency_label = ttk.Label(table_frame, text="0.00", font=('Arial', 10))
        self.ps_latency_label.grid(row=3, column=2, padx=20, pady=5)
        
        # Button reset
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill=tk.X, pady=10)
        ttk.Button(button_frame, text="🔄 Reset Semua Metrik", command=self.reset_metrics,
                   width=30).pack()
        
        self.update_comparison_display()
        
    def draw_rr_visualization(self):
        """Menggambar diagram aliran Request-Response"""
        self.rr_canvas.delete("all")
        width = self.rr_canvas.winfo_width()
        if width < 10:
            width = 600
        center = width // 2
        
        # Client
        self.rr_canvas.create_rectangle(50, 40, 200, 100, fill='#3498db', outline='#2c3e50', width=2)
        self.rr_canvas.create_text(125, 70, text="🖥️ Client", fill='white', font=('Arial', 10, 'bold'))
        
        # Server
        self.rr_canvas.create_rectangle(center - 75, 40, center + 75, 100, fill='#2ecc71', outline='#2c3e50', width=2)
        self.rr_canvas.create_text(center, 70, text="🗄️ Server", fill='white', font=('Arial', 10, 'bold'))
        
        # Panah Request
        self.rr_canvas.create_line(200, 70, center - 75, 70, arrow=tk.LAST, width=3, fill='#e74c3c')
        self.rr_canvas.create_text(center - 100, 55, text="📤 REQUEST", fill='#e74c3c', font=('Arial', 9, 'bold'))
        
        # Panah Response
        self.rr_canvas.create_line(center + 75, 85, 200, 85, arrow=tk.LAST, width=3, fill='#27ae60')
        self.rr_canvas.create_text(center - 100, 95, text="📥 RESPONSE", fill='#27ae60', font=('Arial', 9, 'bold'))
        
    def draw_ps_visualization(self):
        """Menggambar diagram aliran Publish-Subscribe"""
        self.ps_canvas.delete("all")
        width = self.ps_canvas.winfo_width()
        if width < 10:
            width = 800
        
        # Publisher
        self.ps_canvas.create_rectangle(20, 50, 130, 110, fill='#e74c3c', outline='#2c3e50', width=2)
        self.ps_canvas.create_text(75, 80, text="📝 Publisher", fill='white', font=('Arial', 9, 'bold'))
        
        # Broker
        center = width // 2
        self.ps_canvas.create_rectangle(center - 100, 30, center + 100, 130, fill='#f39c12', outline='#2c3e50', width=2)
        self.ps_canvas.create_text(center, 80, text="🏢 BROKER", fill='white', font=('Arial', 10, 'bold'))
        
        # Subscribers
        subs_pos = [(width - 180, 30), (width - 180, 80), (width - 180, 130)]
        subs_names = ["👤 Client A", "👤 Client B", "👤 Client C"]
        for i, (x, y) in enumerate(subs_pos):
            self.ps_canvas.create_rectangle(x, y, x+100, y+50, fill='#3498db', outline='#2c3e50', width=2)
            self.ps_canvas.create_text(x+50, y+25, text=subs_names[i], fill='white', font=('Arial', 8))
            # Panah dari broker ke subscriber
            self.ps_canvas.create_line(center + 100, 80, x, y+25, arrow=tk.LAST, width=2, fill='#27ae60', dash=(4,2))
        
        # Panah dari publisher ke broker
        self.ps_canvas.create_line(130, 80, center - 100, 80, arrow=tk.LAST, width=3, fill='#e74c3c')
        self.ps_canvas.create_text(center - 120, 65, text="📤 PUBLISH", fill='#e74c3c', font=('Arial', 9, 'bold'))
        
    def send_request_response(self):
        """Mengirim request dan mencatat respons dengan latency"""
        def async_request():
            start_time = time.time()
            self.update_status("🔄 Mengirim request...")
            self.log_rr("📤 [REQUEST] Dikirim ke Server")
            
            request = Message(
                id=self.message_count,
                sender="Client",
                content=self.rr_request_text.get("1.0", tk.END).strip(),
                timestamp=start_time
            )
            
            # Update delay server
            self.request_node.response_time = self.rr_delay_var.get()
            
            # Proses request
            response = self.request_node.handle_request(request)
            
            latency_ms = (time.time() - start_time) * 1000
            self.latency_records.append(("Request-Response", latency_ms))
            
            self.log_rr(f"📥 [RESPONSE] Diterima: {response.content}")
            self.log_rr(f"⏱️  Latency: {latency_ms:.2f} ms")
            self.log_rr("-" * 50)
            self.update_status(f"✅ Response diterima dalam {latency_ms:.2f} ms")
            
            self.message_count += 1
            self.update_comparison_display()
            
        threading.Thread(target=async_request, daemon=True).start()
        
    def simulate_multiple_requests(self):
        """Simulasi multiple request untuk mengukur throughput"""
        def run_batch():
            self.update_status("🔄 Menjalankan simulasi batch (5 request)...")
            self.log_rr("\n" + "="*50)
            self.log_rr("📊 SIMULASI BATCH: 5 REQUEST")
            self.log_rr("="*50)
            
            latencies = []
            for i in range(5):
                start = time.time()
                req = Message(i, "Client", f"Batch request {i+1}", start)
                self.request_node.handle_request(req)
                latencies.append((time.time() - start) * 1000)
                self.log_rr(f"  Request {i+1}: {latencies[-1]:.2f} ms")
            
            avg_latency = sum(latencies) / len(latencies)
            min_latency = min(latencies)
            max_latency = max(latencies)
            
            self.log_rr("-" * 50)
            self.log_rr(f"📊 HASIL BATCH:")
            self.log_rr(f"   Rata-rata: {avg_latency:.2f} ms")
            self.log_rr(f"   Min: {min_latency:.2f} ms")
            self.log_rr(f"   Max: {max_latency:.2f} ms")
            self.log_rr("="*50 + "\n")
            
            self.update_status(f"✅ Batch selesai. Rata-rata latency: {avg_latency:.2f} ms")
            
        threading.Thread(target=run_batch, daemon=True).start()
        
    def publish_message(self):
        """Mempublikasikan pesan ke broker dengan pengukuran latency"""
        topic = self.ps_topic_var.get()
        content = self.ps_message_entry.get()
        
        if not content:
            messagebox.showwarning("Peringatan", "Pesan tidak boleh kosong!")
            return
            
        self.update_status(f"🔄 Publishing ke topik '{topic}'...")
        start_time = time.time()  # Mulai hitung waktu
        
        # Buat pesan
        msg = Message(
            id=self.message_count,
            sender="Publisher",
            content=content,
            timestamp=start_time,
            topic=topic
        )
        
        # Publish ke broker
        subscribers = self.pubsub_broker.publish(msg)
        
        # Hitung latency (waktu dari publish sampai pesan sampai ke broker)
        end_time = time.time()
        latency_ms = (end_time - start_time) * 1000
        
        # Catat latency
        self.latency_records.append(("Publish-Subscribe", latency_ms))
        
        # Log untuk publisher
        timestamp = datetime.now().strftime("%H:%M:%S")
        if hasattr(self, 'publisher_log'):
            self.gui_queue.put(("publisher_log", f"[{timestamp}] 📤 PUBLISHED\n"))
            self.gui_queue.put(("publisher_log", f"   Topik: {topic}\n"))
            self.gui_queue.put(("publisher_log", f"   Pesan: {content}\n"))
            self.gui_queue.put(("publisher_log", f"   Latency: {latency_ms:.2f} ms\n"))
            self.gui_queue.put(("publisher_log", f"   Subscribers: {len(subscribers)} client(s)\n"))
            self.gui_queue.put(("publisher_log", "-" * 40 + "\n"))
        
        # Simulasi delivery ke subscriber (asinkron dengan delay kecil)
        for sub in subscribers:
            delivery_delay = random.uniform(0.01, 0.05)
            time.sleep(delivery_delay)
            self.log_ps_subscriber(sub, f"📥 Received from [{topic}]: {content}")
            
        self.message_count += 1
        self.update_status(f"✅ Pesan terkirim ke {len(subscribers)} subscriber(s) dalam {latency_ms:.2f} ms")
        self.update_comparison_display()
        
    def log_rr(self, message):
        """Menambahkan log ke tab Request-Response"""
        timestamp = datetime.now().strftime("%H:%M:%S")
        self.gui_queue.put(("rr_log", f"[{timestamp}] {message}\n"))
        
    def log_ps_subscriber(self, subscriber, message):
        """Menambahkan log ke subscriber tertentu"""
        timestamp = datetime.now().strftime("%H:%M:%S")
        if subscriber in self.subscriber_logs:
            self.gui_queue.put(("ps_log", subscriber, f"[{timestamp}] {message}\n"))
        
    def update_status(self, message):
        """Update status bar"""
        self.gui_queue.put(("status", message))
        
    def update_comparison_display(self):
        """Update metrik perbandingan"""
        rr_latencies = [l[1] for l in self.latency_records if l[0] == "Request-Response"]
        ps_latencies = [l[1] for l in self.latency_records if l[0] == "Publish-Subscribe"]
        
        rr_avg = sum(rr_latencies) / len(rr_latencies) if rr_latencies else 0
        ps_avg = sum(ps_latencies) / len(ps_latencies) if ps_latencies else 0
        
        self.gui_queue.put(("update_stats", 
            len(rr_latencies), rr_avg,
            len(ps_latencies), ps_avg
        ))
        
        # Gambar grafik perbandingan
        self.gui_queue.put(("draw_chart", rr_avg, ps_avg))
        
    def reset_metrics(self):
        """Reset semua metrik"""
        self.message_count = 0
        self.latency_records.clear()
        self.request_node.requests_handled = 0
        self.pubsub_broker.message_history.clear()
        
        # Reset logs
        self.rr_log.delete("1.0", tk.END)
        if hasattr(self, 'publisher_log'):
            self.publisher_log.delete("1.0", tk.END)
        for log in self.subscriber_logs.values():
            log.delete("1.0", tk.END)
            
        self.update_status("🔄 Semua metrik telah direset")
        self.update_comparison_display()
        
    def process_gui_queue(self):
        """Memproses queue untuk update GUI thread-safe"""
        try:
            while True:
                item = self.gui_queue.get_nowait()
                if item[0] == "rr_log":
                    self.rr_log.insert(tk.END, item[1])
                    self.rr_log.see(tk.END)
                elif item[0] == "ps_log":
                    _, subscriber, msg = item
                    self.subscriber_logs[subscriber].insert(tk.END, msg)
                    self.subscriber_logs[subscriber].see(tk.END)
                elif item[0] == "publisher_log":
                    if hasattr(self, 'publisher_log'):
                        self.publisher_log.insert(tk.END, item[1])
                        self.publisher_log.see(tk.END)
                elif item[0] == "status":
                    self.status_bar.config(text=f"💡 {item[1]}")
                elif item[0] == "update_stats":
                    _, rr_count, rr_avg, ps_count, ps_avg = item
                    self.rr_count_label.config(text=str(rr_count))
                    self.rr_latency_label.config(text=f"{rr_avg:.2f}")
                    self.ps_count_label.config(text=str(ps_count))
                    self.ps_latency_label.config(text=f"{ps_avg:.2f}")
                elif item[0] == "draw_chart":
                    _, rr_avg, ps_avg = item
                    self.draw_comparison_chart(rr_avg, ps_avg)
        except queue.Empty:
            pass
        finally:
            self.root.after(100, self.process_gui_queue)
            
    def draw_comparison_chart(self, rr_avg, ps_avg):
        """Menggambar grafik batang perbandingan latency"""
        self.comp_canvas.delete("all")
        width = self.comp_canvas.winfo_width()
        height = self.comp_canvas.winfo_height()
        
        if width < 10:
            width = 600
        if height < 10:
            height = 250
            
        margin = 60
        chart_height = height - 80
        
        # Sumbu
        self.comp_canvas.create_line(margin, chart_height, margin + 400, chart_height, width=2, fill='#2c3e50')
        self.comp_canvas.create_line(margin, 20, margin, chart_height, width=2, fill='#2c3e50')
        
        # Label sumbu Y
        self.comp_canvas.create_text(25, chart_height // 2, text="Latency (ms)", font=('Arial', 9), angle=90)
        
        # Maksimum untuk scaling
        max_val = max(rr_avg, ps_avg, 100)
        
        # Batang RR
        rr_height = (rr_avg / max_val) * (chart_height - 40) if rr_avg > 0 else 0
        x1 = margin + 50
        y1 = chart_height - rr_height
        x2 = margin + 150
        y2 = chart_height
        self.comp_canvas.create_rectangle(x1, y1, x2, y2, fill='#3498db', outline='#2c3e50', width=2)
        self.comp_canvas.create_text((x1+x2)//2, y1-10, text=f"{rr_avg:.1f} ms", fill='#3498db', font=('Arial', 9, 'bold'))
        self.comp_canvas.create_text((x1+x2)//2, y2+15, text="Request-Response", fill='#2c3e50', font=('Arial', 8))
        
        # Batang PS
        ps_height = (ps_avg / max_val) * (chart_height - 40) if ps_avg > 0 else 0
        x1 = margin + 220
        y1 = chart_height - ps_height
        x2 = margin + 320
        y2 = chart_height
        self.comp_canvas.create_rectangle(x1, y1, x2, y2, fill='#2ecc71', outline='#2c3e50', width=2)
        self.comp_canvas.create_text((x1+x2)//2, y1-10, text=f"{ps_avg:.1f} ms", fill='#2ecc71', font=('Arial', 9, 'bold'))
        self.comp_canvas.create_text((x1+x2)//2, y2+15, text="Publish-Subscribe", fill='#2c3e50', font=('Arial', 8))

# ============================================
# MAIN
# ============================================

if __name__ == "__main__":
    root = tk.Tk()
    app = DistributedCommSimulation(root)
    root.mainloop()