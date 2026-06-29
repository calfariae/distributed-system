import asyncio
import aiohttp
import json
import random
import uuid
from datetime import datetime, timezone
from typing import List, Dict, Any
import logging
import time
import os

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class EventPublisher:
    def __init__(self, target_url: str, duplicate_rate: float = 0.3):
        self.target_url = target_url
        self.duplicate_rate = duplicate_rate
        self.event_cache: List[Dict] = []  # Store events for duplication
        self.event_ids: List[str] = []  # Track all event IDs
        self.stats = {
            "sent": 0,
            "duplicates_sent": 0,
            "errors": 0,
            "unique_sent": 0
        }
        self.start_time = time.time()
    
    async def publish_event(self, session: aiohttp.ClientSession, event_data: Dict):
        """Publish event with retry logic"""
        try:
            async with session.post(
                f"{self.target_url}/publish",
                json=event_data,
                timeout=aiohttp.ClientTimeout(total=10)
            ) as response:
                if response.status in [200, 202]:
                    result = await response.json()
                    is_duplicate = result.get('duplicate', False)
                    if is_duplicate:
                        logger.info(f"✅ DUPLICATE detected by server: {event_data.get('event_id')}")
                    else:
                        logger.info(f"Published event {event_data.get('event_id')}, duplicate: {is_duplicate}")
                    return True, is_duplicate
                else:
                    error_text = await response.text()
                    logger.error(f"Failed to publish: {response.status} - {error_text}")
                    return False, False
        except aiohttp.ClientError as e:
            logger.error(f"Client error: {e}")
            return False, False
        except Exception as e:
            logger.error(f"Error publishing event: {e}")
            return False, False
    
    def generate_event(self, topic: str, index: int) -> Dict:
        """Generate a single event with controlled duplication"""
        # Check if we should create a duplicate
        should_duplicate = (
            self.event_ids and  # We have events to duplicate
            random.random() < self.duplicate_rate and
            len(self.event_ids) > 0
        )
        
        if should_duplicate:
            # Select a random existing event ID to duplicate
            duplicate_id = random.choice(self.event_ids)
            logger.info(f"🔄 Creating duplicate of event: {duplicate_id}")
            
            # Find the original event in cache
            original_event = None
            for event in self.event_cache:
                if event['event_id'] == duplicate_id:
                    original_event = event.copy()
                    break
            
            if original_event:
                # Create duplicate event
                duplicate_event = {
                    "topic": original_event['topic'],
                    "event_id": original_event['event_id'],  # Same ID!
                    "source": "publisher",
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "payload": {
                        "data": f"DUPLICATE of {original_event['event_id']} at {datetime.now().isoformat()}",
                        "random": random.randint(1, 1000),
                        "index": index,
                        "is_duplicate": True,
                        "original_index": original_event['payload']['index']
                    }
                }
                return duplicate_event
        
        # Generate new unique event
        event_id = str(uuid.uuid4())
        event = {
            "topic": topic,
            "event_id": event_id,
            "source": "publisher",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "payload": {
                "data": f"Event data {datetime.now().isoformat()}",
                "random": random.randint(1, 1000),
                "index": index,
                "is_duplicate": False
            }
        }
        
        # Cache for future duplicates
        self.event_cache.append(event.copy())
        self.event_ids.append(event_id)
        
        return event
    
    async def run_continuous(
        self, 
        topics: List[str], 
        events_per_second: int = 20,
        duration_seconds: int = 120
    ):
        """Run continuous event generation and publishing"""
        async with aiohttp.ClientSession() as session:
            end_time = time.time() + duration_seconds
            event_count = 0
            total_events_target = 20000
            
            logger.info(f"Starting event generation. Target: {total_events_target} events")
            logger.info(f"Duplicate rate: {self.duplicate_rate*100:.0f}%")
            
            # Warm up - generate some unique events first
            logger.info("Warming up with unique events...")
            for i in range(20):
                for topic in topics[:1]:  # Just use first topic for warmup
                    event = self.generate_event(topic, event_count)
                    success, is_dup = await self.publish_event(session, event)
                    if success:
                        self.stats["sent"] += 1
                        if is_dup:
                            self.stats["duplicates_sent"] += 1
                        else:
                            self.stats["unique_sent"] += 1
                    event_count += 1
                    await asyncio.sleep(0.1)
            
            logger.info(f"Warmup complete. Cache size: {len(self.event_ids)} events")
            
            # Main loop
            while time.time() < end_time and event_count < total_events_target:
                for topic in topics:
                    event = self.generate_event(topic, event_count)
                    success, is_dup = await self.publish_event(session, event)
                    
                    if success:
                        self.stats["sent"] += 1
                        if is_dup:
                            self.stats["duplicates_sent"] += 1
                            logger.info(f"📊 Server confirmed duplicate: {event['event_id']}")
                        else:
                            self.stats["unique_sent"] += 1
                    else:
                        self.stats["errors"] += 1
                    
                    event_count += 1
                    
                    # Rate limiting
                    if event_count % events_per_second == 0:
                        await asyncio.sleep(1)
                    
                    # Print progress every 1000 events
                    if event_count % 1000 == 0:
                        logger.info(f"Progress: {event_count}/{total_events_target} events sent")
                        logger.info(f"  Unique: {self.stats['unique_sent']}, Duplicates: {self.stats['duplicates_sent']}")
                    
                    if event_count >= total_events_target:
                        break
            
            await self.print_stats()
    
    async def print_stats(self):
        """Print publishing statistics"""
        elapsed = time.time() - self.start_time
        logger.info("=" * 60)
        logger.info("📊 PUBLISHER STATISTICS")
        logger.info("=" * 60)
        logger.info(f"Total events sent: {self.stats['sent']}")
        logger.info(f"Unique events: {self.stats['unique_sent']}")
        logger.info(f"Duplicate events sent: {self.stats['duplicates_sent']}")
        logger.info(f"Errors: {self.stats['errors']}")
        logger.info(f"Elapsed time: {elapsed:.2f}s")
        if elapsed > 0:
            logger.info(f"Throughput: {self.stats['sent'] / elapsed:.2f} events/sec")
            if self.stats['sent'] > 0:
                duplicate_percentage = (self.stats['duplicates_sent'] / self.stats['sent']) * 100
                logger.info(f"📈 Duplicate rate sent: {duplicate_percentage:.2f}%")
        logger.info("=" * 60)

async def main():
    target_url = os.getenv("TARGET_URL", "http://aggregator:8080")
    duplicate_rate = float(os.getenv("DUPLICATE_RATE", "0.3"))
    events_per_second = int(os.getenv("EVENTS_PER_SECOND", "20"))
    duration = int(os.getenv("DURATION_SECONDS", "120"))
    
    topics = ["system.logs", "app.events", "user.actions", "performance.metrics"]
    
    publisher = EventPublisher(target_url, duplicate_rate)
    logger.info(f"🚀 Starting publisher with {duplicate_rate*100:.0f}% duplicate rate")
    logger.info(f"Target: {target_url}")
    logger.info(f"Topics: {topics}")
    
    try:
        await publisher.run_continuous(
            topics=topics,
            events_per_second=events_per_second,
            duration_seconds=duration
        )
    except KeyboardInterrupt:
        logger.info("Publisher stopped by user")

if __name__ == "__main__":
    asyncio.run(main())