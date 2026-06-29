import asyncio
import redis.asyncio as redis
from .dedup import DedupManager
from .database import AsyncSessionLocal
from .schemas import Event
import json
import logging
import backoff
from typing import Optional

logger = logging.getLogger(__name__)

class EventConsumer:
    def __init__(self, redis_url: str, queue_name: str = "events_queue"):
        self.redis = redis.from_url(redis_url, decode_responses=True)
        self.queue_name = queue_name
        self.dedup = DedupManager()
        self.running = True
        self.retry_backoff = 1.0
        
    @backoff.on_exception(
        backoff.expo,
        Exception,
        max_tries=5,
        max_time=60
    )
    async def process_event(self, event_data: str):
        """Process a single event with retry logic"""
        try:
            event_dict = json.loads(event_data)
            event = Event(**event_dict)
            
            async with AsyncSessionLocal() as session:
                is_duplicate, error = await self.dedup.process_event(session, event)
                
                if is_duplicate:
                    logger.info(f"Duplicate processed: {event.topic}:{event.event_id}")
                elif error:
                    logger.error(f"Error processing event: {error}")
                    # Could requeue for retry
                    await self.redis.rpush(f"{self.queue_name}:retry", event_data)
                else:
                    logger.info(f"Event processed: {event.topic}:{event.event_id}")
                    
        except Exception as e:
            logger.error(f"Consumer error: {str(e)}")
            raise
    
    async def consume_loop(self):
        """Main consumer loop with backoff on empty queue"""
        retry_delay = 0.1
        
        while self.running:
            try:
                # Try to get event from main queue
                event_data = await self.redis.rpop(self.queue_name)
                
                if event_data:
                    await self.process_event(event_data)
                    retry_delay = 0.1  # Reset on success
                else:
                    # Check retry queue
                    event_data = await self.redis.rpop(f"{self.queue_name}:retry")
                    if event_data:
                        await self.process_event(event_data)
                    else:
                        await asyncio.sleep(retry_delay)
                        retry_delay = min(retry_delay * 1.5, 5.0)
                        
            except Exception as e:
                logger.error(f"Consumer loop error: {str(e)}")
                await asyncio.sleep(1.0)
    
    async def start(self, workers: int = 3):
        """Start multiple consumer workers"""
        tasks = []
        for i in range(workers):
            task = asyncio.create_task(self.consume_loop())
            tasks.append(task)
            logger.info(f"Started consumer worker {i+1}")
        
        await asyncio.gather(*tasks)
    
    async def stop(self):
        """Stop the consumer gracefully"""
        self.running = False
        await self.redis.close()