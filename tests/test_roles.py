import json
import math

import pandas as pd

from fixtures import make_fixture_graph
from moneygraph.evidence import BANNED
from moneygraph.features import compute_features
from moneygraph.graph import build_graph
from moneygraph.roles import assign_roles
from moneygraph.temporal import add_temporal


def fixture_result():
    raw = make_fixture_graph()
    graph = build_graph(raw)
    features = add_temporal(compute_features(graph, raw), raw.tx)
    roles = assign_roles(features, graph)
    return raw, graph, features.set_index("gid"), roles.set_index("gid")


def test_known_roles_and_boundaries():
    _, _, features, roles = fixture_result()
    assert roles.loc[2, "role"] == "consolidator"
    assert roles.loc[3, "role"] == "transit"
    assert roles.loc[4, "role"] == "terminal"
    assert roles.loc[5, "role"] == "distributor"
    assert roles.loc[6, "role"] == "boundary"
    assert roles.loc[7, "role"] == "peripheral"
    assert roles.loc[7, "evidence"] == "Seed без наблюдаемых переводов >=5 000 KZT в июле."
    assert roles.loc[41, "role"] != "coordinator"
    assert math.isnan(features.loc[41, "pass_ratio"])
    assert roles.loc[41, "role"] not in ("transit", "terminal")
    assert features.loc[1, "in_sum"] == 0
    assert math.isnan(features.loc[1, "pass_ratio"])
    assert roles.loc[1, "role"] not in ("transit", "terminal")
    assert features.loc[5, "depth"] == 2


def test_cycles_and_reciprocal_projection():
    _, graph, features, _ = fixture_result()
    assert features.loc[8, "in_cycle"] and features.loc[9, "in_cycle"]
    assert features.loc[8, "in_2cycle"] and features.loc[9, "in_2cycle"]
    assert features.loc[10, "in_cycle"] and not features.loc[10, "in_2cycle"]
    assert math.isclose(graph.graph["undirected_weighted"][8][9]["w"], math.log1p(50_000))


def test_late_inflow_and_depth_three_distributor():
    _, graph, features, roles = fixture_result()
    modified = features.reset_index().copy()
    modified.loc[modified.gid == 4, "late_inflow_share"] = 1.0
    late_roles = assign_roles(modified, graph).set_index("gid")
    assert late_roles.loc[4, "role"] != "terminal"
    assert features.loc[42, "depth"] == 3
    assert all(features.loc[gid, "depth"] == 4 for gid in graph.successors(42))
    assert roles.loc[42, "role"] == "distributor"
    assert roles.loc[6, "role"] != "terminal"


def test_trace_scores_and_censorship():
    _, graph, features, roles = fixture_result()
    for gid, row in roles.iterrows():
        trace = json.loads(row.rule_trace)
        assert {item["rule"] for item in trace} == {"coordinator", "consolidator", "distributor",
                                                    "transit", "terminal", "boundary", "peripheral"}
        assert 0 <= row.role_score <= 1
        if row.role != "peripheral":
            assert 0.5 <= row.role_score <= 1
        assert len(row.evidence) <= 200
        assert not any(word in row.evidence.lower() for word in BANNED)
        if features.loc[gid, "censored"]:
            assert row.role not in ("terminal", "transit", "distributor")


def test_depth_four_hub_can_consolidate():
    _, graph, features, _ = fixture_result()
    hub = features.reset_index().copy()
    hub.loc[hub.gid == 6, ["in_deg", "censored", "out_deg", "depth"]] = [8, True, 0, 4]
    roles = assign_roles(hub, graph).set_index("gid")
    assert roles.loc[6, "role"] == "consolidator"
    assert roles.loc[6, "role"] != "terminal"
