"""Persistent vector indexes for tenant knowledge-base Q&A pairs."""

import json
import logging
import pickle
from pathlib import Path
from typing import Any, Dict, List, Optional

import faiss
import numpy as np
from openai import OpenAI
from sqlalchemy.orm import Session

from config import settings
from database.models import KnowledgeBase

logger = logging.getLogger(__name__)
_REQUIRED_FIELDS = ("questionid", "question", "answer")


class KnowledgeBaseStore:
    def __init__(self):
        self.client = None
        self.vector_dimension = settings.embedding_model_dimension
        self.similarity_threshold = settings.embedding_similarity_threshold
        self.max_results = settings.embedding_max_results
        self.storage_path = Path(settings.data_dir) / "knowledge_bases"
        self.storage_path.mkdir(parents=True, exist_ok=True)

    def _get_client(self) -> OpenAI:
        if self.client is None:
            self.client = OpenAI(
                api_key=settings.embedding_api_key,
                base_url=settings.embedding_api_base_url,
            )
        return self.client

    def _get_embeddings(self, texts: List[str]) -> List[List[float]]:
        client = self._get_client()
        return [
            client.embeddings.create(
                input=[text], model=settings.embedding_model_name
            ).data[0].embedding
            for text in texts
        ]

    def parse_jsonl_file(self, file_content: bytes) -> List[Dict[str, str]]:
        try:
            lines = file_content.decode("utf-8").splitlines()
        except UnicodeDecodeError as exc:
            raise ValueError(f"File encoding error: {exc}")
        pairs = []
        for line_number, line in enumerate(lines, 1):
            if not line.strip():
                continue
            try:
                item = json.loads(line)
            except json.JSONDecodeError as exc:
                logger.warning(f"Line {line_number}: invalid JSON - {exc}")
                continue
            if not all(isinstance(item.get(key), str) for key in _REQUIRED_FIELDS):
                logger.warning(f"Line {line_number}: missing or invalid required fields")
                continue
            cleaned = {key: item[key].strip() for key in _REQUIRED_FIELDS}
            if cleaned["question"] and cleaned["answer"]:
                pairs.append(cleaned)
        if not pairs:
            raise ValueError("No valid QA pairs found in the file")
        return pairs

    def create_vector_index(
        self, qa_pairs: List[Dict[str, str]], knowledge_base_id: int
    ) -> str:
        vectors = np.asarray(
            self._get_embeddings([pair["question"] for pair in qa_pairs]),
            dtype=np.float32,
        )
        index = faiss.IndexFlatIP(self.vector_dimension)
        faiss.normalize_L2(vectors)
        index.add(vectors)
        path = self._vector_path(knowledge_base_id)
        self._write_pickle(
            path,
            {
                "index": faiss.serialize_index(index),
                "qa_pairs": qa_pairs,
                "vector_dimension": self.vector_dimension,
                "total_pairs": len(qa_pairs),
            },
        )
        return str(path)

    def search_similar_questions(
        self,
        query: str,
        knowledge_base_id: int,
        top_k: Optional[int] = None,
        similarity_threshold: Optional[float] = None,
        db: Optional[Session] = None,
    ) -> List[Dict[str, Any]]:
        path = self._vector_path(knowledge_base_id)
        if not path.exists():
            return []
        try:
            data = self._read_pickle(path)
            pairs = data["qa_pairs"]
            threshold = self._threshold(
                knowledge_base_id, similarity_threshold, db
            )
            vector = np.asarray(self._get_embeddings([query]), dtype=np.float32)
            faiss.normalize_L2(vector)
            scores, indices = faiss.deserialize_index(data["index"]).search(
                vector, min(top_k or self.max_results, len(pairs))
            )
            results = []
            for rank, (score, index) in enumerate(zip(scores[0], indices[0]), 1):
                if index >= 0 and score >= threshold:
                    results.append(
                        {
                            **pairs[index],
                            "similarity_score": float(score),
                            "rank": rank,
                        }
                    )
            return results
        except Exception as exc:
            logger.error(f"Failed to search similar questions: {exc}")
            return []

    def save_original_file(
        self,
        file_content: bytes,
        knowledge_base_id: int,
        original_filename: str = None,
    ) -> str:
        filename = (
            Path(original_filename).name if original_filename else "original.jsonl"
        )
        path = self.storage_path / f"kb_{knowledge_base_id}_{filename}"
        path.write_bytes(file_content)
        return str(path)

    def delete_knowledge_base_files(self, knowledge_base_id: int) -> None:
        for path in self.storage_path.glob(f"kb_{knowledge_base_id}_*"):
            if path.is_file():
                path.unlink()

    def get_file_info(self, knowledge_base_id: int) -> Dict[str, Any]:
        originals = sorted(
            path
            for path in self.storage_path.glob(f"kb_{knowledge_base_id}_*.jsonl")
            if path.is_file()
        )
        vector = self._vector_path(knowledge_base_id)
        info = {
            "original_file_exists": bool(originals),
            "vector_file_exists": vector.exists(),
            "original_file_size": originals[0].stat().st_size if originals else 0,
            "vector_file_size": vector.stat().st_size if vector.exists() else 0,
            "total_qa_pairs": 0,
        }
        if vector.exists():
            try:
                info["total_qa_pairs"] = self._read_pickle(vector).get(
                    "total_pairs", 0
                )
            except Exception as exc:
                logger.error(f"Failed to read vector metadata: {exc}")
        return info

    def _threshold(
        self,
        knowledge_base_id: int,
        override: Optional[float],
        db: Optional[Session],
    ) -> float:
        if override is not None:
            return override
        if db is not None:
            record = db.query(KnowledgeBase).filter(
                KnowledgeBase.id == knowledge_base_id
            ).first()
            if record and record.similarity_threshold is not None:
                return record.similarity_threshold
        return self.similarity_threshold

    def _vector_path(self, knowledge_base_id: int) -> Path:
        return self.storage_path / f"kb_{knowledge_base_id}_vectors.pkl"

    @staticmethod
    def _read_pickle(path: Path) -> dict:
        with path.open("rb") as handle:
            return pickle.load(handle)

    @staticmethod
    def _write_pickle(path: Path, value: dict) -> None:
        with path.open("wb") as handle:
            pickle.dump(value, handle)


knowledge_base_service = KnowledgeBaseStore()
