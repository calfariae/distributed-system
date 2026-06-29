import time
from collections import defaultdict
from typing import Dict, List

class MetricsCollector:
    def __init__(self):
        self.metrics: Dict[str, List[float]] = defaultdict(list)
        self.start_times: Dict[str, float] = {}
    
    def start_operation(self, operation: str):
        self.start_times[operation] = time.time()
    
    def end_operation(self, operation: str):
        if operation in self.start_times:
            duration = time.time() - self.start_times[operation]
            self.metrics[f"{operation}_latency"].append(duration)
            del self.start_times[operation]
    
    def record_value(self, metric_name: str, value: float):
        self.metrics[metric_name].append(value)
    
    def get_stats(self, metric_name: str) -> dict:
        values = self.metrics.get(metric_name, [])
        if not values:
            return {}
        
        return {
            "count": len(values),
            "avg": sum(values) / len(values),
            "min": min(values),
            "max": max(values),
            "last": values[-1]
        }

metrics = MetricsCollector()