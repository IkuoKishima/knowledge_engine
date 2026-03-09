from collections import defaultdict
import math
import json

from knowledge_engine.lens_engine.classify_level1 import score_title

recipes = [
    {"title": "親子丼", "ingredients": ["鶏肉","卵","醤油"]},
    {"title": "筑前煮", "ingredients": ["鶏肉","人参","醤油"]},
    {"title": "麻婆豆腐", "ingredients": ["豆腐","豆板醤"]},
    {"title": "青椒肉絲", "ingredients": ["牛肉","ピーマン"]},
]

counts = defaultdict(lambda: defaultdict(int))
doc_freq = defaultdict(int)
total_docs = len(recipes)

# --- カウント ---
for r in recipes:

    title = r["title"]
    level1, conf, scores, hits = score_title(title)

    seen_in_doc = set()

    for ing in r["ingredients"]:
        counts[ing][level1] += 1
        seen_in_doc.add(ing)

    for ing in seen_in_doc:
        doc_freq[ing] += 1

# --- 統計レンズ生成 ---
lens_targets = []

for ing, cat_counts in counts.items():

    total = sum(cat_counts.values())

    # IDF
    df = doc_freq[ing]
    idf = math.log((total_docs + 1) / (df + 1)) + 1

    items = []

    for cat, c in cat_counts.items():
        tf = c / total
        weight = round(tf * idf * 4, 2)

        if weight > 0.3:  # ノイズ除外閾値
            items.append({
                "patterns": [ing],
                "weight": weight
            })

    if items:
        lens_targets.append({
            "label": cat,
            "items": items
        })

lens_json = {
    "lens_id": "statistical_v1",
    "type": "statistical",
    "targets": lens_targets
}

with open("data/lenses/v1/lens_04_statistical.json", "w", encoding="utf-8") as f:
    json.dump(lens_json, f, ensure_ascii=False, indent=2)

print("Statistical lens generated.")