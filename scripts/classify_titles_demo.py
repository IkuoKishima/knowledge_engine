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

# --- review thresholds ---
LOW_CONF_TH = 0.60     # ここ未満は低信頼
CLOSE_MARGIN = 1.5     # 1位と2位の点差がこれ未満なら「競り合い」

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
    "オムライス",
    "チキン南蛮",
]

rows = []
for t in titles:
    level1, conf, scores, hits = score_title(t, lens_files)

    needs_review_flag = (conf <= 0.0)
    if needs_review_flag:
        level1 = "未分類"
        reason, hint = review_reason_and_hint(conf, scores, hits)
    else:
        reason, hint = "", ""

    rows.append({
    "title": t,
    "level1": level1,

    # 数値として保持（ロジック用）
    "confidence": float(conf),

    # CSV表示用（従来）
    "confidence_str": f"{conf:.2f}",

    # 既存レビュー機構（残す）
    "needs_review": "1" if needs_review_flag else "0",
    "review_reason": reason,
    "review_hint": hint,

    # 辞書のまま保持・候補抽出用
    "scores_dict": scores,

    # CSV表示用
    "scores": str(scores),

    # 既存
    "hits": "; ".join([f"{h.lens_id}:{h.label}:{h.pattern}({h.weight})" for h in hits]),

    "hits_list": hits,
})
    
def _top2_gap(scores: dict[str, float]):
    items = sorted(scores.items(), key=lambda kv: kv[1], reverse=True)

    if len(items) < 2:
        if len(items) == 1:
            return 0.0, items[0][0], "NA"
        return 0.0, "NA", "NA"

    gap = items[0][1] - items[1][1]
    return gap, items[0][0], items[1][0]


def summarize_row(r: dict) -> str:
    conf = r["confidence"]
    lv1 = r["level1"]
    scores = r["scores_dict"]
    gap, top1, top2 = _top2_gap(scores)
    return f'{r["title"]}\t[{lv1} conf={conf:.2f}] top2_gap={gap:.2f} ({top1} vs {top2}) scores={scores}'

needs_review_rows = []
low_conf_rows = []
close_call_rows = []

for r in rows:
    conf = r["confidence"]
    scores = r["scores_dict"]
    gap, _, _ = _top2_gap(scores)

    # 1) needs_review: 未分類 or conf==0 or hitsが空（あなたのneeds_review設計があるならそれも使える）
    if r["level1"] in ("未分類", "その他") and conf <= 0.01 and len(r["hits_list"]) == 0:
        needs_review_rows.append(r)
    # 既存のneeds_reviewフラグがあるなら優先
    if "needs_review" in r and r["needs_review"] == "1":
        needs_review_rows.append(r)

    # 2) low_conf
    if conf < LOW_CONF_TH:
        low_conf_rows.append(r)

    # 3) close_call（僅差）
    # “全て0” は close_call に入れても意味ないので除外
    if max(scores.values()) > 0 and gap < CLOSE_MARGIN:
        close_call_rows.append(r)

# 重複除去（titleで一意に）
def uniq_by_title(items: list[dict]) -> list[dict]:
    seen = set()
    out = []
    for r in items:
        if r["title"] in seen:
            continue
        seen.add(r["title"])
        out.append(r)
    return out

needs_review_rows = uniq_by_title(needs_review_rows)
low_conf_rows = uniq_by_title(low_conf_rows)
close_call_rows = uniq_by_title(close_call_rows)  

# CSV出力
rows_for_csv = []
for r in rows:
    rr = dict(r)
    
    rr.pop("hits_list", None)
    rr.pop("scores_dict", None)
    
    rr["confidence"] = f'{r["confidence"]:.2f}'
    
    rows_for_csv.append(rr)

csv_path = OUT_DIR / "classified_titles.csv"
with csv_path.open("w", encoding="utf-8", newline="") as f:
    w = csv.DictWriter(f, fieldnames=list(rows_for_csv[0].keys()))
    w.writeheader()
    w.writerows(rows_for_csv)

# --- write candidate files ---
(OUT_DIR / "candidates_needs_review.txt").write_text(
    "\n".join([summarize_row(r) for r in needs_review_rows]),
    encoding="utf-8"
)

(OUT_DIR / "candidates_low_confidence.txt").write_text(
    "\n".join([summarize_row(r) for r in sorted(low_conf_rows, key=lambda x: x["confidence"])]),
    encoding="utf-8"
)

(OUT_DIR / "candidates_close_call.txt").write_text(
    "\n".join([summarize_row(r) for r in close_call_rows]),
    encoding="utf-8"
)

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
print("Wrote:", OUT_DIR / "candidates_needs_review.txt")
print("Wrote:", OUT_DIR / "candidates_low_confidence.txt")
print("Wrote:", OUT_DIR / "candidates_close_call.txt")