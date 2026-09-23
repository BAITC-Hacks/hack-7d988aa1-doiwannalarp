"""Cached file access and small display helpers for Streamlit views."""

import json
import os
from pathlib import Path

import pandas as pd
import streamlit as st


ROOT = Path(__file__).resolve().parents[1]
OUT = Path(os.getenv("MONEYGRAPH_OUT_DIR", ROOT / "outputs"))
RAW = Path(os.getenv("MONEYGRAPH_DATA_DIR", ROOT / "data"))
ROLE_COLORS = {
    "coordinator": "#d32f2f", "consolidator": "#f57c00",
    "distributor": "#1976d2", "transit": "#388e3c",
    "terminal": "#7b1fa2", "boundary": "#90a4ae",
    "peripheral": "#e0e0e0",
}


@st.cache_data(show_spinner=False)
def read_csv(path: str) -> pd.DataFrame:
    return pd.read_csv(path).sort_values("gid") if Path(path).name == "nodes_roles.csv" else pd.read_csv(path)


@st.cache_data(show_spinner=False)
def read_parquet(path: str) -> pd.DataFrame:
    return pd.read_parquet(path)


@st.cache_data(show_spinner=False)
def read_json(path: str) -> dict:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def optional_csv(name: str) -> pd.DataFrame | None:
    path = OUT / name
    return read_csv(str(path)) if path.exists() else None


def required_csv(name: str) -> pd.DataFrame:
    return read_csv(str(OUT / name))


def features() -> pd.DataFrame:
    path = OUT / "node_features.parquet"
    if path.exists():
        return read_parquet(str(path))
    nodes = read_parquet(str(RAW / "nodes.parquet"))
    edges = graph_edges()
    incoming = edges.groupby("dst").agg(in_deg=("src", "nunique"), in_sum=("sum_kzt", "sum"))
    outgoing = edges.groupby("src").agg(out_deg=("dst", "nunique"), out_sum=("sum_kzt", "sum"))
    result = nodes.merge(incoming, left_on="gid", right_index=True, how="left")
    result = result.merge(outgoing, left_on="gid", right_index=True, how="left")
    for col in ("in_deg", "out_deg", "in_sum", "out_sum"):
        result[col] = result[col].fillna(0)
    result["flow_diff"] = result["in_sum"] - result["out_sum"]
    result["pass_ratio"] = result["out_sum"].div(result["in_sum"].replace(0, float("nan")))
    result["out_observable"] = result["depth"] <= 3
    result["censored"] = (result["depth"] == 4) & (result["out_deg"] == 0)
    result["inflow_incomplete"] = result["is_seed"] | (result["out_sum"] > 1.2 * result["in_sum"])
    result = result.merge(required_csv("nodes_roles.csv"), on="gid", how="left")
    result["seed_reach"] = float("nan")
    result["seed_flow_in"] = float("nan")
    result["x"] = float("nan")
    result["y"] = float("nan")
    top = optional_csv("top_nodes.csv")
    if top is not None:
        result = result.merge(top[["gid", "why"]], on="gid", how="left")
    return result.sort_values("gid")


def graph_edges() -> pd.DataFrame:
    path = OUT / "graph_edges.parquet"
    if path.exists():
        return read_parquet(str(path))
    return read_parquet(str(RAW / "edges.parquet"))


def transactions() -> pd.DataFrame:
    return read_parquet(str(RAW / "transactions.parquet"))


def human_kzt(value) -> str:
    value = float(value)
    if abs(value) >= 1_000_000:
        return f"{value / 1_000_000:,.1f} млн KZT".replace(",", " ")
    if abs(value) >= 1_000:
        return f"{value / 1_000:,.0f} тыс. KZT".replace(",", " ")
    return f"{value:,.0f} KZT".replace(",", " ")


def friendly_missing() -> None:
    st.info("Сначала запустите: python run_pipeline.py")
    st.stop()
