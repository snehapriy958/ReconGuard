FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Best-effort pre-cache of the sentence-transformer model at build time, so a
# production container never needs runtime network access for embeddings —
# this was flagged as an action item back in Phase 2 (see docs/architecture.md)
# when this sandbox's own network couldn't reach huggingface.co. If the build
# environment ALSO can't reach it, this fails silently and the documented
# n-gram fallback embedder takes over at runtime instead of crashing the build.
RUN python -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('sentence-transformers/all-MiniLM-L6-v2')" || true

EXPOSE 8000
