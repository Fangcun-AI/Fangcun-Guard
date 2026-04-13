"""ML Classifier - bge-m3 embedding + MLP for dimension classification.

Pure NumPy inference at runtime. No PyTorch dependency needed.
Loads classifier_weights.json exported by training/train_classifier.py.
"""

import json
import logging
from pathlib import Path
from typing import Dict, Optional, Tuple

import numpy as np

logger = logging.getLogger("fangcunguard_router")


class MLClassifier:
    """Lightweight MLP classifier for safety dimension routing.

    Architecture: bge-m3 (1024d) → ReLU(W1x + b1) → W2x + b2 → softmax → dimension
    Inference time: ~1ms (excluding embedding API call).
    """

    def __init__(self, weights_path: str, embedding_url: str, embedding_key: str, embedding_model: str):
        self._loaded = False
        self._fc1_w = None
        self._fc1_b = None
        self._fc2_w = None
        self._fc2_b = None
        self._idx_to_dim: Dict[int, str] = {}
        self._embedding_url = embedding_url
        self._embedding_key = embedding_key
        self._embedding_model = embedding_model
        self._client = None

        path = Path(weights_path)
        if not path.exists():
            logger.info("ML classifier weights not found, ML routing disabled")
            return

        try:
            with open(path) as f:
                data = json.load(f)
            self._fc1_w = np.array(data["layers"]["fc1_weight"], dtype=np.float32)
            self._fc1_b = np.array(data["layers"]["fc1_bias"], dtype=np.float32)
            self._fc2_w = np.array(data["layers"]["fc2_weight"], dtype=np.float32)
            self._fc2_b = np.array(data["layers"]["fc2_bias"], dtype=np.float32)
            self._idx_to_dim = {int(k): v for k, v in data["dimensions"].items()}
            self._loaded = True
            logger.info(f"ML classifier loaded: {data['input_dim']}→{data['hidden_dim']}→{data['output_dim']}")
        except Exception as e:
            logger.warning(f"Failed to load ML classifier: {e}")

    @property
    def is_available(self) -> bool:
        return self._loaded

    def _get_client(self):
        if self._client is None:
            import httpx
            self._client = httpx.Client(timeout=10.0)
        return self._client

    def classify(self, text: str, min_confidence: float = 0.6) -> Optional[Tuple[str, float]]:
        """Classify text into a safety dimension.

        Returns (dimension_id, confidence) or None if below threshold.
        """
        if not self._loaded:
            return None

        try:
            # Get embedding
            client = self._get_client()
            resp = client.post(
                f"{self._embedding_url}/embeddings",
                json={"input": [text[:512]], "model": self._embedding_model},
                headers={"Authorization": f"Bearer {self._embedding_key}", "Content-Type": "application/json"},
            )
            if resp.status_code != 200:
                return None

            embedding = np.array(resp.json()["data"][0]["embedding"], dtype=np.float32)

            # MLP forward: ReLU(x @ W1^T + b1) @ W2^T + b2
            hidden = np.maximum(0, embedding @ self._fc1_w.T + self._fc1_b)
            logits = hidden @ self._fc2_w.T + self._fc2_b

            # Softmax
            exp_l = np.exp(logits - np.max(logits))
            probs = exp_l / exp_l.sum()

            top_idx = int(np.argmax(probs))
            confidence = float(probs[top_idx])
            dimension = self._idx_to_dim.get(top_idx, "unknown")

            if confidence >= min_confidence:
                return (dimension, confidence)
            return None

        except Exception as e:
            logger.warning(f"ML classifier error: {e}")
            return None
