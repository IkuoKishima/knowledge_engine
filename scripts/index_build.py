#!/usr/bin/env python3
# ============================================================
# FILE: scripts/index_build.py
# DESC: input/json 配下の recipe_knowledge.v1 を走査し、manifest.sqlite(manifest_docs) にドキュメント索引を作成/更新/削除マークする
#
# DEPENDS:
#   input/json/**/*.json (schema: recipe_knowledge.v1)
#   build/manifest.sqlite
#   table: manifest_meta, manifest_docs
#
# PIPELINE ROLE
#
#   knowledge JSON (recipe_knowledge.v1)
#        ↓
#   parse + canonicalize + version_hash生成 + doc_id生成  ← このスクリプト
#        ↓
#   build/manifest.sqlite : manifest_docs (upsert + deletion detection)
#
# ============================================================

from __future__ import annotations

# ============================================================
# SECTION: imports
# ============================================================

import argparse
import datetime as dt
import hashlib
import json
import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, List, Tuple


# ============================================================
# SECTION: constants / schema
# ============================================================

SCHEMA_INPUT = "recipe_knowledge.v1"
MANIFEST_SCHEMA_VERSION = 1


# ============================================================
# SECTION: model
# ============================================================

@dataclass(frozen=True)
class Document:
    doc_id: str
    source_path: str
    source_record_id: str
    genre_level1: str
    genre_level2: str
    title: str
    text: str
    version_hash: str
    created_at: str


# ============================================================
# SECTION: helpers (time / hash / serialization)
# ============================================================

def iso_now() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat()

def sha256_hex(s: str) -> str:
    return hashlib.sha256(s.encode("utf-8")).hexdigest()

def canonical_json(obj: Any) -> str:
    # stable serialization for hashing
    return json.dumps(obj, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


# ============================================================
# SECTION: document builders
# ============================================================

def build_text(title: str, keywords: List[str], examples: List[str]) -> str:
    # minimal: title + keywords + examples
    parts: List[str] = []
    if title:
        parts.append(f"料理名: {title}")
    if keywords:
        parts.append("キーワード: " + " ".join(keywords))
    if examples:
        parts.append("例: " + " / ".join(examples))
    return "\n".join(parts).strip()

def make_doc_id(source_path: str, record_id: str) -> str:
    # stable id based on origin
    return sha256_hex(f"{source_path}::{record_id}")

def load_json(path: Path) -> Dict[str, Any]:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


# ============================================================
# SECTION: input iteration (recipe_knowledge.v1 -> Document)
# ============================================================

def iter_documents(input_root: Path) -> Iterable[Document]:
    for p in sorted(input_root.rglob("*.json")):
        data = load_json(p)
        schema = data.get("schema")
        if schema != SCHEMA_INPUT:
            # skip unknown schema (safe)
            continue

        genre_l1 = str(data.get("genre_level1", "")).strip()
        genre_l2 = str(data.get("genre_level2", "")).strip()

        records = data.get("records", [])
        if not isinstance(records, list):
            continue

        rel_path = str(p.as_posix())

        for r in records:
            if not isinstance(r, dict):
                continue

            rid = str(r.get("id", "")).strip()
            title = str(r.get("title", "")).strip()

            keywords = r.get("keywords", []) or []
            examples = r.get("examples", []) or []

            if not isinstance(keywords, list):
                keywords = []
            if not isinstance(examples, list):
                examples = []

            text = build_text(
                title,
                [str(x) for x in keywords],
                [str(x) for x in examples],
            )

            # version hash should reflect semantic content used for embedding + labels
            payload = {
                "genre_level1": genre_l1,
                "genre_level2": genre_l2,
                "title": title,
                "keywords": keywords,
                "examples": examples,
                "text": text,
            }
            vhash = sha256_hex(canonical_json(payload))
            doc_id = make_doc_id(rel_path, rid)

            yield Document(
                doc_id=doc_id,
                source_path=rel_path,
                source_record_id=rid,
                genre_level1=genre_l1,
                genre_level2=genre_l2,
                title=title,
                text=text,
                version_hash=vhash,
                created_at=iso_now(),
            )


# ============================================================
# SECTION: manifest DB (schema / migrations)
# ============================================================

def ensure_manifest_db(db_path: Path) -> sqlite3.Connection:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(db_path)

    con.execute("PRAGMA journal_mode=WAL;")
    con.execute("PRAGMA foreign_keys=ON;")

    con.execute("""
        CREATE TABLE IF NOT EXISTS manifest_meta (
            key   TEXT PRIMARY KEY,
            value TEXT NOT NULL
        );
    """)

    con.execute("""
        CREATE TABLE IF NOT EXISTS manifest_docs (
            doc_id          TEXT PRIMARY KEY,
            source_path     TEXT NOT NULL,
            source_record_id TEXT NOT NULL,
            genre_level1    TEXT NOT NULL,
            genre_level2    TEXT NOT NULL,
            title           TEXT NOT NULL,
            version_hash    TEXT NOT NULL,
            is_deleted      INTEGER NOT NULL DEFAULT 0,
            created_at      TEXT NOT NULL,
            updated_at      TEXT NOT NULL
        );
    """)

    # schema version
    con.execute("""
        INSERT OR IGNORE INTO manifest_meta(key, value)
        VALUES('schema_version', ?);
    """, (str(MANIFEST_SCHEMA_VERSION),))

    con.commit()
    return con


# ============================================================
# SECTION: manifest operations (fetch / upsert / delete-mark)
# ============================================================

def fetch_existing(con: sqlite3.Connection) -> Dict[str, Tuple[str, int]]:
    """
    Return:
      doc_id -> (version_hash, is_deleted)
    """
    cur = con.execute("SELECT doc_id, version_hash, is_deleted FROM manifest_docs;")
    out: Dict[str, Tuple[str, int]] = {}
    for doc_id, vhash, is_del in cur.fetchall():
        out[str(doc_id)] = (str(vhash), int(is_del))
    return out

def upsert_doc(con: sqlite3.Connection, d: Document) -> None:
    now = iso_now()
    con.execute("""
        INSERT INTO manifest_docs(
            doc_id, source_path, source_record_id, genre_level1, genre_level2, title,
            version_hash, is_deleted, created_at, updated_at
        ) VALUES(?,?,?,?,?,?,?,?,?,?)
        ON CONFLICT(doc_id) DO UPDATE SET
            source_path=excluded.source_path,
            source_record_id=excluded.source_record_id,
            genre_level1=excluded.genre_level1,
            genre_level2=excluded.genre_level2,
            title=excluded.title,
            version_hash=excluded.version_hash,
            is_deleted=0,
            updated_at=excluded.updated_at;
    """, (
        d.doc_id,
        d.source_path,
        d.source_record_id,
        d.genre_level1,
        d.genre_level2,
        d.title,
        d.version_hash,
        0,
        d.created_at,
        now,
    ))

def mark_deleted(con: sqlite3.Connection, doc_id: str) -> None:
    now = iso_now()
    con.execute("""
        UPDATE manifest_docs
        SET is_deleted=1, updated_at=?
        WHERE doc_id=?;
    """, (now, doc_id))


# ============================================================
# SECTION: CLI / main
# ============================================================

def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", default="input/json", help="Input JSON root")
    ap.add_argument("--manifest", default="build/manifest.sqlite", help="Manifest sqlite path")
    args = ap.parse_args()

    input_root = Path(args.input)
    manifest_path = Path(args.manifest)

    con = ensure_manifest_db(manifest_path)
    existing = fetch_existing(con)

    docs = list(iter_documents(input_root))
    current_ids = set(d.doc_id for d in docs)

    added = updated = unchanged = 0

    for d in docs:
        if d.doc_id not in existing:
            upsert_doc(con, d)
            added += 1
        else:
            old_hash, old_del = existing[d.doc_id]
            if old_hash != d.version_hash or old_del == 1:
                upsert_doc(con, d)
                updated += 1
            else:
                unchanged += 1

    # deletion detection: docs that existed before but not present now
    deleted = 0
    for doc_id, (_vh, is_del) in existing.items():
        if doc_id not in current_ids and is_del == 0:
            mark_deleted(con, doc_id)
            deleted += 1

    con.commit()
    con.close()

    print("=== index_build summary ===")
    print(f"input_root : {input_root}")
    print(f"manifest   : {manifest_path}")
    print(f"docs_total : {len(docs)}")
    print(f"added      : {added}")
    print(f"updated    : {updated}")
    print(f"unchanged  : {unchanged}")
    print(f"deleted    : {deleted}")


# ============================================================
# SECTION: entrypoint
# ============================================================

if __name__ == "__main__":
    main()