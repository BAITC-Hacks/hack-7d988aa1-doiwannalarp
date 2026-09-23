"""One-at-a-time role-threshold perturbations and top-20 stability."""

from pathlib import Path

import pandas as pd

from moneygraph import thresholds
from moneygraph.priority import score_priority
from moneygraph.roles import assign_roles


def _ranked(features_df, G, values):
    roles = assign_roles(features_df, G, thresholds=values)
    enriched = features_df.merge(roles, on="gid", how="left")
    priority = score_priority(enriched)
    top = set(priority.sort_values(["priority_score", "gid"], ascending=[False, True])
              .head(20).gid)
    return roles.set_index("gid").role, top


def run(features_df, G) -> pd.DataFrame:
    names = sorted(name for name in vars(thresholds)
                   if name.isupper() and (name.endswith("_MIN") or name.endswith("_STRONG"))
                   and isinstance(getattr(thresholds, name), (int, float)))
    base = {name: getattr(thresholds, name) for name in vars(thresholds)
            if name.isupper()}
    baseline_roles, baseline_top = _ranked(features_df, G, base)
    records = []
    for name in names:
        for factor in (0.75, 1.25):
            changed = dict(base)
            changed[name] = base[name] * factor
            roles, top = _ranked(features_df, G, changed)
            union = baseline_top | top
            records.append({"param": name, "factor": factor,
                            "role_flips": int((roles != baseline_roles).sum()),
                            "top20_jaccard": len(baseline_top & top) / len(union) if union else 1.0})
    result = pd.DataFrame(records, columns=["param", "factor", "role_flips", "top20_jaccard"])
    out = Path("outputs/sensitivity.csv")
    out.parent.mkdir(parents=True, exist_ok=True)
    result.to_csv(out, index=False, encoding="utf-8")
    unstable = sorted(result.loc[result.top20_jaccard < 0.7, "param"].unique())
    print("Sensitivity: top-20 Jaccard < 0.7 for " + (", ".join(unstable) if unstable else "none"))
    return result
