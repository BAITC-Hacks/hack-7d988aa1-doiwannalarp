import streamlit as st

from app.data import OUT, required_csv
from moneygraph.schemas import ROLE_RU


def render() -> None:
    st.subheader("Приоритеты проверки")
    frame = required_csv("top_nodes.csv")
    shown = frame[["rank", "gid", "role", "priority_score", "why"]].copy()
    shown["role"] = shown["role"].map(ROLE_RU).fillna(shown["role"])
    shown.columns = ["Ранг", "gid", "Роль", "Приоритет", "Почему"]
    event = st.dataframe(
        shown, use_container_width=True, hide_index=True,
        on_select="rerun", selection_mode="single-row", key="top_table",
        column_config={"Приоритет": st.column_config.NumberColumn(format="%.3f")},
    )
    if event.selection.rows:
        selected_gid = int(frame.iloc[event.selection.rows[0]]["gid"])
        if st.session_state.get("last_top_gid") != selected_gid:
            st.session_state["active_gid"] = selected_gid
            st.session_state["last_top_gid"] = selected_gid
        st.caption(f"Выбран gid {selected_gid}")
    else:
        st.session_state["last_top_gid"] = None
    st.download_button("Скачать полный CSV", (OUT / "top_nodes.csv").read_bytes(),
                       file_name="top_nodes.csv", mime="text/csv")
