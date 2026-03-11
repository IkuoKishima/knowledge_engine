#!/usr/bin/env python3
# ============================================================
# FILE: knowledge_engine/perceptron_demo.py
# DESC: 最小の“学習っぽさ”を体感するためのデモ（タイトル→手作り特徴量→簡易ロジスティック回帰風で「中華か？」を学習）
#
# DEPENDS:
#   numpy
#
# PIPELINE ROLE
#
#   tiny labeled titles (manual)
#        ↓
#   featurize_title() → (X, y)
#        ↓
#   sigmoid + BCE gradient descent (toy training)  ← このスクリプト
#        ↓
#   learned weights の可視化 + 予測テスト
#
# STATUS:
#   demo / reference (本番パイプライン未使用)
#
# ============================================================

from __future__ import annotations

# ============================================================
# SECTION: imports
# ============================================================

import numpy as np


# ============================================================
# SECTION: math helpers
# ============================================================

def sigmoid(x: np.ndarray) -> np.ndarray:
    """Sigmoid activation."""
    return 1.0 / (1.0 + np.exp(-x))


# ============================================================
# SECTION: feature extraction (title -> vector)
# ============================================================

def featurize_title(title: str) -> tuple[np.ndarray, list[str]]:
    """
    Very small handmade feature extractor.
    This is intentionally simple so you can "see" weights move.

    Return:
      x: shape (D,)
      names: feature names (keep in sync with vector)
    """
    # NOTE: keep raw title for matching (Japanese chars). We lower() for any ASCII.
    _t = title.strip().lower()

    names = [
        "has_kanji_like",   # rough: contains any CJK range char
        "has_ma",           # contains '麻'
        "has_douban",       # contains '豆板' or '豆瓣'
        "has_huiguo",       # contains '回鍋' or '回锅'
        "has_chinjao",      # contains '青椒' or 'チンジャオ'
        "has_miso",         # contains '味噌'
        "has_dashi",        # contains 'だし' or '出汁'
    ]

    def has_cjk(s: str) -> bool:
        # Rough CJK check (kanji/hiragana/katakana)
        return any(
            ("\u3040" <= ch <= "\u30ff") or ("\u4e00" <= ch <= "\u9fff")
            for ch in s
        )

    x = np.array(
        [
            1.0 if has_cjk(title) else 0.0,
            1.0 if ("麻" in title) else 0.0,
            1.0 if ("豆板" in title or "豆瓣" in title) else 0.0,
            1.0 if ("回鍋" in title or "回锅" in title) else 0.0,
            1.0 if ("青椒" in title or "チンジャオ" in title) else 0.0,
            1.0 if ("味噌" in title) else 0.0,
            1.0 if ("だし" in title or "出汁" in title) else 0.0,
        ],
        dtype=np.float64,
    )

    return x, names


# ============================================================
# SECTION: training (toy logistic regression)
# ============================================================

def train_demo(seed: int = 42) -> tuple[np.ndarray, float, list[str]]:
    """
    Train a tiny logistic-regression-like model (sigmoid + gradient descent).

    Output:
      weights (D,), bias (scalar), feature_names (list[str])
    """
    rng = np.random.default_rng(seed)

    # Tiny training set: (title, y) where y=1 means "CHUKA"
    data = [
        ("回鍋肉", 1),
        ("麻婆豆腐", 1),
        ("青椒肉絲", 1),
        ("酢豚", 1),
        ("味噌汁", 0),
        ("だし巻き卵", 0),
        ("鮭の塩焼き", 0),
        ("豚の生姜焼き", 0),
    ]

    X_list: list[np.ndarray] = []
    y_list: list[float] = []
    feat_names: list[str] | None = None

    for title, y in data:
        x, names = featurize_title(title)
        if feat_names is None:
            feat_names = names
        X_list.append(x)
        y_list.append(float(y))

    assert feat_names is not None

    X = np.stack(X_list, axis=0)             # (N, D)
    y = np.array(y_list, dtype=np.float64)   # (N,)
    N, D = X.shape

    # Initialize weights small random, bias 0
    w = rng.normal(loc=0.0, scale=0.1, size=(D,))
    b = 0.0

    lr = 0.3
    steps = 200

    def predict_proba(Xb: np.ndarray) -> np.ndarray:
        return sigmoid(Xb @ w + b)

    for step in range(1, steps + 1):
        p = predict_proba(X)                 # (N,)

        # Binary cross-entropy gradient
        # dL/dz = (p - y) for sigmoid + BCE
        dz = (p - y)                         # (N,)
        dw = (X.T @ dz) / N                  # (D,)
        db = float(np.mean(dz))              # scalar

        w -= lr * dw
        b -= lr * db

        if step in (1, 2, 3, 5, 10, 20, 50, 100, 200):
            loss = -np.mean(
                y * np.log(p + 1e-12) + (1 - y) * np.log(1 - p + 1e-12)
            )
            acc = float(np.mean((p >= 0.5) == (y >= 0.5)))
            print(f"[step {step:3d}] loss={loss:.4f} acc={acc:.3f}  b={b:+.3f}")

    return w, b, feat_names


# ============================================================
# SECTION: reporting / prediction
# ============================================================

def pretty_weights(w: np.ndarray, feat_names: list[str]) -> None:
    pairs = list(zip(feat_names, w.tolist()))
    pairs.sort(key=lambda x: abs(x[1]), reverse=True)
    print("\n== learned weights (sorted by |weight|) ==")
    for name, val in pairs:
        print(f"{name:14s} {val:+.4f}")


def predict(title: str, w: np.ndarray, b: float, feat_names: list[str]) -> None:
    x, names = featurize_title(title)
    assert names == feat_names

    p = float(sigmoid(x @ w + b))
    label = "中華(Chuka)" if p >= 0.5 else "非中華(Other)"

    print(f"\n[Predict] title='{title}' -> p(chuka)={p:.3f} => {label}")

    # evidence: show which features fired
    fired = [feat_names[i] for i, v in enumerate(x.tolist()) if v > 0.5]
    print("evidence(features fired):", fired if fired else "(none)")


# ============================================================
# SECTION: entrypoint
# ============================================================

def main() -> None:
    w, b, feat_names = train_demo()
    pretty_weights(w, feat_names)

    tests = [
        "回鍋肉",
        "麻婆茄子",
        "チンジャオロース",
        "味噌ラーメン",
        "だしカレー",
        "酢豚",
        "照り焼きチキン",
    ]
    for t in tests:
        predict(t, w, b, feat_names)


if __name__ == "__main__":
    main()