#!/usr/bin/env python3
"""
embed_pending.py

- vectors.sqlite の embedding_status='pending' を取得
- (今回はAPI無しなので) ダミー embedding の “メタ情報だけ” 記録
- embedding_status を 'embedded' に更新

※ 現スキーマには embedding 本体のカラムが無いので保存しない
"""

import sqlite3
from pathlib import Path
from datetime import datetime, timezone


VECTORS_DB = Path("build/vectors.sqlite")

DUMMY_MODEL = "dummy-sha256"
DUMMY_DIM = 8  # 将来のembeddingに合わせて変えてもOK


def now_iso():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


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
        # 今は embedding 本体を保存できないため、メタだけ更新する
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


if __name__ == "__main__":
    main()