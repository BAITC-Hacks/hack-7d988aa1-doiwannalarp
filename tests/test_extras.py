import networkx as nx
import pandas as pd

from moneygraph.extras.completeness import gaps
from moneygraph.extras.llm import ask
from moneygraph.extras.queries import COLUMNS, common_receivers
from moneygraph.extras.routes import find


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


def test_completeness_uses_observation_flags_and_requests_correct_direction():
    frame = pd.DataFrame([
        (1, "consolidator", True, False, 100, 50, 4),
        (2, "transit", False, True, 200, 50, 1),
        (3, "coordinator", True, True, 200, 50, 4),
        (4, "peripheral", False, False, 0, 0, 0),
    ], columns=["gid", "role", "censored", "inflow_incomplete", "seed_flow_in", "in_sum", "in_deg"])

    result = gaps(frame)
    assert result.gid.tolist() == [2, 3, 1]
    by_gid = result.set_index("gid")
    assert by_gid.loc[1, "reason"] == "boundary"
    assert "исходящие" in by_gid.loc[1, "request"]
    assert "входящие" not in by_gid.loc[1, "request"]
    assert by_gid.loc[2, "reason"] == "inflow_incomplete"
    assert "входящие" in by_gid.loc[2, "request"]
    assert "исходящие" not in by_gid.loc[2, "request"]
    assert by_gid.loc[3, "reason"] == "boundary+inflow_incomplete"
    assert "входящие" in by_gid.loc[3, "request"] and "исходящие" in by_gid.loc[3, "request"]
    assert gaps(frame.loc[frame.gid == 4]).empty
    assert list(gaps(frame.iloc[:0]).columns) == list(result.columns)


def test_routes_find_early_and_repeated_dates_despite_later_inflow():
    tx = pd.DataFrame([
        (1, 2, "2026-07-01", 6000),
        (1, 2, "2026-07-01", 6000),  # Same day is not two independent occurrences.
        (2, 3, "2026-07-02", 8000),
        (1, 2, "2026-07-10", 14000),
        (2, 3, "2026-07-12", 9000),
        (1, 2, "2026-07-20", 5000),  # Must not hide the earlier sequences.
        (2, 3, "2026-07-01", 5000),  # Unknown order: separate same-day candidate.
        (2, 3, "2026-07-04", 7000),  # Three days later: excluded.
        (2, 3, "2026-06-30", 5000),  # Before the inflows: excluded.
    ], columns=["src", "dst", "date", "sum_kzt"])
    graph = nx.DiGraph()
    for (src, dst), amount in tx.groupby(["src", "dst"]).sum_kzt.sum().items():
        graph.add_edge(src, dst, sum_kzt=amount)
    enriched = pd.DataFrame({"gid": [1, 2, 3], "role": ["peripheral", "transit", "terminal"]})

    result = find(graph, tx, enriched).set_index("kind")
    assert result.loc["transit_chain", "path"] == "1->2->3"
    assert result.loc["transit_chain", "n_occurrences"] == 2
    assert result.loc["transit_chain", "days_span"] == 1
    assert result.loc["transit_chain", "min_leg_kzt"] == 9000
    assert result.loc["same_day_candidate", "n_occurrences"] == 1
    assert result.loc["same_day_candidate", "days_span"] == 0
    assert result.loc["same_day_candidate", "min_leg_kzt"] == 5000
    reordered = nx.DiGraph()
    reordered.add_edges_from(reversed(list(graph.edges(data=True))))
    pd.testing.assert_frame_equal(
        find(graph, tx, enriched),
        find(reordered, tx.sample(frac=1, random_state=42), enriched.iloc[::-1]),
    )


def test_cycles_are_structural_not_claimed_temporal_occurrences():
    graph = nx.DiGraph()
    graph.add_weighted_edges_from([(3, 1, 9000), (1, 2, 8000), (2, 3, 7000)], weight="sum_kzt")
    tx = pd.DataFrame([
        (1, 2, "2026-07-20", 8000),
        (2, 3, "2026-07-10", 7000),
        (3, 1, "2026-07-01", 9000),
    ], columns=["src", "dst", "date", "sum_kzt"])
    enriched = pd.DataFrame({"gid": [1, 2, 3], "role": ["peripheral"] * 3})
    result = find(graph, tx, enriched)
    assert len(result) == 1
    assert result.iloc[0]["path"] == "1->2->3->1"
    assert result.iloc[0]["kind"] == "structural_cycle"
    assert pd.isna(result.iloc[0]["days_span"])
    assert pd.isna(result.iloc[0]["n_occurrences"])
    reordered = nx.DiGraph()
    reordered.add_edges_from(reversed(list(graph.edges(data=True))))
    pd.testing.assert_frame_equal(result, find(reordered, tx, enriched))
    assert find(nx.DiGraph(), tx.iloc[:0], enriched.iloc[:0]).empty


def test_analysis_displays_all_completeness_requests(monkeypatch):
    from streamlit.testing.v1 import AppTest
    from app.views import analysis

    frame = pd.DataFrame({
        "gid": [1, 2, 3],
        "reason": ["boundary", "inflow_incomplete", "boundary+inflow_incomplete"],
        "request": ["Исходящие", "Входящие", "Оба направления"],
    })
    monkeypatch.setattr(analysis, "optional_csv", lambda name: frame if name == "completeness.csv" else None)
    monkeypatch.setattr(analysis, "load_dotenv", lambda: None)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)

    def show_analysis():
        from app.views.analysis import render
        render()

    app = AppTest.from_function(show_analysis).run()
    assert not app.exception
    assert app.dataframe[0].value.gid.tolist() == [1, 2, 3]
    assert "неполный входящий" in app.dataframe[0].value.iloc[2]["reason"]


def test_adapter_reads_utf8_on_windows_and_exposes_full_action(tmp_path, monkeypatch):
    from pathlib import Path
    import run_fingraph
    from moneygraph.priority import ACTIONS

    raw = tmp_path / "data"
    out = tmp_path / "outputs"
    docs = tmp_path / "docs"
    for folder in (raw, out, docs):
        folder.mkdir()
    pd.DataFrame({"gid": [1, 2], "depth": [0, 1], "is_seed": [True, False]}).to_parquet(raw / "nodes.parquet")
    pd.DataFrame({"src": [1], "dst": [2], "sum_kzt": [5000.0], "n_tx": [1], "depth": [1]}).to_parquet(raw / "edges.parquet")
    pd.DataFrame({"src": [1], "dst": [2], "date": pd.to_datetime(["2026-07-01"]), "sum_kzt": [5000.0]}).to_parquet(raw / "transactions.parquet")
    pd.DataFrame({"gid": [1, 2], "role": ["peripheral", "consolidator"]}).to_csv(out / "nodes_roles.csv", index=False)
    methodology = "Источники и правила: проверяемые гипотезы."
    (docs / "METHODOLOGY.md").write_text(methodology, encoding="utf-8")
    monkeypatch.setattr(run_fingraph, "ROOT", tmp_path)
    original = Path.read_text

    def windows_read(path, encoding=None, errors=None):
        return original(path, encoding=encoding or "cp1252", errors=errors)

    monkeypatch.setattr(Path, "read_text", windows_read)
    result = run_fingraph.dataset(raw, out)
    assert result["methodology"]["text"] == methodology
    assert result["nodes"][1]["recommended_action"] == ACTIONS["consolidator"]
    assert all(isinstance(node["gid"], str) for node in result["nodes"])
