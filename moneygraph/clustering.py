"""Weighted undirected communities and cautious cluster summaries."""

import networkx as nx
import pandas as pd

from moneygraph.schemas import CLUSTERS_COLUMNS


def _internal_sum(G, members):
    return float(sum(d["sum_kzt"] for u, v, d in G.edges(data=True)
                     if u in members and v in members))


def detect_clusters(G, seed=42) -> pd.DataFrame:
    U = G.graph["undirected_weighted"]
    if not U.nodes:
        return pd.DataFrame(columns=["gid", "cluster_id"])
    communities = nx.community.louvain_communities(U, weight="w", resolution=1.0, seed=seed)
    parts = []
    for community in communities:
        parts.extend(set(component) for component in nx.connected_components(U.subgraph(community)))
    multi = [part for part in parts if len(part) > 1]
    single = [part for part in parts if len(part) == 1]
    multi.sort(key=lambda part: (-_internal_sum(G, part), -len(part), min(part)))
    single.sort(key=lambda part: min(part))
    rows = [{"gid": int(gid), "cluster_id": cid}
            for cid, part in enumerate(multi + single, start=1)
            for gid in sorted(part)]
    return pd.DataFrame(rows).sort_values("gid", kind="mergesort").reset_index(drop=True)


def summarize_clusters(enriched_df, G) -> pd.DataFrame:
    rows = []
    for cid, group in enriched_df.groupby("cluster_id", sort=True):
        members = set(group.gid)
        ordered = group.sort_values(["priority_score", "gid"], ascending=[False, True], kind="mergesort")
        top_gid = int(ordered.iloc[0].gid)
        n_seed = int(group.is_seed.sum())
        roles = set(group.role)
        if len(group) == 1 and G.graph["undirected_weighted"].degree(top_gid) == 0:
            hypothesis = "Изолированный узел: нет наблюдаемых переводов >=5 000 KZT"
        elif "coordinator" in roles:
            hypothesis = f"Гипотеза: контур сбора — средства {n_seed} seed сходятся к gid {top_gid}"
        elif "consolidator" in roles and n_seed >= 2:
            hypothesis = f"Гипотеза: сбор средств {n_seed} seed через gid {top_gid}"
        elif "distributor" in roles:
            distributors = set(group.loc[group.role == "distributor", "gid"])
            k = len({v for u, v in G.edges() if u in distributors and v in members})
            hypothesis = f"Гипотеза: веерное распределение от gid {top_gid} на {k} получателей"
        elif (group.role == "transit").mean() >= 0.3:
            hypothesis = "Гипотеза: транзитная цепочка без удержания средств"
        elif (group.role == "boundary").mean() >= 0.5:
            pct = round(100 * (group.role == "boundary").mean())
            hypothesis = f"Ветка на границе выгрузки: {pct}% узлов на 4-м колене"
        else:
            hypothesis = "Периферийная группа без выраженных ролей"
        rows.append({"cluster_id": int(cid), "n_nodes": len(group), "n_seed": n_seed,
                     "sum_kzt_internal": _internal_sum(G, members),
                     "top_gids": ";".join(str(int(gid)) for gid in ordered.gid.head(5)),
                     "hypothesis": hypothesis})
    return pd.DataFrame(rows, columns=CLUSTERS_COLUMNS).sort_values("cluster_id").reset_index(drop=True)
