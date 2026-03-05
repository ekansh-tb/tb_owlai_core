"""
Optional sqlite-vec vector storage backend for OwlAI RAG.

Provides fast KNN search via sqlite-vec virtual tables alongside the
existing MariaDB + Redis path. Falls back gracefully if not installed.

Install:
    pip install sqlite-vec
"""

import json
import os
import sqlite3
import struct

import frappe

try:
    import sqlite_vec  # noqa: F401
    HAS_SQLITE_VEC = True
except ImportError:
    HAS_SQLITE_VEC = False

logger = frappe.logger("owlai.vector_store_sqlite")


def _db_path() -> str:
    return os.path.join(frappe.get_site_path("private"), "ai_memory.db")


def _serialize_float_list(v: list) -> bytes:
    """Pack a list of floats into a little-endian binary blob for sqlite-vec."""
    return struct.pack(f"{len(v)}f", *v)


class SqliteVecStore:
    """KNN vector store backed by sqlite-vec.

    All operations are idempotent — calling init() multiple times is safe.
    The DB file lives at {site}/private/ai_memory.db.
    """

    def __init__(self):
        if not HAS_SQLITE_VEC:
            raise ImportError(
                "sqlite-vec is not installed. Run: pip install sqlite-vec"
            )
        self._db_path = _db_path()
        self._conn = self._connect()
        self._init_schema()

    # ------------------------------------------------------------------
    # Connection helpers
    # ------------------------------------------------------------------

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self._db_path, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        sqlite_vec.load(conn)
        return conn

    def _init_schema(self):
        """Create tables if they don't exist yet."""
        cur = self._conn.cursor()

        # Metadata + content table
        cur.execute("""
            CREATE TABLE IF NOT EXISTS vectors (
                chunk_id     TEXT PRIMARY KEY,
                content      TEXT NOT NULL,
                metadata_json TEXT DEFAULT '{}',
                embedding    BLOB NOT NULL
            )
        """)

        # Determine embedding dimension from existing rows (default 768)
        cur.execute("SELECT embedding FROM vectors LIMIT 1")
        row = cur.fetchone()
        if row:
            dim = len(struct.unpack(f"{len(row['embedding']) // 4}f", row["embedding"]))
        else:
            dim = 768

        # Virtual KNN table — recreate only if dimension changed or missing
        cur.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='vec_chunks'"
        )
        if not cur.fetchone():
            cur.execute(f"""
                CREATE VIRTUAL TABLE vec_chunks USING vec0(
                    chunk_id TEXT PRIMARY KEY,
                    embedding FLOAT[{dim}]
                )
            """)

        self._conn.commit()

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    def store(self, chunk_id: str, content: str, embedding: list, metadata: dict):
        """Insert or replace a vector."""
        blob = _serialize_float_list(embedding)
        meta_json = json.dumps(metadata or {})

        cur = self._conn.cursor()

        # Ensure vec_chunks has the right dimension on first write
        cur.execute("SELECT COUNT(*) FROM vec_chunks")
        if cur.fetchone()[0] == 0:
            dim = len(embedding)
            cur.execute("DROP TABLE IF EXISTS vec_chunks")
            cur.execute(f"""
                CREATE VIRTUAL TABLE vec_chunks USING vec0(
                    chunk_id TEXT PRIMARY KEY,
                    embedding FLOAT[{dim}]
                )
            """)

        cur.execute(
            """
            INSERT OR REPLACE INTO vectors (chunk_id, content, metadata_json, embedding)
            VALUES (?, ?, ?, ?)
            """,
            (chunk_id, content, meta_json, blob),
        )
        cur.execute(
            """
            INSERT OR REPLACE INTO vec_chunks (chunk_id, embedding)
            VALUES (?, ?)
            """,
            (chunk_id, blob),
        )
        self._conn.commit()

    def search(self, query_embedding: list, limit: int = 5) -> list:
        """KNN search. Returns list of {"content", "meta", "score"} dicts."""
        if not query_embedding:
            return []

        blob = _serialize_float_list(query_embedding)
        cur = self._conn.cursor()

        try:
            cur.execute(
                """
                SELECT v.chunk_id, v.content, v.metadata_json, vc.distance
                FROM vec_chunks vc
                JOIN vectors v ON v.chunk_id = vc.chunk_id
                WHERE vc.embedding MATCH ?
                  AND K = ?
                ORDER BY vc.distance
                """,
                (blob, limit),
            )
        except sqlite3.OperationalError as e:
            logger.warning(f"sqlite-vec search error: {e}")
            return []

        results = []
        for row in cur.fetchall():
            meta = {}
            try:
                meta = json.loads(row["metadata_json"])
            except (json.JSONDecodeError, TypeError):
                pass
            # sqlite-vec returns L2 distance; convert to a 0-1 similarity score
            distance = row["distance"] or 0.0
            score = 1.0 / (1.0 + distance)
            results.append({
                "content": row["content"],
                "meta": meta,
                "score": score,
            })

        return results

    def delete(self, chunk_id: str):
        """Remove a vector by chunk_id."""
        cur = self._conn.cursor()
        cur.execute("DELETE FROM vectors WHERE chunk_id = ?", (chunk_id,))
        cur.execute("DELETE FROM vec_chunks WHERE chunk_id = ?", (chunk_id,))
        self._conn.commit()

    def delete_by_doc(self, doc_name: str):
        """Remove all vectors for a knowledge base document."""
        cur = self._conn.cursor()
        cur.execute(
            "SELECT chunk_id FROM vectors WHERE json_extract(metadata_json, '$.doc_name') = ?",
            (doc_name,),
        )
        ids = [r["chunk_id"] for r in cur.fetchall()]
        for cid in ids:
            cur.execute("DELETE FROM vec_chunks WHERE chunk_id = ?", (cid,))
        cur.execute(
            "DELETE FROM vectors WHERE json_extract(metadata_json, '$.doc_name') = ?",
            (doc_name,),
        )
        self._conn.commit()

    def count(self) -> int:
        """Total number of vectors stored."""
        cur = self._conn.cursor()
        cur.execute("SELECT COUNT(*) FROM vectors")
        return cur.fetchone()[0]

    def clear(self):
        """Drop all vectors from both tables."""
        cur = self._conn.cursor()
        cur.execute("DELETE FROM vectors")
        cur.execute("DELETE FROM vec_chunks")
        self._conn.commit()

    def migrate_from_doctype(self) -> int:
        """Import existing OwlAI Vector Chunk records into sqlite-vec.

        Safe to call multiple times — uses INSERT OR REPLACE.
        Returns number of vectors migrated.
        """
        try:
            chunks = frappe.get_all(
                "OwlAI Vector Chunk",
                fields=[
                    "chunk_id", "content", "embedding",
                    "doc_name", "meta_data", "chunk_index",
                ],
                limit_page_length=0,
            )
        except Exception as e:
            logger.error(f"migrate_from_doctype: failed to load chunks: {e}")
            return 0

        migrated = 0
        for c in chunks:
            try:
                embedding = (
                    json.loads(c.embedding)
                    if isinstance(c.embedding, str)
                    else c.embedding
                )
                if not embedding:
                    continue
                meta = (
                    json.loads(c.meta_data)
                    if isinstance(c.meta_data, str)
                    else (c.meta_data or {})
                )
                meta["doc_name"] = c.doc_name
                meta["chunk_index"] = c.chunk_index
                self.store(c.chunk_id, c.content, embedding, meta)
                migrated += 1
            except Exception as e:
                logger.warning(f"migrate_from_doctype: skipping chunk {c.chunk_id}: {e}")

        logger.info(f"migrate_from_doctype: migrated {migrated} vectors")
        return migrated


# ------------------------------------------------------------------
# Singleton accessor
# ------------------------------------------------------------------

_store_instance = None


def _get_vector_store():
    """Return the singleton SqliteVecStore if sqlite-vec is available, else None."""
    global _store_instance
    if not HAS_SQLITE_VEC:
        return None
    if _store_instance is None:
        try:
            _store_instance = SqliteVecStore()
        except Exception as e:
            frappe.log_error(f"SqliteVecStore init error: {e}")
            return None
    return _store_instance
