"""Evidence card for one observed gid."""

import json

import pandas as pd
import plotly.express as px
import streamlit as st

from app.data import features, graph_edges, human_kzt, optional_csv, transactions
from moneygraph.schemas import ROLE_RU


METRICS = {
    "in_deg": ("Входящие контрагенты", "Число разных наблюдаемых отправителей."),
    "out_deg": ("Исходящие контрагенты", "Число разных наблюдаемых получателей."),
    "in_sum": ("Входящий поток", "Сумма наблюдаемых входящих переводов, KZT."),
    "out_sum": ("Исходящий поток", "Сумма наблюдаемых исходящих переводов, KZT."),
    "flow_diff": ("Разность потоков", "Входящий минус исходящий наблюдаемый поток; не баланс счёта."),
    "pass_ratio": ("Доля исходящего", "Исходящий поток / входящий; н/д при ненаблюдаемом входящем."),
    "seed_reach": ("Достижимые seed", "Число исходных узлов, из которых есть путь к gid."),
    "seed_flow_in": ("Расчётный поток seed", "Оценка части входящего потока, связанной с исходными узлами."),
    "out_observable": ("Исходящие наблюдаемы", "Выборка позволяет видеть следующий переход из этого узла."),
    "censored": ("Граница выгрузки", "Узел на четвёртом шаге, его исходящие могут отсутствовать в выгрузке."),
    "inflow_incomplete": ("Неполный входящий", "Есть признаки входящих переводов за пределами выборки."),
}

ACTIONS = {
    "coordinator": "Углублённая проверка связей и источников средств.",
    "consolidator": "Проверить источники поступлений и связанные ветви.",
    "distributor": "Проверить получателей веерной рассылки.",
    "transit": "Проследить цепочку до следующего узла.",
    "terminal": "Проверить дальнейшее движение после наблюдаемого периода.",
    "boundary": "Запросить исходящие переводы по узлу за пределами выгрузки.",
    "peripheral": "Низкий приоритет; сохранить в наблюдении.",
}


def _display(value, key):
    if value is None or pd.isna(value):
        return "н/д"
    if key in ("in_sum", "out_sum", "flow_diff", "seed_flow_in"):
        return human_kzt(value)
    if key in ("out_observable", "censored", "inflow_incomplete"):
        return "да" if bool(value) else "нет"
    if key == "pass_ratio":
        return f"{float(value):.2f}"
    return f"{int(value)}"


def _neighbors(edges, gid, incoming):
    selected = edges[edges["dst" if incoming else "src"] == gid].copy()
    neighbor_col = "src" if incoming else "dst"
    if selected.empty:
        return selected
    result = selected.groupby(neighbor_col, as_index=False)["sum_kzt"].sum()
    return result.nlargest(10, "sum_kzt").sort_values("sum_kzt")


def render() -> None:
    st.subheader("Карточка узла")
    gid = st.session_state.get("active_gid")
    if gid is None:
        st.info("Введите gid в поиске или выберите строку в таблице приоритетов.")
        return
    frame = features()
    chosen = frame.loc[frame["gid"] == gid]
    if chosen.empty:
        st.info(f"gid {gid} отсутствует в наблюдаемом графе.")
        return
    node = chosen.iloc[0]
    role = node.get("role", "peripheral")
    st.markdown(f"### gid {gid} — {ROLE_RU.get(role, role)}")
    scores = st.columns(2)
    scores[0].metric("Сила признаков роли", f"{float(node.get('role_score', 0)):.3f}")
    scores[1].metric("Приоритет", f"{float(node.get('priority_score', 0)):.3f}")
    st.write("**Наблюдаемые признаки:**", node.get("evidence", "н/д"))
    top = optional_csv("top_nodes.csv")
    why = node.get("why", "")
    if top is not None and (match := top.loc[top["gid"] == gid]).shape[0]:
        why = match.iloc[0]["why"]
    if pd.notna(why) and str(why).strip():
        st.write("**Почему этот приоритет:**", why)

    trace = node.get("rule_trace")
    if isinstance(trace, str) and trace.strip():
        try:
            trace = json.loads(trace)
        except json.JSONDecodeError:
            trace = []
    if isinstance(trace, list) and trace:
        trace_frame = pd.DataFrame(trace).rename(columns={
            "rule": "Правило", "condition": "Условие", "value": "Значение",
            "threshold": "Порог", "passed": "Результат",
        })
        trace_frame["Результат"] = trace_frame["Результат"].map(lambda value: "✓" if value else "✗")
        st.markdown("#### Проверка всех правил")
        st.dataframe(trace_frame[["Правило", "Условие", "Значение", "Порог", "Результат"]],
                     hide_index=True, use_container_width=True)
    else:
        st.caption("Подробная проверка правил появится после запуска полного расчёта.")

    st.markdown("#### Показатели")
    for key, (label, explanation) in METRICS.items():
        st.write(f"**{label}: {_display(node.get(key), key)}.** {explanation}")

    edges = graph_edges()
    left, right = st.columns(2)
    for col, incoming, title in ((left, True, "Топ-10 отправителей"),
                                 (right, False, "Топ-10 получателей")):
        neighbors = _neighbors(edges, gid, incoming)
        with col:
            st.markdown(f"#### {title}")
            if neighbors.empty:
                st.caption("Наблюдаемых переводов нет.")
            else:
                key = "src" if incoming else "dst"
                neighbors["gid"] = neighbors[key].astype(str)
                figure = px.bar(neighbors, x="sum_kzt", y="gid", orientation="h",
                                labels={"sum_kzt": "KZT", "gid": "Контрагент"})
                st.plotly_chart(figure, use_container_width=True)

    st.markdown("#### Переводы по дням")
    tx = transactions()
    relevant = tx[(tx["src"] == gid) | (tx["dst"] == gid)].copy()
    if relevant.empty:
        st.caption("Наблюдаемых переводов нет.")
    else:
        relevant["Направление"] = relevant["dst"].eq(gid).map({True: "вход", False: "выход"})
        relevant["date"] = pd.to_datetime(relevant["date"]).dt.date
        daily = relevant.groupby(["date", "Направление"], as_index=False)["sum_kzt"].sum()
        figure = px.bar(daily, x="date", y="sum_kzt", color="Направление",
                        color_discrete_map={"вход": "#1976d2", "выход": "#d32f2f"},
                        labels={"date": "Дата", "sum_kzt": "KZT"}, barmode="group")
        st.plotly_chart(figure, use_container_width=True)

    action = ACTIONS.get(role, ACTIONS["peripheral"])
    if isinstance(why, str) and "Действие:" in why:
        action = why.split("Действие:", 1)[1].strip()
    st.info(f"Рекомендуемое действие: {action}")
