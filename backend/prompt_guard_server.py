"""
Prompt Guard Inference Server

Standalone FastAPI service that loads a prompt injection detection model
and exposes a /classify endpoint.

Supports:
  - Prompt-Guard-86M (v1): 3 labels (BENIGN, INJECTION, JAILBREAK)
  - Llama-Prompt-Guard-2-86M (v2): 2 labels (BENIGN, MALICIOUS)
  - ProtectAI/deberta-v3-base-prompt-injection-v2: 2 labels (SAFE, INJECTION)
  - Any HuggingFace sequence classification model with id2label config

Usage:
    python prompt_guard_server.py [--port 58006] [--model /opt/models/deberta-v3-prompt-injection-v2]
"""

import argparse
import logging
import time
from contextlib import asynccontextmanager
from typing import List, Optional

import torch
import uvicorn
from fastapi import FastAPI
from pydantic import BaseModel, Field

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("prompt_guard")

# Global model/tokenizer
_model = None
_tokenizer = None
_device = None
_label_map = {}  # Populated from model.config.id2label at load time
_num_labels = 0


class ClassifyRequest(BaseModel):
    text: Optional[str] = Field(None, description="Text to classify")
    texts: Optional[List[str]] = Field(None, description="Batch of texts to classify")
    threshold: float = Field(0.5, ge=0.0, le=1.0, description="Threshold for injection/jailbreak")


class ClassifyResult(BaseModel):
    label: str  # BENIGN | INJECTION | JAILBREAK | MALICIOUS
    scores: dict  # e.g. {BENIGN: 0.99, MALICIOUS: 0.01} or {BENIGN: 0.01, INJECTION: 0.95, JAILBREAK: 0.04}
    is_injection: bool  # True if malicious score > threshold
    latency_ms: float


class ClassifyResponse(BaseModel):
    results: List[ClassifyResult]


class HealthResponse(BaseModel):
    status: str
    model: str
    device: str


def _normalize_label(raw_label: str) -> str:
    """Normalize model labels to canonical names.

    v1 (Prompt-Guard-86M): {0: 'BENIGN', 1: 'INJECTION', 2: 'JAILBREAK'} → keep as-is
    v2 (Llama-Prompt-Guard-2-86M): {0: 'LABEL_0', 1: 'LABEL_1'} → BENIGN / MALICIOUS
    ProtectAI: {0: 'SAFE', 1: 'INJECTION'} → BENIGN / INJECTION
    """
    mapping = {
        "LABEL_0": "BENIGN",
        "LABEL_1": "MALICIOUS",
        "SAFE": "BENIGN",       # ProtectAI: SAFE → BENIGN
    }
    return mapping.get(raw_label, raw_label)


def load_model(model_name: str):
    """Load model and tokenizer."""
    global _model, _tokenizer, _device, _label_map, _num_labels

    from transformers import AutoModelForSequenceClassification, AutoTokenizer

    logger.info(f"Loading model: {model_name}")
    start = time.time()

    _tokenizer = AutoTokenizer.from_pretrained(model_name)
    _model = AutoModelForSequenceClassification.from_pretrained(model_name)

    # Build label map from model config
    raw_id2label = _model.config.id2label  # e.g. {0: 'LABEL_0', 1: 'LABEL_1'} or {"0": "LABEL_0", ...}
    _label_map = {int(i): _normalize_label(lbl) for i, lbl in raw_id2label.items()}
    _num_labels = len(_label_map)
    logger.info(f"Label map ({_num_labels} labels): {_label_map}")

    if torch.cuda.is_available():
        _device = torch.device("cuda")
    elif hasattr(torch.backends, "mps") and torch.backends.mps.is_available():
        _device = torch.device("mps")
    else:
        _device = torch.device("cpu")

    _model = _model.to(_device)
    _model.eval()

    elapsed = time.time() - start
    logger.info(f"Model loaded on {_device} in {elapsed:.1f}s")


def classify_texts(texts: List[str], threshold: float = 0.5) -> List[ClassifyResult]:
    """Classify a batch of texts."""
    results = []
    for text in texts:
        start = time.time()
        inputs = _tokenizer(
            text,
            return_tensors="pt",
            truncation=True,
            max_length=512,
            padding=True,
        ).to(_device)

        with torch.no_grad():
            logits = _model(**inputs).logits
            probs = torch.softmax(logits, dim=-1)[0]

        scores = {_label_map[i]: round(probs[i].item(), 4) for i in range(_num_labels)}
        label = _label_map[probs.argmax().item()]

        # Compute malicious score:
        # v2 (2-label): MALICIOUS score
        # v1 (3-label): INJECTION + JAILBREAK scores
        malicious_score = scores.get("MALICIOUS", 0) + scores.get("INJECTION", 0) + scores.get("JAILBREAK", 0)
        is_injection = malicious_score > threshold

        latency_ms = (time.time() - start) * 1000
        results.append(ClassifyResult(
            label=label,
            scores=scores,
            is_injection=is_injection,
            latency_ms=round(latency_ms, 2),
        ))

    return results


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Model is loaded before uvicorn starts (in main)
    yield


app = FastAPI(title="Prompt Guard Server", lifespan=lifespan)


@app.get("/health", response_model=HealthResponse)
async def health():
    return HealthResponse(
        status="ok" if _model is not None else "not_loaded",
        model=str(getattr(_model, "name_or_path", "unknown")),
        device=str(_device),
    )


@app.post("/classify", response_model=ClassifyResponse)
async def classify(req: ClassifyRequest):
    if not req.texts and not req.text:
        from fastapi import HTTPException
        raise HTTPException(status_code=400, detail="Either 'text' or 'texts' must be provided")
    texts = req.texts if req.texts else [req.text]
    results = classify_texts(texts, threshold=req.threshold)
    return ClassifyResponse(results=results)


def main():
    parser = argparse.ArgumentParser(description="Prompt Guard Inference Server")
    parser.add_argument("--port", type=int, default=58006, help="Server port")
    parser.add_argument("--host", type=str, default="0.0.0.0", help="Server host")
    parser.add_argument("--model", type=str, default="meta-llama/Llama-Prompt-Guard-2-86M",
                        help="HuggingFace model name or local path")
    parser.add_argument("--workers", type=int, default=1, help="Uvicorn workers")
    args = parser.parse_args()

    load_model(args.model)
    uvicorn.run(app, host=args.host, port=args.port, workers=args.workers)


if __name__ == "__main__":
    main()
