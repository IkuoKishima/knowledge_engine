from __future__ import annotations

import argparse
from pathlib import Path

from .rules_classifier import load_label_keywords, predict


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("title", help="recipe title")
    ap.add_argument("--ingredients", default=None, help="ingredients text (optional)")
    ap.add_argument("--root", default="input/json", help="input/json root path")
    args = ap.parse_args()

    root = Path(args.root)
    label_keywords = load_label_keywords(root)

    res = predict(
        title=args.title,
        ingredients=args.ingredients,
        label_keywords=label_keywords,
    )

    print("\n== RESULT ==")
    print("label      :", res.label)
    print("confidence :", f"{res.confidence:.4f}")
    print("\n== SCORES ==")
    for k, v in sorted(res.scores.items(), key=lambda x: x[1], reverse=True):
        print(f"{k:12s} {v:.6f}")

    print("\n== HITS (top) ==")
    # 上位2ラベルだけ理由を出す
    top2 = [k for k, _ in sorted(res.scores.items(), key=lambda x: x[1], reverse=True)[:2]]
    for lab in top2:
        hs = res.reason_hits.get(lab, [])[:20]
        print(f"- {lab}: {hs}")


if __name__ == "__main__":
    main()