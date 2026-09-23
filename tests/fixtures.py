"""Small synthetic graph with known structures; IDs are fixture-local only."""

import pandas as pd

from moneygraph.io import RawData


def make_fixture_graph():
    nodes = [(1, 0, True), (2, 1, False), (3, 1, False),
             (4, 2, False), (5, 2, False), (6, 4, False),
             (7, 0, True), (8, 2, False), (9, 2, False), (10, 2, False)]
    nodes += [(gid, 0, True) for gid in range(11, 16)]
    nodes += [(gid, 3, False) for gid in range(20, 32)]
    nodes += [(40, 0, True), (41, 0, True), (42, 3, False)]
    nodes += [(gid, 4, False) for gid in range(50, 62)]
    edges = [(1, 2, 100_000), (1, 3, 50_000), (3, 5, 50_000),
             (2, 4, 600_000), (5, 6, 10_000), (8, 9, 20_000),
             (9, 8, 30_000), (8, 10, 10_000), (10, 9, 10_000),
             (40, 41, 5_000), (5, 42, 20_000)]
    edges += [(gid, 2, 100_000) for gid in range(11, 16)]
    edges += [(5, gid, 10_000) for gid in range(20, 32)]
    edges += [(42, gid, 5_000) for gid in range(50, 62)]
    node_df = pd.DataFrame(nodes, columns=["gid", "depth", "is_seed"])
    depth = dict(zip(node_df.gid, node_df.depth))
    edge_df = pd.DataFrame([(u, v, amount, 1, depth[v]) for u, v, amount in edges],
                           columns=["src", "dst", "sum_kzt", "n_tx", "depth"])
    tx_df = pd.DataFrame([(u, v, pd.Timestamp("2026-07-31" if u == 40 else "2026-07-10"), amount)
                          for u, v, amount in edges],
                         columns=["src", "dst", "date", "sum_kzt"])
    return RawData(nodes=node_df, edges=edge_df, tx=tx_df)
