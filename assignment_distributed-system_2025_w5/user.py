"""
user.py - Represents a social media user node.
Each user can post, follow others, and maintain a local feed.
"""


class User:
    def __init__(self, name, broker):
        self.name = name
        self.broker = broker
        self.feed = []          # received posts from followed users
        self.own_posts = []     # posts authored by this user
        self.following = []     # list of usernames this user follows
        self.feed_update_cb = None  # GUI callback when feed updates

    # ──────────────────────────────────────────────
    # Follow (Pub-Sub subscription)
    # ──────────────────────────────────────────────
    def follow(self, other_user):
        """Subscribe to another user's posts via the broker."""
        topic = f"{other_user.name.lower()}_posts"
        self.following.append(other_user.name)
        self.broker.subscribe(topic, self.name, self._on_receive_post)

    # ──────────────────────────────────────────────
    # Post (Request-Response)
    # ──────────────────────────────────────────────
    def post(self, content):
        """Send a post via Request-Response to the broker."""
        post = self.broker.receive_post(self.name, content)
        self.own_posts.append(post)
        return post

    # ──────────────────────────────────────────────
    # Like (Request-Response)
    # ──────────────────────────────────────────────
    def like(self, post_id):
        """Send a like request to the broker."""
        return self.broker.like_post(post_id, self.name)

    # ──────────────────────────────────────────────
    # Pub-Sub callback (called by broker on notify)
    # ──────────────────────────────────────────────
    def _on_receive_post(self, post):
        """Triggered automatically when a followed user publishes."""
        self.feed.append(post)
        if self.feed_update_cb:
            self.feed_update_cb(post)