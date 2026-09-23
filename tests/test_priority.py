import json

import pandas as pd

from fixtures import make_fixture_graph
from moneygraph import thresholds
from moneygraph.evidence import BANNED
from moneygraph.features import compute_features
from moneygraph.graph import build_graph
from moneygraph.priority import build_top_nodes, score_priority
from moneygraph.roles import assign_roles
from moneygraph.schemas import WHY_MAX
from moneygraph.temporal import add_temporal


def ranked_fixture():
    raw = make_fixture_graph()
    graph = build_graph(raw)
    features = add_temporal(compute_features(graph, raw), raw.tx)
    roles = assign_roles(features, graph)
    enriched = features.merge(roles, on="gid")
    priority = score_priority(enriched)
    return enriched.merge(priority, on="gid"), graph


def test_scores_explanations_and_novelty():
    enriched, _ = ranked_fixture()
    assert enriched.priority_score.between(0, 1).all()
    for row in enriched.itertuples():
        assert row.why and len(row.why) <= WHY_MAX
        assert not any(word in row.why.lower() for word in BANNED)
        raw_score = sum(json.loads(row.priority_components).values())
        factor = thresholds.NOVELTY_SEED if row.is_seed else 1.0
        assert abs(row.priority_score - factor * raw_score) < 1e-12


def test_top_ranks_and_determinism():
    enriched, graph = ranked_fixture()
    top = build_top_nodes(enriched, n=15)
    assert top["rank"].tolist() == list(range(1, len(top) + 1))
    assert top.priority_score.is_monotonic_decreasing
    first = score_priority(enriched.drop(columns=["priority_score", "why", "priority_components"]))
    second = score_priority(enriched.drop(columns=["priority_score", "why", "priority_components"]))
    pd.testing.assert_frame_equal(first, second)
