"""Frozen contracts for the MoneyGraph pipeline. Additive changes only."""

ROLES = ["coordinator", "consolidator", "distributor", "transit", "terminal", "boundary", "peripheral"]

ROLE_RU = {
    "coordinator": "Кандидат в координаторы",
    "consolidator": "Признаки консолидации",
    "distributor": "Признаки веерного распределения",
    "transit": "Признаки транзита",
    "terminal": "Кандидат в конечные получатели",
    "boundary": "Граница выгрузки",
    "peripheral": "Периферия",
}

NODES_ROLES_COLUMNS = ["gid", "role", "role_score", "cluster_id", "priority_score", "evidence"]
CLUSTERS_COLUMNS = ["cluster_id", "n_nodes", "n_seed", "sum_kzt_internal", "top_gids", "hypothesis"]
TOP_COLUMNS = ["rank", "gid", "role", "priority_score", "why"]
FEATURES_COLUMNS = [
    "gid", "depth", "is_seed", "in_deg", "out_deg", "seed_payers",
    "in_sum", "out_sum", "in_tx", "out_tx", "flow_diff", "pass_ratio",
    "out_observable", "censored", "inflow_incomplete",
    "seed_reach", "feeder_branches", "convergence_gain", "seed_flow_in",
    "returns_to_seed", "in_cycle", "in_2cycle",
    "betweenness", "wcc_id", "wcc_size",
    "max_payers_same_day", "max_payers_date", "max_payers_3d",
    "fast_through_share", "late_inflow_share", "first_date", "last_date",
    "x", "y",
]
ROLE_OUT_COLUMNS = ["gid", "role", "role_score", "secondary_roles", "evidence", "rule_trace"]
ENRICHED_COLUMNS = FEATURES_COLUMNS + [
    "role", "role_score", "secondary_roles", "evidence",
    "rule_trace", "cluster_id", "priority_score", "why",
    "priority_components",
]

EVIDENCE_MAX = 200
WHY_MAX = 300
TOP_N = 30


class DataError(Exception):
    pass
