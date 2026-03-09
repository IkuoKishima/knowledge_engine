from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path
import json
import re
from typing import Dict, List, Tuple, Any

LABELS_L1 = ["和食", "洋食", "中華", "その他"]

def normalize_text(s: str) -> str:
    s = s.strip()
    s = s.replace("　", " ")
    s = re.sub(r"\s+", " ", s)
    # 記号は軽く潰す（必要なら増やす）
    s = s.replace("〜", "~")
    return s

def pattern_to_regex(pat: str) -> re.Pattern:
    # 超簡易： "炒" など部分一致。必要になったら単語境界や同義語へ拡張。
    # "〜風" のような表記はそのままでもヒットしにくいので、ここでは "~" をワイルドカード扱いにする例。
    pat = pat.replace("〜", "~")
    if "~" in pat:
        # "~" を任意文字列に
        pat = re.escape(pat).replace("\\~", ".*")
        return re.compile(pat)
    return re.compile(re.escape(pat))

@dataclass
class Hit:
    lens_id: str
    label: str
    pattern: str
    weight: float

def load_lens(path: Path) -> Dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))

def score_record(
    title: str,
    ingredients: List[str],
    lens_files: List[Path]
) -> Tuple[str, float, Dict[str, float], List[Hit]]:

    title_norm = normalize_text(title)
    scores: Dict[str, float] = {k: 0.0 for k in LABELS_L1}
    hits: List[Hit] = []
    global_penalty = 0.0

    for lf in lens_files:
        lens = load_lens(lf)
        lens_id = lens.get("lens_id", lf.stem)
        lens_type = lens.get("type", "rule")

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
                            if rx.search(ing_norm):
                                if label in scores:
                                    scores[label] += weight
                                    hits.append(Hit(lens_id, label, pat, weight))

    sorted_labels = sorted(scores.keys(), key=lambda k: scores[k], reverse=True)
    best = sorted_labels[0]
    second = sorted_labels[1] if len(sorted_labels) > 1 else "その他"

    if scores[best] <= 0.0:
        return "その他", 0.0, scores, hits

    gap = scores[best] - scores[second]
    confidence = max(0.0, min(1.0, (gap + global_penalty) / 8.0))

    return best, confidence, scores, hits