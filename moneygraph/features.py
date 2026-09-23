import networkx as nx
import numpy as np
import pandas as pd

from moneygraph.io import RawData
from moneygraph.schemas import FEATURES_COLUMNS


def _seed_reach_sets(G: nx.DiGraph, seeds: list[int]) -> dict[int, frozenset[int]]:
    """S(v): seeds with a directed path to v, excluding v itself."""
    reach: dict[int, set[int]] = {gid: set() for gid in G.nodes}
    for s in seeds:
        for v in nx.descendants(G, s):
            reach[v].add(s)
    return {gid: frozenset(s) for gid, s in reach.items()}


def _flow_propagation(G: nx.DiGraph, seeds: set[int], out_sum: dict, in_sum: dict) -> dict[int, float]:
    def edge_sum(u, v):
        return G[u][v]["sum_kzt"]

    flow_out = {gid: (out_sum.get(gid, 0.0) if gid in seeds else 0.0) for gid in G.nodes}
    flow_in = {gid: 0.0 for gid in G.nodes}

    def recompute(order):
        for v in order:
            preds = list(G.predecessors(v))
            fi = 0.0
            for u in preds:
                ou = out_sum.get(u, 0.0)
                if ou > 0:
                    fi += flow_out[u] * edge_sum(u, v) / ou
            flow_in[v] = fi
            if v not in seeds:
                iv = in_sum.get(v, 0.0)
                flow_out[v] = fi * min(1.0, out_sum.get(v, 0.0) / iv) if iv > 0 else 0.0

    if nx.is_directed_acyclic_graph(G):
        recompute(list(nx.topological_sort(G)))
    else:
        order = sorted(G.nodes)
        prev_in = dict(flow_in)
        for _ in range(50):
            recompute(order)
            max_delta = max((abs(flow_in[v] - prev_in[v]) for v in order), default=0.0)
            prev_in = dict(flow_in)
            if max_delta < 1.0:
                break

    return flow_in


def compute_features(G: nx.DiGraph, raw: RawData) -> pd.DataFrame:
    gids = sorted(G.nodes)
    seeds = {gid for gid, d in G.nodes(data=True) if d.get("is_seed")}
    depth = {gid: d.get("depth", 0) for gid, d in G.nodes(data=True)}

    in_deg = dict(G.in_degree())
    out_deg = dict(G.out_degree())
    seed_payers = {gid: sum(1 for u in G.predecessors(gid) if u in seeds) for gid in gids}

    in_sum = {gid: 0.0 for gid in gids}
    out_sum = {gid: 0.0 for gid in gids}
    in_tx = {gid: 0 for gid in gids}
    out_tx = {gid: 0 for gid in gids}
    for u, v, d in G.edges(data=True):
        out_sum[u] += d["sum_kzt"]
        in_sum[v] += d["sum_kzt"]
        out_tx[u] += d["n_tx"]
        in_tx[v] += d["n_tx"]

    reach = _seed_reach_sets(G, sorted(seeds))
    seed_reach = {gid: len(reach[gid]) for gid in gids}

    def seed_set_with_self(u):
        s = reach[u]
        return (s | {u}) if u in seeds else s

    feeder_branches = {}
    convergence_gain = {}
    for v in gids:
        preds = list(G.predecessors(v))
        feeder_branches[v] = sum(1 for u in preds if len(seed_set_with_self(u)) >= 2)
        if preds:
            best = max(len(seed_set_with_self(u) - {v}) for u in preds)
        else:
            best = 0
        convergence_gain[v] = seed_reach[v] - best

    flow_in = _flow_propagation(G, seeds, out_sum, in_sum)

    returns_to_seed = {gid: any(d in seeds for d in nx.descendants(G, gid)) for gid in gids}

    in_cycle_nodes: set[int] = set()
    for cyc in nx.simple_cycles(G, length_bound=4):
        in_cycle_nodes.update(cyc)

    in_2cycle = {gid: any(G.has_edge(gid, u) for u in G.predecessors(gid)) for gid in gids}

    betweenness = nx.betweenness_centrality(G, normalized=True)

    wcc_id = {}
    wcc_size = {}
    for i, comp in enumerate(sorted(nx.weakly_connected_components(G), key=min), start=1):
        for gid in comp:
            wcc_id[gid] = i
            wcc_size[gid] = len(comp)

    layout = nx.spring_layout(G.graph["undirected_weighted"], seed=42)

    rows = []
    for gid in gids:
        i_sum = in_sum[gid]
        o_sum = out_sum[gid]
        is_seed = gid in seeds
        d = depth[gid]
        censored = bool(d == 4 and out_deg.get(gid, 0) == 0)
        pos = layout.get(gid, (0.0, 0.0))
        rows.append({
            "gid": gid,
            "depth": d,
            "is_seed": is_seed,
            "in_deg": in_deg.get(gid, 0),
            "out_deg": out_deg.get(gid, 0),
            "seed_payers": seed_payers[gid],
            "in_sum": i_sum,
            "out_sum": o_sum,
            "in_tx": in_tx[gid],
            "out_tx": out_tx[gid],
            "flow_diff": i_sum - o_sum,
            "pass_ratio": np.nan if (is_seed or i_sum == 0) else o_sum / i_sum,
            "out_observable": bool(d <= 3),
            "censored": censored,
            "inflow_incomplete": bool(is_seed or o_sum > 1.2 * i_sum),
            "seed_reach": seed_reach[gid],
            "feeder_branches": feeder_branches[gid],
            "convergence_gain": convergence_gain[gid],
            "seed_flow_in": flow_in[gid],
            "returns_to_seed": bool(returns_to_seed[gid]),
            "in_cycle": gid in in_cycle_nodes,
            "in_2cycle": bool(in_2cycle[gid]),
            "betweenness": betweenness.get(gid, 0.0),
            "wcc_id": wcc_id[gid],
            "wcc_size": wcc_size[gid],
            "x": float(pos[0]),
            "y": float(pos[1]),
        })

    df = pd.DataFrame(rows)
    # temporal columns are filled in by moneygraph.temporal.add_temporal
    for col in ["max_payers_same_day", "max_payers_date", "max_payers_3d",
                "fast_through_share", "late_inflow_share", "first_date", "last_date"]:
        df[col] = np.nan
    return df[FEATURES_COLUMNS]
