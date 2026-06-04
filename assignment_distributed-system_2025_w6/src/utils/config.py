import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    NODE_ID = os.getenv("NODE_ID", "node1")
    NODE_HOST = os.getenv("NODE_HOST", "0.0.0.0")
    NODE_PORT = int(os.getenv("NODE_PORT", "8000"))
    
    REDIS_HOST = os.getenv("REDIS_HOST", "localhost")
    REDIS_PORT = int(os.getenv("REDIS_PORT", "6379"))
    
    CLUSTER_NODES = os.getenv("CLUSTER_NODES", "").split(",")
    LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")

config = Config()