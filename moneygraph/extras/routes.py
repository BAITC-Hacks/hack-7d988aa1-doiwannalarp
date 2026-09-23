import networkx as nx
import pandas as pd


def find(G: nx.DiGraph, tx_df: pd.DataFrame, enriched_df: pd.DataFrame) -> pd.DataFrame:
    tx = tx_df.copy()
    tx["date"] = pd.to_datetime(tx["date"]).dt.normalize()
    last_date = tx.groupby(["src", "dst"])["date"].max()
    first_date = tx.groupby(["src", "dst"])["date"].min()

    transit_nodes = set(enriched_df.loc[enriched_df["role"] == "transit", "gid"])

    rows = []
    # ponytail: only 2-hop u->transit->w chains, not full multi-hop route search;
    # extend to longer chains if the analyst needs deeper tracing.
    for t in sorted(transit_nodes):
        for u in G.predecessors(t):
            for w in G.successors(t):
                if u == w:
                    continue
                if (u, t) not in last_date.index or (t, w) not in first_date.index:
                    continue
                gap = (first_date[(t, w)] - last_date[(u, t)]).days
                if 0 <= gap <= 2:
                    leg1 = G[u][t]["sum_kzt"]
                    leg2 = G[t][w]["sum_kzt"]
                    rows.append({
                        "path": f"{u}->{t}->{w}",
                        "kind": "transit_chain",
                        "min_leg_kzt": round(min(leg1, leg2), 4),
                        "days_span": gap,
                        "n_occurrences": 1,
                    })

    for cyc in nx.simple_cycles(G, length_bound=4):
        edges_kzt = [G[cyc[i]][cyc[(i + 1) % len(cyc)]]["sum_kzt"] for i in range(len(cyc))]
        path = "->".join(str(g) for g in cyc) + f"->{cyc[0]}"
        rows.append({
            "path": path,
            "kind": "cycle",
            "min_leg_kzt": round(min(edges_kzt), 4),
            "days_span": None,
            "n_occurrences": 1,
        })

    if not rows:
        return pd.DataFrame(columns=["path", "kind", "min_leg_kzt", "days_span", "n_occurrences"])
    return pd.DataFrame(rows).sort_values(["kind", "path"]).reset_index(drop=True)


def run(G, enriched_df, raw) -> pd.DataFrame:
    return find(G, raw.tx, enriched_df)
