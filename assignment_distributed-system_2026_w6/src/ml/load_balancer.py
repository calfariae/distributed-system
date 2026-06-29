import numpy as np
import logging
from typing import List, Dict, Optional
from sklearn.ensemble import RandomForestRegressor, IsolationForest
from sklearn.preprocessing import StandardScaler
import joblib
import os

logger = logging.getLogger(__name__)

class AdaptiveLoadBalancer:
    """ML-based adaptive load balancing"""
    def __init__(self, model_dir: str = "/tmp/ml_models"):
        self.model_dir = model_dir
        os.makedirs(model_dir, exist_ok=True)
        
        self.load_predictor = RandomForestRegressor(n_estimators=20, max_depth=5)
        self.anomaly_detector = IsolationForest(contamination=0.1, random_state=42)
        self.scaler = StandardScaler()
        
        self.is_trained = False
        self.prediction_history: List[Dict] = []
        
        # Try to load existing models
        self._load_models()
    
    def train(self, X: List[List[float]], y_load: List[float]):
        """Train the load prediction model"""
        if len(X) < 10:
            logger.warning("Not enough data for training")
            return
        
        X = np.array(X)
        y_load = np.array(y_load)
        
        # Fit scaler
        X_scaled = self.scaler.fit_transform(X)
        
        # Train load predictor
        self.load_predictor.fit(X_scaled, y_load)
        
        # Train anomaly detector
        self.anomaly_detector.fit(X_scaled)
        
        self.is_trained = True
        logger.info(f"Models trained on {len(X)} samples")
        
        # Save models
        self._save_models()
    
    def predict_load(self, features: List[float]) -> float:
        """Predict future load for a node"""
        if not self.is_trained:
            return 0.5  # Default prediction
        
        X = np.array([features])
        X_scaled = self.scaler.transform(X)
        return self.load_predictor.predict(X_scaled)[0]
    
    def detect_anomaly(self, features: List[float]) -> bool:
        """Detect if current metrics are anomalous"""
        if not self.is_trained:
            return False
        
        X = np.array([features])
        X_scaled = self.scaler.transform(X)
        prediction = self.anomaly_detector.predict(X_scaled)[0]
        return prediction == -1  # -1 means anomaly
    
    def get_best_node(self, nodes_features: Dict[str, List[float]]) -> Optional[str]:
        """Select the best node for routing based on ML predictions"""
        if not self.is_trained or not nodes_features:
            return None
        
        best_node = None
        best_score = float('inf')
        
        for node_id, features in nodes_features.items():
            # Check for anomalies
            if self.detect_anomaly(features):
                logger.warning(f"Node {node_id} shows anomalous behavior, skipping")
                continue
            
            # Predict future load
            predicted_load = self.predict_load(features)
            
            # Score based on current features and predicted load
            current_load = features[4] if len(features) > 4 else 0  # request_rate
            queue_depth = features[2] if len(features) > 2 else 0
            
            score = predicted_load * 0.5 + current_load * 0.3 + queue_depth * 0.2
            
            if score < best_score:
                best_score = score
                best_node = node_id
        
        return best_node
    
    def _save_models(self):
        """Save models to disk"""
        try:
            joblib.dump(self.load_predictor, os.path.join(self.model_dir, "load_predictor.pkl"))
            joblib.dump(self.anomaly_detector, os.path.join(self.model_dir, "anomaly_detector.pkl"))
            joblib.dump(self.scaler, os.path.join(self.model_dir, "scaler.pkl"))
        except Exception as e:
            logger.error(f"Error saving models: {e}")
    
    def _load_models(self):
        """Load models from disk"""
        try:
            lp_path = os.path.join(self.model_dir, "load_predictor.pkl")
            ad_path = os.path.join(self.model_dir, "anomaly_detector.pkl")
            sc_path = os.path.join(self.model_dir, "scaler.pkl")
            
            if all(os.path.exists(p) for p in [lp_path, ad_path, sc_path]):
                self.load_predictor = joblib.load(lp_path)
                self.anomaly_detector = joblib.load(ad_path)
                self.scaler = joblib.load(sc_path)
                self.is_trained = True
                logger.info("Loaded existing ML models")
        except Exception as e:
            logger.error(f"Error loading models: {e}")