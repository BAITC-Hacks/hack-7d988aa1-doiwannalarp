"""Deterministic role rules with a complete condition trace."""

import json
import math

import pandas as pd

from moneygraph import thresholds as defaults
from moneygraph.evidence import build_evidence


def _threshold(source, name):
    return source[name] if isinstance(source, dict) else getattr(source, name)


def _num(value):
    try:
        value = float(value)
        return value if math.isfinite(value) else float("nan")
    except (TypeError, ValueError):
        return float("nan")


def _graded(value, minimum, strong):
    if not math.isfinite(value):
        return 0.5
    if strong <= minimum:
        return 1.0
    return 0.5 + 0.5 * max(0.0, min(1.0, (value - minimum) / (strong - minimum)))


def assign_roles(features_df, G, thresholds=None) -> pd.DataFrame:
    """Evaluate every rule in precedence order and retain every condition result."""
    th = defaults if thresholds is None else thresholds
    rows = []
    for data in features_df.sort_values("gid", kind="mergesort").to_dict("records"):
        gid = int(data["gid"])
        seed = bool(data["is_seed"])
        indeg, outdeg = int(data["in_deg"]), int(data["out_deg"])
        depth = int(data["depth"])
        censored = bool(data.get("censored", False)) or (depth == 4 and outdeg == 0)
        observable = bool(data.get("out_observable", depth <= 3)) and not censored
        insum = _num(data["in_sum"])
        ratio = _num(data.get("pass_ratio")) if not seed else float("nan")
        late = _num(data.get("late_inflow_share"))
        reach = _num(data.get("seed_reach"))
        feeders = _num(data.get("feeder_branches"))
        gain = _num(data.get("convergence_gain"))
        trace = []
        results = {}

        def rule(name, conditions):
            passed = all(p for _, _, _, p in conditions)
            results[name] = passed
            for label, value, threshold, result in conditions:
                if isinstance(value, float) and not math.isfinite(value):
                    value = None
                trace.append({"rule": name, "condition": label, "value": value,
                              "threshold": threshold, "passed": bool(result)})

        rule("coordinator", [
            ("seed_reach", reach, _threshold(th, "COORD_SEED_REACH_MIN"), reach >= _threshold(th, "COORD_SEED_REACH_MIN")),
            ("feeder_branches", feeders, _threshold(th, "COORD_FEEDER_MIN"), feeders >= _threshold(th, "COORD_FEEDER_MIN")),
            ("convergence_gain", gain, _threshold(th, "COORD_GAIN_MIN"), gain >= _threshold(th, "COORD_GAIN_MIN")),
        ])
        rule("consolidator", [
            ("in_deg", indeg, _threshold(th, "CONS_PAYERS_MIN"), indeg >= _threshold(th, "CONS_PAYERS_MIN")),
        ])
        rule("distributor", [
            ("out_observable", observable, True, observable),
            ("out_deg", outdeg, _threshold(th, "DIST_RECEIVERS_MIN"), outdeg >= _threshold(th, "DIST_RECEIVERS_MIN")),
        ])
        rule("transit", [
            ("out_observable", observable, True, observable),
            ("not_seed", not seed, True, not seed),
            ("in_sum_positive", insum, 0, insum > 0),
            ("pass_ratio_lower", ratio, _threshold(th, "TRANSIT_RATIO_LO"), ratio >= _threshold(th, "TRANSIT_RATIO_LO")),
            ("pass_ratio_upper", ratio, _threshold(th, "TRANSIT_RATIO_HI"), ratio <= _threshold(th, "TRANSIT_RATIO_HI")),
            ("in_deg_max", indeg, _threshold(th, "TRANSIT_DEG_MAX"), indeg <= _threshold(th, "TRANSIT_DEG_MAX")),
            ("out_deg_max", outdeg, _threshold(th, "TRANSIT_DEG_MAX"), outdeg <= _threshold(th, "TRANSIT_DEG_MAX")),
        ])
        terminal_flow = (math.isfinite(ratio) and ratio <= _threshold(th, "TERMINAL_RATIO_MAX")) or outdeg == 0
        rule("terminal", [
            ("out_observable", observable, True, observable),
            ("not_censored", not censored, True, not censored),
            ("not_seed", not seed, True, not seed),
            ("in_sum", insum, _threshold(th, "TERMINAL_INSUM_MIN"), insum >= _threshold(th, "TERMINAL_INSUM_MIN")),
            ("low_forwarding_or_no_outflow", ratio if outdeg else 0, _threshold(th, "TERMINAL_RATIO_MAX"), terminal_flow),
            ("late_inflow_share", late, _threshold(th, "LATE_INFLOW_MAX"), late < _threshold(th, "LATE_INFLOW_MAX")),
        ])
        rule("boundary", [
            ("censored", censored, True, censored),
            ("no_prior_rule", not any(results.values()), True, not any(results.values())),
        ])
        rule("peripheral", [
            ("no_prior_rule", not any(results.values()), True, not any(results.values())),
        ])
        role = next(name for name in ("coordinator", "consolidator", "distributor", "transit",
                                      "terminal", "boundary", "peripheral") if results[name])
        secondary = [name for name in ("coordinator", "consolidator", "distributor", "transit",
                                        "terminal", "boundary") if name != role and results[name]]
        if role == "coordinator":
            strengths = [_graded(reach, _threshold(th, "COORD_SEED_REACH_MIN"), _threshold(th, "COORD_SEED_REACH_STRONG")),
                         _graded(feeders, _threshold(th, "COORD_FEEDER_MIN"), _threshold(th, "COORD_FEEDER_STRONG")),
                         _graded(gain, _threshold(th, "COORD_GAIN_MIN"), _threshold(th, "COORD_GAIN_STRONG"))]
        elif role == "consolidator":
            strengths = [_graded(indeg, _threshold(th, "CONS_PAYERS_MIN"), _threshold(th, "CONS_PAYERS_STRONG"))]
        elif role == "distributor":
            strengths = [_graded(outdeg, _threshold(th, "DIST_RECEIVERS_MIN"), _threshold(th, "DIST_RECEIVERS_STRONG"))]
        elif role == "transit":
            strengths = [_graded(min(ratio, 1.0), _threshold(th, "TRANSIT_RATIO_LO"), 1.0)]
        elif role == "terminal":
            strengths = [_graded(insum, _threshold(th, "TERMINAL_INSUM_MIN"), _threshold(th, "TERMINAL_INSUM_STRONG"))]
        elif role == "boundary":
            strengths = [1.0]
        else:
            fractions = []
            for name in ("coordinator", "consolidator", "distributor", "transit", "terminal"):
                checks = [item["passed"] for item in trace if item["rule"] == name]
                fractions.append(sum(checks) / len(checks))
            strengths = [1.0 - 0.5 * max(fractions)]
        score = float(sum(strengths) / len(strengths))
        evidence = build_evidence({**data, "role": role, "censored": censored})
        rows.append({"gid": gid, "role": role, "role_score": score,
                     "secondary_roles": json.dumps(secondary, ensure_ascii=False),
                     "evidence_key": role, "evidence": evidence,
                     "rule_trace": json.dumps(trace, ensure_ascii=False, separators=(",", ":"))})
    return pd.DataFrame(rows, columns=["gid", "role", "role_score", "secondary_roles",
                                       "evidence_key", "evidence", "rule_trace"])
