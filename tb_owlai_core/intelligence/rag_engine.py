"""
Lightweight RAG Engine — Zero heavy dependencies.

Uses:
- Ollama /api/embed for embeddings (already running locally)
- Redis as hot cache for fast cosine similarity search
- Frappe DB (OwlAI Vector Chunk) as cold storage / source of truth

No agno, no lancedb, no numpy, no langchain.
"""

import frappe
import json
import hashlib
import requests
import re
import math

logger = frappe.logger("owlai.rag")

# Redis key constants
CACHE_KEY_VECTORS = "owlai:vectors"
CACHE_KEY_VECTOR_IDS = "owlai:vector_ids"
CACHE_TTL = 604800  # 7 days


# ------------------------------------------------------------------
# Public API
# ------------------------------------------------------------------

def index_document(doc):
    """Index a Frappe 'OwlAI Knowledge Base' document.

    Extracts text, chunks it, embeds each chunk, stores in DB + Redis.
    Returns: {"chunks": int, "vector_id": str}
    """
    # 1. Extract text
    text = _extract_text(doc)
    text = _clean_text(text)
    if not text:
        raise ValueError("No content extracted to index.")

    # 2. Chunk text
    settings = frappe.get_single("OwlAI Settings")
    chunk_size = getattr(settings, "chunk_size", 1000) or 1000
    chunk_overlap = getattr(settings, "chunk_overlap", 100) or 100
    chunks = _chunk_text(text, chunk_size, chunk_overlap)

    if not chunks:
        raise ValueError("Text chunking produced no chunks.")

    # 3. Delete old chunks for this document
    delete_from_index(doc.name)

    # 4. Embed and store each chunk
    embeddings = _embed_texts(chunks)

    for i, (chunk_text, embedding) in enumerate(zip(chunks, embeddings)):
        chunk_id = hashlib.md5(f"{doc.name}:{i}:{chunk_text[:50]}".encode()).hexdigest()

        # Store in DB
        chunk_doc = frappe.new_doc("OwlAI Vector Chunk")
        chunk_doc.chunk_id = chunk_id
        chunk_doc.knowledge_base = doc.name
        chunk_doc.chunk_index = i
        chunk_doc.content = chunk_text
        chunk_doc.embedding = json.dumps(embedding)
        chunk_doc.doc_name = doc.name
        chunk_doc.meta_data = json.dumps({
            "title": doc.title,
            "source_type": doc.source_type,
            "url": getattr(doc, "url", ""),
        })
        chunk_doc.flags.ignore_permissions = True
        chunk_doc.insert()

        # Cache in Redis
        _cache_vector(chunk_id, embedding, chunk_text, {
            "doc_name": doc.name,
            "title": doc.title,
            "source_type": doc.source_type,
            "chunk_index": i,
        })

    frappe.db.commit()

    logger.info(f"Indexed {len(chunks)} chunks for {doc.name}")
    return {"chunks": len(chunks), "vector_id": doc.name}


def search(query, limit=5):
    """Search the knowledge base using vector similarity.

    Returns list of {"content": str, "meta": dict, "score": float}
    """
    if not query:
        return []

    try:
        # Embed the query
        query_embedding = _embed_single(query)
        if not query_embedding:
            return []

        # Load all vectors from cache (or DB fallback)
        vectors = _load_all_vectors()
        if not vectors:
            return []

        # Compute cosine similarity
        scored = []
        for v in vectors:
            score = _cosine_similarity(query_embedding, v["embedding"])
            scored.append({
                "content": v["content"],
                "meta": v["meta"],
                "score": score,
            })

        # Sort by score descending, return top-K
        scored.sort(key=lambda x: x["score"], reverse=True)
        return scored[:limit]

    except Exception as e:
        frappe.log_error(f"RAG Search Error: {e}")
        return []


def delete_from_index(doc_name):
    """Delete all chunks for a document from DB and Redis."""
    try:
        # Get chunk IDs before deletion
        chunk_ids = frappe.get_all(
            "OwlAI Vector Chunk",
            filters={"doc_name": doc_name},
            pluck="chunk_id"
        )

        # Delete from DB
        frappe.db.delete("OwlAI Vector Chunk", {"doc_name": doc_name})

        # Delete from Redis
        for cid in chunk_ids:
            frappe.cache.delete_value(f"{CACHE_KEY_VECTORS}:{cid}")

        # Update vector IDs set
        _remove_from_id_set(chunk_ids)

        frappe.db.commit()
        return {"status": "success", "doc_name": doc_name}

    except Exception as e:
        frappe.log_error(f"RAG Delete Error: {e}")
        raise


def warm_cache():
    """Pre-load all vectors into Redis. Called on after_migrate if count < 500."""
    try:
        count = frappe.db.count("OwlAI Vector Chunk")
        if count == 0:
            return
        if count > 500:
            logger.info(f"Skipping cache warm: {count} chunks (>500)")
            return

        chunks = frappe.get_all(
            "OwlAI Vector Chunk",
            fields=["chunk_id", "content", "embedding", "doc_name", "meta_data", "chunk_index"],
            limit_page_length=0
        )

        ids = []
        for c in chunks:
            embedding = json.loads(c.embedding) if isinstance(c.embedding, str) else c.embedding
            meta = json.loads(c.meta_data) if isinstance(c.meta_data, str) else (c.meta_data or {})
            meta["doc_name"] = c.doc_name
            meta["chunk_index"] = c.chunk_index

            _cache_vector(c.chunk_id, embedding, c.content, meta)
            ids.append(c.chunk_id)

        frappe.cache.set_value(CACHE_KEY_VECTOR_IDS, json.dumps(ids), expires_in_sec=CACHE_TTL)
        logger.info(f"Warmed cache with {len(ids)} vectors")

    except Exception as e:
        frappe.log_error(f"RAG Cache Warm Error: {e}")


# ------------------------------------------------------------------
# Text Extraction
# ------------------------------------------------------------------

def _extract_text(doc):
    """Extract text content from a Knowledge Base document."""
    if doc.source_type == "Text":
        return doc.content or ""

    elif doc.source_type == "URL":
        try:
            resp = requests.get(doc.url, timeout=15)
            resp.raise_for_status()
            from bs4 import BeautifulSoup
            soup = BeautifulSoup(resp.content, "html.parser")
            for tag in soup(["script", "style", "nav", "footer", "header"]):
                tag.extract()
            return soup.get_text(separator=" ")
        except Exception as e:
            raise ValueError(f"Failed to fetch URL {doc.url}: {e}")

    elif doc.source_type == "File":
        file_path = frappe.get_site_path(doc.file.lstrip("/"))
        return _extract_file_text(file_path, doc.file)

    return ""


def _extract_file_text(file_path, filename):
    """Extract text from various file formats."""
    if filename.endswith(".pdf"):
        try:
            from pypdf import PdfReader
            reader = PdfReader(file_path)
            return "\n".join(page.extract_text() or "" for page in reader.pages)
        except ImportError:
            raise ValueError("pypdf not installed. Run: pip install pypdf")

    elif filename.endswith((".xlsx", ".xls")):
        try:
            import openpyxl
            wb = openpyxl.load_workbook(file_path, read_only=True)
            text_parts = []
            for sheet in wb:
                for row in sheet.iter_rows(values_only=True):
                    text_parts.append(" | ".join(str(c) for c in row if c is not None))
            return "\n".join(text_parts)
        except ImportError:
            raise ValueError("openpyxl not installed. Run: pip install openpyxl")

    elif filename.endswith(".csv"):
        import csv
        with open(file_path, "r", errors="replace") as f:
            reader = csv.reader(f)
            return "\n".join(" | ".join(row) for row in reader)

    else:
        # Plain text
        with open(file_path, "r", errors="replace") as f:
            return f.read()


# ------------------------------------------------------------------
# Text Chunking (pure Python, no dependencies)
# ------------------------------------------------------------------

def _chunk_text(text, chunk_size=1000, overlap=100):
    """Split text into overlapping chunks using sentence boundaries."""
    if not text:
        return []

    # Split on sentence boundaries
    sentences = re.split(r'(?<=[.!?])\s+', text)

    chunks = []
    current_chunk = ""

    for sentence in sentences:
        if len(current_chunk) + len(sentence) > chunk_size and current_chunk:
            chunks.append(current_chunk.strip())
            # Keep overlap from end of current chunk
            if overlap > 0:
                current_chunk = current_chunk[-overlap:] + " " + sentence
            else:
                current_chunk = sentence
        else:
            current_chunk = (current_chunk + " " + sentence).strip()

    if current_chunk.strip():
        chunks.append(current_chunk.strip())

    return chunks


def _clean_text(text):
    """Clean extracted text."""
    if not text:
        return ""
    text = re.sub(r'\s+', ' ', text)
    text = re.sub(r'\n{3,}', '\n\n', text)
    return text.strip()


# ------------------------------------------------------------------
# Embedding via Ollama /api/embed
# ------------------------------------------------------------------

def _get_ollama_config():
    """Get Ollama host and embedding model from settings."""
    try:
        settings = frappe.get_single("OwlAI Settings")
        embedding_model = getattr(settings, "embedding_model", "nomic-embed-text") or "nomic-embed-text"
    except Exception:
        embedding_model = "nomic-embed-text"

    import os
    ollama_host = os.getenv("OLLAMA_HOST", "http://localhost:11434")
    # Ensure protocol prefix
    if not ollama_host.startswith("http"):
        ollama_host = f"http://{ollama_host}"

    return ollama_host, embedding_model


def _embed_single(text):
    """Embed a single text string. Returns list of floats."""
    host, model = _get_ollama_config()
    try:
        resp = requests.post(
            f"{host}/api/embed",
            json={"model": model, "input": text},
            timeout=30
        )
        resp.raise_for_status()
        data = resp.json()
        # Ollama returns {"embeddings": [[...]]}
        embeddings = data.get("embeddings", [])
        if embeddings:
            return embeddings[0]
        return []
    except Exception as e:
        logger.error(f"Embedding error: {e}")
        return []


def _embed_texts(texts):
    """Embed multiple texts. Returns list of embedding vectors."""
    host, model = _get_ollama_config()
    embeddings = []

    # Ollama supports batch embedding via list input
    try:
        resp = requests.post(
            f"{host}/api/embed",
            json={"model": model, "input": texts},
            timeout=120
        )
        resp.raise_for_status()
        data = resp.json()
        return data.get("embeddings", [])
    except Exception:
        # Fallback: embed one by one
        for text in texts:
            emb = _embed_single(text)
            embeddings.append(emb)
        return embeddings


# ------------------------------------------------------------------
# Cosine Similarity (pure Python)
# ------------------------------------------------------------------

def _cosine_similarity(a, b):
    """Compute cosine similarity between two vectors. No numpy needed."""
    if not a or not b or len(a) != len(b):
        return 0.0

    dot = sum(x * y for x, y in zip(a, b))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(x * x for x in b))

    if norm_a == 0 or norm_b == 0:
        return 0.0

    return dot / (norm_a * norm_b)


# ------------------------------------------------------------------
# Redis Cache Management
# ------------------------------------------------------------------

def _cache_vector(chunk_id, embedding, content, meta):
    """Cache a single vector in Redis."""
    data = {
        "embedding": embedding,
        "content": content,
        "meta": meta,
    }
    frappe.cache.set_value(
        f"{CACHE_KEY_VECTORS}:{chunk_id}",
        json.dumps(data),
        expires_in_sec=CACHE_TTL
    )
    # Add to ID set
    _add_to_id_set(chunk_id)


def _add_to_id_set(chunk_id):
    """Add a chunk ID to the cached set of all vector IDs."""
    try:
        raw = frappe.cache.get_value(CACHE_KEY_VECTOR_IDS)
        ids = json.loads(raw) if raw and isinstance(raw, str) else (raw or [])
        if chunk_id not in ids:
            ids.append(chunk_id)
            frappe.cache.set_value(CACHE_KEY_VECTOR_IDS, json.dumps(ids), expires_in_sec=CACHE_TTL)
    except Exception:
        frappe.cache.set_value(CACHE_KEY_VECTOR_IDS, json.dumps([chunk_id]), expires_in_sec=CACHE_TTL)


def _remove_from_id_set(chunk_ids):
    """Remove chunk IDs from the cached set."""
    if not chunk_ids:
        return
    try:
        raw = frappe.cache.get_value(CACHE_KEY_VECTOR_IDS)
        ids = json.loads(raw) if raw and isinstance(raw, str) else (raw or [])
        ids = [i for i in ids if i not in chunk_ids]
        frappe.cache.set_value(CACHE_KEY_VECTOR_IDS, json.dumps(ids), expires_in_sec=CACHE_TTL)
    except Exception:
        pass


def _load_all_vectors():
    """Load all vectors from Redis cache, falling back to DB."""
    vectors = []

    # Try Redis first
    try:
        raw = frappe.cache.get_value(CACHE_KEY_VECTOR_IDS)
        ids = json.loads(raw) if raw and isinstance(raw, str) else (raw or [])

        if ids:
            for chunk_id in ids:
                raw_vec = frappe.cache.get_value(f"{CACHE_KEY_VECTORS}:{chunk_id}")
                if raw_vec:
                    data = json.loads(raw_vec) if isinstance(raw_vec, str) else raw_vec
                    vectors.append(data)

            if vectors:
                return vectors
    except Exception:
        pass

    # Fallback: load from DB
    try:
        chunks = frappe.get_all(
            "OwlAI Vector Chunk",
            fields=["chunk_id", "content", "embedding", "doc_name", "meta_data", "chunk_index"],
            limit_page_length=0
        )

        ids = []
        for c in chunks:
            embedding = json.loads(c.embedding) if isinstance(c.embedding, str) else c.embedding
            meta = json.loads(c.meta_data) if isinstance(c.meta_data, str) else (c.meta_data or {})
            meta["doc_name"] = c.doc_name
            meta["chunk_index"] = c.chunk_index

            vectors.append({
                "embedding": embedding,
                "content": c.content,
                "meta": meta,
            })

            # Re-cache
            _cache_vector(c.chunk_id, embedding, c.content, meta)
            ids.append(c.chunk_id)

        if ids:
            frappe.cache.set_value(CACHE_KEY_VECTOR_IDS, json.dumps(ids), expires_in_sec=CACHE_TTL)

    except Exception as e:
        frappe.log_error(f"RAG load vectors error: {e}")

    return vectors
