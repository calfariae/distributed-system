from fastapi import FastAPI, HTTPException, Depends, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse  # Add this import
from sqlalchemy.ext.asyncio import AsyncSession
from .database import get_db, init_db
from .schemas import Event, EventBatch, StatsResponse
from .dedup import DedupManager
from .consumer import EventConsumer
from .stats import StatsManager
import redis.asyncio as redis
import os
import time
import logging
from contextlib import asynccontextmanager
import asyncio

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

start_time = time.time()
dedup_manager = DedupManager()
stats_manager = StatsManager()

async def wait_for_database():
    from sqlalchemy import text
    from .database import AsyncSessionLocal
    
    for attempt in range(10):
        try:
            async with AsyncSessionLocal() as session:
                await session.execute(text("SELECT 1"))
                logger.info("Database ready")
                return True
        except Exception as e:
            logger.warning(f"DB not ready (attempt {attempt+1}): {e}")
            await asyncio.sleep(2)
    return False

@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting application...")
    
    if not await wait_for_database():
        logger.error("Could not connect to database")
        raise RuntimeError("Database connection failed")
    
    await init_db()
    
    redis_url = os.getenv("REDIS_URL", "redis://broker:6379")
    consumer = EventConsumer(redis_url)
    consumer_task = asyncio.create_task(consumer.start(workers=3))
    app.state.consumer = consumer
    
    logger.info("Application started")
    yield
    
    logger.info("Shutting down...")
    await consumer.stop()
    consumer_task.cancel()

app = FastAPI(title="Distributed Log Aggregator", version="1.0.0", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

@app.post("/publish", status_code=status.HTTP_202_ACCEPTED)
async def publish_event(event: Event, session: AsyncSession = Depends(get_db)):
    try:
        is_duplicate, error = await dedup_manager.process_event(session, event)
        
        if is_duplicate:
            return {"status": "accepted", "event_id": event.event_id, "duplicate": True}
        if error:
            raise HTTPException(status_code=500, detail=error)
        
        # Publish to Redis
        try:
            redis_client = redis.from_url(os.getenv("REDIS_URL", "redis://broker:6379"), decode_responses=True)
            await redis_client.rpush("events_queue", event.model_dump_json())
            await redis_client.close()
        except Exception as e:
            logger.error(f"Redis error: {e}")
            # Continue even if Redis fails - event is already persisted
        
        return {"status": "accepted", "event_id": event.event_id, "duplicate": False}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error publishing event: {str(e)}", exc_info=True)
        return JSONResponse(
            status_code=500,
            content={"detail": str(e)}
        )

@app.post("/publish/batch")
async def publish_batch(batch: EventBatch, session: AsyncSession = Depends(get_db)):
    results = []
    duplicates = 0
    
    try:
        await session.execute("SET TRANSACTION ISOLATION LEVEL SERIALIZABLE")
        for event in batch.events:
            is_duplicate, error = await dedup_manager.process_event(session, event, atomic_batch=False)
            if error:
                raise HTTPException(status_code=500, detail=error)
            results.append({"event_id": event.event_id, "duplicate": is_duplicate})
            if is_duplicate:
                duplicates += 1
        
        await session.commit()
        
        # Publish to Redis
        try:
            redis_client = redis.from_url(os.getenv("REDIS_URL", "redis://broker:6379"), decode_responses=True)
            for event in batch.events:
                await redis_client.rpush("events_queue", event.model_dump_json())
            await redis_client.close()
        except Exception as e:
            logger.error(f"Redis error: {e}")
        
        return {
            "status": "accepted", 
            "batch_size": len(batch.events), 
            "duplicates": duplicates, 
            "results": results
        }
    except HTTPException:
        raise
    except Exception as e:
        await session.rollback()
        logger.error(f"Error publishing batch: {str(e)}")
        return JSONResponse(
            status_code=500,
            content={"detail": str(e)}
        )

@app.get("/events")
async def get_events(topic: str = None, limit: int = 100, offset: int = 0, session: AsyncSession = Depends(get_db)):
    try:
        events = await stats_manager.get_events(session, topic, limit, offset)
        return {"events": events, "total": len(events)}
    except Exception as e:
        logger.error(f"Error getting events: {e}")
        return JSONResponse(
            status_code=500,
            content={"detail": str(e)}
        )

@app.get("/stats")
async def get_stats(session: AsyncSession = Depends(get_db)):
    try:
        stats = await stats_manager.get_stats(session)
        return {
            "total_received": stats.get('total_received', 0),
            "total_unique_processed": stats.get('total_unique_processed', 0),
            "total_duplicate_dropped": stats.get('total_duplicate_dropped', 0),
            "topics": stats.get('topics', {}),
            "uptime_seconds": time.time() - start_time
        }
    except Exception as e:
        logger.error(f"Error getting stats: {e}")
        return JSONResponse(
            status_code=500,
            content={"detail": str(e)}
        )

@app.get("/health")
async def health_check():
    return {"status": "healthy", "uptime_seconds": time.time() - start_time}

@app.get("/ready")
async def readiness_check(session: AsyncSession = Depends(get_db)):
    try:
        await session.execute("SELECT 1")
        return {"status": "ready"}
    except:
        raise HTTPException(status_code=503, detail="Database not ready")