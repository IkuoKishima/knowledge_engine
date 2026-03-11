# ============================================================
# FILE: knowledge_engine/lens_engine/classify_level1.py
# DESC: Lens(JSON)のパターンルールを用いて料理タイトル/材料から Level1（和食/洋食/中華/その他）をスコアリングし、best + confidence + hits を返す
#
# DEPENDS:
#   data/lenses/v1/lens_*.json (lens schema: {lens_id,type,targets[{label,items[{patterns,weight}]}]})
#   callers: score_title()/score_record() を利用する各スクリプト
#
# PIPELINE ROLE
#
#   lens JSON (rule + statistical)
#        ↓
#   normalize → regex match → score aggregation  ← このモジュール
#        ↓
#   best label / confidence / scores / hits を上流パイプラインへ返す
#
# ============================================================

from __future__ import annotations

# ============================================================
# SECTION: imports
# ============================================================

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Tuple
import json
import re


# ============================================================
# SECTION: constants
# ============================================================

LABELS_L1 = ["和食", "洋食", "中華", "その他"]


# ============================================================
# SECTION: text normalization / regex helpers
# ============================================================

def normalize_text(s: str) -> str:
    """
    正規化（最小）
    - 前後空白の除去
    - 全角スペース → 半角
    - 連続スペースを1つに
    - 一部記号を統一（〜 → ~）
    """
    s = s.strip()
    s = s.replace("　", " ")
    s = re.sub(r"\s+", " ", s)
    s = s.replace("〜", "~")
    return s


def pattern_to_regex(pat: str) -> re.Pattern:
    """
    レンズパターン → regex
    - 基本は部分一致（re.escape）
    - "~" をワイルドカードとして扱う（任意文字列 ".*"）
    """
    pat = pat.replace("〜", "~")
    if "~" in pat:
        pat = re.escape(pat).replace("\\~", ".*")
        return re.compile(pat)
    return re.compile(re.escape(pat))


# ============================================================
# SECTION: hit model
# ============================================================

@dataclass
class Hit:
    lens_id: str
    label: str
    pattern: str
    weight: float


# ============================================================
# SECTION: lens loader
# ============================================================

def load_lens(path: Path) -> Dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


# ============================================================
# SECTION: scoring core
# ============================================================

def score_record(
    title: str,
    ingredients: List[str],
    lens_files: List[Path],
) -> Tuple[str, float, Dict[str, float], List[Hit]]:
    """
    Return:
      (best_label, confidence, scores_dict, hits)

    - rule系: タイトルに対して patterns を適用
    - statistical系: 材料に対して patterns を適用
    - label="ALL" は global penalty（現状は confidence に加点）として扱う
    """
    title_norm = normalize_text(title)
    scores: Dict[str, float] = {k: 0.0 for k in LABELS_L1}
    hits: List[Hit] = []
    global_penalty = 0.0

    for lf in lens_files:
        lens = load_lens(lf)
        lens_id = lens.get("lens_id", lf.stem)
        lens_type = lens.get("type", "rule")  # "rule" or "statistical"

        for target in lens.get("targets", []):
            label = target.get("label")

            for item in target.get("items", []):
                weight = float(item.get("weight", 0.0))

                for pat in item.get("patterns", []):
                    rx = pattern_to_regex(pat)

                    # --- ① タイトル適用（rule系） ---
                    if lens_type != "statistical":
                        if rx.search(title_norm):
                            if label == "ALL":
                                global_penalty += weight
                                hits.append(Hit(lens_id, "ALL", pat, weight))
                            elif label in scores:
                                scores[label] += weight
                                hits.append(Hit(lens_id, label, pat, weight))

                    # --- ② 材料適用（statistical系） ---
                    else:
                        for ing in ingredients:
                            ing_norm = normalize_text(ing)
                            if rx.search(ing_norm) and label in scores:
                                scores[label] += weight
                                hits.append(Hit(lens_id, label, pat, weight))

    # ========================================================
    # SECTION: best label + confidence
    # ========================================================

    sorted_labels = sorted(scores.keys(), key=lambda k: scores[k], reverse=True)
    best = sorted_labels[0]
    second = sorted_labels[1] if len(sorted_labels) > 1 else "その他"

    # シグナルなし
    if scores[best] <= 0.0:
        return "その他", 0.0, scores, hits

    gap = scores[best] - scores[second]

    # NOTE:
    # confidence は暫定スケール（8.0）で 0..1 に正規化している
    confidence = max(0.0, min(1.0, (gap + global_penalty) / 8.0))

    return best, confidence, scores, hits