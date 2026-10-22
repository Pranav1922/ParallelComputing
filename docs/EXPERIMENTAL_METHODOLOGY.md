# Experimental Methodology

No experiment has been run. Every runtime figure in this document is an **estimate** to be replaced by the pilot's
measurement.

---

## 1. Workload model

### 1.1 Task DAG families (`workloads.py`)

**`layered`** (main family). Parameters: `n`, fatness `f`, density `d`, width regularity.

1. Number of layers `L = max(2, round(sqrt(n) / f))`. Small `f` → deep and narrow; large `f` → shallow and wide.
2. Layer widths: equal (regular) or drawn uniformly in `[1, 2·n/L]` then rescaled to sum to `n` (irregular).
3. Every task outside the first layer gets `1 + Binomial(3, d)` distinct parents, each from the previous layer with
   probability 0.8, otherwise from any earlier layer.
4. Tasks are numbered layer by layer, so task ids are already a topological order.

**`forkjoin`** (out-of-distribution only). Repeated stages of: one fork task → `w` parallel chains of length `c` → one
join task, with `w` and `c` drawn per stage until `n` tasks are used.

Per instance, `f ~ logUniform(0.5, 2)` and `d ~ Uniform(0.1, 0.5)` are drawn from the instance seed and stored in the
instance metadata, so each class contains a range of shapes.

### 1.2 Task work

Base work `w_t ~ Lognormal` with mean 100 `sim_tu` and coefficient of variation set by the class.

### 1.3 Platforms

| Platform | Cost matrix |
|---|---|
| `homog` | `cost[t, p] = w_t` for all `p` |
| `hetero` | Two processor types. `max(1, round(m/4))` accelerators, the rest CPUs. `cost[t, cpu] = w_t`; `cost[t, acc] = w_t / a_t`, with `a_t ~ Lognormal(median 4, σ = 1)` clipped to `[0.25, 32]`. Some tasks are slower on the accelerator. |

[ASSUMPTION] These parameters are illustrative, not calibrated against measured CPU–GPU data.

### 1.4 Workload classes

| Class | Work CV | Layer widths | Platform |
|---|---|---|---|
| `regular` | 0.1 | equal | `homog` |
| `irregular` | 1.5 | irregular | `homog` |
| `heterogeneous` | 0.5 | equal | `hetero` |
| `irregular_hetero` | 1.5 | irregular | `hetero` |

---

## 2. Experiment matrix

### 2.1 Factors

| Factor | Levels |
|---|---|
| Problem size `n` | 50, 100, 200 (plus 400 in the OOD set) |
| Processors `m` | 2, 4, 8 (plus 16 in the OOD set) |
| Workload class | `regular`, `irregular`, `heterogeneous`, `irregular_hetero` |
| Algorithm | 6 heuristics, `GA`, `RL` × 3 training seeds, `ADAPTIVE`, `ADAPTIVE-TOP2`, `TRY-ALL` |

In-distribution cells: 3 × 3 × 4 = **36**.

### 2.2 Splits

| Split | Instances | Used for |
|---|---|---|
| `train` | 30 per cell = 1,080 (selector); unbounded stream (RL) | Training only |
| `val` | 5 per cell = 180 | GA parameter choice, RL checkpoint selection, tree depth, choice of `SBS`, the S03 contingency (`ALGORITHM_DESIGN.md` §5.7) |
| `test_id` | 10 per cell = 360 | Final evaluation, in-distribution |
| `test_ood` | 10 per cell × 9 cells = 90 | Final evaluation, out-of-distribution |

Instance seeds come from
`numpy.random.SeedSequence([campaign_seed, split_code, crc32(family/class/cv), n, m, instance_index])`, so
splits cannot collide by construction. Each instance also gets a content hash (SHA-1 of edges and cost bytes); the
runner refuses to evaluate a learned model on any instance whose hash appears in that model's training-hash file.

**Scope of the separation claim.** It covers the *experimental matrix*: the instances produced by
`workloads.experiment_matrix()` from a config's `[workload]` section, which is the only way the runner obtains
instances. For those, `assert_separated()` verifies at the start of every campaign that no content hash repeats inside
a split or appears in two splits, and the result is written to the manifest. Empty workloads (`n = 0`) are outside the
claim: they have no content, so all of them share one hash whatever their split. They exist only as edge-case test
fixtures, and `experiment_matrix()` rejects any size below 1.

### 2.3 Repetitions

| Algorithm type | Repeats per instance | What varies |
|---|---|---|
| Deterministic (heuristics, `RL` greedy, `ADAPTIVE`, `TRY-ALL`) | 3 | Nothing in makespan (asserted identical). Gives variation of wall-clock scheduling time. |
| `GA` and its variants | 3 | Algorithm seed. |
| `RL` | 3 training seeds × 3 timing repeats | Training seed. |

The unit of replication for makespan statistics is the **instance** (10 per cell). Timing repeats are averaged per
instance first; they are not counted as independent samples.

### 2.4 Out-of-distribution sets (`test_ood`)

| Set | Cells | What is unseen |
|---|---|---|
| `ood_size` | `n = 400`, `m = 4`, all 4 classes (4 cells) | Larger DAGs |
| `ood_procs` | `n = 200`, `m = 16`, `irregular` and `irregular_hetero` (2 cells) | More processors |
| `ood_struct` | `forkjoin`, `n = 100`, `m = 4`, irregular work on `homog` and on `hetero` (2 cells) | DAG structure |
| `ood_cv` | `layered`, `n = 100`, `m = 4`, work CV = 3.0, `homog` (1 cell) | More extreme irregularity |

`n = 400` also serves S01 as a fourth DAG size.

### 2.5 Ablations (on a reduced set: `n = 100`, `m = 4`, all 4 classes, `test_id` instances = 40 instances)

| Sub-problem | Ablations |
|---|---|
| S01 | `GA-UNSEEDED`, `GA-KEYS-EFT`, `RANDOM-SEARCH`, `HILL-CLIMB` (equal budget) |
| S02 | Features 4 and 7 removed (no HEFT-like inputs); retrained once |
| S03 | Tree depth; feature groups; novelty guard off; `RANDOM-SELECT` |

---

## 3. Procedure

1. `pytest` passes.
2. Pilot (§6) passes its gate.
3. Tune on `val`: GA parameters, RL training, tree depth. Freeze. Record model hashes.
4. Run the full campaign on `test_id` and `test_ood` **once**.
5. `analyze` produces `master.csv`, tables and figures from the raw directory.
6. If a bug forces a rerun, the old campaign directory is kept and the rerun is recorded in the report.

Timing discipline:

- `time.perf_counter_ns()` around the scheduler call only. Instance generation, validation and file output are outside.
- One untimed warm-up call per algorithm at campaign start.
- Scheduler is single-threaded (`Threads = 1`). Campaign runs with **one worker process** so timings are not distorted
  by sibling processes. If more workers are used for GA to save time, `workers` is recorded per row and those timings
  are labelled.
- On battery vs mains, other applications, and thermal state are noted in the manifest's free-text field.
- Fitness-evaluation count is recorded as a machine-independent cost measure next to wall-clock time.

---

## 4. Metrics

Formal definitions and column mappings are in `DATA_SCHEMA.md` §4. Summary:

| Metric | Formula | Baseline / reference | Required by |
|---|---|---|---|
| Makespan | `Cmax = max finish` | — | all |
| Normalised makespan | `Cmax / LB` | lower bound | all (comparison across sizes) |
| Speedup | `serial_best / Cmax` | **all tasks run sequentially on the single best processor of the same simulated platform** | manual, S03 |
| Efficiency | `Speedup / m` | — | manual |
| Utilization | `Σ_t cost[t, proc[t]] / (m · Cmax)` | — | S01, S02 |
| Improvement | `(Cmax_base − Cmax_alg) / Cmax_base` | named each time: `FCFS-EAT`, or best heuristic on that instance | S01 |
| Optimization time | wall-clock seconds of the GA call; also evaluations | — | S01 |
| Inference overhead | wall-clock seconds of the RL call; per decision = / `n` | `HEFT` scheduling time | S02 |
| Generalization | mean `Cmax_RL / Cmax_HEFT` on each OOD set minus the same on `test_id` | `HEFT` | S02 |
| Decision overhead | `decision_time_s` (features + selection) | `TRY-ALL` scheduling time | S03 |
| Regret | `Cmax_alg / Cmax_VBS − 1` | per-instance oracle | S03 |
| Robustness | worst-class mean regret; 95th-percentile regret; share of instances with regret ≤ 5% | — | S03 |
| Gap closed | `(mean_SBS − mean_ADAPTIVE) / (mean_SBS − mean_VBS)` on `Cmax/LB` | `SBS`, `VBS` | S03 |
| Break-even `τ*` | see §5.3 | named baseline | all |

Scalability is reported as normalised makespan and speedup against `n` (fixed `m`) and against `m` (fixed `n`).

---

## 5. Analysis

### 5.1 Statistics

- All comparisons are **paired by instance**.
- Report mean and median of per-instance ratios, with IQR and a 95% bootstrap confidence interval (10,000 resamples of
  instances).
- Wilcoxon signed-rank test on paired makespans for the three primary comparisons: `GA` vs best heuristic, `RL` vs
  `HEFT`, `ADAPTIVE` vs `SBS`. Holm correction across the three.
- GA: per instance, the **mean over 3 algorithm seeds** is the primary value. Best-of-3 is reported separately and
  charged 3× the optimization time.
- RL: each training seed is reported separately; the mean across seeds is the headline.
- Effect sizes are reported with every p-value. A statistically significant 0.3% improvement is described as 0.3%.
- **Outliers are retained.** No row is deleted from raw or derived data. Points beyond 3 × IQR are flagged in the
  analysis, listed in the report and, where possible, explained. Medians are reported next to means so a few extreme
  timings do not drive a conclusion. Failed and invalid runs are counted and listed, never dropped.
- **Speedup always names its baseline**: sequential execution on the best single simulated processor
  (`Speedup_Baseline` column). "Improvement" always names the algorithm it is relative to. No figure or table uses the
  word speedup for a ratio between two schedulers.

### 5.2 Graphs and tables

| ID | Content | Sub-problem |
|---|---|---|
| G1 | DAG size vs normalised makespan: one panel per workload class × `m`, one line per algorithm, median with interquartile range over instances (classes are never pooled; the quantity is ≥ 1 by definition and so are the plotted quartiles). Source data: per-instance CSV and plotted-summary CSV | S01 |
| G2a | Measured optimization time (s, log) vs DAG size, one panel per `m`, median and IQR over runs (each seed a run), HEFT and MINMIN for reference | S01 |
| G2b | Convergence: best-so-far `Cmax / Cmax_HEFT` vs evaluations, one panel per `n`, median and IQR over runs, plus a zoomed row (replaces the planned inset) | S01 |
| G3 | Paired per-instance improvement over `FCFS-EAT` and over best heuristic, by workload class (`test_id`) and OOD set (`test_ood`); box = quartiles, whiskers = 5th–95th percentile, triangle = mean | S01 |
| T-S01 | Paired comparison table `s01_paired.csv` and overhead–quality table `s01_overhead_quality.csv` (formulas in `DATA_SCHEMA.md` §4.1) | S01 |
| G4 | Training reward and validation ratio vs updates, 3 training seeds | S02 |
| G5 | Makespan (`Cmax/LB`) by method (box plot) | S02 |
| G6 | `Cmax_RL / Cmax_HEFT` on `test_id` vs each OOD set | S02 |
| G7 | Two most important workload features, points coloured by selected policy, tree split lines overlaid | S03 |
| G8 | Adaptive vs fixed: `Cmax/LB` for each fixed policy, `SBS`, `ADAPTIVE`, `ADAPTIVE-TOP2`, `TRY-ALL`/`VBS` | S03 |
| G9 | Regret heatmap, workload class × policy, with worst-class value marked | S03 |
| G10 | Quality vs overhead: scheduling time (log) vs mean `Cmax/LB`, every method, Pareto front marked | combined |
| T1 | Summary table: per algorithm, mean and median `Cmax/LB`, improvement vs `FCFS-EAT` and vs `HEFT`, speedup, efficiency, utilization, scheduling time, one-off training time | combined |
| T2 | Ablation table | each |

Each figure is produced by a function in `analysis.py` from `master.csv` and saved as PDF, SVG and the CSV of plotted
values ("plots in editable/source form").

### 5.3 Charging the overhead: break-even `τ*`

Makespan is in `sim_tu`; scheduling time is in seconds. They cannot be added without an exchange rate `τ`
(seconds per `sim_tu`). Instead of picking one, the analysis reports the break-even:

```
τ*(A vs B, instance) = (T_sched_A − T_sched_B) / (Cmax_B − Cmax_A)      if Cmax_A < Cmax_B
                     = ∞ (never pays off)                               otherwise
```

Method A is worth its extra scheduling time only when one `sim_tu` lasts longer than `τ*` seconds. Since mean task work
is 100 `sim_tu`, this reads as "tasks must average at least `100·τ*` seconds". Reported: median `τ*` and the share of
instances with no break-even. For RL and the selector, the one-off training time is reported next to it together with
the number of instances needed to amortise it at a stated `τ`.

---

## 6. Initial validation experiment (pilot)

Purpose: prove the pipeline end to end and calibrate cost before the full campaign. Target wall time: under 10 minutes.

| Item | Pilot setting |
|---|---|
| Split | `val` (the test split is not touched by any pilot) |
| Sizes | `n ∈ {20, 50}` |
| Processors | `m ∈ {2, 4}` |
| Classes | `regular`, `irregular_hetero` |
| Instances | 3 per cell → 24 |
| Algorithms | all 6 heuristics; `GA` (1,000 evaluations, 2 seeds); `RL` trained 200 updates on `n = 20`; `ADAPTIVE` trained on 10 instances per cell |
| Extra | 20 tiny instances (`n = 6`, `m = 2`) solved exactly by enumerating all (order, assignment) pairs |

**Acceptance criteria.** Each is a yes/no check on pilot output.

*Core — must all pass before any full-campaign run:*

| # | Criterion |
|---|---|
| P1 | `validate()` returns no violations for 100% of pilot schedules. |
| P2 | `makespan ≥ lower_bound − ε` on every row. |
| P3 | On the tiny instances, no algorithm's makespan is below the exact optimum. |
| P4 | Two pilot runs with the same config give identical `makespan_sim` columns. |
| P5 | `runs.csv` → `analyze` → `master.csv` (19 manual columns present, in order) and one figure, with no manual step. |
| P6 | Every (instance, algorithm, repeat) has a row; failed runs have `status ≠ ok` and `NA` measurements. |
| P7 | Projected full-campaign runtime, computed from measured pilot costs (below), is ≤ 8 hours single-worker, or a reduction from §7 has been chosen and recorded. |

*Per sub-problem — a failure blocks only that sub-problem's campaign:*

| # | Criterion |
|---|---|
| P8 (S01) | Seeded `GA` makespan ≤ each seed heuristic's on every pilot instance; best-so-far in every trace is non-increasing; evaluations used = budget. |
| P9 (S02) | For the pilot training run, mean validation `Cmax_RL/Cmax_HEFT` at the best checkpoint is lower than at update 0. |
| P10 (S03) | The selector trains, every decision is a portfolio member, and the `SBS`–`VBS` gap on `val` is computed and recorded. |

*Diagnostics — recorded, not pass/fail:*

- Share of tiny instances on which `GA`, `RANDOM-SEARCH` and `HILL-CLIMB` each reach the exact optimum. A low GA hit
  rate is investigated but does not by itself fail the pilot; a tiny instance says little about `n = 200`.
- GA evaluations per second at each pilot size; RL episodes per second; heuristic scheduling times.
- Coefficient of variation of scheduling time across timing repeats.

**Runtime projection from pilot measurements.** For GA-family runs:
`time ≈ Σ over cells (runs in cell × B / evaluations-per-second measured at that n)`, with evaluations per second at
`n = 100, 200, 400` measured by a 200-evaluation probe on one instance of each size (seconds, part of the pilot).
RL training is bounded by its wall-clock cap. The projection replaces the estimates in §7 and is written into the
pilot's manifest notes.

---

## 7. Computational cost (estimates, to be calibrated by the pilot)

| Part | Volume | Estimate |
|---|---|---|
| Heuristics | 450 test instances × 6 × 3 repeats; plus 1,080 training instances × 6 for selector labels | seconds to a few minutes |
| GA main | 450 instances × 3 seeds = 1,350 runs × 6,000 evaluations | 1–6 CPU-hours (depends on evaluations/second in pure Python; the largest unknown) |
| GA ablations | 40 instances × 3 seeds × 4 variants = 480 runs | 0.5–2 CPU-hours |
| RL training | 3 seeds, capped at 45 minutes each | ≤ 2.25 hours |
| RL ablation | 1 retrain | ≤ 45 minutes |
| RL inference, adaptive, `TRY-ALL` | 450 instances × 3 repeats | minutes |

If the pilot shows the GA campaign exceeding about 6 hours single-worker, reduce in this order: (1) run `n = 400` GA
with 1 seed, (2) lower the budget to 3,000 evaluations for all sizes, (3) use multiple workers and label the timings.
The reduction taken is recorded in the report.

---

### 7.1 Measured costs (pilots of 2026-10-11, Apple M4, single worker)

These replace the GA estimate above. Heuristic scheduling time per call: 0.03–0.05 ms at `n = 20`, 0.3–1.3 ms at
`n = 100`, 2.3–17 ms at `n = 400` (cost probe). Search methods at the full 6,000-evaluation budget, median wall time
per run from the S01 pilot: 0.11 s (`n = 20`), 0.27 s (`n = 50`), 0.59 s (`n = 100`) for `GA`; `GA-KEYS-EFT` is about
1.7× slower. A 600-evaluation probe gave about 4,400 evaluations/s at `n = 200` and 1,700 at `n = 400`, i.e. roughly
1.4 s and 3.6 s per 6,000-evaluation run.

**Projection (not a measurement):** the full campaign's 1,350 runs per search method come to roughly 25 minutes per
method, about 2 hours for all five, single worker. This is within the P7 limit of 8 hours with no reduction needed.

### 7.2 S01 final campaign: lock and projection (2026-10-17, before any test-split evaluation)

- Config: `configs/s01_final.toml`, config hash `430d8a10`, file sha256 prefix `550007b6e5dd4a04`; code hash at launch
  `9a1f83786ce9df0b`. `[workload]` and seed equal `full.toml`; `[ga]` equals the pilot (untuned, per the decision of
  2026-10-17: full `GA` primary, `GA-KEYS-EFT` reported as an ablation, three heuristic seeds, `B = 6,000`).
- Scope: all six heuristics and all five S01 methods on all 450 test instances (`test_id` 360, `test_ood` 90),
  3 algorithm seeds, 3 timing repeats for heuristics: 14,850 rows. Running the four controls on every instance, rather
  than only on the reduced ablation set of §2.5, is a superset; T2 is also reported on that predeclared subset.
- Projection from a 600-evaluation probe per method on one `val` instance of each campaign shape (`n, m` = 50/8,
  200/2, 200/8, 400/4, 200/16, forkjoin 100/4), × 10: about 7,100 s (≈ 2.0 h) single worker. Projection, not a
  measurement. Host on battery at launch; `caffeinate -i` kept it awake.
- **Actual (verified):** 04:47:34 → 06:46:01 UTC, runner wall time 7,106 s, 14,850 rows, 0 failed. On battery
  throughout (84% → 15%). Results: `docs/S01_ACCEPTANCE_REPORT.md`; provenance: `provenance/s01_final/`.

### 7.3 S03: predeclared pilot criteria and campaign analysis plan (written 2026-10-17, before the S03 pilot ran)

**Pilot** (`configs/s03_pilot.toml`): the selector is trained on the real `train` split (30 per cell, 1,080) and
its depth, `SBS` and the §5.7 contingency are chosen on the real `val` split (5 per cell, 180), exactly as the full
campaign would use them. The pilot campaign then runs the six heuristics and all S03 methods on `val` only. This
replaces the generic pilot's "10 per cell, n ≤ 50" setting for S03 (stronger: real sizes, real splits). Because `val`
chose depth and `SBS`, pilot quality numbers are in-sample for those choices and are pipeline evidence, not results.

Pass/fail, all required before the full S03 campaign:

| # | Criterion |
|---|---|
| S03-P1 | Core P1, P2, P5, P6 hold for the S03 pilot campaign; P4: a second pilot run gives identical `makespan_sim` columns. |
| S03-P2 (= P10) | The selector trains; every decision is a portfolio heuristic; the `SBS`–`VBS` gap on `val` is computed and recorded in `model.json`. |
| S03-P3 | `analysis._check_s03` passes: each S03 result equals its selected heuristic run directly; `TRY-ALL` equals the per-instance best; guard fallbacks pick `SBS`; `ADAPTIVE-NOGUARD` never falls back; every S03 row carries the manifest's `model_id`; no evaluated instance is in the training set. |
| S03-P4 | Information flow: the model's training hashes are exactly the `train` split, its selection hashes exactly `val`, and neither contains a `test_id` or `test_ood` hash. |
| S03-P5 | Projected full S03 campaign runtime from measured pilot costs is ≤ 8 h single worker. |
| S03-P6 | The §5.7 contingency decision is computed on `val` and recorded. If it triggers, the full campaign does not start until the GA portfolio member's labelling rule is specified and approved (the design does not yet define how the cost of calling GA is traded against its makespan gain; without such a rule GA, which is never worse than its seeds, would be the label almost everywhere). |

Diagnostics, recorded, not pass/fail: `val` regret by tree depth and with each feature group removed; guard fallback
rate; selection counts by class; decision time vs `TRY-ALL` scheduling time.

**Full S03 campaign analysis plan (fixed now; no test data seen):**

- Populations: **`test_id` (360) is the primary population**; `test_ood` (90) is the unseen-workload evaluation and
  is secondary. Results on both are reported.
- Primary comparison: `ADAPTIVE` vs `SBS` on `test_id`, Wilcoxon signed-rank on paired makespans (two-sided, zero
  differences dropped), member of the three-test Holm family (§5.1). Effect size: mean paired improvement
  `(C_SBS − C_ADAPTIVE) / C_SBS` with a 95% bootstrap CI, and gap closed `(mean_SBS − mean_ADAPTIVE) /
  (mean_SBS − mean_VBS)` on `Cmax/LB` with a 95% bootstrap CI (H3: CI above 0).
- Secondary / exploratory, no p-values: `ADAPTIVE` vs each fixed heuristic and vs `BEST-FIXED-HINDSIGHT` (labelled
  hindsight); `ADAPTIVE-TOP2`, `ADAPTIVE-NOGUARD`, `RANDOM-SELECT`, `TRY-ALL`; robustness (worst-class mean regret,
  95th-percentile regret, share of instances with regret ≤ 5%); decision overhead vs `TRY-ALL` time; speedup
  (baseline: serial on best single simulated processor); everything on `test_ood`.
- Technical acceptance as for S01: complete rows, failures explained, campaign checks and tests pass, figures
  regenerate from saved CSVs, provenance recorded.

**Batches 1–3 and 7.** The manual's first S03 objective ("Use findings from Batches 1–3 and 7") cannot be met: no
findings from those batches are available, and none are invented. What the current evidence supports: features chosen
from those batches' *topics* (granularity and irregularity, DAG shape, heterogeneity), and this project's own S01
results. What needs faculty clarification or data: whether the objective can be met by topic-motivated features, or
which batch findings (measured results, recommended policies) should be supplied.

**Outcome (verified, 2026-10-17):** full S03 campaign `20261017T083329Z-s03_final-b8e5be9a`, 237 s, 17,550 rows,
0 failures. Primary: `ADAPTIVE` vs `SBS` on `test_id`, n = 360, mean paired improvement −0.016%, Wilcoxon p = 0.78,
gap closed −0.03 (95% CI −0.30–0.19): H3 not supported. Details: `docs/S03_ACCEPTANCE_REPORT.md`.

**S02 outcome (verified, 2026-10-17):** final campaign `20261017T115054Z-s02_final-898ee9e1`, AC power, 80 s, 13,500
rows, 0 failures. Primary `RL` vs `HEFT` on `test_id` (population fixed in the approved S02 plan): mean ρ 1.0097,
CI 1.0034–1.0160 [corrected 2026-10-17, see docs/report/ERRATA.md], Wilcoxon p = 6.8e-6. Holm over the three primary tests: S01 and S02 rejected, S03 not.
Details: `docs/S02_ACCEPTANCE_REPORT.md`.

### 7.4 S03 contingency extension (`GA-1000` member): rules fixed 2026-10-17, before any extension data were computed

**The trigger, and what it is not.** Source: `ALGORITHM_DESIGN.md` §5.7 (and §2.2 of this document), written in the
architecture phase, before any S03 code existed; there is no git history to timestamp it. Rule: if on `val` the gap
between `SBS` and `VBS`, defined as `mean_i (C_SBS,i / C_VBS,i − 1)` over the six heuristics, is below **2%**, add
`GA` with 1,000 evaluations to the portfolio. Data used: the 180 `val` instances of the full matrix (seed 20261011),
six heuristics each, from `results/models/s03_selector_v1/model.json`: `SBS` = `HEFT`, gap = **0.663%** → triggered.
This 2% is a statement about how much *selection among heuristics* can gain. It is unrelated to S01's results: the
S01 GA's 1.17% mean improvement over the best heuristic (test split, 6,000 evaluations) was not used here and is not
a threshold of any kind.

**The label margin θ (new, S03 only).** With the GA member, an instance is labelled `GA-1000` if
`C_GA1000,i < (1 − θ) · min_h C_h,i` (GA beats the best heuristic by more than a fraction θ; strict, so at θ = 0 a
GA tie goes to the cheaper heuristic), else the best heuristic (ties as before). θ is a minimum worthwhile *simulated* gain; it is not a time conversion. θ = 0 is included to show
what happens without any cost charge (GA, never worse than its seeds, becomes the label almost everywhere).

| Item | Fixed rule |
|---|---|
| GA member | S01's `GA` (keys + assignment, seeds `HEFT`, `MINMIN`, `FCFS-EAT`; population 60, tournament 3, crossover 0.9, σ 0.15, 1 mutation, 2 elites, the locked `s01_final.toml` values) with `max_evals = 1000` |
| GA makespans for labels | one run per `train` / `val` instance, RNG seeded from (20261017, instance hash); measured time recorded |
| θ grid | {0, 0.005, 0.01, 0.02, 0.05} |
| Per θ | tree fitted on `train` with the θ-labels and weights `(worst − best) / best` over the seven members; depth from {1, 2, 3, 4} by lowest mean `val` regret against that θ's own oracle label, ties shallower |
| θ choice (on `val`) | maximise **GA-call efficiency** = (mean `val` regret of `SBS` − mean `val` regret of the θ-selector) / (number of `val` instances on which it calls GA), regret measured against the six-heuristic `VBS`; only θ with ≥ 1 GA call and a positive numerator qualify; ties → larger θ. Dimensionless: simulated quality gained per optimiser call. No seconds enter it. If no θ qualifies, the extension selector never calls GA and that is reported. |
| Guard fallback | `SBS` (= the six-heuristic `SBS`, `HEFT`) |
| Methods | `ADAPTIVE-GA` (the extension selector) and `GA-1000` (always call GA: the fixed "optimiser" policy), each with algorithm seeds 0, 1, 2 at run time |
| Reference | The six-heuristic `ADAPTIVE` (model `s03_selector_v1`, unchanged) remains the **primary** S03 method; the predeclared primary comparison (§7.3, `ADAPTIVE` vs `SBS` on `test_id`) is unchanged. `ADAPTIVE-GA` is the **contingency extension**, secondary, no p-values. |
| Overhead | Reported separately: measured seconds per call (`ADAPTIVE-GA`, `GA-1000`, `ADAPTIVE`, `HEFT`), share of instances where GA is called, simulated improvement. The only combination of units is the labelled-hypothetical break-even τ* of §5.3. |

## 8. Limitations and threats to validity

**Internal**

- Simulator bugs would bias every result. Mitigated by the independent validator, the lower-bound check and exact
  optima on tiny instances.
- Wall-clock timings on a laptop are noisy (frequency scaling, background load, Python GC). Mitigated by repeats,
  single worker, evaluation counts.
- Hyperparameters tuned on `val` share the generator with the test set, so in-distribution results are optimistic
  about new workload types. The OOD sets measure this.

**Construct**

- Makespan in a simulator with no communication cost, exact estimates and free dispatch is a proxy for real execution
  time. The size of the gap is unknown and is not estimated here.
- The lower bound is loose on heterogeneous platforms, so `Cmax/LB` overstates distance from optimal there. It is used
  as a normaliser, not as an optimality gap.
- On `hetero` platforms speedup against the best single processor can exceed `m` (tasks each run on their preferred
  device). Efficiency above 1 there is a property of the baseline definition, not an anomaly.
- `HEFT` here has no communication term, because the model has no communication costs.
- S03 was meant to build on findings from Batches 1–3 and 7. None were available; features were chosen from those
  batches' topics, not their results.

**External**

- Synthetic DAGs only; no real application traces.
- One machine; overhead numbers are specific to an Apple M4 and to a pure-Python implementation. A compiled GA would
  have very different optimization times.
- Static, offline scheduling with full information. Nothing here speaks to online arrivals or runtime variability.

**Conclusion validity**

- Ten instances per cell is small; per-cell claims are avoided in favour of pooled and per-class claims with intervals.
- Three RL training seeds cannot characterise training variance well; they are shown individually.

**Future directions** (manual asks for at least three): stochastic task durations and online rescheduling; communication
costs; replay of schedules on a real OpenMP task runtime to measure the simulator gap;
a compiled simulator to shrink optimization overhead; graph-neural state encoders for RL.
