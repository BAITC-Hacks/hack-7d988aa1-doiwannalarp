import os

import networkx as nx
import plotly.express as px
import streamlit as st
from dotenv import load_dotenv

from app.data import features, graph_edges, optional_csv
from moneygraph.extras.queries import common_receivers


def _query_graph(nodes, edges):
    graph = nx.DiGraph()
    for row in nodes[["gid", "role"]].itertuples(index=False):
        graph.add_node(int(row.gid), role=row.role)
    graph.add_edges_from(edges[["src", "dst"]].itertuples(index=False, name=None))
    return graph


def _section(name, filename):
    frame = optional_csv(filename)
    if frame is None:
        st.caption(f"{name}: файл {filename} пока не создан.")
    return frame


def render() -> None:
    st.subheader("Дополнительный анализ")
    sensitivity = _section("Чувствительность", "sensitivity.csv")
    if sensitivity is not None:
        st.markdown("#### Чувствительность к порогам")
        st.caption("Проверяются градуируемые пороги (_MIN и _STRONG). Границы отношений, "
                   "ограничения степени, поздние поступления и веса приоритета не варьируются; "
                   "это проверка устойчивости, не точности ролей.")
        st.dataframe(sensitivity, use_container_width=True, hide_index=True)
        if "top20_jaccard" in sensitivity and sensitivity["top20_jaccard"].lt(0.7).any():
            st.warning("Часть изменений порогов заметно меняет топ-20; используйте ранги как ориентир проверки.")

    resilience = _section("Устойчивость", "resilience.csv")
    if resilience is not None and not resilience.empty:
        st.markdown("#### Устойчивость сети")
        figure = px.line(resilience.sort_values(["strategy", "n_removed"]),
                         x="n_removed", y="largest_wcc", color="strategy", markers=True,
                         labels={"n_removed": "Удалено узлов", "largest_wcc": "Размер крупнейшей компоненты",
                                 "strategy": "Стратегия"})
        st.plotly_chart(figure, use_container_width=True)

    completeness = _section("Полнота", "completeness.csv")
    if completeness is not None:
        st.markdown("#### Запросы для дополнения данных")
        st.caption("Граница выгрузки требует исходящих переводов; неполный входящий поток — входящих. "
                   "У одного узла могут быть оба ограничения независимо от его роли.")
        shown = completeness.copy()
        shown["reason"] = shown["reason"].replace({
            "boundary": "Граница выгрузки",
            "inflow_incomplete": "Неполный входящий поток",
            "boundary+inflow_incomplete": "Граница выгрузки и неполный входящий поток",
        })
        st.dataframe(shown, use_container_width=True, hide_index=True)
        st.download_button("Скачать запросы CSV", completeness.to_csv(index=False).encode("utf-8"),
                           file_name="completeness.csv", mime="text/csv")

    routes = _section("Маршруты", "routes.csv")
    if routes is not None:
        st.markdown("#### Цепочки и циклы")
        st.caption("Цепочки: поступление и отправка через 1–2 дня; совпадения в один день "
                   "показаны отдельно, их порядок неизвестен. Число повторений — число совместимых "
                   "пар дат, а не независимых перемещений одних и тех же средств. "
                   "Структурный цикл не подтверждает возврат денег во времени.")
        shown_routes = routes.copy()
        shown_routes["kind"] = shown_routes["kind"].replace({
            "transit_chain": "Цепочка с интервалом 1–2 дня",
            "same_day_candidate": "Совпадение в один день: порядок неизвестен",
            "structural_cycle": "Структурный цикл без проверки времени",
            "cycle": "Структурный цикл без проверки времени",
        })
        st.dataframe(shown_routes, use_container_width=True, hide_index=True)
        st.caption("min_leg_kzt: для цепочки — максимум меньшей из двух дневных сумм "
                   "по совместимым парам дат; для цикла — минимальная месячная сумма ребра. "
                   "Это наблюдаемые суммы, не объём прослеженных средств. "
                   "days_span — минимальный интервал в днях; для структурного цикла интервал "
                   "и число повторений не определены.")

    st.markdown("#### Общие достижимые получатели")
    query = st.text_input("gid источников через запятую", placeholder="101, 202")
    if query.strip():
        try:
            gids = [int(part.strip()) for part in query.split(",") if part.strip()]
        except ValueError:
            st.warning("Введите целочисленные gid через запятую.")
            return
        nodes = features()
        edges = graph_edges()
        result = common_receivers(_query_graph(nodes, edges), gids)
        if result.empty:
            st.info("Общие достижимые получатели не найдены.")
        else:
            st.dataframe(result, use_container_width=True, hide_index=True)

    load_dotenv()
    if os.getenv("OPENAI_API_KEY"):
        st.markdown("#### Вопрос по вычисленным признакам")
        question = st.text_input("Вопрос с gid")
        if question.strip() and st.button("Получить объяснение"):
            from moneygraph.extras.llm import ask

            nodes = features()
            answer = ask(question, _query_graph(nodes, graph_edges()), nodes)
            if answer:
                st.write(answer)
            else:
                st.info("Объяснение сейчас недоступно.")
