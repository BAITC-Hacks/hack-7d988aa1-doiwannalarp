"""STUB — owned by DEV2. Returns correct-shaped output so the pipeline runs
end to end before real role rules land."""
import pandas as pd

from moneygraph.schemas import ROLE_OUT_COLUMNS


def assign_roles(features_df: pd.DataFrame, G, thresholds=None) -> pd.DataFrame:
    n = len(features_df)
    out = pd.DataFrame({
        "gid": features_df["gid"].values,
        "role": ["peripheral"] * n,
        "role_score": [0.5] * n,
        "secondary_roles": ["[]"] * n,
        "evidence": ["Заглушка"] * n,
        "rule_trace": ["[]"] * n,
    })
    return out[ROLE_OUT_COLUMNS]
