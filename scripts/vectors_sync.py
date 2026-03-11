#!/usr/bin/env python3
# ============================================================
# FILE: scripts/vectors_sync.py
# DESC: manifest.sqlite(manifest_docs) の active(is_deleted=0) を vectors.sqlite(vector_docs) に同期し、差分に応じて pending リセット/追加/更新/削除を行う
#
# DEPENDS:
#   build/manifest.sqlite (table: manifest_docs)
#   build/vectors.sqlite  (table: vector_docs, vectors_meta)
#   schema_version: VECTORS_SCHEMA_VERSION=1
#
# PIPELINE ROLE
#
#   index_build.py → build/manifest.sqlite (manifest_docs)
#        ↓
#   active docs を vectors DB に反映（embedding用のキュー化）  ← このスクリプト
#        ↓
#   build/vectors.sqlite : vector_docs (pending/embedded 状態管理)
#        ↓
#   embed_pending.py / embedder導入後の埋め込み生成
#
# ============================================================

from __future__ import annotations

# ============================================================
# SECTION: imports
# ============================================================

import argparse
import datetime as dt
import sqlite3
from pathlib import Path
from typing import Any, Dict, Tuple


# ============================================================
# SECTION: constants
# ============================================================

VECTORS_SCHEMA_VERSION = 1


# ============================================================
# SECTION: helpers (time / sqlite)
# ============================================================

def iso_now() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat()

def connect_sqlite(path: Path) -> sqlite3.Connection:
    path.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(path)
    con.execute("PRAGMA journal_mode=WAL;")
    con.execute("PRAGMA foreign_keys=ON;")
    return con


# ============================================================
# SECTION: vectors DB schema
# ============================================================

def ensure_vectors_db(con: sqlite3.Connection) -> None:
    con.execute("""
        CREATE TABLE IF NOT EXISTS vectors_meta (
            key   TEXT PRIMARY KEY,
            value TEXT NOT NULL
        );
    """)
    con.execute("""
        INSERT OR IGNORE INTO vectors_meta(key, value)
        VALUES('schema_version', ?);
    """, (str(VECTORS_SCHEMA_VERSION),))

    con.execute("""
        CREATE TABLE IF NOT EXISTS vector_docs (
            doc_id           TEXT PRIMARY KEY,
            genre_level1     TEXT NOT NULL,
            genre_level2     TEXT NOT NULL,
            title            TEXT NOT NULL,
            text             TEXT NOT NULL,
            version_hash     TEXT NOT NULL,
            embedding_status TEXT NOT NULL DEFAULT 'pending',
            embedding_model  TEXT,
            embedding_dim    INTEGER,
            updated_at       TEXT NOT NULL
        );
    """)
    con.commit()


# ============================================================
# SECTION: fetch docs (manifest / vectors)
# ============================================================

def fetch_manifest_docs(manifest_con: sqlite3.Connection) -> Dict[str, Dict[str, Any]]:
    # Only active docs (is_deleted=0)
    cur = manifest_con.execute("""
        SELECT doc_id, genre_level1, genre_level2, title, version_hash
        FROM manifest_docs
        WHERE is_deleted=0;
    """)
    out: Dict[str, Dict[str, Any]] = {}
    for doc_id, g1, g2, title, vhash in cur.fetchall():
        out[str(doc_id)] = {
            "genre_level1": str(g1),
            "genre_level2": str(g2),
            "title": str(title),
            "version_hash": str(vhash),
        }
    return out

def fetch_vectors_docs(vectors_con: sqlite3.Connection) -> Dict[str, Tuple[str, str]]:
    # doc_id -> (version_hash, embedding_status)
    cur = vectors_con.execute("""
        SELECT doc_id, version_hash, embedding_status
        FROM vector_docs;
    """)
    out: Dict[str, Tuple[str, str]] = {}
    for doc_id, vhash, status in cur.fetchall():
        out[str(doc_id)] = (str(vhash), str(status))
    return out


# ============================================================
# SECTION: upsert / delete operations
# ============================================================

def upsert_vector_doc(
    vectors_con: sqlite3.Connection,
    doc_id: str,
    genre_level1: str,
    genre_level2: str,
    title: str,
    text: str,
    version_hash: str,
    reset_embedding: bool
) -> None:
    now = iso_now()

    if reset_embedding:
        # If content changed, mark as pending again
        vectors_con.execute("""
            INSERT INTO vector_docs(
                doc_id, genre_level1, genre_level2, title, text, version_hash,
                embedding_status, embedding_model, embedding_dim, updated_at
            ) VALUES(?,?,?,?,?,?, 'pending', NULL, NULL, ?)
            ON CONFLICT(doc_id) DO UPDATE SET
                genre_level1=excluded.genre_level1,
                genre_level2=excluded.genre_level2,
                title=excluded.title,
                text=excluded.text,
                version_hash=excluded.version_hash,
                embedding_status='pending',
                embedding_model=NULL,
                embedding_dim=NULL,
                updated_at=excluded.updated_at;
        """, (doc_id, genre_level1, genre_level2, title, text, version_hash, now))
    else:
        vectors_con.execute("""
            INSERT INTO vector_docs(
                doc_id, genre_level1, genre_level2, title, text, version_hash, updated_at
            ) VALUES(?,?,?,?,?,?,?)
            ON CONFLICT(doc_id) DO UPDATE SET
                genre_level1=excluded.genre_level1,
                genre_level2=excluded.genre_level2,
                title=excluded.title,
                text=excluded.text,
                version_hash=excluded.version_hash,
                updated_at=excluded.updated_at;
        """, (doc_id, genre_level1, genre_level2, title, text, version_hash, now))

def delete_vector_doc(vectors_con: sqlite3.Connection, doc_id: str) -> None:
    vectors_con.execute("DELETE FROM vector_docs WHERE doc_id=?;", (doc_id,))


# ============================================================
# SECTION: main
# ============================================================

def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--manifest", default="build/manifest.sqlite")
    ap.add_argument("--vectors", default="build/vectors.sqlite")
    args = ap.parse_args()

    manifest_path = Path(args.manifest)
    vectors_path = Path(args.vectors)

    man = connect_sqlite(manifest_path)
    vec = connect_sqlite(vectors_path)
    ensure_vectors_db(vec)

    manifest_docs = fetch_manifest_docs(man)
    vectors_docs = fetch_vectors_docs(vec)

    # We need "text" for embedding later.
    # For now, reconstruct minimal text from title + labels (enough to carry forward).
    # Later we can source the full text from a dedicated document store if desired.
    added = updated = unchanged = deleted = 0

    for doc_id, info in manifest_docs.items():
        g1 = info["genre_level1"]
        g2 = info["genre_level2"]
        title = info["title"]
        vhash = info["version_hash"]

        # minimal text placeholder (will be improved later when we store full doc text)
        text = f"料理名: {title}\nジャンル: {g1} / {g2}".strip()

        if doc_id not in vectors_docs:
            upsert_vector_doc(vec, doc_id, g1, g2, title, text, vhash, reset_embedding=True)
            added += 1
        else:
            old_hash, old_status = vectors_docs[doc_id]
            if old_hash != vhash:
                upsert_vector_doc(vec, doc_id, g1, g2, title, text, vhash, reset_embedding=True)
                updated += 1
            else:
                # keep as-is
                unchanged += 1

    # Delete in vectors if no longer in manifest active set
    active_ids = set(manifest_docs.keys())
    for doc_id in list(vectors_docs.keys()):
        if doc_id not in active_ids:
            delete_vector_doc(vec, doc_id)
            deleted += 1

    vec.commit()
    man.close()
    vec.close()

    print("=== vectors_sync summary ===")
    print(f"manifest : {manifest_path}")
    print(f"vectors  : {vectors_path}")
    print(f"added    : {added}")
    print(f"updated  : {updated}")
    print(f"unchanged: {unchanged}")
    print(f"deleted  : {deleted}")


# ============================================================
# SECTION: entrypoint
# ============================================================

if __name__ == "__main__":
    main()