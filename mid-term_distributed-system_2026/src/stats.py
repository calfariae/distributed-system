from datetime import datetime, timezone


class StatsCollector:
    def __init__(self):
        self._received: int = 0
        self._unique_processed: int = 0
        self._duplicate_dropped: int = 0
        self._topics: set[str] = set()
        self._startup_time: datetime = datetime.now(timezone.utc)

    def increment_received(self) -> None:
        self._received += 1

    def increment_unique(self) -> None:
        self._unique_processed += 1

    def increment_duplicate(self) -> None:
        self._duplicate_dropped += 1

    def add_topic(self, topic: str) -> None:
        self._topics.add(topic)

    def snapshot(self) -> dict:
        uptime_seconds = (
            datetime.now(timezone.utc) - self._startup_time
        ).total_seconds()

        return {
            "received": self._received,
            "unique_processed": self._unique_processed,
            "duplicate_dropped": self._duplicate_dropped,
            "topics": sorted(self._topics),
            "uptime_seconds": round(uptime_seconds, 2),
        }