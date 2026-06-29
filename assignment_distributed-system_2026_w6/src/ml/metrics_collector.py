import time
import json
import os
from typing import Dict, List
from collections import deque
import logging

logger = logging.getLogger(__name__)

class MetricsCollector:
    """Collects system metrics for ML training"""
    def __init__(self, max_history: int = 1000):
        self.max_history = max_history
        self.metrics_history: deque = deque(maxlen=max_history)
        self.persistence_dir = "/tmp/ml_metrics"
        os.makedirs(self.persistence_dir, exist_ok=True)
    
    def collect_node_metrics(self, node_id: str, metrics: Dict) -> Dict:
        """Collect metrics from a node"""
        data = {
            "timestamp": time.time(),
            "node_id": node_id,
            **metrics
        }
        self.metrics_history.append(data)
        return data
    
    def get_recent_metrics(self, n: int = 100) -> List[Dict]:
        """Get the most recent metrics"""
        return list(self.metrics_history)[-n:]
    
    def get_features(self) -> List[List[float]]:
        """Extract features for ML model"""
        features = []
        for m in self.metrics_history:
            features.append([
                m.get("cpu_usage", 0),
                m.get("memory_usage", 0),
                m.get("queue_depth", 0),
                m.get("lock_contention", 0),
                m.get("request_rate", 0),
                m.get("cache_hit_rate", 0),
                m.get("active_connections", 0),
            ])
        return features
    
    def save(self):
        """Persist metrics to disk"""
        filename = os.path.join(self.persistence_dir, "metrics.json")
        with open(filename, 'w') as f:
            json.dump(list(self.metrics_history), f)
    
    def load(self):
        """Load metrics from disk"""
        filename = os.path.join(self.persistence_dir, "metrics.json")
        if os.path.exists(filename):
            with open(filename, 'r') as f:
                data = json.load(f)
                self.metrics_history = deque(data, maxlen=self.max_history)