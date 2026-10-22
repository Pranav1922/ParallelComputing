# Validation Plan and Hostile Architecture Review

Nothing here has been run. No validation outcome is claimed.

---

## 1. Correctness tests (unit and property) — `tests/`

Property tests are plain pytest loops over a few hundred seeded random instances (`n ≤ 30`), since `hypothesis` is not
installed.

### `test_model.py`

| Test | Checks |
|---|---|
| Hand-computed schedules | 3 small DAGs with makespans worked out by hand; builder output matches exactly. |
| `validate` catches each violation | Four deliberately broken schedules (precedence, overlap, wrong duration, missing task) each return a violation. This proves the checker is not vacuous. |
| `place` rejects non-ready task | Raises. |
| Insertion | Crafted case: a gap exists and fits → the task starts in the gap; gap too short → appended. On random instances, insertion `est ≤` append `est`, and the result passes `validate`. |
| Append reproduces insertion | For random insertion-built schedules, replaying tasks in start-time order in append mode gives the identical schedule. |
| Append restriction | A valid but deliberately delayed (non-semi-active) schedule is **not** reproduced: the replay starts every task no later and has a strictly smaller makespan. |
| Independent recomputation | Start and finish times and the makespan recomputed from processor assignment and per-processor order alone (no builder) equal the builder's. |
| Bounds | For random instances and random valid schedules: `lower_bound ≤ Cmax ≤ Σ_t max_p cost[t, p]`. |
| Edge cases | `n = 1`; chain (no parallelism: `Cmax` = sum on chosen processors); independent tasks (no edges); `m = 1` (`Cmax = serial`); `m > n`. |
| Independence | `validate` uses only `Instance` and the three `Schedule` arrays; it does not import or call `ScheduleBuilder`. |

### `test_workloads.py`

| Test | Checks |
|---|---|
| DAG invariants | Acyclic; edges go from lower to higher id; `n` exact; every non-source task has ≥ 1 parent; costs > 0; shape `(n, m)`. |
| Determinism | Same seed → identical hash. Different instance index → different hash. |
| Class properties | Empirical work CV within tolerance of the class target over many instances; `homog` columns identical; `hetero` has the stated number of accelerators. |
| Split disjointness | For the actual matrices of `configs/full.toml`, `pilot.toml` and `cost_probe.toml`: no duplicate hash inside any split, none shared by any pair of splits. Empty workloads are excluded from the matrix and tested separately as fixtures. The runner repeats the check at campaign start. |

### `test_heuristics.py`

| Test | Checks |
|---|---|
| Validity | Every heuristic yields a valid schedule on every one of 500 seeded instances. |
| Reachable by append | On the same 500 instances, every heuristic schedule replays exactly in append mode. |
| Determinism | Two calls give identical arrays. |
| Known cases | `m = 1`: all heuristics give `Cmax = Σ cost`. Independent equal tasks on `homog`: `Cmax = ceil(n/m) · w`. |
| Rule semantics | On a crafted instance, `SPT-EFT` places the shortest ready task first; `HEFT` follows upward-rank order. |
| Tie-breaking | Instances with deliberately equal costs and ranks give the schedule predicted by the rules in `ALGORITHM_DESIGN.md` §1.3; result is unchanged under a different `PYTHONHASHSEED`. |
| Not handicapped | On `homog`, `FCFS-EAT` ≡ `FCFS-EFT`. A crafted gap-filling case shows insertion strictly improving on append for `LPT-EFT` and `HEFT`. The mean makespan of each heuristic with insertion vs forced append on random instances is printed as a diagnostic (greedy rules give no per-instance guarantee, so it is not asserted). |

### `test_ga.py`

| Test | Checks |
|---|---|
| Decode validity | Random chromosomes always decode to valid schedules. |
| Round trip | Encoding any heuristic schedule (start-time order) and decoding returns the identical schedule. |
| Elitism monotonicity | Best fitness in the trace never increases. |
| Budget matching | All five methods report exactly `max_evals` evaluations, seeds included, for budgets from 1 to 300 including ones below the population size and not divisible by it. |
| Runner integration | S01 rows carry the algorithm seed, evaluation count and measured optimization time; `ga_trace.csv` ends at each run's makespan and budget; a GA timeout becomes a `timeout` row with `NA` measurements; the campaign reproduces. |
| Figure data | Normalised makespan ≥ 1 for every row, instance value and plotted quartile; the plotted summary is recomputable from the per-instance CSV, which matches `master.csv`. |
| Seeded ≤ seeds | Seeded `GA` result ≤ every seed heuristic's makespan. |
| Exact optimum | On `n = 6, m = 2` instances, no algorithm's result is below the brute-force optimum (hard assertion). How often GA reaches the optimum is printed as a diagnostic, not asserted. |
| Reproducibility | Same `algo_seed` → identical result. |
| `GA-KEYS-EFT` seeds decoded, not injected | With a budget equal to the seed count, the result is exactly the best seed *as decoded by the keys-only decoder*; on the test instances this is sometimes worse than the heuristic, so no non-representable incumbent is kept. |
| Paired table | `improvement_mean = 1 − ratio_mean`; better + tie + worse = instances; GA never worse than its seeds `HEFT`, `FCFS-EAT`; a p-value only for the primary comparison. |
| S01 figure data | G2a per-run CSV matches `master.csv`; G2b curves end at each run's final makespan / HEFT; G3 plotted medians recompute from the per-instance CSV; every plotted q25 ≤ median ≤ q75. |
| Config lock | `configs/s01_final.toml` has the same `[workload]` and seed as `full.toml` and the same `[ga]` as the pilot. |

### `test_analysis_s01.py` (formulas, on a hand-built table)

| Test | Checks |
|---|---|
| Seed mean | Per-instance value is the mean over algorithm seeds; failed rows are ignored; `BEST-HEURISTIC` and `GA-BEST-OF-SEEDS` are per-instance minima. |
| Paired improvement | Mean of per-instance ratios (0.35 on the example), not a ratio of means (0.40) or of totals; geometric mean, median, extremes and counts hand-computed. |
| Ties and pairing | Ties counted at 1e-12; instances missing on one side are dropped. |
| Bootstrap | Deterministic, brackets the mean, collapses on a constant ratio. |
| Summary agreement | Summary `paired_impr_vs_*_mean` equal the paired table; `cmax_over_lb_mean_of_instances` hand-computed. |
| Overhead | Time ratio, `GA-BEST-OF-SEEDS` charged every seed's time, `τ*` hand-computed; `τ* = inf` where there is no gain. |
| Convergence | The trace is read as a step function on the grid; NA before the first log. |

### `test_rl.py`

| Test | Checks |
|---|---|
| Candidate set | Contains exactly the pairs (ready task × processor); never a placed or non-ready task. |
| Features | Finite; shape `(candidates, 12)`; unchanged when all costs are multiplied by a constant (scale-free). |
| Untrained policy | Produces valid schedules. |
| Training smoke test | 20 updates on `n = 10` run without error and change the weights. |
| Determinism | Greedy inference twice → identical schedule. |
| Leakage guard | Evaluating on an instance whose hash is in the model's training-hash file raises. |

Implemented 2026-10-17 (`tests/test_rl.py`, 13 tests): see `docs/S02_PILOT_REPORT.md` §2 for the list, including
the check that HEFT's decisions inside the RL environment reproduce the HEFT baseline exactly.

### Result on the S02 final campaign (2026-10-17)

`analyze` campaign checks (incl. `_check_s02`): all passed. Independent check `provenance/s02_final/verify_campaign.py`:
0 problems — 13,500 / 13,500 rows, AC power at start and end, pinned ids, no training-stream instance evaluated,
every heuristic and RL schedule re-run with no mismatch, primary statistics recomputed from raw. Figures recomputed
(`figure_reproducibility_check.txt`). Tests: 238 passed (incl. the S02 training and final config locks).

### `test_adaptive.py`

| Test | Checks |
|---|---|
| Features | Finite, deterministic, scale-free where intended. |
| Selector output | Always a member of the portfolio. |
| Result identity | `ADAPTIVE` makespan equals the makespan of the selected heuristic run directly. |
| `TRY-ALL` | Equals the minimum over the six heuristics. |
| Novelty guard | A feature vector outside the stored range triggers fallback to `SBS`. |
| No test information | Selector training takes `train` instances only; depth selection and `SBS` take `val` only. The functions take a split argument and raise on `test_id` or `test_ood`. |

Implemented (2026-10-17, 14 tests): features finite, deterministic, invariant to the cost unit, hand-computed on
known instances; label tie-break; training raises on any split other than `train` / `val`; depth, `SBS` and the
contingency recomputed from `val`; save/load round trip and no overwrite; every method's pick is a portfolio member and
its result equals that heuristic run directly; `TOP2` distinct picks; `TRY-ALL` = minimum; guard fallback to `SBS`
(and the `val` ranking for `TOP2`); seeded `RANDOM-SELECT`; leakage guard on training instances and on test instances
used for selection; gap-closed formula; runner integration (rows, model ids, `decisions.csv`, manifest), a corrupted
result caught by `check()`, and S03 tables and figure CSVs recomputed. Contingency extension (6 tests): GA member
settings equal the locked S01 `[ga]` with 1,000 evaluations; strict θ labels with ties to the heuristic; extension
keeps the base's `SBS`, guard and splits and refuses other instances; θ recomputed from the predeclared efficiency
rule; `GA-1000` ≤ its seeds with exactly 1,000 evaluations and no S01 trace; `ADAPTIVE-GA` deterministic per seed;
runner integration with two models; `model_id` independent of measured timings.

## 2. Integration test — `test_pipeline.py`

Runs a 4-instance campaign into a temp directory, then `analyze`. Checks: files exist; `runs.csv` has the exact header
of `DATA_SCHEMA.md` §1; `master.csv` has the manual's 19 column names in order; row count = instances × algorithms ×
repeats; raw directory files are read-only afterwards; a second run with the same config gives identical makespan
columns; a scheduler patched to raise produces a `status = error` row and the campaign completes.

## 3. Campaign validation — `test_results.py <campaign dir>`

Run against the real campaign output before any analysis is trusted.

| Check | Condition |
|---|---|
| Validity | `valid = 1` for all `ok` rows. |
| Lower bound | `makespan_sim ≥ lower_bound_sim − ε` for every row. |
| Upper sanity | `Speedup ≤ m` on `homog` rows. |
| Utilization | `0 < utilization ≤ 1`. |
| Determinism | Deterministic algorithms: identical `makespan_sim` across repeats of the same instance. |
| Pairing | Every test instance has rows for every configured algorithm (or an explicit failed row). |
| Oracle ordering | `TRY-ALL` ≤ each heuristic; `ADAPTIVE-TOP2` ≤ `ADAPTIVE`'s selected policy; seeded `GA`, `RANDOM-SEARCH`, `HILL-CLIMB` ≤ their seed heuristics (not `GA-KEYS-EFT`, whose seeds are re-decoded; `ALGORITHM_DESIGN.md` §3.5). |
| Leakage | No test `instance_hash` appears in any model's training-hash file. |
| Splits | No `train` rows in `runs.csv`. |
| Units and missing values | `time_unit = sim_tu` everywhere; `Communication_Time`, `Synchronization_Time`, `Energy_if_available` are `NA`; no blank cells; no measurement column is 0 on a failed row. |
| Manual fields | `master.csv` begins with the manual's 19 column names, exact spelling and order. |
| Identifiers | `Student_ID` and `Batch_ID` are either confirmed values or the explicit placeholders; a final export with placeholders fails. |
| Row retention | Row count of `master.csv` = row count of `runs.csv`. Nothing filtered. |
| Derived-from-raw | Recomputing Speedup and Efficiency from raw columns reproduces `master.csv`. |
| Failures | `failed_count` in the manifest equals the count of non-`ok` rows; each is listed in the report. |

### Result on the S01 final campaign (2026-10-17)

`analyze` campaign checks: all passed. Independent check `provenance/s01_final/verify_campaign.py` (no use of
`analysis.py`): 0 problems — 14,850 / 14,850 rows, 450 instances, 3 repeats or seeds per (instance, method), 0
failures or duplicates, locked config hashes, budgets exactly 6,000, heuristics re-run with identical makespans, paired
table and Wilcoxon p recomputed from raw. Every plotted summary recomputed from its source CSV
(`figure_reproducibility_check.txt`). Test suite: 201 passed, 0 failed, 0 skipped.

### Result on the S03 final campaign (2026-10-17)

`analyze` campaign checks (incl. `_check_s03`): all passed. Independent check `provenance/s03_final/verify_campaign.py`:
0 problems — 17,550 / 17,550 rows, 0 failures or duplicates, pinned model ids on every S03 row, heuristics re-run and
selector decisions re-derived with no mismatch, primary statistics recomputed from raw. Figures recomputed from their
CSVs (`figure_reproducibility_check.txt`). Tests: 223 passed (incl. the S03 config-lock and model-pin tests).

## 4. Reproducibility

- Fresh clone + `pip install -r requirements.txt` + the README commands regenerate `master.csv` with identical simulated
  columns. Wall-clock columns will differ; that is expected and stated.
- Figures regenerate from `master.csv` alone.

## 5. Performance validation

- Scheduling-time measurements: coefficient of variation across the 3 timing repeats is reported per algorithm; if it
  exceeds 20% for sub-millisecond heuristics, timing switches to the minimum of 10 calls and this is recorded.
- GA: evaluations per second measured in the pilot at each `n`, to confirm the cost model `O(B·(e + n log n))`.
- Timer overhead: an empty scheduler call is timed to show the measurement floor.

## 6. Simulator assumptions (stated in every result caption that could be misread)

No communication cost · exact cost estimates · zero dispatch and context-switch cost · no memory, cache or NUMA
effects · no preemption · no failures. Makespans are simulated. Only scheduling times are measured.

---

## 7. Hostile architecture review

Reviewed as a sceptical referee. Severity: **Critical** = invalidates conclusions; **High** = materially misleads;
**Medium** = weakens a claim; **Low** = presentation.

| # | Issue | Severity | Correction in the design | Test that shows it is resolved |
|---|---|---|---|---|
| R1 | **Unit mixing.** Simulated makespan and wall-clock overhead could be summed, or simulated time presented as measured execution time. | Critical | Separate columns and units; `Time_Unit` column; break-even `τ*` instead of a sum; captions say "simulated". | `test_results`: unit check. Review of every figure caption and axis label for the unit. |
| R2 | **Invalid schedules** scored as good ones. | Critical | Single builder that cannot violate constraints; independent `validate()`; invalid rows fail the campaign. | `test_model` broken-schedule tests; `test_results` validity check. |
| R3 | **Wrong makespan** from a builder bug common to all algorithms. | Critical | Hand-computed cases; lower-bound check; brute-force optimum on tiny instances. | `test_model`, `test_ga` exact-optimum test, pilot criterion P3. |
| R4 | **RL train/test leakage**: test instances seen in training, checkpoint chosen on test, hyperparameters tuned on test. | Critical | Seed-space split; content-hash guard in the runner; checkpoint and tuning on `val`; test run once after freeze; model hash in manifest. | `test_workloads` disjointness; `test_rl` leakage guard; `test_results` leakage check. |
| R5 | **S03 oracle leakage**: single best policy picked on the test set, or selector labels from test data. | Critical | The tree is built from `train`; depth and `SBS` from `val`; functions reject test splits. | `test_adaptive` no-test-information test; `test_results` leakage check. |
| R6 | **Strawman baseline.** FCFS-EAT is cost-blind; beating it on heterogeneous platforms proves little. | High | `HEFT` and `MINMIN` included; headline comparisons use the strongest baseline; improvement over FCFS shown but labelled. | Summary table contains both improvements, named. |
| R7 | **Seeded GA wins by construction.** With elitism and HEFT seeding, `GA ≤ HEFT` always. | High | Stated in the design. `GA-UNSEEDED`, `RANDOM-SEARCH` and `HILL-CLIMB` at equal budget are the real test. | Ablation table T2 present; `test_ga` "seeded ≤ seeds" documents the tautology. |
| R8 | **Optimization and decision overhead hidden.** | High | `scheduling_time_s` on every row, measured identically; GA convergence trace; quality-vs-overhead plot G10; `τ*`. | G10 and T1 include scheduling time for every method. |
| R9 | **Training cost hidden** for RL and the selector. | High | Training time and episode count in manifest and T1; all 3 seeds reported; amortisation stated. | T1 has a training-time column; manifest `models[].training_time_s` is non-empty. |
| R10 | **S03 is dominated by `TRY-ALL`** in an offline deterministic setting. | High | `TRY-ALL` is always shown; the S03 claim is restricted to decision cost vs quality. | G8 and G10 include `TRY-ALL`. |
| R11 | **Unrealistic simulator** (no communication, exact estimates, free dispatch). | High (inherent) | Declared as the primary limitation; no hardware claim; optional replay phase. | Wording check of abstract and conclusion: no "speedup on hardware" claim. |
| R12 | **Speedup without a baseline**, or efficiency > 1 on heterogeneous platforms read as an error. | High | `Speedup_Baseline` column; definition fixed in one place; note on `hetero`. | `test_results` derived-from-raw check; `Speedup ≤ m` on `homog`. |
| R13 | **Pseudo-replication**: timing repeats counted as independent makespan samples, shrinking intervals. | Medium | Aggregate repeats per instance first; resample instances. | Analysis unit test: CI width unchanged when timing repeats are duplicated. |
| R14 | **Noisy wall-clock timing** (laptop, frequency scaling, GC, parallel workers). | Medium | Single worker; repeats; warm-up call; evaluation counts; `workers` column; notes field. | §5 timing CV report. |
| R15 | **RL may only imitate HEFT** because its features include rank and EFT. | Medium | Disclosed; ablation without features 4 and 7. | Ablation row in T2. |
| R16 | **Best-of-seeds reporting** for GA or RL. | Medium | Mean over seeds is primary; best-of-3 labelled and charged 3× time; all RL seeds shown. | T1 footnotes; analysis code path named `mean_over_seeds`. |
| R17 | **Cherry-picked comparisons / multiple testing.** | Medium | Three primary comparisons declared in advance; Holm correction; all cells and failures reported. | The three comparisons in this document match those in the report. |
| R18 | **Baselines handicapped by the shared builder.** The first draft was append-only, so fixed-priority heuristics left idle gaps they could not reuse, while GA and RL could learn to avoid them. Found in the pre-implementation audit. | High | Heuristics place with gap insertion; `HEFT` is insertion-based; append mode provably reaches every insertion schedule, so the proposed methods gain nothing the baselines lack. | `test_model` insertion and append-reproduces-insertion tests; `test_heuristics` not-handicapped test. |
| R19 | **Confounding from randomised DAG shape within a class.** | Medium | Paired design: every algorithm runs on identical instances; shape parameters recorded. | `test_results` pairing check. |
| R20 | **Tuning on `val` drawn from the same generator** flatters in-distribution results. | Medium | OOD sets; statement in threats to validity. | G6 and G9 include OOD sets. |
| R21 | **Loose lower bound** read as an optimality gap. | Low | Used as a normaliser only; stated. | Wording check. |
| R22 | **Memory metric is process-wide peak**, not per run. | Low | Documented in the schema as an upper bound. | — |
| R23 | **Scope: three learning systems, one person, eight days.** Risk of three half-finished parts. | High (schedule) | Shared core; strict priority order; S02 time-boxed with a pre-declared fallback; negative results accepted. | Roadmap acceptance criteria per phase. |
| R24 | **Manual deviations**: no C++ simulator, no OpenMP/CUDA, Batches 1–3/7 findings not used. | High (assessment) | Flagged as open decisions; stated in the report's methodology and limitations. | Faculty acceptance recorded before submission. |
| R26 | **Scope exceeds the manual's individual allowance** (one student, three sub-problems) and could be described as approved when it is not. | High (assessment) | `ARCHITECTURE.md` §1.1 states that faculty approval is required and not recorded; no document or output calls the scope approved. | Approval recorded by you before submission; text search of the report for "approved". |
| R27 | **Identifiers guessed.** | Medium | Explicit placeholders, held outside raw data; final export refuses placeholders. | `test_results` identifiers check. |
| R25 | **Non-reproducible results** from unordered iteration, global RNG or nondeterministic torch ops. | Medium | `SeedSequence` streams; id tie-breaks; deterministic torch; no reliance on salted `hash()`. | Integration determinism test; pilot criterion P4. |

### Residual risks that the design does not remove

- R11: the simulator gap is unmeasured unless the optional replay phase is done.
- R23: schedule risk remains; the mitigation is ordering, not elimination.
- R24: depends on faculty expectations, not on design.
