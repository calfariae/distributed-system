"""
broker.py - Central message broker
Handles both Request-Response and Publish-Subscribe logic.
"""

from collections import defaultdict
import time


class Broker:
    def __init__(self, log_callback=None):
        # Pub-Sub: topic -> list of (subscriber_name, callback)
        self.subscriptions = defaultdict(list)
        # Stored posts (simple in-memory)
        self.posts = []
        # Optional GUI log callback
        self.log_callback = log_callback

    def log(self, tag, message, color=None):
        timestamp = time.strftime("%H:%M:%S")
        entry = f"[{timestamp}] [{tag}] {message}"
        if self.log_callback:
            self.log_callback(entry, tag)
        print(entry)

    # ──────────────────────────────────────────────
    # REQUEST-RESPONSE
    # ──────────────────────────────────────────────
    def receive_post(self, author, content):
        """
        Simulates the REQUEST half:
        User sends a post request to the broker.
        """
        self.log("REQUEST", f"{author} → broker: '{content}'")

        # Process and store
        post = {
            "id": len(self.posts) + 1,
            "author": author,
            "content": content,
            "timestamp": time.strftime("%H:%M:%S"),
            "likes": 0,
        }
        self.posts.append(post)

        # RESPONSE back to the author
        self.log("RESPONSE", f"broker → {author}: Post #{post['id']} confirmed ✓")

        # Trigger Pub-Sub distribution
        self._publish(author, post)

        return post

    # ──────────────────────────────────────────────
    # PUBLISH-SUBSCRIBE
    # ──────────────────────────────────────────────
    def subscribe(self, topic, subscriber_name, callback):
        """Register a user to a topic (e.g. 'alice_posts')."""
        self.subscriptions[topic].append((subscriber_name, callback))
        self.log("SUBSCRIBE", f"{subscriber_name} subscribed to [{topic}]")

    def _publish(self, author, post):
        """
        Simulates the PUBLISH half:
        Broker pushes the post to all topic subscribers.
        """
        topic = f"{author.lower()}_posts"
        subscribers = self.subscriptions.get(topic, [])

        self.log("PUBLISH", f"broker → topic [{topic}] ({len(subscribers)} subscribers)")

        for sub_name, callback in subscribers:
            self.log("NOTIFY", f"[{topic}] → {sub_name} received post #{post['id']}")
            callback(post)

    def like_post(self, post_id, liker):
        """Request-Response: user likes a post."""
        for post in self.posts:
            if post["id"] == post_id:
                post["likes"] += 1
                self.log("REQUEST", f"{liker} liked post #{post_id} by {post['author']}")
                self.log("RESPONSE", f"broker → {liker}: Like recorded ✓ ({post['likes']} total)")
                return post
        return None