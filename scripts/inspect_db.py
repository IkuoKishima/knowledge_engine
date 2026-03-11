#!/usr/bin/env python3
# ============================================================
# FILE: scripts/inspect_db.py
# DESC: build/manifest.sqlite と build/vectors.sqlite を読み取り、manifest_docs / vector_docs の最新レコード概要を表示する（デバッグ用インスペクタ）
#
# DEPENDS:
#   build/manifest.sqlite (table: manifest_docs)
#   build/vectors.sqlite  (table: vector_docs)
#
# PIPELINE ROLE
#
#   index_build.py などが生成/更新した sqlite
#        ↓
#   重要カラムのサマリを表示して状態確認  ← このスクリプト
#        ↓
#   次工程のデバッグ/検証（diff確認・pending確認など）
#
# ============================================================

from __future__ import annotations

# ============================================================
# SECTION: imports
# ============================================================

import argparse
import sqlite3
from pathlib import Path


# ============================================================
# SECTION: db helpers
# ============================================================

def connect(path: Path) -> sqlite3.Connection:
    con = sqlite3.connect(path)
    con.row_factory = sqlite3.Row
    return con


# ============================================================
# SECTION: views (print summaries)
# ============================================================

def show_manifest(con: sqlite3.Connection, limit: int) -> None:
    print("=== manifest_docs (active) ===")
    cur = con.execute("""
        SELECT doc_id, genre_level1, genre_level2, title, version_hash, is_deleted, updated_at
        FROM manifest_docs
        ORDER BY updated_at DESC
        LIMIT ?;
    """, (limit,))
    rows = cur.fetchall()
    for r in rows:
        print(
            f"- {r['genre_level1']}/{r['genre_level2']} | {r['title']} "
            f"| del={r['is_deleted']} | {str(r['version_hash'])[:10]}..."
        )

def show_vectors(con: sqlite3.Connection, limit: int) -> None:
    print("=== vector_docs ===")
    cur = con.execute("""
        SELECT doc_id, genre_level1, genre_level2, title, version_hash, embedding_status, updated_at
        FROM vector_docs
        ORDER BY updated_at DESC
        LIMIT ?;
    """, (limit,))
    rows = cur.fetchall()
    for r in rows:
        print(
            f"- {r['genre_level1']}/{r['genre_level2']} | {r['title']} "
            f"| {r['embedding_status']} | {str(r['version_hash'])[:10]}..."
        )


# ============================================================
# SECTION: CLI / main
# ============================================================

def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--manifest", default="build/manifest.sqlite")
    ap.add_argument("--vectors", default="build/vectors.sqlite")
    ap.add_argument("--limit", type=int, default=20)
    args = ap.parse_args()

    mp = Path(args.manifest)
    vp = Path(args.vectors)

    if mp.exists():
        con = connect(mp)
        show_manifest(con, args.limit)
        con.close()
    else:
        print(f"manifest not found: {mp}")

    if vp.exists():
        con = connect(vp)
        show_vectors(con, args.limit)
        con.close()
    else:
        print(f"vectors not found: {vp}")


# ============================================================
# SECTION: entrypoint
# ============================================================

if __name__ == "__main__":
    main()