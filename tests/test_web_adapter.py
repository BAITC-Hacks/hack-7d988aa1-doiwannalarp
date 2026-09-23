"""Validate the browser boundary without requiring a server or the real dataset."""

import json

import pandas as pd
import pytest

from run_fingraph import dataset, read_frames, records


@pytest.fixture
def web_data(tmp_path):
    directory = tmp_path / "data"
    directory.mkdir()
    first, second, isolated = 9223372036854775805, 9223372036854775806, 9223372036854775807
    pd.DataFrame({
        "gid": [first, second, isolated],
        "depth": [0, 4, 0],
        "is_seed": [True, False, True],
    }).to_parquet(directory / "nodes.parquet", index=False)
    pd.DataFrame({
        "src": [first], "dst": [second], "sum_kzt": [10000.0],
        "n_tx": [2], "depth": [4],
    }).to_parquet(directory / "edges.parquet", index=False)
    # Identical rows are distinct observed transactions, not duplicates to discard.
    pd.DataFrame({
        "src": [first, first], "dst": [second, second],
        "date": ["2026-07-01", "2026-07-01"], "sum_kzt": [5000.0, 5000.0],
    }).to_parquet(directory / "transactions.parquet", index=False)
    return directory


def test_dataset_preserves_int64_ids_and_isolated_nodes(web_data, tmp_path):
    result = json.loads(json.dumps(dataset(web_data, tmp_path / "no_outputs")))
    assert [n["gid"] for n in result["nodes"]] == [
        "9223372036854775805", "9223372036854775806", "9223372036854775807",
    ]
    assert result["edges"][0]["src"] == "9223372036854775805"
    assert result["transactions"][0]["dst"] == "9223372036854775806"
    assert result["nodes"][-1]["in_deg"] == result["nodes"][-1]["out_deg"] == 0
    assert result["meta"]["analyzed"] is False
    assert result["exports"] == []
    assert result["meta"]["has_time"] is False
    assert result["meta"]["total_sum"] == 10000
    assert len(result["transactions"]) == 2
    assert all("role" not in node for node in result["nodes"])


def test_records_never_coerce_mixed_numeric_rows_to_float():
    frame = pd.DataFrame({"gid": [9223372036854775807], "priority_score": [0.75]})
    assert records(frame) == [{"gid": "9223372036854775807", "priority_score": 0.75}]


@pytest.mark.parametrize("case, message", [
    ("float_ids", "int64"),
    ("duplicate_nodes", "дубликаты GID"),
    ("unknown_receiver", "идентификаторы отсутствуют"),
    ("wrong_sum", "Агрегаты edges не совпадают"),
    ("wrong_count", "Агрегаты edges не совпадают"),
    ("missing_column", "отсутствуют колонки"),
    ("empty_nodes", "пустой файл"),
])
def test_invalid_sources_are_rejected(web_data, case, message):
    name = "edges" if case in {"unknown_receiver", "wrong_sum", "wrong_count"} else "nodes"
    path = web_data / f"{name}.parquet"
    frame = pd.read_parquet(path)
    if case == "float_ids":
        frame["gid"] = frame.gid.astype(float)
    elif case == "duplicate_nodes":
        frame = pd.concat([frame, frame.iloc[:1]], ignore_index=True)
    elif case == "unknown_receiver":
        frame.loc[0, "dst"] = 123
    elif case == "wrong_sum":
        frame.loc[0, "sum_kzt"] += 1
    elif case == "wrong_count":
        frame.loc[0, "n_tx"] += 1
    elif case == "missing_column":
        frame = frame.drop(columns="depth")
    elif case == "empty_nodes":
        frame = frame.iloc[:0]
    frame.to_parquet(path, index=False)
    with pytest.raises(ValueError, match=message):
        read_frames(web_data)
