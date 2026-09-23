"""Explainable, bounded ranking of nodes for analyst review."""

import json

import pandas as pd

from moneygraph import thresholds
from moneygraph.evidence import BANNED
from moneygraph.schemas import ROLE_RU, TOP_COLUMNS, TOP_N, WHY_MAX

ACTIONS = {
    "coordinator": "углублённая проверка, кандидат для запроса в правоохранительные органы",
    "consolidator": "углублённая проверка, кандидат для запроса в правоохранительные органы",
    "distributor": "проверить получателей рассылки",
    "transit": "проследить цепочку до точки консолидации",
    "terminal": "проверить происхождение средств",
    "boundary": "запросить исходящие переводы по узлу",
    "peripheral": "низкий приоритет",
}
LABELS = {"role": "роль", "seed_flow": "поток от seed", "volume": "объём",
          "betweenness": "посредничество"}


def score_priority(enriched_df, weights=None) -> pd.DataFrame:
    w = thresholds.PRIORITY_WEIGHTS if weights is None else weights
    df = enriched_df.sort_values("gid", kind="mergesort").reset_index(drop=True)
    volume = df[["in_sum", "out_sum"]].max(axis=1)
    ranks = {
        "seed_flow": df.seed_flow_in.fillna(0).rank(pct=True, method="average"),
        "volume": volume.fillna(0).rank(pct=True, method="average"),
        "betweenness": df.betweenness.fillna(0).rank(pct=True, method="average"),
    }
    rows = []
    for i, row in df.iterrows():
        role = row.role
        components = {
            "role": float(w["role"] * thresholds.ROLE_WEIGHTS[role] * row.role_score),
            "seed_flow": float(w["seed_flow"] * ranks["seed_flow"].iloc[i]),
            "volume": float(w["volume"] * ranks["volume"].iloc[i]),
            "betweenness": float(w["betweenness"] * ranks["betweenness"].iloc[i]),
        }
        novelty = thresholds.NOVELTY_SEED if bool(row.is_seed) else 1.0
        score = float(novelty * sum(components.values()))
        top2 = sorted(components, key=lambda key: (-components[key], list(components).index(key)))[:2]
        evidence = str(row.evidence).rstrip(". ")
        prefix = ROLE_RU[role] + ": "
        if evidence.startswith(prefix):
            evidence = evidence[len(prefix):]
        why = f"{ROLE_RU[role]}: {evidence}. Драйверы: {', '.join(LABELS[key] for key in top2)}. Действие: {ACTIONS[role]}"
        if len(why) > WHY_MAX:
            why = why[:WHY_MAX - 1] + "…"
        if any(word in why.lower() for word in BANNED):
            raise ValueError("Priority explanation contains a prohibited term")
        rows.append({"gid": int(row.gid), "priority_score": score, "why": why,
                     "priority_components": json.dumps(components, ensure_ascii=False, separators=(",", ":"))})
    return pd.DataFrame(rows, columns=["gid", "priority_score", "why", "priority_components"])


def build_top_nodes(enriched_df, n=TOP_N) -> pd.DataFrame:
    top = enriched_df.sort_values(["priority_score", "gid"], ascending=[False, True],
                                  kind="mergesort").head(n).reset_index(drop=True)
    top.insert(0, "rank", range(1, len(top) + 1))
    return top[TOP_COLUMNS]
