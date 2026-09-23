# AGENTS.md — MoneyGraph

## Context
HackAlem AI hackathon, case «Граф денег». 5 hours, 3 developers, one repo.
Goal: given 81 known drug-related clients and their outgoing transfers traced 4 hops downstream,
build a pipeline that assigns every one of 2 248 nodes a role, cluster, priority score and evidence,
answering «кого смотреть первым и почему» for an AML analyst.

Tracing is outgoing-only from 81 seeds → downstream in the data = toward organizers (up the hierarchy).
No ground truth. Judged on: working end-to-end pipeline, defensible explainable criteria,
correct handling of declared data limitations, README + reproducibility (25 pts each of 100).

## Ownership — touch ONLY your files
| Developer | Files |
|---|---|
| DEV1 | run_pipeline.py, moneygraph/{config,io,quality,graph,features,temporal,pipeline,schemas}.py, moneygraph/extras/{resilience,completeness,routes}.py, scripts/*, tests/test_pipeline_contract.py, .gitignore, .env.example, requirements.txt, AGENTS.md, CLAUDE.md, docs/DATA_NOTES.md |
| DEV2 | moneygraph/{thresholds,roles,evidence,clustering,priority}.py, moneygraph/extras/sensitivity.py, tests/{fixtures,test_roles,test_priority,test_sensitivity}.py, docs/METHODOLOGY.md |
| DEV3 | app/**, moneygraph/extras/{queries,llm}.py, tests/test_extras.py, docs/solution_diagram.*, README.md |
| SHARED (DEV1 edits, additive only, announce before changing) | moneygraph/schemas.py |

If you need something changed outside your files: stop, tell the team, wait.
If a merge conflict touches a file you don't own: do not resolve it yourself, call the owner.

## Hard rules
1. Only `git add <explicit paths>`. Never `git add -A` or `git add .` after the initial skeleton commit.
2. No secrets anywhere — code, tests, docs, notebooks, commit messages. Keys only in gitignored `.env`.
3. No hardcoded gids. No lists of "expected" nodes. No tuning thresholds to match organizer figures.
4. Deterministic: seed=42 everywhere; sort by gid before any ordered output; never depend on set/dict iteration order.
5. No PageRank. No weighted betweenness (NetworkX treats weight as distance — big transfers become longest paths).
6. Never `G.to_undirected()` for edge weights — it overwrites reciprocal edges. Build summed undirected explicitly.
7. No hub/merchant/payroll suppression — on this graph all depth-4 nodes have out_deg=0, so forwarding-ratio logic erases real distributors.
8. No trained ML models.
9. No network calls in the pipeline. LLM only in extras/llm.py, only called from the UI.
10. All output text in Russian, hedged: «признаки», «кандидат», «гипотеза», «граница выгрузки».
    Banned in any output text: виновен, виновна, преступник, является организатором, установлено, доказано, остаток.
11. `starter/` is read-only. Import or copy with a one-line attribution comment.
12. "Done" = pasted command output proving it. Not a claim.

## Git workflow
- main: only receives merges at C0, C1, C2, final. Never commit directly after C0.
- Branches: dev1/pipeline, dev2/analytics, dev3/ui
- Merge order at every checkpoint: DEV1 → DEV2 → DEV3, merged by DEV1 only.
- After every checkpoint merge: everyone does git pull --rebase origin main on their branch.
- Commit prefix: [dev1], [dev2], [dev3] in every message.

## Checkpoints
- C0 ~0:25 — skeleton on main, contracts frozen, everyone branches
- C1 ~1:15 — real features + real roles + valid CSVs, check_outputs.py green
- C2 ~2:30 — full acceptance run, check_outputs.py --twice --final green. NO bonus work until C2 passes.
- FREEZE ~3:30 — no new features, only fixes
- FINAL ~4:15 — clean clone test, outputs regenerated, secret scan clean

## Commands
```bash
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
python run_pipeline.py                               # --data data --out outputs --seed 42
python scripts/check_outputs.py --twice --final
pytest -q
streamlit run app/main.py
bash scripts/secret_scan.sh
```

## Data
Three parquet files in data/ (gitignored):
- nodes.parquet: gid int64, depth int64, is_seed bool
- edges.parquet: src int64, dst int64, sum_kzt float64, n_tx int64, depth int64
- transactions.parquet: src int64, dst int64, date datetime64, sum_kzt float64

Known facts (verify and record in docs/DATA_NOTES.md at T+0):
- 2248 nodes, 3119 edges, 4840 transactions, 81 seeds, July 2026
- depth=4 nodes with no outgoing = traversal artifact, NOT terminal receivers → role = boundary
- Inflow is always a lower bound. Seed inflow is essentially unobserved.
- 444 nodes have depth=4 and out_deg=0 (censored). Never call these terminal.
- 354 nodes have out_sum > in_sum — likely unobserved inflow sources, not errors.
- 16 weakly connected components (verify on both full-node graph and edge-only graph; don't assert this number).
- Organizer figures (8–24 payers, 60–116 receivers, 72 ratio nodes, 8 Louvain communities) = plausibility checks only. Never tune to them.
- Transfers < 5000 KZT excluded — this is an export threshold, not an AML threshold. Make no claims about structuring.
- Data is July only — inflow on the last days may not have moved on yet. Guard terminal rule with late_inflow_share.
- Check date precision: if day-only, same-day ordering is unknown (note in DATA_NOTES, still compute temporal features).
- Build graph from nodes FIRST (19 isolated seeds have no edges).

## Contracts (moneygraph/schemas.py — frozen at C0, additive changes only)

```python
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

NODES_ROLES_COLUMNS   = ["gid", "role", "role_score", "cluster_id", "priority_score", "evidence"]
CLUSTERS_COLUMNS      = ["cluster_id", "n_nodes", "n_seed", "sum_kzt_internal", "top_gids", "hypothesis"]
TOP_COLUMNS           = ["rank", "gid", "role", "priority_score", "why"]
FEATURES_COLUMNS      = [
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
ROLE_OUT_COLUMNS      = ["gid", "role", "role_score", "secondary_roles", "evidence", "rule_trace"]
ENRICHED_COLUMNS      = FEATURES_COLUMNS + ["role", "role_score", "secondary_roles", "evidence",
                                             "rule_trace", "cluster_id", "priority_score", "why",
                                             "priority_components"]
EVIDENCE_MAX = 200
WHY_MAX      = 300
TOP_N        = 30

class DataError(Exception): pass
```

Function signatures (implement in the module that owns them):
```python
# moneygraph/io.py
def load_raw(data_dir: str | Path) -> RawData: ...          # raises DataError on missing columns
def write_outputs(enriched, clusters, top, out_dir) -> dict: ...  # enforces schema, 4dp, UTF-8 no BOM

# moneygraph/quality.py
def check_data(raw: RawData) -> dict: ...                   # reports, never raises on count mismatches

# moneygraph/graph.py
def build_graph(raw: RawData) -> nx.DiGraph: ...            # nodes first; stores undirected_weighted

# moneygraph/features.py
def compute_features(G: nx.DiGraph, raw: RawData) -> pd.DataFrame: ...

# moneygraph/temporal.py
def add_temporal(features_df: pd.DataFrame, tx_df: pd.DataFrame) -> pd.DataFrame: ...

# moneygraph/roles.py
def assign_roles(features_df, G, thresholds=None) -> pd.DataFrame: ...

# moneygraph/clustering.py
def detect_clusters(G, seed=42) -> pd.DataFrame: ...
def summarize_clusters(enriched_df, G) -> pd.DataFrame: ...

# moneygraph/priority.py
def score_priority(enriched_df, weights=None) -> pd.DataFrame: ...
def build_top_nodes(enriched_df, n=TOP_N) -> pd.DataFrame: ...

# moneygraph/pipeline.py
def run(data_dir, out_dir, seed=42) -> dict: ...

# extras — each wrapped in try/except inside pipeline.run
def resilience.simulate(G, enriched_df) -> pd.DataFrame: ...
def completeness.gaps(enriched_df) -> pd.DataFrame: ...
def routes.find(G, tx_df, enriched_df) -> pd.DataFrame: ...
def sensitivity.run(features_df, G) -> pd.DataFrame: ...
def queries.common_receivers(G, gids, max_hops=4, min_sources=2) -> pd.DataFrame: ...
def llm.ask(question, G, enriched_df) -> str | None: ...   # None on any error or missing key
```

## Methodology

### Features
- in_deg / out_deg: distinct payers / receivers (edges, not transactions; exclude self-loops)
- seed_payers: count of seed in-neighbors
- flow_diff = in_sum − out_sum  («разность наблюдаемых потоков» — never «остаток»)
- pass_ratio = out_sum / in_sum; NaN if is_seed or in_sum == 0
- out_observable = depth <= 3
- censored = depth == 4 AND out_deg == 0
- inflow_incomplete = is_seed OR out_sum > 1.2 * in_sum
- S(v) = frozenset of seeds with a directed path to v (excluding v itself); seed_reach = len(S(v))
- feeder_branches = count of in-neighbors u where |S(u) ∪ ({u} if u is seed else ∅)| >= 2
- convergence_gain = seed_reach − max over predecessors u of |S(u) ∪ ({u} if seed else ∅) − {v}|; 0 if no preds
- seed_flow_in: seeds → flow_out = out_sum; others → flow_in(v) = Σ_u flow_out(u)*edge(u,v)/out_sum(u);
  flow_out(v) = flow_in(v) * min(1, out_sum/in_sum). Topological order if DAG, else iterate 50 rounds until max Δ < 1.
- returns_to_seed: any seed reachable from v
- in_cycle: v in any directed cycle length 2–4 (nx.simple_cycles length_bound=4)
- in_2cycle: reciprocal edge exists (u→v and v→u)
- betweenness: nx.betweenness_centrality(G, normalized=True)  ← UNWEIGHTED, no weight= argument
- wcc_id, wcc_size: on full node graph
- temporal (from transactions.parquet): max_payers_same_day, max_payers_date, max_payers_3d,
  fast_through_share, late_inflow_share, first_date, last_date
- x, y: spring_layout on undirected_weighted, seed=42

### Role rules (fixed precedence; first passing rule = assigned role; others = secondary_roles)
All thresholds live ONLY in thresholds.py. Initial values calibrated by DEV2 from distributions by 0:50.

| Role | Conditions (all must pass) |
|---|---|
| coordinator | seed_reach >= MIN; feeder_branches >= MIN; convergence_gain >= MIN |
| consolidator | in_deg >= MIN |
| distributor | out_observable; out_deg >= MIN |
| transit | out_observable; not seed; in_sum > 0; RATIO_LO <= pass_ratio <= RATIO_HI; in_deg <= DEG_MAX; out_deg <= DEG_MAX |
| terminal | out_observable; not censored; in_sum >= MIN; (pass_ratio <= MAX or out_deg==0); late_inflow_share < 0.5 |
| boundary | censored AND no rule above passed |
| peripheral | nothing passed |

CRITICAL INVARIANTS (check_outputs.py enforces these):
- Zero censored nodes may have role terminal, transit, or distributor
- Zero seed nodes may have a role derived from pass_ratio (transit, terminal)
- All role_score values in [0, 1]; all priority_score values in [0, 1]
- evidence len() in [1, 200] for every node; why len() in [1, 300]

role_score for assigned roles: mean of graded strengths per condition,
  each = 0.5 + 0.5 * clip((value − threshold) / (strong − threshold), 0, 1)
role_score boundary = 1.0
role_score peripheral = 1 − 0.5 * max_fraction_of_any_rule_conditions_passed

rule_trace = JSON list of ALL rules evaluated: [{rule, condition, value, threshold, passed}]

### Evidence templates (Russian, <= 200 chars, humanize KZT)
KZT humanizer: >= 1_000_000 → "X,X млн KZT"; >= 1_000 → "XXX тыс. KZT"; else "XXX KZT"

- coordinator: "Кандидат в координаторы: сходятся средства {seed_reach} seed через {feeder_branches} ветки; получено {in_sum}."
- consolidator: "Признаки консолидации: {in_deg} плательщиков ({seed_payers} seed), получено {in_sum}; дальше ушло {pass_pct}%; до {max_payers_3d} платеж. за 3 дня."
- distributor: "Признаки веерного распределения: {out_deg} получателей, отправлено {out_sum}."
- transit: "Признаки транзита: пропущено {pass_pct}% полученного ({in_sum}); {fast_pct}% ушло в течение 2 дней."
- terminal: "Кандидат в конечные получатели (в наблюдаемом окне): получено {in_sum} от {in_deg} плательщиков, дальше ушло {pass_pct}%."
- boundary: "Граница выгрузки (4-е колено): исходящие не выгружались, роль не определима; получено {in_sum} от {in_deg}."
- peripheral: "Выраженных признаков роли нет: {in_deg} вх. / {out_deg} исх., оборот {turnover}."

Modifiers:
- If censored: replace "дальше ушло X%" with "исходящие не наблюдаются (граница выгрузки)"
- If inflow_incomplete and room: append "; есть входящие вне выборки"
- Isolated seed (is_seed, in_deg==0, out_deg==0): "Seed без наблюдаемых переводов >=5 000 KZT в июле."
- Truncate to 199 chars and append "…" if over limit

### Clustering
- Input: G.graph['undirected_weighted'] — undirected Graph with w(u,v) = log1p(sum of kzt both directions)
- nx.community.louvain_communities(weight='w', resolution=1.0, seed=42)
- Split any disconnected community into its connected components
- Isolated nodes (degree 0) → singleton clusters
- Multi-node cluster IDs: 1..K sorted by (sum_kzt_internal desc, n_nodes desc, min_gid asc)
- Singletons: numbered after, sorted by gid
- sum_kzt_internal = sum of edge sum_kzt where both src and dst are in the cluster
- top_gids = top-5 gids by priority_score, joined with ";"
- hypothesis templates (first match):
  - isolated node → "Изолированный узел: нет наблюдаемых переводов >=5 000 KZT"
  - has coordinator → "Гипотеза: контур сбора — средства {n_seed} seed сходятся к gid {top_gid}"
  - consolidator and n_seed>=2 → "Гипотеза: сбор средств {n_seed} seed через gid {top_gid}"
  - distributor → "Гипотеза: веерное распределение от gid {top_gid} на {k} получателей"
  - transit share >= 0.3 → "Гипотеза: транзитная цепочка без удержания средств"
  - boundary share >= 0.5 → "Ветка на границе выгрузки: {pct}% узлов на 4-м колене"
  - else → "Периферийная группа без выраженных ролей"

### Priority
priority_score = novelty * (0.35*role_weight*role_score + 0.30*pct(seed_flow_in) + 0.20*pct(max(in_sum,out_sum)) + 0.15*pct(betweenness))
- pct = rank(pct=True, method='average')
- novelty: 0.7 if is_seed else 1.0
- role_weights: coordinator=1.0, consolidator=0.9, distributor=0.75, transit=0.6, terminal=0.6, boundary=0.4, peripheral=0.1

why = "{ROLE_RU}: {evidence}. Драйверы: {top2}. Действие: {action}"
actions:
- coordinator/consolidator → "углублённая проверка, кандидат для запроса в правоохранительные органы"
- distributor → "проверить получателей рассылки"
- transit → "проследить цепочку до точки консолидации"
- terminal → "проверить происхождение средств"
- boundary → "запросить исходящие переводы по узлу"
- peripheral → "низкий приоритет"

### Extras (all run after mandatory CSVs, each in try/except, failure = warning only)
- resilience.csv: remove top-N by priority (5,10,20), all 81 seeds, top-N by degree (5,10,20);
  columns: strategy, n_removed, n_components, largest_wcc, role_nodes_in_largest_wcc
- completeness.csv: boundary + inflow_incomplete nodes ranked by seed_flow_in;
  columns: gid, reason, seed_flow_in, in_sum, in_deg, request
- routes.csv: chains through transit nodes (0–2 days per hop) + directed cycles via nx.simple_cycles(length_bound=4);
  columns: path, kind, min_leg_kzt, days_span, n_occurrences
- sensitivity.csv: each graded threshold * 0.75 and * 1.25, re-run roles;
  columns: param, factor, role_flips, top20_jaccard

## UI (Streamlit, app/)
Role colors: coordinator=#d32f2f, consolidator=#f57c00, distributor=#1976d2,
             transit=#388e3c, terminal=#7b1fa2, boundary=#90a4ae, peripheral=#e0e0e0

Six tabs: Обзор | Приоритеты | Сеть | Карточка узла | Кластеры | Анализ
Sidebar: gid search → st.session_state['active_gid']
st.cache_data on all file reads. Missing outputs → friendly message, st.stop().

- Обзор: KPIs from run_meta.json, role distribution chart, data quality panel
  (explicitly: boundary count, incomplete inflow, 5000 KZT threshold, July-only, right-edge censoring)
- Приоритеты: top-30 table, row selection sets active_gid, download button
- Сеть: pyvis graph, physics=OFF, precomputed x/y, role/cluster color toggle, size∝priority,
  active_gid enlarged + highlighted; ego view 1–2 hops up/down with sum_kzt labels;
  fallback to ego-only if full graph slow
- Карточка узла: ROLE_RU, role_score, priority_score, evidence, why, full rule_trace table (ALL rules, ✓/✗),
  key metrics with Russian labels, in/out counterparty bar charts, transaction timeline, action
- Кластеры: cluster table + selected cluster subgraph
- Анализ: sensitivity table, resilience chart, completeness table, routes table,
  common_receivers text input, optional LLM question box (hidden if no API key)

## Outputs committed to repo
nodes_roles.csv, clusters.csv, top_nodes.csv, run_meta.json,
sensitivity.csv, resilience.csv, completeness.csv, routes.csv

## Outputs gitignored (generated, large)
node_features.parquet, graph_edges.parquet

## Verification protocol (run after every significant change)
1. Invariants on real data: Σin_deg = Σout_deg = edge count; every depth-4 node has out_deg=0;
   every non-seed has in_deg>=1 and seed_reach>=1; Σn_tx = transaction count. Investigate failures, never silence.
2. Hand recompute 5 random gids directly from raw edges; features must match exactly.
3. Adversarial fixtures (tests/fixtures.py):
   - seed→seed chain: no coordinator
   - depth-4 hub with many payers: consolidator, NOT terminal
   - late-July-only inflow: not terminal
   - seed with no inflow: no transit or terminal
   - isolated seed: peripheral + correct evidence
   - 2-cycle and 3-cycle: in_cycle=True, in_2cycle correct
   - depth-3 distributor with all receivers at depth-4: still distributor
   - reciprocal pair: projection weight = sum of both directions
4. Print role distribution after every change. If coordinators > ~30: tighten rule, document why.
   If top-30 seed share > 50%: check novelty factor.
5. Determinism: two runs produce byte-identical CSVs.

<!-- concord:start -->
## Concord — shared work-state for coding agents

<!-- concord:workflow-version=6 -->

This project uses Concord MCP. Keep coordination to the five workflow tools:

- **Before editing**, call `start_work` with the task, your agent kind, and
  expected files or modules. It registers presence, accepts assigned work when
  appropriate, claims the scope, and returns overlap warnings. Concord derives
  your `agent_id` from your session — omit it unless your client told you one.
- Use `inspect_work` to read the workspace, one task, one agent, or one message
  thread. Use `update_work` for durable progress and for live prompts/replies
  to another promptable workspace agent, including while that agent is busy.
- Use `transfer_work` for assignment, acceptance, decline, release,
  reassignment, evidence-bearing handoff offers, and reopening.
- **Before finishing**, call `finish_work` once with the outcome, changed
  files, tests, assumptions, decisions, risks, guardrails, and provenance. It
  records evidence and can mark work review-ready or terminal.

Keep each claim small and resolve reported overlaps before editing. Concord
regenerates human-readable review artifacts in `.concord/`.

Enforcement remains client-dependent. `concord doctor` reports setup and
workflow adoption; optional hooks can block exact-file collisions.

In Grok Build, keep this session reachable while idle by starting one persistent
monitor for `concord inbox watch --provider grok`. Do not start a duplicate when that monitor is active.

In Cursor, start exactly one Cursor background Shell task for `concord inbox watch --provider cursor --once`.
Leave it active when the turn ends. When Cursor resumes you with its completion,
answer the emitted peer message and immediately start a fresh background monitor.

In Gemini CLI, start the exact monitor command supplied by the SessionStart hook
(`concord inbox watch --agent <agent-id> --provider gemini --once`) with `run_shell_command` and `is_background: true`. Project
settings inject background completion into the agent. Answer the peer message,
then immediately start a fresh background monitor.
<!-- concord:end -->
