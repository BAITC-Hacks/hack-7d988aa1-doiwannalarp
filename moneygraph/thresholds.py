"""Role-rule thresholds. Owned by DEV2; DEV1 seeds initial placeholder values
so the pipeline runs end to end. All values are domain-reasoned guesses to be
recalibrated by DEV2 from the real feature distributions.

Each threshold has a *_STRONG pair used to grade role_score in [0.5, 1.0].
"""

# coordinator: funds from multiple seeds converge through multiple branches.
# convergence_gain is the true rarity filter here — on this dataset it only
# takes values {0, 1, 2} and is >0 for 47/2248 nodes, so MIN=1 already isolates
# real convergence points; seed_reach/feeder_branches trim the rest.
COORDINATOR_SEED_REACH_MIN = 3       # p50 of nonzero seed_reach is 7, so 3 is a low bar kept for the AND
COORDINATOR_SEED_REACH_STRONG = 10   # ~p95 of nonzero seed_reach
COORDINATOR_FEEDER_BRANCHES_MIN = 2  # p75 of nonzero feeder_branches
COORDINATOR_FEEDER_BRANCHES_STRONG = 5  # ~p95 of nonzero feeder_branches
COORDINATOR_CONVERGENCE_GAIN_MIN = 1    # any measured gain; observed max on this data is 2
COORDINATOR_CONVERGENCE_GAIN_STRONG = 2  # observed max convergence_gain

# consolidator: many distinct payers feed one node
CONSOLIDATOR_IN_DEG_MIN = 4          # between p95 (3) and p99 (6) of nonzero in_deg
CONSOLIDATOR_IN_DEG_STRONG = 10      # beyond p99 of nonzero in_deg

# distributor: fans out to many receivers while still observable (depth<=3)
DISTRIBUTOR_OUT_DEG_MIN = 4          # ~p75 of nonzero out_deg
DISTRIBUTOR_OUT_DEG_STRONG = 16      # ~p95 of nonzero out_deg

# transit: passes most of what it receives straight through, low fan-in/out
TRANSIT_RATIO_LO = 0.7               # passes through most of inflow
TRANSIT_RATIO_HI = 1.3               # allow small measurement slack above 1.0
TRANSIT_DEG_MAX = 3                  # simple pass-through, not a hub

# terminal: receives observable inflow, does not forward it on (in this window)
TERMINAL_IN_SUM_MIN = 50_000.0       # p50 of nonzero in_sum, a few real transfers not noise
TERMINAL_IN_SUM_STRONG = 620_000.0   # ~p95 of nonzero in_sum
TERMINAL_PASS_RATIO_MAX = 0.3        # keeps most of what it receives
TERMINAL_LATE_INFLOW_GUARD = 0.5     # matches methodology spec: guard against right-edge censoring

role_weights = {
    "coordinator": 1.0,
    "consolidator": 0.9,
    "distributor": 0.75,
    "transit": 0.6,
    "terminal": 0.6,
    "boundary": 0.4,
    "peripheral": 0.1,
}

priority_weights = {
    "role": 0.35,
    "seed_flow_in": 0.30,
    "turnover": 0.20,
    "betweenness": 0.15,
}
