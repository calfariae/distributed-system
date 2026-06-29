import asyncio
import logging
import time
from typing import Dict, List
from collections import deque
import numpy as np

logger = logging.getLogger(__name__)

class PredictiveScaler:
    """Predictive scaling based on traffic patterns"""
    def __init__(self, window_size: int = 50):
        self.window_size = window_size
        self.traffic_history: deque = deque(maxlen=window_size)
        self.scaling_recommendations: List[Dict] = []
    
    def add_traffic_data(self, request_rate: float, timestamp: float = None):
        """Add traffic data point"""
        self.traffic_history.append({
            "timestamp": timestamp or time.time(),
            "request_rate": request_rate
        })
    
    def predict_future_load(self, minutes_ahead: int = 5) -> float:
        """Predict future load using simple exponential smoothing"""
        if len(self.traffic_history) < 5:
            return 0
        
        # Simple prediction using recent trend
        recent = list(self.traffic_history)[-10:]
        rates = [d["request_rate"] for d in recent]
        
        if len(rates) >= 2:
            # Linear trend
            x = np.arange(len(rates))
            z = np.polyfit(x, rates, 1)
            trend = z[0]  # Slope
            
            # Predict future
            last_rate = rates[-1]
            predicted = last_rate + trend * minutes_ahead
            return max(0, predicted)
        
        return np.mean(rates)
    
    def get_scaling_recommendation(self, current_nodes: int, max_nodes: int = 10) -> Dict:
        """Get scaling recommendation"""
        predicted_load = self.predict_future_load()
        
        # Simple threshold-based recommendation
        if predicted_load > 0.8 * current_nodes:
            action = "scale_up"
            recommended_nodes = min(current_nodes + 1, max_nodes)
        elif predicted_load < 0.3 * current_nodes and current_nodes > 1:
            action = "scale_down"
            recommended_nodes = max(current_nodes - 1, 1)
        else:
            action = "maintain"
            recommended_nodes = current_nodes
        
        recommendation = {
            "timestamp": time.time(),
            "current_nodes": current_nodes,
            "predicted_load": predicted_load,
            "action": action,
            "recommended_nodes": recommended_nodes
        }
        
        self.scaling_recommendations.append(recommendation)
        return recommendation