import pandas as pd
import plotly.express as px
import streamlit as st

from app.data import OUT, ROLE_COLORS, human_kzt, read_json, required_csv
from moneygraph.schemas import ROLE_RU


def render() -> None:
    st.subheader("Обзор наблюдаемого графа")
    meta = read_json(str(OUT / "run_meta.json"))
    roles = required_csv("nodes_roles.csv")
    counts = meta.get("counts", {})
    quality = meta.get("quality", {})
    total_kzt = quality.get("total_kzt")
    if total_kzt is None:
        from app.data import graph_edges
        total_kzt = graph_edges()["sum_kzt"].sum()
    runtime = sum(meta.get("timings_seconds", {}).values())
    cols = st.columns(5)
    for col, label, value in zip(cols,
        ["Узлы", "Рёбра", "Переводы, KZT", "Время расчёта", "Кластеры"],
        [counts.get("nodes", len(roles)), counts.get("edges", "н/д"), human_kzt(total_kzt),
         f"{runtime:.1f} с", counts.get("clusters", "н/д")]):
        col.metric(label, value)

    distribution = roles.groupby("role", as_index=False).size().sort_values("role")
    distribution["Роль"] = distribution["role"].map(ROLE_RU).fillna(distribution["role"])
    figure = px.bar(distribution, x="Роль", y="size", color="role",
                    color_discrete_map=ROLE_COLORS, labels={"size": "Число узлов"})
    figure.update_layout(showlegend=False)
    st.plotly_chart(figure, use_container_width=True)

    st.subheader("Качество и границы данных")
    boundary = quality.get("censored_depth4_no_outflow", "н/д")
    incomplete = quality.get("nodes_out_gt_in", "н/д")
    st.info(
        f"**Граница выгрузки:** {boundary} узлов четвёртого поколения не имеют наблюдаемых исходящих "
        "переводов из-за способа обхода графа. Это не доказывает, что они конечные получатели.\n\n"
        f"**Неполный входящий поток:** {incomplete} узлов отправили больше, чем получили "
        "в наблюдаемой сети. Входящие seed также видны не полностью; суммы входящего потока — нижняя граница.\n\n"
        "**Порог выгрузки:** переводы меньше 5 000 KZT исключены из данных. Это условие экспорта, "
        "а не критерий подозрительного поведения.\n\n"
        "**Период:** только июль 2026 года. Перевод в конце периода мог получить продолжение "
        "позже; это правостороннее цензурирование наблюдения."
    )
