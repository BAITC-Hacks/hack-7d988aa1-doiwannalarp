import argparse
import hashlib
import io
import subprocess
import sys
from pathlib import Path

import pandas as pd

if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from moneygraph.schemas import CLUSTERS_COLUMNS, NODES_ROLES_COLUMNS, ROLES, TOP_COLUMNS  # noqa: E402

BANNED_WORDS = [
    "виновен", "виновна", "преступник", "является организатором",
    "установлено", "доказано", "остаток",
]

OUT_DIR = Path("outputs")


def fail(msg: str, errors: list[str]):
    errors.append(msg)


def check_nodes_roles(errors: list[str], final: bool):
    path = OUT_DIR / "nodes_roles.csv"
    df = pd.read_csv(path)
    if list(df.columns) != NODES_ROLES_COLUMNS:
        fail(f"nodes_roles.csv columns mismatch: {list(df.columns)} != {NODES_ROLES_COLUMNS}", errors)
    if df.isnull().values.any():
        fail("nodes_roles.csv contains nulls", errors)
    bad_roles = set(df["role"]) - set(ROLES)
    if bad_roles:
        fail(f"nodes_roles.csv has roles outside ROLES: {bad_roles}", errors)
    if not df["role_score"].between(0, 1).all():
        fail("nodes_roles.csv role_score out of [0,1]", errors)
    if not df["priority_score"].between(0, 1).all():
        fail("nodes_roles.csv priority_score out of [0,1]", errors)
    lengths = df["evidence"].astype(str).str.len()
    if not lengths.between(1, 200).all():
        fail("nodes_roles.csv evidence length out of [1,200]", errors)

    if final:
        stub_rows = df["evidence"].astype(str).str.contains("Заглушка")
        if stub_rows.any():
            fail(f"nodes_roles.csv still has {stub_rows.sum()} stub 'Заглушка' evidence rows", errors)
    return df


def check_clusters(errors: list[str]):
    path = OUT_DIR / "clusters.csv"
    df = pd.read_csv(path)
    if list(df.columns) != CLUSTERS_COLUMNS:
        fail(f"clusters.csv columns mismatch: {list(df.columns)} != {CLUSTERS_COLUMNS}", errors)
    total_nodes = int(df["n_nodes"].sum())
    total_seed = int(df["n_seed"].sum())
    if total_nodes != 2248:
        fail(f"clusters.csv n_nodes sums to {total_nodes}, expected 2248", errors)
    if total_seed != 81:
        fail(f"clusters.csv n_seed sums to {total_seed}, expected 81", errors)


def check_top_nodes(errors: list[str], final: bool):
    path = OUT_DIR / "top_nodes.csv"
    df = pd.read_csv(path)
    if list(df.columns) != TOP_COLUMNS:
        fail(f"top_nodes.csv columns mismatch: {list(df.columns)} != {TOP_COLUMNS}", errors)
    if len(df) < 20:
        fail(f"top_nodes.csv has only {len(df)} rows, expected >=20", errors)
    if list(df["rank"]) != list(range(1, len(df) + 1)):
        fail("top_nodes.csv rank is not 1..N", errors)
    if (df["priority_score"].diff().dropna() > 1e-9).any():
        fail("top_nodes.csv priority_score is not non-increasing", errors)

    if final:
        stub_rows = df["why"].astype(str).str.contains("Заглушка")
        if stub_rows.any():
            fail(f"top_nodes.csv still has {stub_rows.sum()} stub 'Заглушка' why rows", errors)


def check_invariants(errors: list[str], nodes_roles: pd.DataFrame):
    features_path = OUT_DIR / "node_features.parquet"
    if not features_path.exists():
        fail("node_features.parquet missing, cannot check censored/seed invariants", errors)
        return
    features = pd.read_parquet(features_path)
    merged = features.merge(nodes_roles[["gid", "role"]], on="gid", suffixes=("", "_out"))

    bad_censored = merged[merged["censored"] & merged["role"].isin(["terminal", "transit", "distributor"])]
    if len(bad_censored):
        fail(f"{len(bad_censored)} censored node(s) have role terminal/transit/distributor", errors)

    bad_seed = merged[merged["is_seed"] & merged["role"].isin(["transit", "terminal"])]
    if len(bad_seed):
        fail(f"{len(bad_seed)} seed node(s) have a pass_ratio-derived role", errors)


def check_banned_words(errors: list[str]):
    for name in ["nodes_roles.csv", "clusters.csv", "top_nodes.csv"]:
        path = OUT_DIR / name
        if not path.exists():
            continue
        text = path.read_text(encoding="utf-8")
        for word in BANNED_WORDS:
            if word in text:
                fail(f"{name} contains banned word '{word}'", errors)


def file_hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def check_twice(errors: list[str]):
    csvs = ["nodes_roles.csv", "clusters.csv", "top_nodes.csv"]
    before = {name: file_hash(OUT_DIR / name) for name in csvs}
    result = subprocess.run(
        [sys.executable, "run_pipeline.py", "--out", str(OUT_DIR)],
        capture_output=True, text=True,
    )
    if result.returncode != 0:
        fail(f"second pipeline run failed: {result.stderr[-2000:]}", errors)
        return
    after = {name: file_hash(OUT_DIR / name) for name in csvs}
    for name in csvs:
        if before[name] != after[name]:
            fail(f"{name} hash differs between two runs (non-deterministic)", errors)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--twice", action="store_true")
    parser.add_argument("--final", action="store_true")
    args = parser.parse_args()

    errors: list[str] = []
    nodes_roles = check_nodes_roles(errors, args.final)
    check_clusters(errors)
    check_top_nodes(errors, args.final)
    check_invariants(errors, nodes_roles)
    check_banned_words(errors)
    if args.twice:
        check_twice(errors)

    if errors:
        print(f"FAILED: {len(errors)} issue(s)")
        for e in errors:
            print(f"  - {e}")
        sys.exit(1)

    print("OK: all output checks passed")
    sys.exit(0)


if __name__ == "__main__":
    main()
