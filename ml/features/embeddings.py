"""
ReconLens — semantic embedding features.

Primary backend: local sentence-transformers model (no OpenAI, no API key —
see docs/architecture.md Phase 2 notes for why, and for the caveat about
needing the model weights pre-baked into the Docker image for the "no
external dependency at demo time" property to actually hold).

Fallback backend: a deterministic, dependency-free character n-gram hashing
vector. This exists ONLY so the pipeline can run in network-restricted
environments (this build sandbox has no route to huggingface.co). It is
NOT a semantic embedding — it will catch some lexical overlap but nothing
like true synonymy/abbreviation understanding. Every feature row and the
feature-quality report record which backend actually produced the numbers,
so results are never silently mislabeled as "semantic similarity" when
they're really "character overlap similarity."
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Optional

import numpy as np

EMBEDDING_MODEL_NAME = "sentence-transformers/all-MiniLM-L6-v2"
FALLBACK_DIM = 256
CACHE_DIR = Path(__file__).parent.parent.parent / "cache" / "embeddings"


class EmbeddingBackend:
    """Loads the real model if possible; otherwise activates the fallback
    and makes that fact loudly visible rather than silently degrading.
    """

    def __init__(self):
        self.backend_name: str
        self.dim: int
        self._model = None
        self._load()

    def _load(self):
        try:
            from sentence_transformers import SentenceTransformer
            self._model = SentenceTransformer(EMBEDDING_MODEL_NAME)
            self.dim = self._model.get_sentence_embedding_dimension()
            self.backend_name = EMBEDDING_MODEL_NAME
        except Exception as e:
            print(
                f"[embeddings] WARNING: could not load '{EMBEDDING_MODEL_NAME}' "
                f"({type(e).__name__}: {e}). Falling back to a deterministic "
                f"character n-gram hashing embedder. This is NOT a semantic "
                f"embedding — see ml/features/embeddings.py module docstring. "
                f"Every downstream report will be tagged with backend="
                f"'fallback_ngram_hash' so this is never confused with real "
                f"model output."
            )
            self._model = None
            self.dim = FALLBACK_DIM
            self.backend_name = "fallback_ngram_hash"

    def encode(self, text: str) -> np.ndarray:
        if not text:
            return np.zeros(self.dim, dtype=np.float32)
        if self._model is not None:
            vec = self._model.encode(text, convert_to_numpy=True, normalize_embeddings=True)
            return vec.astype(np.float32)
        return self._ngram_hash_embed(text)

    def _ngram_hash_embed(self, text: str, n: int = 3) -> np.ndarray:
        """Deterministic: hashes each character n-gram into a fixed-size
        vector via SHA-256, then L2-normalizes. Same input always produces
        the same output, satisfying the reproducibility requirement even
        though it isn't semantic.
        """
        vec = np.zeros(self.dim, dtype=np.float32)
        s = text.lower()
        grams = [s[i:i + n] for i in range(max(1, len(s) - n + 1))] or [s]
        for g in grams:
            h = int(hashlib.sha256(g.encode()).hexdigest(), 16)
            idx = h % self.dim
            sign = 1.0 if (h // self.dim) % 2 == 0 else -1.0
            vec[idx] += sign
        norm = np.linalg.norm(vec)
        if norm > 0:
            vec = vec / norm
        return vec


class EmbeddingCache:
    """Deterministic on-disk cache keyed by (model_name, normalized_text).
    Avoids recomputing embeddings for repeated vendor names / descriptions,
    which matters once this scales past 600 transactions.
    """

    def __init__(self, backend_name: str, cache_dir: Path = CACHE_DIR):
        self.backend_name = backend_name
        self.cache_dir = cache_dir
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self._mem: dict[str, np.ndarray] = {}
        self._path = self.cache_dir / f"{self._safe_name(backend_name)}.npz"
        self._load_disk()

    @staticmethod
    def _safe_name(name: str) -> str:
        return name.replace("/", "__")

    def _key(self, text: str) -> str:
        raw = f"{self.backend_name}::{text}"
        return hashlib.sha256(raw.encode()).hexdigest()

    def _load_disk(self):
        if self._path.exists():
            data = np.load(self._path, allow_pickle=False)
            for k in data.files:
                self._mem[k] = data[k]

    def get(self, text: str) -> Optional[np.ndarray]:
        return self._mem.get(self._key(text))

    def put(self, text: str, vec: np.ndarray):
        self._mem[self._key(text)] = vec

    def flush(self):
        np.savez_compressed(self._path, **self._mem)


def cosine_similarity(a: np.ndarray, b: np.ndarray) -> float:
    na, nb = np.linalg.norm(a), np.linalg.norm(b)
    if na < 1e-9 or nb < 1e-9:
        return 0.0
    sim = float(np.dot(a, b) / (na * nb))
    # guard against float noise pushing marginally outside [-1, 1]
    return round(max(-1.0, min(1.0, sim)), 6)
