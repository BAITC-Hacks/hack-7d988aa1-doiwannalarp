import networkx as nx
import pandas as pd


def simulate(G: nx.DiGraph, enriched_df: pd.DataFrame) -> pd.DataFrame:
    def wcc_stats(graph: nx.DiGraph) -> tuple[int, int, dict]:
        comps = list(nx.weakly_connected_components(graph))
        if not comps:
            return 0, 0, {}
        largest = max(comps, key=len)
        roles_in_largest = enriched_df.loc[
            enriched_df["gid"].isin(largest), "role"
        ].value_counts().to_dict()
        return len(comps), len(largest), {str(k): int(v) for k, v in roles_in_largest.items()}

    by_priority = enriched_df.sort_values(["priority_score", "gid"], ascending=[False, True])["gid"].tolist()
    by_degree = sorted(G.nodes, key=lambda g: (-(G.in_degree(g) + G.out_degree(g)), g))
    seeds = enriched_df.loc[enriched_df["is_seed"], "gid"].tolist()

    strategies: list[tuple[str, list]] = []
    for n in (5, 10, 20):
        strategies.append((f"top_priority_{n}", by_priority[:n]))
    for n in (5, 10, 20):
        strategies.append((f"top_degree_{n}", by_degree[:n]))
    strategies.append(("all_seeds", seeds))

    rows = []
    for strategy, removed in strategies:
        H = G.copy()
        H.remove_nodes_from(removed)
        n_components, largest_wcc, role_nodes = wcc_stats(H)
        rows.append({
            "strategy": strategy,
            "n_removed": len(removed),
            "n_components": n_components,
            "largest_wcc": largest_wcc,
            "role_nodes_in_largest_wcc": role_nodes,
        })
    return pd.DataFrame(rows)


def run(G, enriched_df, raw=None) -> pd.DataFrame:
    return simulate(G, enriched_df)
