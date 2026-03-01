from pathlib import Path
import csv
from knowledge_engine.lens_engine.classify_level1 import score_title

def review_reason_and_hint(conf: float, scores: dict, hits: list):
    """
    未分類(needs_review)の理由を機械的に説明する。
    conf==0 のときのみ意味を持つ想定（ただし他にも使える）
    """
    if hits is None:
        hits = []

    pos = [h for h in hits if getattr(h, "weight", 0) > 0]
    neg = [h for h in hits if getattr(h, "weight", 0) < 0]

    # 短いヒント（最大3件）
    neg_patterns = []
    for h in neg[:3]:
        pat = getattr(h, "pattern", "")
        if pat:
            neg_patterns.append(pat)
    hint = ""
    if neg_patterns:
        hint = "neg:" + ", ".join(neg_patterns)

    # reason 判定
    if len(hits) == 0:
        return "no_hits", ""

    if len(pos) == 0 and len(neg) > 0:
        return "negative_only", hint

    # scores が全部 0以下（実質シグナルなし）
    if scores and max(scores.values()) <= 0:
        return "no_positive_signal", hint

    # ここまで来たら、理由は薄いが一応ヒットはある
    return "uncertain", hint

BASE = Path(__file__).resolve().parents[1]
LENS_DIR = BASE / "data" / "lenses" / "v1"
OUT_DIR = BASE / "output" / "demo"
OUT_DIR.mkdir(parents=True, exist_ok=True)

lens_files = [
    LENS_DIR / "lens_01_dishname.json",
    LENS_DIR / "lens_02_method.json",
    LENS_DIR / "lens_03_ingredient.json",
    LENS_DIR / "lens_06_negative_exception.json",
]

titles = [
    "麻婆豆腐",
    "本格四川風 麻婆豆腐",
    "親子丼",
    "和風パスタ 明太クリーム",
    "回鍋肉",
    "ローストビーフ",
    "ナポリタン",
    "中華風あんかけ焼きそば",
    "筑前煮",
    "グラタン",
    "青椒肉絲",
    "カツ丼",
]

rows = []
for t in titles:
    level1, conf, scores, hits = score_title(t, lens_files)

    needs_review = (conf <= 0.0)
    if needs_review:
        level1 = "未分類"
        reason, hint = review_reason_and_hint(conf, scores, hits)
    else:
        reason, hint = "", ""

    rows.append({
        "title": t,
        "level1": level1,
        "confidence": f"{conf:.2f}",
        "needs_review": "1" if needs_review else "0",
        "review_reason": reason,
        "review_hint": hint,
        "scores": str(scores),
        "hits": "; ".join([f"{h.lens_id}:{h.label}:{h.pattern}({h.weight})" for h in hits])
    })

# CSV出力
csv_path = OUT_DIR / "classified_titles.csv"
with csv_path.open("w", encoding="utf-8", newline="") as f:
    w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
    w.writeheader()
    w.writerows(rows)

# 索引パターンA：ふりがな順の代わりに、まずはtitle順（仮）
index_a = sorted(rows, key=lambda r: r["title"])
(OUT_DIR / "index_view_A.txt").write_text(
    "\n".join([f'{r["title"]}  [{r["level1"]} {r["confidence"]}]' for r in index_a]),
    encoding="utf-8"
)

# 索引パターンB：Level1グループ→title
order = ["和食", "洋食", "中華", "その他", "未分類"]
index_b_lines = []
for g in order:
    grp = [r for r in rows if r["level1"] == g]
    if not grp:
        continue
    index_b_lines.append(f"## {g}")
    for r in sorted(grp, key=lambda x: x["title"]):
        index_b_lines.append(f'- {r["title"]}  ({r["confidence"]})')
    index_b_lines.append("")
(OUT_DIR / "index_view_B.txt").write_text("\n".join(index_b_lines), encoding="utf-8")

print("Wrote:", csv_path)
print("Wrote:", OUT_DIR / "index_view_A.txt")
print("Wrote:", OUT_DIR / "index_view_B.txt")