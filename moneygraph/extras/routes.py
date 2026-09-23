import networkx as nx
import pandas as pd


def find(G: nx.DiGraph, tx_df: pd.DataFrame, enriched_df: pd.DataFrame) -> pd.DataFrame:
    """Find compatible daily pairs, not provenance of particular funds.

    Count distinct (incoming date, outgoing date) pairs per path and kind.
    Same-day pairs have unknown ordering. Structural cycles have no temporal
    occurrence count. Amounts are daily observations, never traced funds.
    """
    tx = tx_df.copy()
    tx["date"] = pd.to_datetime(tx["date"]).dt.normalize()
    daily = tx.groupby(["src", "dst", "date"], sort=True)["sum_kzt"].sum()
    by_edge = {}
    for (src, dst, date), amount in daily.items():
        by_edge.setdefault((src, dst), {})[date] = amount

    transit_nodes = set(enriched_df.loc[enriched_df["role"] == "transit", "gid"])

    rows = []
    # Bounded two-hop search; three outgoing-date lookups per incoming date.
    for t in sorted(transit_nodes):
        for u in sorted(G.predecessors(t)):
            for w in sorted(G.successors(t)):
                if u == w:
                    continue
                incoming = by_edge.get((u, t), {})
                outgoing = by_edge.get((t, w), {})
                matches = {}
                for date, leg1 in incoming.items():
                    for gap in (0, 1, 2):
                        leg2 = outgoing.get(date + pd.Timedelta(days=gap))
                        if leg2 is None:
                            continue
                        kind = "same_day_candidate" if gap == 0 else "transit_chain"
                        matches.setdefault(kind, []).append((gap, min(leg1, leg2)))
                for kind, pairs in sorted(matches.items()):
                    rows.append({
                        "path": f"{u}->{t}->{w}",
                        "kind": kind,
                        "min_leg_kzt": round(max(amount for _, amount in pairs), 4),
                        "days_span": min(gap for gap, _ in pairs),
                        "n_occurrences": len(pairs),
                    })

    for cyc in nx.simple_cycles(G, length_bound=4):
        if len(cyc) < 2:
            continue
        # Canonical rotation makes cycle paths independent of graph insertion order.
        start = cyc.index(min(cyc))
        cyc = cyc[start:] + cyc[:start]
        edges_kzt = [G[cyc[i]][cyc[(i + 1) % len(cyc)]]["sum_kzt"] for i in range(len(cyc))]
        path = "->".join(str(g) for g in cyc) + f"->{cyc[0]}"
        rows.append({
            "path": path,
            "kind": "structural_cycle",
            "min_leg_kzt": round(min(edges_kzt), 4),
            "days_span": None,
            "n_occurrences": None,
        })

    if not rows:
        return pd.DataFrame(columns=["path", "kind", "min_leg_kzt", "days_span", "n_occurrences"])
    result = pd.DataFrame(rows).sort_values(["kind", "path"]).reset_index(drop=True)
    result["days_span"] = result["days_span"].astype("Int64")
    result["n_occurrences"] = result["n_occurrences"].astype("Int64")
    return result


def run(G, enriched_df, raw) -> pd.DataFrame:
    return find(G, raw.tx, enriched_df)
