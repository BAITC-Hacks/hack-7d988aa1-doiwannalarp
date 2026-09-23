import math

import networkx as nx

from moneygraph.io import RawData


def build_graph(raw: RawData) -> nx.DiGraph:
    G = nx.DiGraph()

    for row in raw.nodes.itertuples(index=False):
        G.add_node(row.gid, depth=row.depth, is_seed=row.is_seed)

    self_loops = 0
    for row in raw.edges.itertuples(index=False):
        if row.src == row.dst:
            self_loops += 1
            continue
        G.add_edge(row.src, row.dst, sum_kzt=row.sum_kzt, n_tx=row.n_tx)
    if self_loops:
        print(f"[graph] excluded {self_loops} self-loop edge(s)")

    undirected = nx.Graph()
    undirected.add_nodes_from(G.nodes())
    pair_weight: dict[tuple[int, int], float] = {}
    for u, v, data in G.edges(data=True):
        key = (u, v) if u <= v else (v, u)
        pair_weight[key] = pair_weight.get(key, 0.0) + data["sum_kzt"]
    for (u, v), total in pair_weight.items():
        undirected.add_edge(u, v, w=math.log1p(total))

    G.graph["undirected_weighted"] = undirected
    return G
