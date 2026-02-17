#!/usr/bin/env python3
from __future__ import annotations

import argparse
import sqlite3
from pathlib import Path

def connect(path: Path) -> sqlite3.Connection:
  con = sqlite3.connect(path)
  con.row_factory = sqlite3.Row
  return con

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
    print(f"- {r['genre_level1']}/{r['genre_level2']} | {r['title']} | del={r['is_deleted']} | {str(r['version_hash'])[:10]}...")

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
    print(f"- {r['genre_level1']}/{r['genre_level2']} | {r['title']} | {r['embedding_status']} | {str(r['version_hash'])[:10]}...")

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

if __name__ == "__main__":
  main()
