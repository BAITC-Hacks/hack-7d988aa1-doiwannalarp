from fixtures import make_fixture_graph
from moneygraph.extras.sensitivity import run
from moneygraph.features import compute_features
from moneygraph.graph import build_graph
from moneygraph.temporal import add_temporal


def test_sensitivity_is_bounded_and_written(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    raw = make_fixture_graph()
    graph = build_graph(raw)
    features = add_temporal(compute_features(graph, raw), raw.tx)
    result = run(features, graph)
    assert not result.empty
    assert set(result.factor) == {0.75, 1.25}
    assert (result.role_flips >= 0).all()
    assert result.top20_jaccard.between(0, 1).all()
    assert (tmp_path / "outputs/sensitivity.csv").exists()


def test_sensitivity_respects_custom_output_directory(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    raw = make_fixture_graph()
    graph = build_graph(raw)
    features = add_temporal(compute_features(graph, raw), raw.tx)
    run(features, graph, out_dir=tmp_path / "custom")
    assert (tmp_path / "custom/sensitivity.csv").exists()
    assert not (tmp_path / "outputs").exists()
