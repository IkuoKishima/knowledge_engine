## Level1 Classification Flow

1. タイトルを正規化する
2. レンズ辞書を順に適用する
3. 各レンズでスコアリングする
4. 例外・否定で補正する
5. 最大スコアを Level1 とする
6. confidence を算出する

構造の処理は以下のような流れで行われる、いわゆる設計図です。

"""
Level1 Classification Algorithm (conceptual)

1. normalize title
2. score by dishname/method/ingredient lenses
3. apply negative/exception lenses
4. pick best label
5. compute confidence (gap-based)

See DESIGN.md for full rationale.
"""

title_norm = normalize(title)

scores = {"和食":0, "洋食":0, "中華":0, "その他":0}
hits = []   # どのパターンが当たったか（デバッグ用）

for lens in [dishname, method, ingredient, negative_exception]:
  for target in lens.targets:
    label = target.label
    for item in target.items:
      for pat in item.patterns:
        if match(title_norm, pat):
          if label == "ALL":
            # 全体補正：confidenceに効かせる or 後段で扱う
            hits.append((lens_id, "ALL", pat, item.weight))
          else:
            scores[label] += item.weight
            hits.append((lens_id, label, pat, item.weight))

best, second = top2(scores)
gap = scores[best] - scores[second]
confidence = clamp(gap / 8.0, 0, 1)  # 8.0は仮（調整）

if scores[best] <= 0:
  best = "その他"
  confidence = 0.0

return best, confidence, hits


KNOWLEDGE_ENGINE
┣ .venv
┃ ┣ bin
┃ ┗ lib
┣ build
┃ ┣ manifest.sqlite
┃ ┗ vectors.sqlite
┣ data
┃ ┗ lenses
┃ 　┗ v1
┃ 　　　lens_01_dishname.json
┃ 　　　lens_02_method.json
┃ 　　　lens_03_ingredient.json
┃      lens_04_statistical.json
┃ 　　　lens_06_negative_exception.json
┃ 　　　README.md
┣ docs
┃ DESIGN.md
┣ export
┣ input
┃ ┗ json
┃ 　┣ chuka
┃ 　┃ 　chuka_v1.json
┃ 　┣ korean
┃ 　┣ thai
┃ 　┣ washoku
┃ 　┃ 　washoku_v1.json
┃ 　┗ yoshoku
┣ knowledge_engine
┃ ┣ __pycache__
┃ ┗ lens_engine
┃　　　__init__.py
┃　　　classify_level1.py
┃　　　load_lenses.py
┃　　　normalize.py
┃ 　__init__.py
┃ 　cli.py
┃ 　perceptron_demo.py : 初期検証用。現在は未使用（参考実装）
┃ 　rules_classifier.py
┣ output
┃ ┗ demo
┃ 　　classified_titles.csv
┃ 　　index_view_A.txt
┃ 　　index_view_B.txt
┣ schema
┃ 　document_schema.json
┃ 　lens_bundle.schema.v1.json
┗ scripts
　　build_statictical_lens.py
　　classify_titles_demo.py
　　embed_pending.py　
　　index_build.py
　　inspect_db.py
　　vectors_sync.py
.gitignore
README.md

| 層                   | 役割      | 目的              |
| ------------------- | ------- | --------------- |
| ① ルールレンズ            | 明示知識    | 和食・中華などの強い判定    |
| ② 統計レンズ（TF-IDF）     | 一般語除外   | 情報量の少ない語の減衰     |
| ③ 共起レンズ             | 組み合わせ判定 | 「麻婆 × 豆腐」型の意味確定 |
| ④ グラフレンズ（PageRank的） | 構造的重要度  | 中心語の重み          |
| ⑤ 地域レンズ             | 文脈補正    | 四川風・京風など        |
| ⑥ （将来的）コースレンズ       | 構造分類    | 前菜・主菜・酢の物       |
