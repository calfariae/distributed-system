"""
main.py - Tkinter GUI for the Social Media Feed Simulation

Models demonstrated:
  - Request-Response : posting a message, liking a post
  - Publish-Subscribe: followers receiving posts in real time

Layout:
  Left   → Active User panel (select who is "you", write & post)
  Center → Feed panel (live updates from followed users)
  Right  → Activity Log (color-coded by model/event type)
"""

import tkinter as tk
from tkinter import ttk, scrolledtext
import threading
import time
import random

from broker import Broker
from user import User

# ── Palette ────────────────────────────────────────────────────────────────
BG         = "#0f0f13"
PANEL_BG   = "#16161e"
CARD_BG    = "#1e1e2a"
ACCENT     = "#7c6af7"        # purple
ACCENT2    = "#f76a8c"        # pink
GREEN      = "#4ade80"
YELLOW     = "#fbbf24"
CYAN       = "#22d3ee"
TEXT       = "#e2e2ef"
MUTED      = "#6b6b85"
BORDER     = "#2a2a38"

TAG_COLORS = {
    "REQUEST":   CYAN,
    "RESPONSE":  GREEN,
    "PUBLISH":   ACCENT,
    "NOTIFY":    ACCENT2,
    "SUBSCRIBE": YELLOW,
}

AVATAR_COLORS = {
    "Alice":   "#f76a8c",
    "Bob":     "#7c6af7",
    "Charlie": "#22d3ee",
    "Diana":   "#fbbf24",
}

FONT_MONO   = ("Courier New", 10)
FONT_BODY   = ("Segoe UI", 10)
FONT_BOLD   = ("Segoe UI", 10, "bold")
FONT_TITLE  = ("Segoe UI", 13, "bold")
FONT_SMALL  = ("Segoe UI", 8)
FONT_LARGE  = ("Segoe UI", 16, "bold")


class SocialSimApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Distributed Comm Simulator — Social Feed")
        self.configure(bg=BG)
        self.geometry("1200x720")
        self.minsize(1000, 620)
        self.resizable(True, True)

        # ── Bootstrap broker & users ──────────────────────────────────────
        self.broker = Broker(log_callback=self._log_event)
        self.users = {}
        for name in ["Alice", "Bob", "Charlie", "Diana"]:
            u = User(name, self.broker)
            self.users[name] = u

        # Fixed follow graph
        # Alice ← Bob, Charlie, Diana
        # Bob   ← Alice, Charlie
        # Charlie ← Alice
        # Diana ← Alice, Bob
        self.users["Bob"].follow(self.users["Alice"])
        self.users["Charlie"].follow(self.users["Alice"])
        self.users["Diana"].follow(self.users["Alice"])
        self.users["Alice"].follow(self.users["Bob"])
        self.users["Charlie"].follow(self.users["Bob"])
        self.users["Diana"].follow(self.users["Bob"])
        self.users["Alice"].follow(self.users["Charlie"])

        self.active_user_var = tk.StringVar(value="Alice")
        self.post_cards = {}   # post_id -> frame (for like count update)

        self._build_ui()
        self._bind_user_feed_callbacks()
        self._run_demo_posts()

    # ══════════════════════════════════════════════════════════════════════
    # UI BUILD
    # ══════════════════════════════════════════════════════════════════════

    def _build_ui(self):
        # Top header bar
        header = tk.Frame(self, bg=PANEL_BG, height=52)
        header.pack(fill="x", side="top")
        header.pack_propagate(False)

        tk.Label(header, text="◈  DistFeed", font=FONT_LARGE,
                 fg=ACCENT, bg=PANEL_BG).pack(side="left", padx=20, pady=10)
        tk.Label(header, text="Request-Response  ·  Publish-Subscribe",
                 font=FONT_SMALL, fg=MUTED, bg=PANEL_BG).pack(side="left", padx=4)

        # Legend chips
        for tag, color in TAG_COLORS.items():
            chip = tk.Frame(header, bg=color, padx=6, pady=2)
            chip.pack(side="right", padx=4, pady=14)
            tk.Label(chip, text=tag, font=FONT_SMALL, fg=BG, bg=color).pack()

        # Main 3-column body
        body = tk.Frame(self, bg=BG)
        body.pack(fill="both", expand=True, padx=10, pady=(0, 10))

        body.columnconfigure(0, weight=2, minsize=220)
        body.columnconfigure(1, weight=4)
        body.columnconfigure(2, weight=3)
        body.rowconfigure(0, weight=1)

        self._build_left_panel(body)
        self._build_center_panel(body)
        self._build_right_panel(body)

    # ── Left: User selector + Post composer ──────────────────────────────
    def _build_left_panel(self, parent):
        frame = tk.Frame(parent, bg=PANEL_BG, padx=14, pady=14)
        frame.grid(row=0, column=0, sticky="nsew", padx=(0, 6))

        tk.Label(frame, text="Active User", font=FONT_TITLE,
                 fg=TEXT, bg=PANEL_BG).pack(anchor="w")
        tk.Label(frame, text="You are posting as:", font=FONT_SMALL,
                 fg=MUTED, bg=PANEL_BG).pack(anchor="w", pady=(2, 8))

        # Avatar buttons
        for name in self.users:
            color = AVATAR_COLORS[name]
            btn = tk.Button(
                frame, text=f"  {name}", font=FONT_BOLD,
                fg=TEXT, bg=CARD_BG, activebackground=color,
                activeforeground=BG, relief="flat", anchor="w",
                padx=10, pady=7, cursor="hand2",
                command=lambda n=name: self._switch_user(n)
            )
            btn.pack(fill="x", pady=2)
            self._add_hover(btn, color, CARD_BG)
            setattr(self, f"btn_{name}", btn)

        self._highlight_active_btn()

        # Follow info
        self.follow_info = tk.Label(frame, text="", font=FONT_SMALL,
                                    fg=MUTED, bg=PANEL_BG, wraplength=190,
                                    justify="left")
        self.follow_info.pack(anchor="w", pady=(10, 0))
        self._update_follow_info()

        tk.Frame(frame, bg=BORDER, height=1).pack(fill="x", pady=12)

        # Composer
        tk.Label(frame, text="New Post", font=FONT_BOLD,
                 fg=TEXT, bg=PANEL_BG).pack(anchor="w")
        tk.Label(frame, text="Request-Response flow", font=FONT_SMALL,
                 fg=ACCENT, bg=PANEL_BG).pack(anchor="w", pady=(0, 6))

        self.post_text = tk.Text(
            frame, height=4, font=FONT_BODY,
            bg=CARD_BG, fg=TEXT, insertbackground=TEXT,
            relief="flat", padx=8, pady=6, wrap="word",
            highlightthickness=1, highlightcolor=ACCENT,
            highlightbackground=BORDER
        )
        self.post_text.pack(fill="x")
        self.post_text.insert("1.0", "What's on your mind?")
        self.post_text.bind("<FocusIn>", self._clear_placeholder)

        self.post_btn = tk.Button(
            frame, text="POST  →", font=FONT_BOLD,
            fg=BG, bg=ACCENT, activebackground=ACCENT2,
            relief="flat", pady=8, cursor="hand2",
            command=self._on_post
        )
        self.post_btn.pack(fill="x", pady=(8, 0))

        # Stats
        tk.Frame(frame, bg=BORDER, height=1).pack(fill="x", pady=12)
        self.stats_label = tk.Label(frame, text="", font=FONT_SMALL,
                                    fg=MUTED, bg=PANEL_BG, justify="left")
        self.stats_label.pack(anchor="w")
        self._update_stats()

    # ── Center: Feed ──────────────────────────────────────────────────────
    def _build_center_panel(self, parent):
        outer = tk.Frame(parent, bg=PANEL_BG)
        outer.grid(row=0, column=1, sticky="nsew", padx=6)

        header = tk.Frame(outer, bg=PANEL_BG, pady=12, padx=14)
        header.pack(fill="x")
        tk.Label(header, text="Live Feed", font=FONT_TITLE,
                 fg=TEXT, bg=PANEL_BG).pack(side="left")
        tk.Label(header, text="← Pub-Sub pushes here", font=FONT_SMALL,
                 fg=ACCENT2, bg=PANEL_BG).pack(side="right")

        tk.Frame(outer, bg=BORDER, height=1).pack(fill="x")

        # Scrollable canvas for feed cards
        canvas_frame = tk.Frame(outer, bg=PANEL_BG)
        canvas_frame.pack(fill="both", expand=True)

        self.feed_canvas = tk.Canvas(canvas_frame, bg=PANEL_BG,
                                     highlightthickness=0)
        scrollbar = ttk.Scrollbar(canvas_frame, orient="vertical",
                                  command=self.feed_canvas.yview)
        self.feed_canvas.configure(yscrollcommand=scrollbar.set)

        scrollbar.pack(side="right", fill="y")
        self.feed_canvas.pack(side="left", fill="both", expand=True)

        self.feed_inner = tk.Frame(self.feed_canvas, bg=PANEL_BG)
        self.feed_canvas_window = self.feed_canvas.create_window(
            (0, 0), window=self.feed_inner, anchor="nw"
        )
        self.feed_inner.bind("<Configure>", self._on_feed_resize)
        self.feed_canvas.bind("<Configure>", self._on_canvas_resize)
        self.feed_canvas.bind_all("<MouseWheel>", self._on_mousewheel)

    # ── Right: Activity log ───────────────────────────────────────────────
    def _build_right_panel(self, parent):
        frame = tk.Frame(parent, bg=PANEL_BG)
        frame.grid(row=0, column=2, sticky="nsew", padx=(6, 0))

        header = tk.Frame(frame, bg=PANEL_BG, pady=12, padx=14)
        header.pack(fill="x")
        tk.Label(header, text="Activity Log", font=FONT_TITLE,
                 fg=TEXT, bg=PANEL_BG).pack(side="left")

        clear_btn = tk.Button(header, text="Clear", font=FONT_SMALL,
                              fg=MUTED, bg=PANEL_BG, relief="flat",
                              cursor="hand2", command=self._clear_log)
        clear_btn.pack(side="right")

        tk.Frame(frame, bg=BORDER, height=1).pack(fill="x")

        self.log_box = scrolledtext.ScrolledText(
            frame, font=FONT_MONO, bg=PANEL_BG, fg=TEXT,
            relief="flat", padx=10, pady=8, state="disabled",
            wrap="word", spacing1=2, spacing3=2
        )
        self.log_box.pack(fill="both", expand=True, padx=4, pady=4)

        # Tag colors for log
        for tag, color in TAG_COLORS.items():
            self.log_box.tag_config(tag, foreground=color)
        self.log_box.tag_config("DIM", foreground=MUTED)

    # ══════════════════════════════════════════════════════════════════════
    # LOGIC & CALLBACKS
    # ══════════════════════════════════════════════════════════════════════

    def _switch_user(self, name):
        self.active_user_var.set(name)
        self._highlight_active_btn()
        self._update_follow_info()

    def _highlight_active_btn(self):
        active = self.active_user_var.get()
        for name in self.users:
            btn = getattr(self, f"btn_{name}")
            color = AVATAR_COLORS[name]
            if name == active:
                btn.config(bg=color, fg=BG)
            else:
                btn.config(bg=CARD_BG, fg=TEXT)

    def _update_follow_info(self):
        active = self.active_user_var.get()
        user = self.users[active]
        following = user.following or ["nobody yet"]
        self.follow_info.config(
            text=f"Following: {', '.join(following)}\n"
                 f"Their posts appear in your feed via Pub-Sub."
        )

    def _clear_placeholder(self, event):
        if self.post_text.get("1.0", "end-1c") == "What's on your mind?":
            self.post_text.delete("1.0", "end")

    def _on_post(self):
        content = self.post_text.get("1.0", "end-1c").strip()
        if not content or content == "What's on your mind?":
            self._flash_btn(self.post_btn, ACCENT2, "Write something first!")
            return

        active = self.active_user_var.get()
        user = self.users[active]
        user.post(content)

        self.post_text.delete("1.0", "end")
        self._update_stats()
        self._flash_btn(self.post_btn, GREEN, "POST  →")

    def _bind_user_feed_callbacks(self):
        """Each user's feed update triggers a GUI card addition."""
        for name, user in self.users.items():
            user.feed_update_cb = lambda post, n=name: self.after(
                0, self._add_feed_card, post, n
            )

    def _add_feed_card(self, post, recipient):
        """Add a post card to the feed panel."""
        author = post["author"]
        color = AVATAR_COLORS.get(author, ACCENT)

        card = tk.Frame(self.feed_inner, bg=CARD_BG, padx=14, pady=10)
        card.pack(fill="x", padx=10, pady=4)

        # Flash animation on new card
        self.after(50,  lambda: card.config(bg=BORDER))
        self.after(200, lambda: card.config(bg=CARD_BG))

        # Header row
        top = tk.Frame(card, bg=CARD_BG)
        top.pack(fill="x")

        # Avatar circle (simulated with colored label)
        avatar = tk.Label(top, text=author[0], font=("Segoe UI", 10, "bold"),
                          fg=BG, bg=color, width=2, pady=2)
        avatar.pack(side="left", padx=(0, 8))

        tk.Label(top, text=author, font=FONT_BOLD,
                 fg=color, bg=CARD_BG).pack(side="left")
        tk.Label(top, text=f"→ {recipient}'s feed  •  {post['timestamp']}",
                 font=FONT_SMALL, fg=MUTED, bg=CARD_BG).pack(side="left", padx=6)

        tk.Label(top, text=f"#{post['id']}", font=FONT_SMALL,
                 fg=MUTED, bg=CARD_BG).pack(side="right")

        # Content
        tk.Label(card, text=post["content"], font=FONT_BODY,
                 fg=TEXT, bg=CARD_BG, wraplength=360,
                 justify="left", anchor="w").pack(fill="x", pady=(6, 8))

        # Like row
        bottom = tk.Frame(card, bg=CARD_BG)
        bottom.pack(fill="x")

        like_count = tk.Label(bottom, text=f"♥  {post['likes']}",
                              font=FONT_SMALL, fg=MUTED, bg=CARD_BG)
        like_count.pack(side="left", padx=(0, 8))

        # Store reference for live like count update
        self.post_cards[post["id"]] = like_count

        like_btn = tk.Button(
            bottom, text="Like", font=FONT_SMALL,
            fg=ACCENT2, bg=CARD_BG, relief="flat", cursor="hand2",
            command=lambda pid=post["id"], lc=like_count: self._on_like(pid, lc)
        )
        like_btn.pack(side="left")

        tag = tk.Label(bottom, text="via Pub-Sub", font=FONT_SMALL,
                       fg=ACCENT, bg=CARD_BG)
        tag.pack(side="right")

        # Scroll to bottom
        self.feed_canvas.update_idletasks()
        self.feed_canvas.yview_moveto(1.0)

    def _on_like(self, post_id, like_label):
        active = self.active_user_var.get()
        post = self.users[active].like(post_id)
        if post:
            like_label.config(text=f"♥  {post['likes']}", fg=ACCENT2)
            self._update_stats()

    def _log_event(self, message, tag=""):
        """Called by broker to append to activity log."""
        def _do():
            self.log_box.config(state="normal")
            if tag in TAG_COLORS:
                # Tag label
                self.log_box.insert("end", f"[{tag}]", tag)
                rest = message[message.index("]") + 1:]  # strip first bracket block
                # re-add the rest cleanly
                rest = message.split(f"[{tag}]", 1)[-1]
                self.log_box.insert("end", rest + "\n", "DIM")
            else:
                self.log_box.insert("end", message + "\n")
            self.log_box.config(state="disabled")
            self.log_box.yview_moveto(1.0)
        self.after(0, _do)

    def _clear_log(self):
        self.log_box.config(state="normal")
        self.log_box.delete("1.0", "end")
        self.log_box.config(state="disabled")

    def _update_stats(self):
        total_posts = len(self.broker.posts)
        total_likes = sum(p["likes"] for p in self.broker.posts)
        self.stats_label.config(
            text=f"Total posts: {total_posts}\n"
                 f"Total likes: {total_likes}\n"
                 f"Active subscribers: {sum(len(v) for v in self.broker.subscriptions.values())}"
        )

    # ── Canvas helpers ─────────────────────────────────────────────────────
    def _on_feed_resize(self, event):
        self.feed_canvas.configure(scrollregion=self.feed_canvas.bbox("all"))

    def _on_canvas_resize(self, event):
        self.feed_canvas.itemconfig(self.feed_canvas_window, width=event.width)

    def _on_mousewheel(self, event):
        self.feed_canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")

    # ── Helpers ────────────────────────────────────────────────────────────
    def _add_hover(self, widget, hover_bg, normal_bg):
        widget.bind("<Enter>", lambda e: widget.config(bg=hover_bg, fg=BG))
        widget.bind("<Leave>", lambda e: widget.config(
            bg=normal_bg,
            fg=BG if widget.cget("bg") != CARD_BG else TEXT
        ))

    def _flash_btn(self, btn, color, text=None):
        orig = btn.cget("bg")
        orig_text = btn.cget("text")
        if text:
            btn.config(bg=color, text=text)
        else:
            btn.config(bg=color)
        self.after(800, lambda: btn.config(bg=orig, text=orig_text))

    # ── Demo posts on startup ──────────────────────────────────────────────
    def _run_demo_posts(self):
        """Post a few messages after startup to populate the feed."""
        demo = [
            ("Alice",   "Just deployed a new distributed system 🚀"),
            ("Bob",     "Request-Response is so satisfying when it just works"),
            ("Charlie", "Anyone else love watching Pub-Sub events propagate?"),
            ("Alice",   "Pro tip: loose coupling > tight coupling always 💡"),
            ("Diana",   "Following this conversation from afar 👀"),
        ]

        def _post_sequence(i=0):
            if i >= len(demo):
                self._update_stats()
                return
            name, content = demo[i]
            self.users[name].post(content)
            self._update_stats()
            self.after(900, lambda: _post_sequence(i + 1))

        self.after(400, _post_sequence)


# ══════════════════════════════════════════════════════════════════════════
if __name__ == "__main__":
    app = SocialSimApp()
    app.mainloop()