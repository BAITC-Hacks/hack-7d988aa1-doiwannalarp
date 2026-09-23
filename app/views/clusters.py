import streamlit as st

from app.data import features, graph_edges, required_csv
from app.views.network import render_graph


def render() -> None:
    st.subheader("Кластеры — гипотезы о контурах переводов")
    clusters = required_csv("clusters.csv")
    shown = clusters[["cluster_id", "n_nodes", "n_seed", "sum_kzt_internal", "hypothesis"]]
    event = st.dataframe(shown, hide_index=True, use_container_width=True,
                         on_select="rerun", selection_mode="single-row")
    if not event.selection.rows:
        st.caption("Выберите строку, чтобы открыть сеть кластера.")
        return
    cluster_id = clusters.iloc[event.selection.rows[0]]["cluster_id"]
    nodes = features()
    selected = nodes[nodes["cluster_id"] == cluster_id]
    if selected.empty:
        st.info("В выбранном кластере нет наблюдаемых узлов.")
        return
    show_labels = len(selected) <= 30
    if not show_labels:
        st.caption(f"В кластере {len(selected)} узлов — подписи скрыты для читаемости, "
                  "наведите курсор, чтобы увидеть gid и роль.")
    st.components.v1.html(render_graph(selected, graph_edges(), height="520px",
                                       show_labels=show_labels, hierarchical=True),
                          height=540, scrolling=True)
