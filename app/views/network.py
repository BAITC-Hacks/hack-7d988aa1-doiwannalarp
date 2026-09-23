"""Directed graph and reusable pyvis rendering for network and cluster views."""

import colorsys
import time

import networkx as nx
import pandas as pd
import streamlit as st
from pyvis.network import Network

from app.data import ROLE_COLORS, features, graph_edges, human_kzt


def _cluster_color(value) -> str:
    try:
        hue = (int(value) * 0.61803398875) % 1
    except (TypeError, ValueError):
        return "#90a4ae"
    red, green, blue = colorsys.hsv_to_rgb(hue, 0.58, 0.83)
    return "#{:02x}{:02x}{:02x}".format(int(red * 255), int(green * 255), int(blue * 255))


def ego_gids(edges: pd.DataFrame, active_gid: int, hops: int = 2) -> set[int]:
    graph = nx.DiGraph()
    graph.add_edges_from(edges[["src", "dst"]].itertuples(index=False, name=None))
    if active_gid not in graph:
        return {active_gid}
    result = {active_gid}
    for traversal in (graph, graph.reverse(copy=False)):
        lengths = nx.single_source_shortest_path_length(traversal, active_gid, cutoff=hops)
        result.update(lengths)
    return result


def render_graph(nodes: pd.DataFrame, edges: pd.DataFrame, *, color_by="role",
                 active_gid=None, height="700px") -> str:
    net = Network(directed=True, height=height, width="100%")
    net.toggle_physics(False)
    node_ids = set(nodes["gid"].astype(int))
    for row in nodes.sort_values("gid").to_dict("records"):
        gid = int(row["gid"])
        score = row.get("priority_score", 0)
        score = 0 if pd.isna(score) else float(score)
        size = 10 + 30 * score
        selected = gid == active_gid
        if selected:
            size *= 2
        base_color = (ROLE_COLORS.get(row.get("role"), "#e0e0e0") if color_by == "role"
                      else _cluster_color(row.get("cluster_id")))
        kwargs = {
            "label": str(gid), "title": f"gid {gid} · {row.get('role', '')}",
            "size": size,
            "color": {"background": base_color, "border": "#d32f2f" if selected else base_color},
            "borderWidth": 4 if selected else 1,
        }
        x, y = row.get("x"), row.get("y")
        if pd.notna(x) and pd.notna(y):
            kwargs.update(x=float(x) * 700, y=float(y) * 700)
        net.add_node(gid, **kwargs)
    for row in edges.sort_values(["src", "dst"]).to_dict("records"):
        src, dst = int(row["src"]), int(row["dst"])
        if src in node_ids and dst in node_ids:
            label = human_kzt(row["sum_kzt"])
            net.add_edge(src, dst, label=label, title=label, arrows="to")
    return net.generate_html()


def render() -> None:
    st.subheader("Сеть наблюдаемых переводов")
    nodes = features()
    edges = graph_edges()
    active_gid = st.session_state.get("active_gid")
    color_by = st.radio("Цвет узлов", ["Роль", "Кластер"], horizontal=True)
    mode = "role" if color_by == "Роль" else "cluster"
    if active_gid is not None and active_gid not in set(nodes["gid"].astype(int)):
        st.info(f"gid {active_gid} отсутствует в наблюдаемом графе.")
        active_gid = None

    ego_nodes = None
    if active_gid is not None:
        near = ego_gids(edges, active_gid)
        ego_nodes = nodes[nodes["gid"].isin(near)]

    started = time.perf_counter()
    full_html = render_graph(nodes, edges, color_by=mode, active_gid=active_gid)
    elapsed = time.perf_counter() - started
    if elapsed > 3:
        if ego_nodes is None:
            focus_gid = int(nodes.sort_values(["priority_score", "gid"], ascending=[False, True]).iloc[0]["gid"])
            ego_nodes = nodes[nodes["gid"].isin(ego_gids(edges, focus_gid))]
            active_gid = focus_gid
        st.info("Полная сеть строится дольше 3 секунд; показано окружение узла с высоким приоритетом.")
    else:
        st.components.v1.html(full_html, height=720, scrolling=True)
    if ego_nodes is not None:
        st.markdown("#### Окружение узла: до двух переходов в обе стороны")
        st.components.v1.html(render_graph(ego_nodes, edges, color_by=mode,
                                           active_gid=active_gid, height="420px"),
                              height=440, scrolling=True)
