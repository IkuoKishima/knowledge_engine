# ============================================================
# FILE: scripts/build_statictical_lens.py
# DESC: レシピ(title+ingredients)の簡易コーパスからTF-IDF風の重みを計算し、統計レンズ(lens_04_statistical.json)を生成する
#
# DEPENDS:
#   knowledge_engine.lens_engine.classify_level1.score_title()
#   data/lenses/v1/ (出力先)
#
# PIPELINE ROLE
#
#   recipes sample corpus (title + ingredients)
#        ↓
#   ingredient × Level1 の出現統計 → TF-IDF風 weighting  ← このスクリプト
#        ↓
#   data/lenses/v1/lens_04_statistical.json (statistical lens)
#
# ============================================================

# ============================================================
# SECTION: imports
# ============================================================

from collections import defaultdict
import math
import json

from knowledge_engine.lens_engine.classify_level1 import score_title


# ============================================================
# SECTION: sample corpus
# ============================================================

recipes = [
    {"title": "親子丼", "ingredients": ["鶏肉", "卵", "醤油"]},
    {"title": "筑前煮", "ingredients": ["鶏肉", "人参", "醤油"]},
    {"title": "麻婆豆腐", "ingredients": ["豆腐", "豆板醤"]},
    {"title": "青椒肉絲", "ingredients": ["牛肉", "ピーマン"]},
]


# ============================================================
# SECTION: counters (TF/DF)
# ============================================================

counts = defaultdict(lambda: defaultdict(int))  # counts[ingredient][level1] = count
doc_freq = defaultdict(int)                    # doc_freq[ingredient] = docs containing ingredient
total_docs = len(recipes)


# ============================================================
# SECTION: count occurrences
# ============================================================

for r in recipes:
    title = r["title"]

    # NOTE: score_title のシグネチャ次第で lens_files が必要な場合があります。
    # その場合は score_title(title, lens_files) に合わせてください。
    level1, conf, scores, hits = score_title(title)

    seen_in_doc = set()

    for ing in r["ingredients"]:
        counts[ing][level1] += 1
        seen_in_doc.add(ing)

    for ing in seen_in_doc:
        doc_freq[ing] += 1


# ============================================================
# SECTION: build statistical lens (TF-IDF-ish)
# ============================================================

lens_targets = []

for ing, cat_counts in counts.items():
    total = sum(cat_counts.values())

    # IDF（平滑化込み）
    df = doc_freq[ing]
    idf = math.log((total_docs + 1) / (df + 1)) + 1

    # 各カテゴリ向けitemを作成
    per_cat_items = []
    for cat, c in cat_counts.items():
        tf = c / total
        weight = round(tf * idf * 4, 2)

        if weight > 0.3:  # ノイズ除外閾値
            per_cat_items.append({
                "patterns": [ing],
                "weight": weight
            })

    # NOTE:
    # あなたの元コードでは cat は for cat, c... の最後の cat が残り、
    # label が意図せず「最後のカテゴリ」になる可能性が高いです。
    # ここでは「ingredient はカテゴリ別にターゲットを分ける」形に修正し、
    # label=cat のtargetsを作ります（レンズとして自然）。
    for cat, c in cat_counts.items():
        tf = c / total
        weight = round(tf * idf * 4, 2)
        if weight > 0.3:
            lens_targets.append({
                "label": cat,
                "items": [{
                    "patterns": [ing],
                    "weight": weight
                }]
            })


# ============================================================
# SECTION: output JSON
# ============================================================

lens_json = {
    "lens_id": "statistical_v1",
    "type": "statistical",
    "targets": lens_targets
}

out_path = "data/lenses/v1/lens_04_statistical.json"
with open(out_path, "w", encoding="utf-8") as f:
    json.dump(lens_json, f, ensure_ascii=False, indent=2)

print("Statistical lens generated:", out_path)