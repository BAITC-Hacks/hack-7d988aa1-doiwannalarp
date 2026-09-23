from dataclasses import dataclass
from pathlib import Path

import pandas as pd

from moneygraph.schemas import CLUSTERS_COLUMNS, DataError, ENRICHED_COLUMNS, TOP_COLUMNS

REQUIRED_COLUMNS = {
    "nodes": {"gid": "int64", "depth": "int64", "is_seed": "bool"},
    "edges": {"src": "int64", "dst": "int64", "sum_kzt": "float64", "n_tx": "int64", "depth": "int64"},
    "transactions": {"src": "int64", "dst": "int64", "date": "datetime64[ns]", "sum_kzt": "float64"},
}


@dataclass
class RawData:
    nodes: pd.DataFrame
    edges: pd.DataFrame
    tx: pd.DataFrame


def _load_one(data_dir: Path, name: str) -> pd.DataFrame:
    path = data_dir / f"{name}.parquet"
    if not path.exists():
        raise DataError(f"missing required file: {path}")
    df = pd.read_parquet(path)
    missing = set(REQUIRED_COLUMNS[name]) - set(df.columns)
    if missing:
        raise DataError(f"{name}.parquet missing required columns: {sorted(missing)}")
    return df


def load_raw(data_dir: str | Path) -> RawData:
    data_dir = Path(data_dir)
    nodes = _load_one(data_dir, "nodes")
    edges = _load_one(data_dir, "edges")
    tx = _load_one(data_dir, "transactions")

    nodes = nodes.astype({"gid": "int64", "depth": "int64", "is_seed": "bool"})
    edges = edges.astype({"src": "int64", "dst": "int64", "sum_kzt": "float64",
                           "n_tx": "int64", "depth": "int64"})
    tx = tx.astype({"src": "int64", "dst": "int64", "sum_kzt": "float64"})
    tx["date"] = pd.to_datetime(tx["date"])

    return RawData(nodes=nodes, edges=edges, tx=tx)


def _prepare(df: pd.DataFrame, columns: list[str]) -> pd.DataFrame:
    out = df[columns].copy()
    for col in out.columns:
        if pd.api.types.is_float_dtype(out[col]):
            out[col] = out[col].round(4)
    return out.sort_values(out.columns[0] if "gid" not in out.columns else "gid")


def write_outputs(enriched: pd.DataFrame, clusters: pd.DataFrame, top: pd.DataFrame, out_dir: str | Path) -> dict:
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    nodes_roles_cols = ["gid", "role", "role_score", "cluster_id", "priority_score", "evidence"]
    nodes_roles = _prepare(enriched, nodes_roles_cols)
    clusters_out = clusters[CLUSTERS_COLUMNS].copy().sort_values("cluster_id")
    for col in clusters_out.select_dtypes("float").columns:
        clusters_out[col] = clusters_out[col].round(4)
    top_out = top[TOP_COLUMNS].copy().sort_values("rank")
    for col in top_out.select_dtypes("float").columns:
        top_out[col] = top_out[col].round(4)

    paths = {
        "nodes_roles": out_dir / "nodes_roles.csv",
        "clusters": out_dir / "clusters.csv",
        "top_nodes": out_dir / "top_nodes.csv",
        "node_features": out_dir / "node_features.parquet",
        "graph_edges": out_dir / "graph_edges.parquet",
    }

    nodes_roles.to_csv(paths["nodes_roles"], index=False, encoding="utf-8")
    clusters_out.to_csv(paths["clusters"], index=False, encoding="utf-8")
    top_out.to_csv(paths["top_nodes"], index=False, encoding="utf-8")

    enriched_out = enriched[ENRICHED_COLUMNS].copy().sort_values("gid")
    for col in enriched_out.select_dtypes("float").columns:
        enriched_out[col] = enriched_out[col].round(4)
    enriched_out.to_parquet(paths["node_features"], index=False)

    return {k: str(v) for k, v in paths.items()}


def write_graph_edges(edges: pd.DataFrame, out_dir: str | Path) -> str:
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    agg = (
        edges.groupby(["src", "dst"], as_index=False)
        .agg(sum_kzt=("sum_kzt", "sum"), n_tx=("n_tx", "sum"))
        .sort_values(["src", "dst"])
    )
    agg["sum_kzt"] = agg["sum_kzt"].round(4)
    path = out_dir / "graph_edges.parquet"
    agg.to_parquet(path, index=False)
    return str(path)
