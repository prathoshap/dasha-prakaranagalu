"""
AI Shastri — One-time ingestion script
---------------------------------------
Run this once to chunk, embed, and store the Shastric text in ChromaDB.

Usage:
    source venv/bin/activate
    python ingest.py
"""

import os
import sys
import time
import random

import chromadb
from chromadb import Documents, EmbeddingFunction, Embeddings
from dotenv import load_dotenv
from google import genai
from google.genai import types

load_dotenv()

# ── Config ─────────────────────────────────────────────────────────────────────
GEMINI_API_KEY  = os.getenv("GEMINI_API_KEY")
TXT_PATH        = "/Users/prathosh/Downloads/reignofrealismin032789mbp_hocr_searchtext.txt"
CHROMA_PATH     = "./chroma_db"
COLLECTION_NAME = "shastra_texts"
CHUNK_SIZE      = 400   # words per chunk
CHUNK_OVERLAP   = 50    # word overlap between chunks
EMBED_BATCH     = 5     # chunks per embedding call (rate-limit safe)

if not GEMINI_API_KEY:
    sys.exit("ERROR: GEMINI_API_KEY not set in .env")

client = genai.Client(api_key=GEMINI_API_KEY)


# ── Custom embedding function with exponential backoff ────────────────────────

def embed_with_retry(texts: list[str], max_retries: int = 8) -> list:
    for attempt in range(max_retries):
        try:
            result = client.models.embed_content(
                model="gemini-embedding-001",
                contents=texts,
            )
            return [e.values for e in result.embeddings]
        except Exception as e:
            if "429" in str(e) or "RESOURCE_EXHAUSTED" in str(e):
                wait = min(2 ** attempt + random.uniform(0, 1), 60)
                print(f"\n      Rate limited — retrying in {wait:.1f}s (attempt {attempt+1}/{max_retries})")
                time.sleep(wait)
            else:
                raise
    raise RuntimeError("Max retries exceeded on embedding API")


class GeminiEmbeddingFunction(EmbeddingFunction):
    def __call__(self, input: Documents) -> Embeddings:
        return embed_with_retry(list(input))


# ── Text cleaning ──────────────────────────────────────────────────────────────

def clean_line(line: str) -> str:
    """Collapse multiple spaces (hOCR artifact) and strip edges."""
    return " ".join(line.split())


def load_and_clean(path: str) -> list[str]:
    with open(path, "r", encoding="utf-8") as f:
        raw_lines = f.readlines()

    paragraphs = []
    for line in raw_lines:
        line = clean_line(line)
        if len(line) > 40:   # skip noise lines
            paragraphs.append(line)
    return paragraphs


# ── Chunking ───────────────────────────────────────────────────────────────────

def chunk_text(paragraphs: list[str], chunk_size: int, overlap: int) -> list[str]:
    all_words = []
    for para in paragraphs:
        all_words.extend(para.split())
        all_words.append("")   # paragraph boundary

    chunks = []
    i = 0
    while i < len(all_words):
        window = all_words[i : i + chunk_size]
        chunk  = " ".join(w for w in window if w)
        if len(chunk) > 100:
            chunks.append(chunk)
        i += chunk_size - overlap
    return chunks


# ── Main ───────────────────────────────────────────────────────────────────────

def main():
    print("=" * 60)
    print("  AI Shastri — Ingestion Pipeline")
    print("=" * 60)

    print("\n[1/4] Loading and cleaning text...")
    paragraphs = load_and_clean(TXT_PATH)
    print(f"      {len(paragraphs)} paragraphs loaded")

    print("\n[2/4] Chunking...")
    chunks = chunk_text(paragraphs, CHUNK_SIZE, CHUNK_OVERLAP)
    print(f"      {len(chunks)} chunks (~{CHUNK_SIZE} words each)")

    print("\n[3/4] Setting up ChromaDB...")
    embed_fn   = GeminiEmbeddingFunction()
    chroma     = chromadb.PersistentClient(path=CHROMA_PATH)

    try:
        collection = chroma.get_collection(
            name=COLLECTION_NAME,
            embedding_function=embed_fn,
        )
        print(f"      Found existing collection ({collection.count()} chunks) — will resume")
    except Exception:
        collection = chroma.create_collection(
            name=COLLECTION_NAME,
            embedding_function=embed_fn,
            metadata={"hnsw:space": "cosine"},
        )
        print(f"      Created new collection '{COLLECTION_NAME}'")

    # Find already-stored chunk IDs to resume from checkpoint
    existing_ids = set(collection.get(include=[])["ids"])
    print(f"\n[4/4] Embedding and storing {len(chunks)} chunks...")
    if existing_ids:
        print(f"      Resuming — {len(existing_ids)} chunks already stored\n")
    else:
        print()

    for i in range(0, len(chunks), EMBED_BATCH):
        batch      = chunks[i : i + EMBED_BATCH]
        batch_ids  = [f"chunk_{i + j}" for j in range(len(batch))]
        batch_meta = [{"chunk_index": i + j} for j in range(len(batch))]

        # Skip chunks already in the DB
        new = [(d, id_, m) for d, id_, m in zip(batch, batch_ids, batch_meta)
               if id_ not in existing_ids]
        if not new:
            continue

        docs, ids, metas = zip(*new)
        collection.upsert(documents=list(docs), ids=list(ids), metadatas=list(metas))

        done = min(i + EMBED_BATCH, len(chunks))
        pct  = int(done / len(chunks) * 100)
        print(f"      [{pct:3d}%] {done}/{len(chunks)} chunks stored", end="\r")
        time.sleep(5)

    print(f"\n\n✅  Done! {len(chunks)} chunks stored in ChromaDB at '{CHROMA_PATH}/'")


if __name__ == "__main__":
    main()
