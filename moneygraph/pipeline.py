import json
import time
import traceback
from pathlib import Path

from moneygraph import clustering, config, graph, io, priority, quality, roles, temporal
from moneygraph.features import compute_features
from moneygraph.schemas import ENRICHED_COLUMNS


def _stage(timings: dict, name: str, fn, *args, **kwargs):
    t0 = time.perf_counter()
    result = fn(*args, **kwargs)
    timings[name] = round(time.perf_counter() - t0, 4)
    return result


def run(data_dir=None, out_dir=None, seed: int = config.SEED) -> dict:
    data_dir = Path(data_dir) if data_dir else config.DATA_DIR
    out_dir = Path(out_dir) if out_dir else config.OUT_DIR
    out_dir.mkdir(parents=True, exist_ok=True)

    timings: dict = {}

    raw = _stage(timings, "load_raw", io.load_raw, data_dir)
    quality_report = _stage(timings, "check_data", quality.check_data, raw)
    quality.write_data_notes(quality_report)

    G = _stage(timings, "build_graph", graph.build_graph, raw)
    features_df = _stage(timings, "compute_features", compute_features, G, raw)
    features_df = _stage(timings, "add_temporal", temporal.add_temporal, features_df, raw.tx)

    roles_df = _stage(timings, "assign_roles", roles.assign_roles, features_df, G)
    enriched = features_df.merge(roles_df, on="gid", how="left")

    clusters_assign = _stage(timings, "detect_clusters", clustering.detect_clusters, G, seed)
    enriched = enriched.merge(clusters_assign, on="gid", how="left")

    priority_df = _stage(timings, "score_priority", priority.score_priority, enriched)
    enriched = enriched.merge(priority_df, on="gid", how="left")

    for col in ENRICHED_COLUMNS:
        if col not in enriched.columns:
            enriched[col] = None
    enriched = enriched[ENRICHED_COLUMNS].sort_values("gid").reset_index(drop=True)

    clusters_df = _stage(timings, "summarize_clusters", clustering.summarize_clusters, enriched, G)
    top_df = _stage(timings, "build_top_nodes", priority.build_top_nodes, enriched)

    paths = _stage(timings, "write_outputs", io.write_outputs, enriched, clusters_df, top_df, out_dir)
    paths["graph_edges"] = _stage(timings, "write_graph_edges", io.write_graph_edges, raw.edges, out_dir)

    extras_status = {}
    for name, fn_path in [
        ("resilience", "moneygraph.extras.resilience"),
        ("completeness", "moneygraph.extras.completeness"),
        ("routes", "moneygraph.extras.routes"),
    ]:
        try:
            t0 = time.perf_counter()
            module = __import__(fn_path, fromlist=["run"])
            df = module.run(G, enriched, raw)
            df.to_csv(out_dir / f"{name}.csv", index=False, encoding="utf-8")
            timings[f"extra_{name}"] = round(time.perf_counter() - t0, 4)
            extras_status[name] = "ok"
        except Exception as exc:  # noqa: BLE001 - extras must never break the pipeline
            print(f"[pipeline] warning: extra '{name}' failed: {exc}")
            traceback.print_exc()
            extras_status[name] = f"failed: {exc}"

    role_distribution = enriched["role"].value_counts().to_dict()

    meta = {
        "timings_seconds": timings,
        "counts": {
            "nodes": int(quality_report["n_nodes"]),
            "edges": int(quality_report["n_edges"]),
            "transactions": int(quality_report["n_tx"]),
            "seeds": int(quality_report["n_seeds"]),
            "clusters": int(clusters_df["cluster_id"].nunique()),
        },
        "role_distribution": {str(k): int(v) for k, v in role_distribution.items()},
        "quality": quality_report,
        "extras_status": extras_status,
        "output_paths": paths,
        "seed": seed,
    }
    (out_dir / "run_meta.json").write_text(json.dumps(meta, indent=2, ensure_ascii=False), encoding="utf-8")

    return meta
