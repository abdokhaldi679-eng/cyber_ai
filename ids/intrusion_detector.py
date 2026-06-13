import numpy as np
from sklearn.ensemble import IsolationForest, RandomForestClassifier
from sklearn.preprocessing import StandardScaler
import joblib
import os
from utils.helpers import info, success, error


class IntrusionDetector:
    def __init__(self, model_path=None):
        self.model = None
        self.scaler = StandardScaler()
        self.model_path = model_path
        self.feature_names = [
            "duration", "protocol_type", "src_bytes", "dst_bytes",
            "count", "same_srv_rate", "diff_srv_rate",
            "dst_host_count", "dst_host_srv_count",
            "dst_host_same_srv_rate", "dst_host_diff_srv_rate",
            "flag", "land", "urgent", "num_failed_logins",
            "logged_in", "root_shell", "num_file_creations",
            "num_shells", "num_access_files", "is_guest_login"
        ]

    def train(self, X, y=None):
        info("Entraînement du modèle de détection d'intrusion...")
        if y is not None:
            self.model = RandomForestClassifier(
                n_estimators=100,
                max_depth=20,
                random_state=42,
                n_jobs=-1
            )
            X_scaled = self.scaler.fit_transform(X)
            self.model.fit(X_scaled, y)
            success(f"Modèle supervisé entraîné sur {len(X)} échantillons")
        else:
            self.model = IsolationForest(
                n_estimators=100,
                contamination=0.1,
                random_state=42
            )
            X_scaled = self.scaler.fit_transform(X)
            self.model.fit(X_scaled)
            success(f"Modèle non supervisé entraîné sur {len(X)} échantillons")

    def predict(self, X):
        if self.model is None:
            error("Modèle non entraîné")
            return None
        X_scaled = self.scaler.transform(X)
        if isinstance(self.model, IsolationForest):
            preds = self.model.predict(X_scaled)
            return [1 if p == -1 else 0 for p in preds]
        return self.model.predict(X_scaled).tolist()

    def predict_proba(self, X):
        if self.model is None:
            error("Modèle non entraîné")
            return None
        X_scaled = self.scaler.transform(X)
        if hasattr(self.model, "predict_proba"):
            return self.model.predict_proba(X_scaled).tolist()
        return None

    def analyze_connection(self, features):
        if self.model is None:
            self._load_or_create_default()
        pred = self.predict([features])[0]
        if pred == 1:
            proba = self.predict_proba([features])
            confidence = max(proba[0]) if proba else 0.5
            return {"threat": True, "confidence": confidence}
        return {"threat": False, "confidence": 0.0}

    def _load_or_create_default(self):
        model_dir = os.path.join(os.path.dirname(__file__), "..", "models")
        os.makedirs(model_dir, exist_ok=True)
        model_file = os.path.join(model_dir, "ids_model.joblib")
        if os.path.exists(model_file):
            self.load(model_file)
            info("Modèle IDS chargé depuis le disque")
        else:
            info("Création d'un modèle IDS par défaut...")
            np.random.seed(42)
            n_normal = 500
            n_anomaly = 50
            normal = np.random.randn(n_normal, 5) * 0.5 + np.array([10, 3, 500, 300, 50])
            anomaly = np.random.randn(n_anomaly, 5) * 2.0 + np.array([100, 0, 5000, 100, 5])
            X = np.vstack([normal, anomaly])
            y = np.array([0] * n_normal + [1] * n_anomaly)
            self.train(X, y)
            self.save(model_file)

    def save(self, path):
        joblib.dump({"model": self.model, "scaler": self.scaler}, path)
        success(f"Modèle IDS sauvegardé: {path}")

    def load(self, path):
        data = joblib.load(path)
        self.model = data["model"]
        self.scaler = data["scaler"]
        success(f"Modèle IDS chargé: {path}")
