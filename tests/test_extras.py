import networkx as nx

from moneygraph.extras.llm import ask
from moneygraph.extras.queries import COLUMNS, common_receivers


def test_common_receivers_known_answer():
    graph = nx.DiGraph()
    graph.add_edges_from([(1, 3), (2, 4), (3, 5), (4, 5), (5, 6)])
    graph.nodes[5]["role"] = "consolidator"

    result = common_receivers(graph, [2, 1], max_hops=2)

    assert result.to_dict("records") == [{
        "gid": 5, "n_sources": 2, "source_gids": "1, 2",
        "min_hops_from_any": 2, "role": "consolidator",
    }]


def test_unknown_gids_are_empty(caplog):
    graph = nx.DiGraph([(1, 2)])
    result = common_receivers(graph, [98, 99])
    assert result.empty
    assert list(result.columns) == COLUMNS
    assert "98" in caplog.text


def test_llm_without_key_returns_none(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.setattr("moneygraph.extras.llm.load_dotenv", lambda: None)
    assert ask("Кто получает от 1?", nx.DiGraph([(1, 2)]), None) is None
