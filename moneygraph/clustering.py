"""STUB — owned by DEV2. Weakly-connected-component clustering placeholder
so the pipeline runs end to end before Louvain clustering lands."""
import networkx as nx
import pandas as pd

from moneygraph.schemas import CLUSTERS_COLUMNS


def detect_clusters(G: nx.DiGraph, seed: int = 42) -> pd.DataFrame:
    rows = []
    for wcc_id, comp in enumerate(sorted(nx.weakly_connected_components(G), key=lambda c: min(c)), start=1):
        for gid in comp:
            rows.append({"gid": gid, "cluster_id": wcc_id})
    return pd.DataFrame(rows).sort_values("gid").reset_index(drop=True)


def summarize_clusters(enriched_df: pd.DataFrame, G: nx.DiGraph) -> pd.DataFrame:
    rows = []
    for cluster_id, grp in enriched_df.groupby("cluster_id"):
        rows.append({
            "cluster_id": cluster_id,
            "n_nodes": len(grp),
            "n_seed": int(grp["is_seed"].sum()),
            "sum_kzt_internal": 0.0,
            "top_gids": ";".join(str(g) for g in grp.sort_values("gid")["gid"].head(5)),
            "hypothesis": "Заглушка",
        })
    out = pd.DataFrame(rows).sort_values("cluster_id").reset_index(drop=True)
    return out[CLUSTERS_COLUMNS]
