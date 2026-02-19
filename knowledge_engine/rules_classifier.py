from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, List, Set, Tuple


@dataclass(frozen=True)
class ScoreResult:
    label: str
    scores: Dict[str, float]
    confidence: float
    reason_hits: Dict[str, List[str]]  # label -> matched keywords


def _iter_json_files(root: Path) -> Iterable[Path]:
    if not root.exists():
        return []
    return [p for p in root.rglob("*.json") if p.is_file()]


def _normalize_text(s: str) -> str:
    # まずは最小。あとで表記ゆれ対策（全角半角、ひらカタ、英大小など）を追加できる
    return (s or "").strip().lower()


def _extract_keywords(obj) -> Set[str]:
    """
    JSONの構造がまだ揺れていても拾えるように、文字列を“全部回収”する。
    - dict/list を再帰的に走査して、文字列を keywords として集める
    """
    out: Set[str] = set()

    def walk(x):
        if x is None:
            return
        if isinstance(x, str):
            t = _normalize_text(x)
            if t:
                out.add(t)
            return
        if isinstance(x, dict):
            for k, v in x.items():
                # key も一応拾う（タグ名が重要なケースがある）
                if isinstance(k, str):
                    tk = _normalize_text(k)
                    if tk:
                        out.add(tk)
                walk(v)
            return
        if isinstance(x, list):
            for it in x:
                walk(it)
            return
        # 数値などは無視

    walk(obj)
    return out


def load_label_keywords(input_json_root: Path) -> Dict[str, Set[str]]:
    """
    input/json 配下を想定。
    例:
      input/json/chuka/*.json  -> label "chuka"
      input/json/washoku/*.json -> label "washoku"
    """
    label_to_keywords: Dict[str, Set[str]] = {}

    # 直下のフォルダ名を label として扱う（最小運用）
    # input/json/<label>/**.json を読む
    for label_dir in sorted([p for p in input_json_root.iterdir() if p.is_dir()]):
        label = label_dir.name
        kws: Set[str] = set()
        for jf in _iter_json_files(label_dir):
            try:
                obj = json.loads(jf.read_text(encoding="utf-8"))
            except Exception:
                continue
            kws |= _extract_keywords_v1(obj)
        # ノイズ減らし（短すぎる単語は一旦捨てる。後で調整OK）
        kws = {k for k in kws if len(k) >= 2}
        label_to_keywords[label] = kws

    return label_to_keywords


def score_text(
    text: str,
    label_keywords: Dict[str, Set[str]],
) -> Tuple[Dict[str, float], Dict[str, List[str]]]:
    """
    超シンプルなスコア:
      - 各labelについて「含まれていたキーワード数」を数える
      - 正規化して0..1に丸める（辞書の大きさ差の影響を弱める）
    """
    t = _normalize_text(text)

    scores: Dict[str, float] = {}
    hits: Dict[str, List[str]] = {}

    for label, kws in label_keywords.items():
        matched = [kw for kw in kws if kw and (kw in t)]
        hits[label] = matched[:50]  # 理由表示の上限
        # マッチ数を辞書サイズで割ってスケールを揃える（最小）
        denom = max(len(kws), 1)
        scores[label] = len(matched) / denom

    return scores, hits


def predict(
    title: str,
    ingredients: str | None,
    label_keywords: Dict[str, Set[str]],
    unsure_margin: float = 0.10,
    min_conf: float = 0.02,
) -> ScoreResult:
    """
    - title + ingredients をまとめてスコアリング
    - 1位と2位の差が小さい or そもそもスコアが低い -> 要確認
    """
    combined = title if ingredients is None else (title + " " + ingredients)

    scores, hits = score_text(combined, label_keywords)

    ranked = sorted(scores.items(), key=lambda x: x[1], reverse=True)
    best_label, best_score = ranked[0]
    second_score = ranked[1][1] if len(ranked) > 1 else 0.0

    confidence = best_score - second_score  # 差分を“自信度”として使う（最小）
    if best_score < min_conf or confidence < unsure_margin:
        return ScoreResult(label="needs_review", scores=scores, confidence=confidence, reason_hits=hits)

    return ScoreResult(label=best_label, scores=scores, confidence=confidence, reason_hits=hits)

def _extract_keywords_v1(obj) -> Set[str]:
    """
    recipe_knowledge.v1 の想定構造から、必要な語だけ抽出する。
    """
    out: Set[str] = set()
    if not isinstance(obj, dict):
        return out

    records = obj.get("records", [])
    if not isinstance(records, list):
        return out

    for r in records:
        if not isinstance(r, dict):
            continue

        title = r.get("title")
        if isinstance(title, str):
            out.add(_normalize_text(title))

        kws = r.get("keywords", [])
        if isinstance(kws, list):
            for k in kws:
                if isinstance(k, str):
                    out.add(_normalize_text(k))

        exs = r.get("examples", [])
        if isinstance(exs, list):
            for e in exs:
                if isinstance(e, str):
                    out.add(_normalize_text(e))

    # ノイズ除去
    out = {k for k in out if k and len(k) >= 2}
    return out