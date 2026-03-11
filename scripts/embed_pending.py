#!/usr/bin/env python3
# ============================================================
# FILE: scripts/embed_pending.py
# DESC: vectors.sqlite の vector_docs から embedding_status='pending' を拾い、(現段階はAPI無しのため) ダミー埋め込み“メタ情報”だけを記録して embedded に更新する
#
# DEPENDS:
#   build/vectors.sqlite
#   table: vector_docs (doc_id, title, text, embedding_status, embedding_model, embedding_dim, updated_at ...)
#
# PIPELINE ROLE
#
#   manifest.sqlite / docs ingest
#        ↓
#   build/vectors.sqlite : vector_docs (embedding_status='pending')
#        ↓
#   pending を embedded に更新 + embeddingメタ記録  ← このスクリプト
#        ↓
#   次工程: embedder導入時に embedding本体(vector) を別テーブル/別DBへ保存
#
# ============================================================

"""
embed_pending.py

- vectors.sqlite の embedding_status='pending' を取得
- (今回はAPI無しなので) ダミー embedding の “メタ情報だけ” 記録
- embedding_status を 'embedded' に更新

※ 現スキーマには embedding 本体のカラムが無いので保存しない
"""

# ============================================================
# SECTION: imports
# ============================================================

import sqlite3
from pathlib import Path
from datetime import datetime, timezone


# ============================================================
# SECTION: constants
# ============================================================

VECTORS_DB = Path("build/vectors.sqlite")

DUMMY_MODEL = "dummy-sha256"
DUMMY_DIM = 8  # 将来のembeddingに合わせて変えてもOK


# ============================================================
# SECTION: time helper
# ============================================================

def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


# ============================================================
# SECTION: main
# ============================================================

def main():
    conn = sqlite3.connect(VECTORS_DB)
    cur = conn.cursor()

    # pending を取得（あなたのスキーマに合わせる）
    cur.execute("""
        SELECT doc_id, title, text
        FROM vector_docs
        WHERE embedding_status = 'pending'
    """)
    rows = cur.fetchall()

    updated = 0
    ts = now_iso()

    for doc_id, title, text in rows:
        # NOTE:
        # 現スキーマは embedding 本体(vector)を保持しない前提のため、
        # model / dim / updated_at と status のみ更新する。
        cur.execute("""
            UPDATE vector_docs
            SET embedding_status = 'embedded',
                embedding_model = ?,
                embedding_dim = ?,
                updated_at = ?
            WHERE doc_id = ?
        """, (DUMMY_MODEL, DUMMY_DIM, ts, doc_id))
        updated += 1

    conn.commit()
    conn.close()

    print("=== embed_pending summary ===")
    print(f"vectors_db : {VECTORS_DB}")
    print(f"updated    : {updated}")
    print(f"model      : {DUMMY_MODEL}")
    print(f"dim        : {DUMMY_DIM}")
    print(f"ts         : {ts}")


# ============================================================
# SECTION: entrypoint
# ============================================================

if __name__ == "__main__":
    main()