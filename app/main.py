"""MoneyGraph analyst dashboard."""

import logging

import streamlit as st

from app.data import friendly_missing
from app.views import analysis, clusters, network, node_card, overview, top


LOGGER = logging.getLogger(__name__)


st.set_page_config(page_title="Граф денег", layout="wide")
st.title("Граф денег")
st.caption("Гипотезы о ролях в наблюдаемой сети переводов")

if "active_gid" not in st.session_state:
    st.session_state["active_gid"] = None
if "gid_search" not in st.session_state:
    st.session_state["gid_search"] = ""


def _update_gid_from_search():
    raw = st.session_state["gid_search"].strip()
    if not raw:
        st.session_state["active_gid"] = None
        st.session_state["gid_search_invalid"] = False
        return
    try:
        st.session_state["active_gid"] = int(raw)
        st.session_state["gid_search_invalid"] = False
    except ValueError:
        st.session_state["gid_search_invalid"] = True

with st.sidebar:
    st.header("Поиск узла")
    st.text_input("gid", key="gid_search", on_change=_update_gid_from_search)
    if st.session_state.get("gid_search_invalid"):
        st.warning("Введите целочисленный gid.")

tabs = st.tabs(["Обзор", "Приоритеты", "Сеть", "Карточка узла", "Кластеры", "Анализ"])
views = [overview, top, network, node_card, clusters, analysis]
for tab, view in zip(tabs, views):
    with tab:
        try:
            view.render()
        except (FileNotFoundError, OSError, KeyError) as exc:
            LOGGER.warning("Данные представления недоступны: %s", exc)
            friendly_missing()
        except Exception as exc:
            LOGGER.warning("Ошибка представления %s: %s", view.__name__, exc, exc_info=True)
            st.warning("Представление временно недоступно. Проверьте данные и повторите расчёт.")
