"""Distribution-calibrated, reproducible MoneyGraph decision thresholds."""

# Three reached seeds separates convergence from ordinary one-source chains.
COORD_SEED_REACH_MIN = 3
# Ten reached seeds is a clear multi-source concentration.
COORD_SEED_REACH_STRONG = 10
# Three feeder branches narrow 31 initial candidates to 13 clear convergence points.
COORD_FEEDER_MIN = 3
# Five feeder branches denotes a pronounced convergence point.
COORD_FEEDER_STRONG = 5
# Any positive gain identifies convergence absent from a single predecessor.
COORD_GAIN_MIN = 1
# Two gained seed paths is the observed high-convergence level.
COORD_GAIN_STRONG = 2

# Four payers exceeds the all-node in-degree p95 of three.
CONS_PAYERS_MIN = 4
# Ten payers is well beyond the all-node in-degree p99 of six.
CONS_PAYERS_STRONG = 10
# Three distinct payers in three days supports a concentrated collection burst.
CONS_3D_STRONG = 3

# Six receivers exceeds the all-node out-degree p95 of five.
DIST_RECEIVERS_MIN = 6
# Twenty-four receivers approximates the all-node out-degree p99 of 23.53.
DIST_RECEIVERS_STRONG = 24

# Passing at least 70% of observed inflow separates through-flow from p75=57%.
TRANSIT_RATIO_LO = 0.7
# A 130% ceiling allows modest missing inflow but excludes extreme ratios.
TRANSIT_RATIO_HI = 1.3
# At most three counterparties per side keeps transit distinct from hubs.
TRANSIT_DEG_MAX = 3

# Fifty thousand KZT equals the all-node median observed inflow.
TERMINAL_INSUM_MIN = 50_000.0
# Six hundred twenty thousand KZT is slightly above inflow p95=613,779.
TERMINAL_INSUM_STRONG = 620_000.0
# Forwarding at most 30% indicates weak observed onward flow.
TERMINAL_RATIO_MAX = 0.3
# Less than half the inflow arriving late guards the July right edge.
LATE_INFLOW_MAX = 0.5

# Role multipliers encode analytical relevance without declaring guilt.
ROLE_WEIGHTS = dict(coordinator=1.0, consolidator=0.9, distributor=0.75,
                    transit=0.6, terminal=0.6, boundary=0.4, peripheral=0.1)
# The role and seed-linked flow lead; volume and unweighted centrality support.
PRIORITY_WEIGHTS = dict(role=0.35, seed_flow=0.30, volume=0.20,
                        betweenness=0.15)
# Known seeds receive a novelty discount so discovery favors downstream nodes.
NOVELTY_SEED = 0.7
