# Algorithm Design

All algorithms build schedules through the same `ScheduleBuilder` (see `ARCHITECTURE.md` §3.1). No algorithm is claimed
to be better than another here; that is what the experiments are for.

Notation: `n` tasks, `m` processors, `e` edges, `cost[t, p]` in `sim_tu`, `c̄(t)` = mean of `cost[t, ·]`,
`Cmax` = makespan, `LB` = lower bound (see `DATA_SCHEMA.md` §4).

---

## 1. Shared mechanics

### 1.1 Feasibility

- A task is **ready** when all its predecessors have been *placed* (not necessarily finished in simulated time).
- `place(t, p)` in append mode: `start = max(avail[p], ready_time[t])`, `finish = start + cost[t, p]`,
  `avail[p] = finish`, successors' `ready_time` updated. `ready_time[t] = max finish over predecessors`.
- `place(t, p, insert=True)`: `start` = the earliest time `≥ ready_time[t]` at which `p` has an idle interval of length
  `≥ cost[t, p]`; falls back to the append start if no gap fits. Each processor keeps its busy intervals sorted.
- **Dependencies**: `start ≥ ready_time` guarantees precedence in both modes.
- **Resource contention**: append starts after `avail[p]`; insertion only uses an interval verified to be idle. Either
  way one task per processor at a time.
- `place` raises on a non-ready task, so an invalid action is a crash in tests, not a silently wrong schedule.

### 1.2 Fair comparison rules

1. Every algorithm sees the same information: the full DAG and the full cost matrix.
2. Every algorithm is evaluated on the same instances (paired).
3. Every schedule passes the same `validate()`.
4. Every algorithm's scheduling time is measured the same way and includes everything it does per instance
   (rank computation, heuristic seeding, feature extraction, network inference).
5. One-off costs (RL training, selector training) are reported separately and never hidden.
6. Hyperparameters are tuned on the `val` split only. The test split is run once, after everything is frozen.
7. Heuristics place with insertion; GA and RL place in append mode. Append mode reproduces every heuristic schedule
   exactly, because insertion-built schedules are semi-active (proof and tests: `ARCHITECTURE.md` §3.1). It cannot fill
   a gap retroactively; the gap-filling task must be ordered first. The baselines are never denied a capability the
   proposed methods have, and no baseline is weakened.

### 1.3 Deterministic tie-breaking and seeds

| Where | Rule |
|---|---|
| Heuristic task choice | lowest task id |
| Heuristic processor choice | lowest processor id |
| `MINMIN` pair choice | lowest task id, then lowest processor id |
| GA decode, equal keys | lowest task id |
| GA selection and elitism, equal fitness | lowest population index |
| RL greedy argmax, equal scores | first candidate; candidates are ordered by task id, then processor id |
| Selector, equal class probability | portfolio order as listed in the config |
| Selector labels, equal makespan | cheaper heuristic to run, then portfolio order |
| Floating-point comparisons in `validate` | tolerance `1e-9 · max(1, value)` |

Seeds: every random stream is a `numpy.random.Generator` from
`SeedSequence([campaign_seed, purpose_code, crc32(algorithm name), instance_index, algo_seed])`. Algorithm names are
hashed with `zlib.crc32`, not Python's `hash()`, which is salted per process. No global RNG, no time-based seed.

---

## 2. Baselines (`heuristics.py`)

A heuristic = **task rule** × **processor rule**, applied until all tasks are placed.

| Task rule | Picks the ready task with… |
|---|---|
| `FCFS` | smallest `ready_time` (tie: lowest task id) |
| `SPT` | smallest `c̄(t)` |
| `LPT` | largest `c̄(t)` |
| `RANKU` | largest upward rank: `rank(t) = c̄(t) + max over successors rank(s)` |

| Processor rule | Picks the processor with… |
|---|---|
| `EAT` | earliest possible start `est(t, p, insert=True)` (cost-blind) |
| `EFT` | earliest finish `eft(t, p, insert=True)` (cost-aware) |

| Name | Definition | Role |
|---|---|---|
| `FCFS-EAT` | FCFS × EAT | Naive baseline required by the manual. Cost-blind, so it is weak on heterogeneous platforms by construction. |
| `FCFS-EFT` | FCFS × EFT | FCFS made cost-aware; separates "bad order" from "bad assignment". |
| `SPT-EFT`, `LPT-EFT` | | Priority heuristics. |
| `HEFT` | RANKU × EFT | Strong baseline: upward rank on mean costs, insertion-based EFT. No communication term (the model has none). |
| `MINMIN` | Over all (ready task, processor) pairs, pick the pair with minimum `eft` | Strong on heterogeneous independent-ish workloads. |

Cost: the gap search makes each `est` up to `O(tasks on p)`, so rule-based heuristics are `O(e + n²)` worst case and
`MINMIN` is `O(n · |ready| · n)` worst case. This is still far below the GA's cost at the sizes used.

All are deterministic; tie-breaking is in §1.3.

On `homog` platforms `EAT` and `EFT` choose the same processor, so `FCFS-EAT` and `FCFS-EFT` coincide there. This is
expected and is checked by a test.

---

## 3. S01 — Genetic algorithm (`ga.py`)

### 3.1 Chromosome

Two arrays of length `n`:

- `keys ∈ [0, 1]^n` — task priorities (random keys).
- `assign ∈ {0..m−1}^n` — processor for each task.

### 3.2 Decoding and precedence handling

```
builder = ScheduleBuilder(inst)
while not builder.done():
    t = ready task with the highest key      # heap keyed on -keys
    builder.place(t, assign[t])
fitness = builder.schedule().finish.max()    # makespan, minimised
```

- Only ready tasks are ever chosen, so **every chromosome decodes to a feasible schedule**. No repair operator and no
  penalty term are needed.
- Every topological order is reachable (give keys that decrease along it), and every assignment is reachable, so the
  encoding contains an optimal schedule.
- Decode cost: `O(e + n log n)`.

### 3.3 Operators and parameters

| Element | Choice | Starting value [DECISION, tuned on `val` only] |
|---|---|---|
| Population | fixed size | 60 |
| Initialisation | 3 heuristic individuals (`HEFT`, `MINMIN`, `FCFS-EAT`) + random | — |
| Selection | tournament | size 3 |
| Crossover | uniform, applied independently to `keys` and `assign` | probability 0.9 |
| Mutation (keys) | Gaussian, clipped to [0, 1] | per-gene rate `mutations_per_chromosome / n` = `1/n`, σ = 0.15 |
| Mutation (assign) | random reset to a uniformly random processor | per-gene rate `1/n` |
| Elitism | best individuals copied unchanged | 2 |
| Stopping | fixed evaluation budget `B` | 6,000 evaluations: 60 for the initial population, then 58 children per generation, with the last generation truncated so the count is exactly `B` (103 generations) |
| Result | best-so-far schedule over all evaluations, kept as the evaluated `Schedule` object (earliest on ties) | — |

There is no stagnation early stop: every search method runs exactly `B` evaluations so budgets match (§3.5). The trace
records the evaluation at which the last improvement occurred, which shows where a stagnation rule would have stopped.

A heuristic schedule is encoded as `keys[t] = 1 − position(t)/n` with positions in order of **start time**, and
`assign[t] = proc[t]`. Decoded in append mode this reproduces the heuristic's schedule exactly
(`ARCHITECTURE.md` §3.1, corollary; tested on every campaign instance).

### 3.4 Cost

`O(B · (e + n log n))` for budget `B`, plus `O(P · n)` per generation for operators. With elitism and heuristic seeding
the GA's result is never worse than its best seed. That makes "GA ≥ HEFT" true by construction, so it is **not**
evidence that evolution helps. The controls below are what test that.

### 3.5 Controls and ablations

| Variant | Purpose |
|---|---|
| `GA` | Primary: seeded, keys + assignment. |
| `GA-UNSEEDED` | Shows what the GA finds without heuristic help. |
| `GA-KEYS-EFT` | Keys only; processor chosen by append-mode EFT at decode. Smaller search space; tests whether evolving the assignment is worth it at a fixed budget. Can exclude the optimum. See "What `GA-KEYS-EFT` measures" below. |
| `RANDOM-SEARCH` | Same encoding, same budget, same seeding: evaluates the seeds, then uniformly random chromosomes. Tests whether the GA beats blind sampling. |
| `HILL-CLIMB` | (1+1) search from the best seed with the GA's mutation operator (at least one gene always changes); a move is accepted if it is not worse. Same budget. Tests whether a population and crossover are needed. |

The primary variant is fixed after the pilot on `val`; it is not chosen by looking at test results.

**Budget matching.**

- One evaluation = one full decode of a chromosome to a makespan. Evaluating the seed individuals counts.
- `GA`, `GA-UNSEEDED`, `GA-KEYS-EFT`, `RANDOM-SEARCH` and `HILL-CLIMB` each get exactly `B` evaluations per run and
  the same algorithm seeds. `GA`, `RANDOM-SEARCH` and `HILL-CLIMB` start from the same three seed chromosomes, which
  decode to exactly the seed heuristics' schedules, so these three are never worse than the seeds; only the search
  operator differs. `GA-UNSEEDED` has no seeds. `GA-KEYS-EFT` receives the seeds' task orders only (next item).
- All five write the same trace (evaluations, elapsed seconds, best makespan), so they can be compared at equal
  evaluations **and** at equal wall-clock time, at any point up to `B`.
- Heuristics are not search methods and have no budget to match. They are compared at their own cost: one heuristic is
  one evaluation-equivalent, and `TRY-ALL` (best of six) is six. Their makespan and measured scheduling time appear on
  the same quality-vs-overhead plot (G10), and the GA's trace shows what it had achieved at the heuristic's time.
- Optimization time (measured seconds) and makespan (simulated) are separate columns and are never combined except
  through the break-even `τ*`.

**What `GA-KEYS-EFT` measures (audit of 2026-10-17).** Its chromosome is the key vector only; the decoder places the
highest-key ready task on the processor with the earliest append-mode finish time (ties: lowest id). A heuristic seed
enters as `encode(schedule).keys`, i.e. the heuristic's start-time order, and is then decoded with this rule, not
with the heuristic's own processor choice or gap insertion. So the seed's *schedule* is generally not representable:
on the 450 test instances of the full campaign, decoding HEFT's order this way gives HEFT's makespan on 154, a shorter
one on 137 and a longer one on 159 (MINMIN: 27 / 254 / 169; FCFS-EAT: 230 / 219 / 1). The pilot's 48 `val` instances
show the same pattern. There is no hidden incumbent: every candidate, seeds included, is a decoded schedule, the best
decoded schedule is what is returned, and `test_keys_eft_seeds_are_decoded_not_injected` checks this (with a budget
equal to the seed count the result is the best *decoded* seed, which the test confirms is sometimes worse than the
heuristic). Consequences: `GA-KEYS-EFT` carries no "never worse than the seeds" guarantee, the campaign check for
that guarantee does not apply to it, and its results measure "search over task orders with a greedy EFT append
placement, started from heuristic orders". Its space is a subset of the full `GA`'s (every schedule it produces is
semi-active, so the full decoder can express it), so where it wins it shows that, at `B = 6,000`, a smaller search
space beats a larger one, not that the full representation is less expressive.

**Final-campaign outcome (verified, 2026-10-17; `docs/S01_ACCEPTANCE_REPORT.md`).** The design above was run
unchanged. Observed: `GA` 1.17% mean paired improvement over the best heuristic (450 test instances); `GA-KEYS-EFT`
3.38%, and better than `GA` on 343 of 450; `HILL-CLIMB` within 0.27% of `GA`; `RANDOM-SEARCH` never improved on its
seeds; `GA-UNSEEDED` 17% worse than the best heuristic. No design change follows from these test results.

**Reporting.** Every algorithm seed's result is written as its own row. Per-seed results, the mean over seeds, runs
where the GA did not improve on its seeds, and any failed runs are all reported. A result where `GA` does not beat
`RANDOM-SEARCH` or `HILL-CLIMB` is reported as such.

**Implementation (S01 milestone).** `schedlab/ga.py`: `decode`, `encode`, `optimize(inst, rng, method, **settings)`.
Settings come from the `[ga]` section of a config (`population`, `max_evals`, `tournament`, `crossover_prob`,
`key_sigma`, `mutations_per_chromosome`, `elite`, `seed_heuristics`, `seeds`); unknown or out-of-range settings raise.
On an empty workload every method returns the empty schedule with 0 evaluations.

### 3.6 What is recorded

Per run: final makespan, evaluations used, wall-clock optimization time. Per generation (`ga_trace.csv`): evaluations so
far, elapsed seconds, best and mean fitness. The trace gives makespan-vs-optimization-time curves at every budget without
extra runs.

---

## 4. S02 — Reinforcement learning (`rl.py`)

### 4.1 Environment

One **episode** = scheduling one instance from empty to complete. Exactly `n` steps.

- **State**: the `ScheduleBuilder` (placed tasks, `avail`, `ready`, `ready_time`) plus the instance.
- **Action**: one pair `(t, p)` with `t` in the ready set and `p` any processor. This is the "resource/task assignment"
  named in the manual's problem statement.
- **Valid-action handling**: the candidate list contains only valid pairs. The network scores candidates; softmax is
  taken over that list. Invalid actions cannot be sampled, so no masking and no invalid-action penalty are needed.
- **Transition**: `builder.place(t, p)` in append mode. Deterministic: the next state is fully determined by the
  current state and the action.
- **Termination**: all tasks placed.

### 4.2 Candidate features

Twelve scale-free features per candidate `(t, p)`, so one network applies to any `n` and `m`:

| # | Feature |
|---|---|
| 1 | `log(cost[t,p] / min_q cost[t,q])` — how good this processor is for this task |
| 2 | `cost[t,p] / c̄(t)` |
| 3 | `c̄(t) / mean task cost` — task size |
| 4 | `rank_u(t) / max rank_u` — criticality |
| 5 | `outdegree(t) / max outdegree` |
| 6 | `(est(t,p) − min avail) / mean task cost` — waiting before start |
| 7 | `(eft(t,p) − min eft over candidates) / mean task cost` |
| 8 | `(est(t,p) − avail[p]) / mean task cost` — idle gap created on `p` |
| 9 | `(ready_time[t] − min avail) / mean task cost` |
| 10 | fraction of tasks already placed |
| 11 | `|ready| / m` |
| 12 | `(max avail − min avail) / mean task cost` — load imbalance |

Features 4 and 7 are the quantities `HEFT` uses. The policy can therefore imitate HEFT; this is disclosed, and an
ablation removes them.

### 4.3 Policy

MLP: 12 → 64 → 64 → 1 (ReLU), applied to all candidates in one batch; softmax over the candidate scores.
CPU only, `torch.set_num_threads(1)`.

### 4.4 Reward and training

- **Return**: `G = −Cmax / LB` at the end of the episode (no intermediate reward; equivalent objective to makespan).
- **Baseline**: `b = −Cmax_HEFT / LB` on the same instance. Advantage `A = G − b = (Cmax_HEFT − Cmax) / LB`,
  standardised within the batch.
- **Loss**: `−Σ_steps log π(a_step) · A − β · entropy`.
- **Algorithm**: REINFORCE (policy gradient). Adam.

| Parameter | Starting value [DECISION, tuned on `val` only] |
|---|---|
| Learning rate | 3e-4 |
| Batch | 16 episodes per update |
| Entropy coefficient β | 0.01 |
| Gradient clip | 1.0 |
| Updates | up to 3,000, or a 45-minute wall-clock cap per training seed |
| Training instances | freshly generated each batch from the `train` seed stream; all four classes, `n ∈ {50, 100, 200}`, `m ∈ {2, 4, 8}` |
| Validation | every 100 updates on the fixed `val` set, greedy decoding; keep the checkpoint with the best mean `Cmax/Cmax_HEFT` |
| Training seeds | 3 independent runs; **all three are reported**, not the best one |

Recorded in `rl_training.csv`: update, episodes, elapsed seconds, mean return, mean `Cmax/Cmax_HEFT` on the batch, and
the validation value. Total training time and episode count go in the summary table.

### 4.5 Evaluation

- Greedy (argmax) decoding: deterministic given the model.
- **Inference overhead**: wall-clock scheduling time per instance and per decision, compared with `HEFT`'s
  scheduling time on the same instance. Model load time is reported once, separately.
- **Generalization**: the same frozen models on `test_id` (unseen seeds, seen distribution) and on each `test_ood` set
  (unseen size, unseen processor count, unseen DAG structure, unseen cost variability). See
  `EXPERIMENTAL_METHODOLOGY.md` §2.4.

- **Comparators**: `FCFS-EAT` (conventional) and `HEFT` (strong), plus the other heuristics, all on the identical
  `test_id` and `test_ood` instances. None of those instances is used in training, checkpoint selection or tuning.

### 4.6 Criteria fixed before the full campaign

These thresholds are design decisions, written down now so they cannot be adjusted after seeing test results.
`ρ = Cmax_RL / Cmax_HEFT` per instance; intervals are 95% bootstrap over instances.

| Question | Data | Criterion |
|---|---|---|
| **Did it learn?** | `val`, per training seed | The best checkpoint's mean `ρ` is lower than the untrained network's (update 0) with the CI of the paired difference below 0, **and** its mean makespan is below `FCFS-EAT`'s. "Learned" if this holds for at least 2 of 3 seeds. |
| **Does it improve over the strong heuristic?** | `test_id`, mean over seeds | "Improves" if the CI of mean `ρ` lies below 1. "Matches" if the CI lies within [0.98, 1.02]. Otherwise "does not improve". |
| **Does it improve over FCFS?** | `test_id` | CI of mean `Cmax_RL / Cmax_FCFS-EAT` below 1. |
| **Does it generalise?** | each `test_ood` set | Gap `Δ = mean ρ_OOD − mean ρ_ID`. "Generalises" to that set if the upper CI bound of `Δ` is ≤ 0.02 **and** RL still beats `FCFS-EAT` there. Reported per OOD set, not pooled. |
| **Is it stable across training seeds?** | `test_id` | Range and standard deviation of per-seed mean `ρ` are reported. If seeds disagree on the "improves" verdict, the answer is reported as seed-dependent. |

Whatever the verdicts are, they are reported.

### 4.6a Implementation notes (S02 milestone, 2026-10-17)

`schedlab/rl.py`. Approved changes from the text above: placement uses gap insertion (as every baseline) instead of
append mode; no hyperparameter tuning (the starting values are the settings); BC fallback numbers fixed before the
pilot (200 updates, batch 16, lr 3e-4). Training stream: `train` split, indices ≥ 1000, cell drawn uniformly from the
36 in-distribution cells by `SeedSequence([20261017, k])`, shared by all training seeds. Each trained policy is its
own runner method (`RL-S0`…, `RL-NOHEFTFEAT`); `RL` = per-instance mean over the seed models. Pilot outcome:
`docs/S02_PILOT_REPORT.md`.

**Final-campaign outcome (verified, 2026-10-17; `docs/S02_ACCEPTANCE_REPORT.md`).** Seed-mean `RL` vs `HEFT` on
`test_id`: ρ 1.0097 (CI 1.0034–1.0160 [corrected 2026-10-17, see docs/report/ERRATA.md]) — verdict "matches" by the §4.6 band, but a significant ~1% shortfall;
vs `FCFS-EAT` ρ 0.822 ("improves"); seeds disagree (seed-dependent); generalises to `ood_size` and `ood_cv`, not to
`ood_procs` or `ood_struct`; the ablation is 3.7 points worse. Fallback not used.

### 4.7 Pre-declared fallback

If, by the end of its time box, the policy does not improve on its own initial validation score, a behaviour-cloning
warm start from `HEFT` decisions (cross-entropy on HEFT's chosen pair) may be used before REINFORCE. If used, it is
stated in the report and recorded in the model's metadata. If RL still does not match HEFT, the answer to the research
question is "no, under these conditions", and that is reported.

---

## 5. S03 — Adaptive workload-aware scheduler (`adaptive.py`)

### 5.1 Approach

Per-instance **algorithm selection**: compute workload features, predict which of the six heuristics (§2) will give the
lowest makespan, run that one.

### 5.2 Workload features

Nine features, all computable in `O(e + n·m)` before scheduling:

| Feature | Definition | Motivating topic |
|---|---|---|
| `log_n` | `log n` | scale |
| `par_ratio` | mean DAG level width / `m` | parallelism vs resources |
| `depth_ratio` | number of levels / `n` | DAG shape (CS 3) |
| `edge_density` | `e / n` | dependency density (CS 3) |
| `work_cv` | CV of `c̄(t)` | regularity, granularity (CS 1, CS 2) |
| `work_skew` | skewness of `c̄(t)` | irregularity (CS 2) |
| `cp_ratio` | mean-cost critical path / (`Σ c̄(t) / m`) | critical-path-bound vs work-bound (CS 3) |
| `het_machine` | mean over tasks of CV of `cost[t, ·]` | heterogeneity (CS 7) |
| `het_affinity` | fraction of tasks whose fastest processor is not the overall fastest processor | task–device affinity (CS 7) |

[OPEN] The manual says to use findings from Batches 1–3 and 7. **No empirical findings from those batches are
available to this project, and none are assumed or invented.** The "motivating topic" column records only which case
study's subject suggested a feature. Consequence, to be stated in the report: the features and the portfolio are not
grounded in measured results from those batches, so S03's first objective is only partly met unless you supply them.

### 5.3 Selector

- **Training data**: `train`-split instances (30 per cell). Each is scheduled by all six heuristics; the label is the
  one with the lowest makespan (tie: the cheaper to run, then alphabetical).
- **Model**: `sklearn.tree.DecisionTreeClassifier`, `max_depth ≤ 4` (chosen on `val`), sample weight =
  `(worst − best) / best` so instances where the choice matters count more.
- **Why a tree**: it prints as rules (`export_text`), which is what the "workload feature vs selected policy" graph
  shows, and its decision cost is a handful of comparisons.

### 5.4 Unfamiliar workloads: novelty guard

At training time the per-feature min and max are stored. At decision time, if any feature lies outside
`[min − 10% range, max + 10% range]`, the selector does not trust the tree and falls back to `SBS`. The fallback rate
is reported per test set. An ablation runs without the guard.

### 5.5 Variants and reference points

| Name | Definition | Scheduling cost |
|---|---|---|
| each fixed heuristic | §2 | 1 heuristic run |
| `SBS` | The fixed heuristic with the best mean `Cmax/LB` **on the `val` split** | 1 run |
| `BEST-FIXED-HINDSIGHT` | The fixed heuristic with the best mean on the test set itself. Not achievable in advance; shown only as a harder reference, always labelled as hindsight | 1 run |
| `ADAPTIVE` | features → tree → run 1 heuristic | features + 1 run |
| `ADAPTIVE-TOP2` | run the tree's top two predicted heuristics, keep the better ("combines") | features + 2 runs |
| `TRY-ALL` | run all six, keep the best | 6 runs |
| `VBS` | per-instance oracle; equals `TRY-ALL`'s makespan | — (bound) |
| `RANDOM-SELECT` | uniformly random heuristic | 1 run |

Information flow, with nothing from `test_id` or `test_ood` on the left-hand side:

| Artefact | Built from |
|---|---|
| Tree structure and thresholds, sample weights, labels | `train` |
| Novelty-guard feature ranges | `train` |
| Tree depth | `val` |
| `SBS` | `val` |
| §5.7 contingency decision | `val` |

`ADAPTIVE` is compared against **every** fixed heuristic individually, against `SBS`, and against
`BEST-FIXED-HINDSIGHT`. Beating `SBS` but not the hindsight policy is reported as exactly that.

**Stated plainly:** in this offline, deterministic setting `TRY-ALL` achieves oracle quality at six times the heuristic
cost, which is still small. The adaptive selector cannot beat `TRY-ALL` on makespan. Its only possible advantage is
reaching near-oracle makespan at lower decision cost. The evaluation is framed that way, and `TRY-ALL` is always shown.

### 5.6 Decision overhead

`decision_time_s` = feature extraction + tree prediction + guard check (excludes running the chosen heuristic).
`scheduling_time_s` = the whole call. Both are recorded.

### 5.7 Pre-declared contingency

If on `val` the gap between `SBS` and `VBS` is under 2% of `Cmax` (one heuristic dominates everywhere), selection among
heuristics has nothing to gain. In that case a seventh portfolio member, `GA` with a small budget (1,000 evaluations),
is added, so the selector decides when an expensive optimiser is worth calling. This decision is made on `val`, before
the test run, and reported either way.

### 5.7a Implementation notes (S03 milestone, 2026-10-17)

`schedlab/adaptive.py`. Label ties go to the cheaper heuristic in the order `FCFS-EAT`, `FCFS-EFT`, `LPT-EFT`,
`SPT-EFT`, `HEFT`, `MINMIN`; depth is chosen from {1, 2, 3, 4} by lowest mean `val` regret, ties to the shallower tree.
`SBS` = lowest mean `Cmax/LB` on `val`. The §5.7 gap is defined as `mean_i (C_SBS,i / C_VBS,i − 1)` on `val`.
`ADAPTIVE-TOP2` under a guard fallback runs the top two fixed policies of the `val` ranking. `TRY-ALL` makes no
decision and computes no features. Feature-group ablations are evaluated offline on `val` at training time (recorded in
`model.json`), not as runner methods. Pilot outcome and the open contingency question: `docs/S03_PILOT_REPORT.md`.

**Contingency applied (2026-10-17).** The §5.7 trigger fired (`val` gap 0.663%). Per your decision the GA member
was added as a *separate extension* (`ADAPTIVE-GA`, plus the fixed policy `GA-1000`) with a θ-margin label; the
six-heuristic `ADAPTIVE` remains the primary method. Rules: EXPERIMENTAL_METHODOLOGY §7.4; pilot: S03 pilot report §8.

**Final-campaign outcome (verified, 2026-10-17; `docs/S03_ACCEPTANCE_REPORT.md`).** Run unchanged. `ADAPTIVE` did
not improve on `SBS` = `HEFT` (`test_id` −0.016%, p = 0.78); it differed from `SBS` only on 18 heterogeneous
instances. On `test_ood` the guard fired on 66% of instances and the selector equalled `SBS` everywhere.
`ADAPTIVE-GA` +0.10% vs `SBS` (CI includes 0); always-`GA-1000` +0.87% at 155–282× HEFT's mean time.

### 5.8 Ablations

Tree depth (1, 2, 4, unlimited); feature groups removed (structure only, work only, heterogeneity only); with and
without the novelty guard; `ADAPTIVE` vs `RANDOM-SELECT`.
