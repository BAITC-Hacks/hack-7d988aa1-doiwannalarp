import hashlib
from pathlib import Path

import pandas as pd
import pytest

from moneygraph import pipeline, quality
from moneygraph.io import load_raw
from moneygraph.schemas import ENRICHED_COLUMNS


@pytest.fixture()
def synthetic_data(tmp_path):
    """10-node synthetic graph: 2 seeds, a consolidator, a distributor,
    a transit hop, terminal receivers, and one depth-4 censored (boundary) node."""
    data_dir = tmp_path / "data"
    data_dir.mkdir()

    # gid layout: 1,2 seeds (depth0) -> 3 consolidator (depth1) -> 4 distributor (depth2)
    # -> 5,6,7 receivers (depth3) -> 8 transit (depth3) -> 9 terminal (depth4, out_deg=0, censored)
    # 10 isolated seed
    nodes = pd.DataFrame({
        "gid": [1, 2, 3, 4, 5, 6, 7, 8, 9, 10],
        "depth": [0, 0, 1, 2, 3, 3, 3, 3, 4, 0],
        "is_seed": [True, True, False, False, False, False, False, False, False, True],
    })

    edges = pd.DataFrame([
        (1, 3, 100_000.0, 2, 1),
        (2, 3, 80_000.0, 1, 1),
        (3, 4, 150_000.0, 2, 2),
        (4, 5, 40_000.0, 1, 3),
        (4, 6, 40_000.0, 1, 3),
        (4, 7, 40_000.0, 1, 3),
        (4, 8, 30_000.0, 1, 3),
        (8, 9, 25_000.0, 1, 4),
    ], columns=["src", "dst", "sum_kzt", "n_tx", "depth"])

    tx = pd.DataFrame([
        (1, 3, "2026-07-01", 50_000.0),
        (1, 3, "2026-07-01", 50_000.0),
        (2, 3, "2026-07-02", 80_000.0),
        (3, 4, "2026-07-03", 100_000.0),
        (3, 4, "2026-07-03", 50_000.0),
        (4, 5, "2026-07-04", 40_000.0),
        (4, 6, "2026-07-04", 40_000.0),
        (4, 7, "2026-07-05", 40_000.0),
        (4, 8, "2026-07-05", 30_000.0),
        (8, 9, "2026-07-06", 25_000.0),
    ], columns=["src", "dst", "date", "sum_kzt"])
    tx["date"] = pd.to_datetime(tx["date"])

    nodes.to_parquet(data_dir / "nodes.parquet", index=False)
    edges.to_parquet(data_dir / "edges.parquet", index=False)
    tx.to_parquet(data_dir / "transactions.parquet", index=False)
    return data_dir


def test_pipeline_contract(synthetic_data, tmp_path, monkeypatch):
    # A custom-output run must not overwrite the working checkout's notes.
    working_dir = tmp_path / "checkout"
    (working_dir / "docs").mkdir(parents=True)
    notes = working_dir / "docs" / "DATA_NOTES.md"
    notes.write_text("Existing real-data notes", encoding="utf-8")
    monkeypatch.chdir(working_dir)
    out_dir = tmp_path / "out"
    meta = pipeline.run(data_dir=synthetic_data, out_dir=out_dir, seed=42)
    assert notes.read_text(encoding="utf-8") == "Existing real-data notes"
    assert "nodes: 10" in (out_dir / "docs" / "DATA_NOTES.md").read_text(encoding="utf-8")
    assert not (working_dir / "outputs").exists()
    sensitivity = pd.read_csv(out_dir / "sensitivity.csv")
    assert list(sensitivity.columns) == ["param", "factor", "role_flips", "top20_jaccard"]
    assert not sensitivity.empty
    assert sensitivity.top20_jaccard.between(0, 1).all()
    assert meta["extras_status"]["sensitivity"] == "ok"

    nodes_roles = pd.read_csv(out_dir / "nodes_roles.csv")
    assert len(nodes_roles) == 10
    assert set(nodes_roles["gid"]) == set(range(1, 11))

    features = pd.read_parquet(out_dir / "node_features.parquet")
    assert list(features.columns) == ENRICHED_COLUMNS
    assert len(features) == 10

    edges = pd.read_parquet(synthetic_data / "edges.parquet")
    assert features["in_deg"].sum() == len(edges)
    assert features["out_deg"].sum() == len(edges)

    depth4 = features[features["depth"] == 4]
    assert (depth4["out_deg"] == 0).all()

    assert meta["counts"]["nodes"] == 10
    assert meta["counts"]["edges"] == len(edges)
    assert meta["extras_status"]["sensitivity"] == "ok"
    assert Path(meta["output_paths"]["sensitivity"]) == out_dir / "sensitivity.csv"
    assert (out_dir / "sensitivity.csv").exists()
    assert not (tmp_path / "outputs").exists()


def test_determinism(synthetic_data, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    out_dir1 = tmp_path / "out1"
    out_dir2 = tmp_path / "out2"
    pipeline.run(data_dir=synthetic_data, out_dir=out_dir1, seed=42)
    pipeline.run(data_dir=synthetic_data, out_dir=out_dir2, seed=42)

    for name in ["nodes_roles.csv", "clusters.csv", "top_nodes.csv", "sensitivity.csv",
                 "completeness.csv", "routes.csv"]:
        h1 = hashlib.sha256((out_dir1 / name).read_bytes()).hexdigest()
        h2 = hashlib.sha256((out_dir2 / name).read_bytes()).hexdigest()
        assert h1 == h2, f"{name} not deterministic"


def test_data_notes_preserve_legacy_appendix_and_refresh_report(synthetic_data, tmp_path):
    report = quality.check_data(load_raw(synthetic_data))
    docs_dir = tmp_path / "docs"
    path = Path(quality.write_data_notes(report, docs_dir))
    legacy = path.read_text(encoding="utf-8").replace("<!-- moneygraph:quality:start -->\n", "").replace("\n<!-- moneygraph:quality:end -->", "")
    appendix = "\nAnalyst note without a heading.\n\n## DEV2 calibration measurements\nKeep these percentiles.\n"
    path.write_text(legacy.rstrip() + appendix, encoding="utf-8")
    updated = {**report, "n_nodes": report["n_nodes"] + 1}
    quality.write_data_notes(updated, docs_dir)
    first = path.read_text(encoding="utf-8")
    quality.write_data_notes(updated, docs_dir)
    assert path.read_text(encoding="utf-8") == first
    assert first.endswith(appendix)
    assert f"- nodes: {updated['n_nodes']}," in first
    assert first.count("<!-- moneygraph:quality:start -->") == 1


def test_data_notes_preserve_unrecognized_authored_content(synthetic_data, tmp_path):
    report = quality.check_data(load_raw(synthetic_data))
    path = tmp_path / "DATA_NOTES.md"
    authored = "# Analyst notes\n\nKeep this original content.\n"
    path.write_text(authored, encoding="utf-8")
    quality.write_data_notes(report, tmp_path)
    assert path.read_text(encoding="utf-8").startswith(authored)


def test_sensitivity_failure_keeps_required_outputs(synthetic_data, tmp_path, monkeypatch):
    from moneygraph.extras import sensitivity

    def unavailable(*args, **kwargs):
        raise RuntimeError("Sensitivity unavailable for this test")

    monkeypatch.setattr(sensitivity, "run", unavailable)
    out_dir = tmp_path / "out"
    meta = pipeline.run(synthetic_data, out_dir)
    assert meta["extras_status"]["sensitivity"].startswith("failed:")
    for name in ("nodes_roles.csv", "clusters.csv", "top_nodes.csv", "run_meta.json"):
        assert (out_dir / name).exists()
