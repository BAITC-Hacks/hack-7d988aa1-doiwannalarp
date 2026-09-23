"""STUB — owned by DEV2. Proportional-rank placeholder priority scoring so
the pipeline runs end to end before the real weighted score lands."""
import pandas as pd

from moneygraph.schemas import TOP_COLUMNS, TOP_N


def score_priority(enriched_df: pd.DataFrame, weights=None) -> pd.DataFrame:
    turnover = enriched_df[["in_sum", "out_sum"]].max(axis=1)
    priority_score = turnover.rank(pct=True, method="average").fillna(0.0)
    why = ["Заглушка"] * len(enriched_df)
    return pd.DataFrame({
        "gid": enriched_df["gid"].values,
        "priority_score": priority_score.values,
        "why": why,
        "priority_components": ["{}"] * len(enriched_df),
    })


def build_top_nodes(enriched_df: pd.DataFrame, n: int = TOP_N) -> pd.DataFrame:
    top = enriched_df.sort_values(
        ["priority_score", "gid"], ascending=[False, True]
    ).head(n).reset_index(drop=True)
    top.insert(0, "rank", range(1, len(top) + 1))
    return top[TOP_COLUMNS]
