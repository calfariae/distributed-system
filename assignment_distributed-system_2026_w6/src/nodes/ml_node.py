import asyncio
import json
import logging
import time
import random
from typing import Dict, List
from aiohttp import web

from src.nodes.base_node import BaseNode
from src.ml.metrics_collector import MetricsCollector
from src.ml.load_balancer import AdaptiveLoadBalancer
from src.ml.predictive_scaler import PredictiveScaler

logger = logging.getLogger(__name__)

class MLNode(BaseNode):
    """Node with ML-based optimization"""
    def __init__(self, node_id: str, host: str, port: int, peers: List[str]):
        super().__init__(node_id, host, port)
        self.peers = peers
        
        # ML components
        self.metrics_collector = MetricsCollector()
        self.load_balancer = AdaptiveLoadBalancer()
        self.predictive_scaler = PredictiveScaler()
        
        # Simulated metrics
        self.cpu_usage = 0.0
        self.memory_usage = 0.0
        self.request_rate = 0.0
        self.active_connections = 0
        
        # Training data
        self.load_labels: List[float] = []
    
    def setup_routes(self, app: web.Application):
        """Setup routes"""
        app.router.add_post('/health', self.handle_health)
        app.router.add_post('/ml/metrics', self.handle_metrics)
        app.router.add_post('/ml/predict', self.handle_predict)
        app.router.add_post('/ml/train', self.handle_train)
        app.router.add_get('/ml/status', self.handle_ml_status)
        app.router.add_post('/ml/anomaly', self.handle_anomaly_check)
    
    async def start(self):
        """Start ML node"""
        await super().start()
        
        # Start background tasks
        asyncio.create_task(self.metrics_simulation())
        asyncio.create_task(self.periodic_training())
        
        logger.info(f"ML Node started on {self.host}:{self.port}")
    
    async def metrics_simulation(self):
        """Simulate metrics collection"""
        while self.is_running:
            # Simulate realistic metrics
            self.cpu_usage = min(1.0, max(0.1, random.gauss(0.5, 0.2)))
            self.memory_usage = min(1.0, max(0.2, random.gauss(0.6, 0.15)))
            self.request_rate = random.randint(10, 100)
            self.active_connections = random.randint(1, 50)
            
            # Simulated metrics from other components
            node_metrics = {
                "cpu_usage": self.cpu_usage,
                "memory_usage": self.memory_usage,
                "queue_depth": random.randint(0, 20),
                "lock_contention": random.random() * 0.3,
                "request_rate": self.request_rate,
                "cache_hit_rate": random.uniform(0.7, 0.99),
                "active_connections": self.active_connections,
            }
            
            # Collect metrics
            self.metrics_collector.collect_node_metrics(self.node_id, node_metrics)
            
            # Add to training data
            actual_load = self.cpu_usage * 0.4 + self.request_rate / 100 * 0.3 + self.active_connections / 50 * 0.3
            self.load_labels.append(actual_load)
            
            # Traffic data for predictive scaling
            self.predictive_scaler.add_traffic_data(self.request_rate)
            
            await asyncio.sleep(5)
    
    async def periodic_training(self):
        """Periodically train ML models"""
        await asyncio.sleep(30)  # Initial delay
        
        while self.is_running:
            features = self.metrics_collector.get_features()
            
            if len(features) >= 10 and len(self.load_labels) >= 10:
                # Trim labels to match features
                labels = self.load_labels[-len(features):]
                self.load_balancer.train(features, labels)
                logger.info(f"ML models trained with {len(features)} samples")
            
            await asyncio.sleep(60)
    
    async def handle_metrics(self, request: web.Request) -> web.Response:
        """Report current metrics"""
        recent = self.metrics_collector.get_recent_metrics(5)
        
        return web.Response(
            text=json.dumps({
                "node_id": self.node_id,
                "current": {
                    "cpu_usage": self.cpu_usage,
                    "memory_usage": self.memory_usage,
                    "request_rate": self.request_rate,
                    "active_connections": self.active_connections,
                },
                "recent_history": recent,
                "ml_trained": self.load_balancer.is_trained
            }),
            content_type="application/json"
        )
    
    async def handle_predict(self, request: web.Request) -> web.Response:
        """Predict best node for routing"""
        data = await request.json()
        nodes_features = data.get("nodes_features", {})
        
        if not nodes_features:
            return web.Response(
                text=json.dumps({"error": "nodes_features required"}),
                status=400,
                content_type="application/json"
            )
        
        best_node = self.load_balancer.get_best_node(nodes_features)
        
        return web.Response(
            text=json.dumps({
                "best_node": best_node,
                "ml_trained": self.load_balancer.is_trained
            }),
            content_type="application/json"
        )
    
    async def handle_train(self, request: web.Request) -> web.Response:
        """Trigger model training"""
        features = self.metrics_collector.get_features()
        
        if len(features) >= 10 and len(self.load_labels) >= 10:
            labels = self.load_labels[-len(features):]
            self.load_balancer.train(features, labels)
            
            return web.Response(
                text=json.dumps({
                    "trained": True,
                    "samples": len(features)
                }),
                content_type="application/json"
            )
        
        return web.Response(
            text=json.dumps({
                "trained": False,
                "error": f"Need at least 10 samples, have {len(features)}"
            }),
            content_type="application/json"
        )
    
    async def handle_ml_status(self, request: web.Request) -> web.Response:
        """Get ML system status"""
        scaling_rec = self.predictive_scaler.get_scaling_recommendation(
            current_nodes=len(self.peers) + 1
        )
        
        return web.Response(
            text=json.dumps({
                "node_id": self.node_id,
                "ml_trained": self.load_balancer.is_trained,
                "metrics_count": len(self.metrics_collector.metrics_history),
                "predicted_load": self.predictive_scaler.predict_future_load(),
                "scaling_recommendation": scaling_rec["action"],
                "recommended_nodes": scaling_rec["recommended_nodes"]
            }),
            content_type="application/json"
        )
    
    async def handle_anomaly_check(self, request: web.Request) -> web.Response:
        """Check if current metrics are anomalous"""
        data = await request.json()
        features = data.get("features", [
            self.cpu_usage,
            self.memory_usage,
            0,  # queue_depth
            0,  # lock_contention
            self.request_rate,
            0,  # cache_hit_rate
            self.active_connections,
        ])
        
        is_anomaly = self.load_balancer.detect_anomaly(features) if self.load_balancer.is_trained else False
        
        return web.Response(
            text=json.dumps({
                "is_anomaly": is_anomaly,
                "features": features,
                "ml_trained": self.load_balancer.is_trained
            }),
            content_type="application/json"
        )