"""Layered, directed rendering of the transfer graph.

Nodes are placed by `depth` (the real traversal distance from a seed, 0..4)
instead of a force-directed layout: depth is the actual structural axis the
case is built on (seeds -> intermediaries -> downstream), so a left-to-right
layered diagram — seed column, then each hop as its own column, role-colored
and role-grouped within each column — reads as a genuine flow diagram
instead of a force-directed hairball. Small subgraphs (a node's ego
neighborhood, a single cluster) use vis.js's own hierarchical layout on the
same depth axis, which additionally auto-spaces nodes within a column.
"""

import colorsys
import json
import time

import networkx as nx
import pandas as pd
import streamlit as st
from pyvis.network import Network

from app.data import ROLE_COLORS, features, graph_edges, human_kzt
from moneygraph.schemas import ROLE_RU, ROLES

EDGE_COLOR = {"color": "#8891a3", "opacity": 0.35, "highlight": "#d32f2f"}
SELECTED_BORDER = "#ffd54f"


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


_ROLE_RANK = {role: i for i, role in enumerate(ROLES)}


def _layered_grid(nodes: pd.DataFrame, *, row_gap=42, col_gap=260,
                  sub_col_gap=64, max_rows=26) -> pd.DataFrame:
    """Grid-pack each depth column (role-grouped, priority-ranked), wrapping
    into extra sub-columns once a column would otherwise be unreadably tall.
    Used for the full graph, where some depth columns hold hundreds of nodes
    and vis.js's own hierarchical layout (single row per level) would produce
    an unusable multi-thousand-pixel-tall column."""
    out = nodes.copy()
    out["depth"] = pd.to_numeric(out["depth"], errors="coerce").fillna(0).astype(int)
    out["_rank"] = out["role"].map(_ROLE_RANK).fillna(len(_ROLE_RANK))
    out["_priority"] = pd.to_numeric(out.get("priority_score"), errors="coerce").fillna(0)
    xs: dict[int, float] = {}
    ys: dict[int, float] = {}
    for depth, group in out.groupby("depth"):
        ordered = group.sort_values(["_rank", "_priority"], ascending=[True, False])
        rows = min(max_rows, len(ordered)) or 1
        for i, gid in enumerate(ordered["gid"].astype(int)):
            row, sub_col = i % rows, i // rows
            xs[int(gid)] = float(depth) * col_gap + sub_col * sub_col_gap
            ys[int(gid)] = (row - (rows - 1) / 2) * row_gap
    out["x"] = out["gid"].astype(int).map(xs)
    out["y"] = out["gid"].astype(int).map(ys)
    return out.drop(columns=["_rank", "_priority"])


def render_graph(nodes: pd.DataFrame, edges: pd.DataFrame, *, color_by="role",
                 active_gid=None, height="700px", show_labels=True,
                 hierarchical=False) -> str:
    net = Network(directed=True, height=height, width="100%", bgcolor="#0e1117", font_color="#e6e9ef")
    node_ids = set(nodes["gid"].astype(int))

    for row in nodes.sort_values("gid").to_dict("records"):
        gid = int(row["gid"])
        score = row.get("priority_score", 0)
        score = 0 if pd.isna(score) else float(score)
        size = 10 + 32 * score
        selected = gid == active_gid
        if selected:
            size *= 1.8
        base_color = (ROLE_COLORS.get(row.get("role"), "#e0e0e0") if color_by == "role"
                      else _cluster_color(row.get("cluster_id")))
        depth = row.get("depth")
        level = int(depth) if pd.notna(depth) else 0
        kwargs = {
            "label": str(gid) if show_labels or selected else " ",
            "title": f"gid {gid} · {row.get('role', '')} · колено {level}",
            "size": size,
            "color": {"background": base_color, "border": SELECTED_BORDER if selected else base_color,
                     "highlight": {"background": base_color, "border": SELECTED_BORDER}},
            "borderWidth": 4 if selected else 1,
            "level": level,
        }
        if not hierarchical:
            x, y = row.get("x"), row.get("y")
            if pd.notna(x) and pd.notna(y):
                kwargs.update(x=float(x), y=float(y))
        net.add_node(gid, **kwargs)

    for row in edges.sort_values(["src", "dst"]).to_dict("records"):
        src, dst = int(row["src"]), int(row["dst"])
        if src in node_ids and dst in node_ids:
            label = human_kzt(row["sum_kzt"])
            edge_kwargs = {"title": label, "arrows": "to", "color": EDGE_COLOR, "smooth": False}
            if show_labels:
                edge_kwargs["label"] = label
            net.add_edge(src, dst, **edge_kwargs)

    options = {"physics": {"enabled": False},
              "interaction": {"hover": True, "dragView": True, "zoomView": True}}
    if hierarchical:
        options["layout"] = {"hierarchical": {
            "enabled": True, "direction": "LR", "sortMethod": "directed",
            "levelSeparation": 220, "nodeSpacing": 90, "treeSpacing": 140,
            "blockShifting": True, "edgeMinimization": True,
        }}
    net.set_options(json.dumps(options))

    html = net.generate_html()
    # pyvis never calls fit() on its own, so a static (physics-off) graph
    # keeps the default viewport instead of framing the laid-out content.
    return html.replace("return network;", "network.fit(); return network;")


def _role_legend() -> None:
    chips = "".join(
        f'<span style="display:inline-flex;align-items:center;gap:6px;margin-right:16px;">'
        f'<span style="width:11px;height:11px;border-radius:50%;background:{ROLE_COLORS[role]};'
        f'display:inline-block;"></span>{ROLE_RU[role]}</span>'
        for role in ROLES
    )
    st.markdown(f'<div style="font-size:0.85rem;color:#c7cdd6;margin-bottom:6px;">{chips}</div>',
               unsafe_allow_html=True)


def render() -> None:
    st.subheader("Сеть наблюдаемых переводов")
    st.caption("Слева направо: seed (колено 0) → 1-е → 2-е → 3-е → 4-е колено. "
              "Узлы сгруппированы по роли внутри каждого колена — цвет = роль.")
    _role_legend()
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

    st.caption("Подписи узлов и переводов скрыты из-за плотности графа — "
              "наведите курсор на узел или ребро, чтобы увидеть gid, роль и сумму.")
    started = time.perf_counter()
    laid_out = _layered_grid(nodes)
    full_html = render_graph(laid_out, edges, color_by=mode, active_gid=active_gid,
                             show_labels=False)
    elapsed = time.perf_counter() - started
    if elapsed > 3:
        if ego_nodes is None:
            focus_gid = int(nodes.sort_values(["priority_score", "gid"], ascending=[False, True]).iloc[0]["gid"])
            ego_nodes = nodes[nodes["gid"].isin(ego_gids(edges, focus_gid))]
            active_gid = focus_gid
        st.info("Полная сеть строится дольше 3 секунд; показано окружение узла с высоким приоритетом.")
    else:
        st.components.v1.html(full_html, height=760, scrolling=True)
    if ego_nodes is not None:
        st.markdown("#### Окружение узла: до двух переходов в обе стороны")
        ego_labels = len(ego_nodes) <= 30
        if not ego_labels:
            st.caption(f"В окружении {len(ego_nodes)} узлов — подписи скрыты для читаемости, "
                      "наведите курсор, чтобы увидеть gid и роль.")
        st.components.v1.html(render_graph(ego_nodes, edges, color_by=mode,
                                           active_gid=active_gid, height="480px",
                                           show_labels=ego_labels, hierarchical=True),
                              height=500, scrolling=True)
