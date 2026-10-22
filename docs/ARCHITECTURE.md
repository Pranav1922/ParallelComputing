# CS 15 — AI-Based and Adaptive Scheduling: System Architecture

Status: **architecture only, nothing implemented.** Written 2026-10-11. Submission deadline (manual): 2026-10-19.

Labels used in all docs: **[FACT]** verified from the manual, repo or machine · **[DECISION]** a design choice ·
**[ASSUMPTION]** unverified, must be stated in the report · **[OPEN]** needs your approval or input.

---

## 1. Verified starting point

| Item | Finding |
|---|---|
| Repository | [FACT] `cs15/` was empty: no code, docs, config or git history. Nothing to preserve or reuse. |
| Manual | [FACT] Not in the repo. Read from `~/Downloads/Case_Study_Manual.pdf` (17 pages, BCSE412L, Fall 2026-27). |
| Sub-problem | [FACT] Not recorded anywhere in the project. Your intended scope, stated on 2026-10-11: **S01 + S02 + S03, all built by you.** This is **not faculty-approved** (see §1.1). |
| Machine | [FACT] Apple M4, 10 cores, 16 GB RAM, macOS (Darwin 27.2.0), Python 3.12.9. |
| Installed packages | [FACT] numpy 2.4.4, scipy 1.17.1, scikit-learn 1.8.0, torch 2.11.0, matplotlib 3.10.8, pandas 3.0.2, pytest 9.1.1. **DEAP and hypothesis are not installed.** |

### 1.1 Scope and compliance (pre-implementation audit, 2026-10-11)

What the manual says [FACT]:

- A batch has at most 3 students and chooses one problem statement (case study), with prior faculty approval, granted
  first come, first served.
- Each problem statement has 3 sub-problems and each student in the batch owns one.
- A batch of one or two students "can take any one or two problem statements according to the availability". Read with
  the previous rule, this means one student → one sub-problem, two students → two.
- Deliverables are a 2–3 page individual technical note per member and an 8–12 page batch report integrating the three
  contributions.

What follows:

- The manual contains **no rule that permits one student to own all three sub-problems**. The intended scope
  (one person, S01 + S02 + S03) exceeds the individually permitted scope as written.
- **Faculty approval is required** for (a) CS 15 as the batch's problem statement and (b) one student covering three
  sub-problems. Neither approval has been recorded in this project. Nothing in these documents or in any generated CSV
  or report may describe the scope as approved until you confirm it.
- If approval is refused, the design degrades cleanly: the shared core and baselines are needed for any single
  sub-problem, and each sub-problem is one module that can be dropped.

### 1.2 Deviations from the manual's suggested tools

| Manual | This design | Status |
|---|---|---|
| S01: "C++ workload simulator" | Python simulator | Deviation, documented (§4 D1). Needs faculty acceptance. |
| S01: "Python + DEAP or equivalent" | Hand-written NumPy GA | Within "or equivalent". |
| S03: "Python/C++ + OpenMP/CUDA as appropriate" | Python, simulation only | Deviation in spirit (§4 D2). Needs faculty acceptance. |
| S03: "Use findings from Batches 1–3 and 7" | Topics only; no findings available | Limitation, stated; no findings are invented. |

### What the manual requires for CS 15 [FACT]

| | S01 Evolutionary | S02 Reinforcement learning | S03 Adaptive workload-aware |
|---|---|---|---|
| Problem | Compare heuristic scheduling with a GA for DAG/task workloads | Investigate whether an RL policy can learn resource/task assignment | Scheduler that selects or combines policies according to workload characteristics |
| Research question | Can evolutionary optimization reduce makespan compared with baseline heuristics? | Can RL scheduling improve over a conventional heuristic after training? | Can an adaptive scheduler outperform a fixed scheduling policy across diverse workloads? |
| Objectives | Chromosome/fitness representation; compare with FCFS/priority heuristic; vary DAG size | State/action/reward; train on representative workloads; test on unseen workloads | Use findings from Batches 1–3 and 7; build workload features; compare adaptive vs fixed |
| Workloads | Synthetic DAGs | Synthetic DAG/task environment | Synthetic regular/irregular/heterogeneous |
| Tools | Python + DEAP or equivalent; C++ workload simulator | Python + PyTorch | Python/C++ + OpenMP/CUDA as appropriate |
| Metrics | Makespan; Utilization; Optimization time; Improvement | Makespan; Utilization; Inference overhead; Generalization | Makespan; Speedup; Decision overhead; Robustness |
| Graphs | DAG size vs makespan; Optimization time; Improvement vs workload | Training reward; Makespan vs method; Generalization performance | Workload feature vs selected policy; Adaptive vs fixed time; Robustness across workloads |

Common requirements [FACT]: baseline before optimization; ≥3 problem sizes; ≥3 resource configurations; execution time,
speedup, efficiency, scalability where applicable; overhead separated; repeated runs with mean/median and variation;
≥3 graphs and 1 summary table; limitations, threats to validity, ≥3 future directions; ≥5 scholarly papers; one CSV row per
experiment with the 19 mandated columns; derived metrics computed from raw data; hardware and software recorded; README
with exact reproduction commands; no speedup without a named baseline.

---

## 2. The research system

### 2.1 Problem

Static, non-preemptive scheduling of a task DAG on `m` processors to minimise makespan.

- **Workload**: DAG `G = (V, E)`, `|V| = n`. Task `t` may start only after every predecessor has finished.
- **Resources**: `m` processors, each runs one task at a time. A task runs on exactly one processor, without preemption.
- **Cost model**: a matrix `cost[t, p]` = time for task `t` on processor `p`, in **simulated time units (`sim_tu`)**.
  Homogeneous platforms have identical columns. Heterogeneous platforms use two processor types with per-task affinity
  (unrelated-machines model, motivated by CS 7 CPU–GPU).
- **Objective**: makespan `Cmax = max_t finish[t]`.

[ASSUMPTION] No communication cost, exact cost estimates, zero dispatch cost, no memory/cache/NUMA contention.
These are simulator simplifications and are the main limitation (see `VALIDATION_PLAN.md` §6).

### 2.2 Scheduling algorithm vs execution simulator

These are separate things and the report must keep them separate:

| | What it is | Unit | Measured or simulated |
|---|---|---|---|
| **Makespan** | Quality of the produced schedule under the cost model | `sim_tu` | **Simulated** |
| **Scheduling time** | Wall-clock time the scheduler itself takes to produce the schedule (GA optimization, RL inference, adaptive decision) | seconds | **Measured** on the M4 |

A lower simulated makespan is **not** a measured speedup on real hardware. The two quantities are never added. They are
related only through an explicit exchange rate `τ` (seconds per `sim_tu`) in a break-even analysis
(`EXPERIMENTAL_METHODOLOGY.md` §5.3).

### 2.3 Baseline and proposed approaches

| Role | Algorithm | Used by |
|---|---|---|
| Naive baseline (manual: FCFS) | `FCFS-EAT` | all |
| Priority heuristics (manual: priority heuristic) | `FCFS-EFT`, `SPT-EFT`, `LPT-EFT`, `MINMIN` | all |
| Strong baseline | `HEFT` (upward rank + insertion-based earliest finish time) | all |
| Proposed S01 | Genetic algorithm (`GA`) | S01 |
| Proposed S02 | Policy-gradient RL scheduler (`RL`) | S02 |
| Proposed S03 | Feature-based policy selector (`ADAPTIVE`, `ADAPTIVE-TOP2`) over the six heuristics above | S03 |
| S03 reference points | `SBS` (single best fixed policy, chosen on validation data), `VBS` (per-instance oracle), `TRY-ALL` (run all six, keep best) | S03 |

Every headline claim is made against the **strongest** baseline, not only FCFS.

### 2.4 Variables

| Kind | Variables |
|---|---|
| Independent | algorithm; problem size `n`; processor count `m`; workload class (regular, irregular, heterogeneous, irregular_hetero); for learned methods: in-distribution vs out-of-distribution test set |
| Controlled | generator and its parameter ranges; cost model; seeds; evaluation instances (identical for every algorithm: paired design); GA evaluation budget; RL and selector frozen before test; single-threaded scheduler; same machine |
| Measured (raw) | makespan, total busy time, scheduling time, decision time, decision count, fitness evaluations, peak RSS, validity |
| Derived | speedup, efficiency, utilization, normalised makespan, improvement, regret, robustness, generalization gap, break-even `τ*` |

### 2.5 Hypotheses

Each is falsifiable; a negative result is a valid outcome and will be reported (manual: "report unexpected results").

| ID | Hypothesis | Evidence required |
|---|---|---|
| H1 (S01) | GA produces lower makespan than FCFS and than the best heuristic on the same instances. | Paired per-instance ratio `Cmax_GA / Cmax_base`; 95% bootstrap CI below 1; Wilcoxon signed-rank. |
| H1b | GA's improvement shrinks where the heuristic is already close to the lower bound, and its optimization time grows with `n`. | Improvement vs heuristic's `Cmax/LB`; optimization time vs `n`. |
| H2 (S02) | After training, the greedy RL policy matches or beats `HEFT` on unseen in-distribution instances. | Paired ratio `Cmax_RL / Cmax_HEFT` per training seed; CI. |
| H2b | RL degrades on out-of-distribution workloads more than heuristics do. | Same ratio on each OOD set vs ID. |
| H3 (S03) | The adaptive selector has lower mean normalised makespan than the single best fixed policy. | Gap closed `(SBS − ADAPTIVE)/(SBS − VBS)` with CI above 0. |
| H3b | It does so at lower scheduling cost than `TRY-ALL`. | Scheduling time of `ADAPTIVE` vs `TRY-ALL`. |
| H4 (all) | Once scheduling overhead is charged, the ranking of methods depends on task time scale. | Break-even `τ*` distribution per method. |

---

## 3. Architecture

Diagram: [`architecture_diagram.mmd`](architecture_diagram.mmd).

### 3.1 Key idea: one schedule builder for every algorithm

[DECISION] Every scheduler, baseline or proposed, produces its schedule by repeatedly choosing a pair
`(ready task, processor)` and calling `ScheduleBuilder.place(t, p)`. The algorithms differ **only** in how they choose
the next pair.

The builder has two placement modes on the same state:

- **Append** (`insert=False`): `start = max(avail[p], ready_time[t])`. Used by GA and RL.
- **Insertion** (`insert=True`): the task goes into the earliest idle gap on `p` that starts at or after
  `ready_time[t]` and is long enough; otherwise it is appended. Used by all six heuristics.

**Audit correction (2026-10-11).** The first draft was append-only for every algorithm. That handicapped the baselines:
a fixed priority order (LPT, upward rank) can place a task whose predecessors finish late, leaving an idle gap that
later tasks could not use, a loss that conventional implementations of these heuristics do not suffer. GA and RL can
learn orders that avoid such gaps; fixed-priority heuristics cannot. Insertion removes the artefact and makes `HEFT`
the insertion-based form.

#### Schedule representation and expressiveness (correction of 2026-10-11, second pass)

The audit said "append mode can reproduce any insertion schedule". That was asserted, not shown, and as worded it hid
a restriction. The precise statements, each with its proof and its test, are below.

**How each method fixes a task's processor and start time.** No method ever sets a start time directly; the builder
computes it. All methods emit the same `Schedule(proc, start, finish)` and pass the same `validate()`.

| Method | Next task | Processor | Start time (computed by the builder) |
|---|---|---|---|
| Six heuristics | rule over the list-ready set | `EAT`/`EFT` rule, evaluated with insertion | **Insertion**: earliest time `≥ ready_time[t]` at which `p` has an idle interval of length `≥ cost[t, p]` |
| `GA` | highest key among list-ready tasks | gene `assign[t]` | **Append**: `max(avail[p], ready_time[t])` |
| `GA-KEYS-EFT` (ablation) | highest key | processor with least append-mode finish time | Append |
| `RL` | policy picks a pair `(t, p)` | from the pair | Append |
| `ADAPTIVE`, `TRY-ALL` | delegated to the chosen heuristic | delegated | Insertion |

**Definitions.** A schedule is *semi-active* if every task starts at `max(ready_time, finish of the task immediately
before it on its processor)`: nothing can start earlier without changing the order on a processor. Costs are strictly
positive (enforced when an instance is built); the proofs need this.

**Claim 1. Append mode generates exactly the semi-active schedules.**
(a) Every append-built schedule is semi-active by construction, since `avail[p]` is the finish of the previous task
on `p`. (b) Conversely, take a semi-active schedule `S` and replay its tasks in order of start time (ties by id) on the
same processors. That order is a valid placement order: a predecessor finishes no later than its successor starts and
has positive cost, so it starts strictly earlier. By induction on that order each replayed task gets the same
predecessors' finish times and the same previous task on its processor, hence the same start. So the replay equals `S`.

**Claim 2. Every insertion-built schedule is semi-active.**
Insertion puts `t` at the earliest fitting time `s ≥ ready_time[t]`. Either `s = ready_time[t]`, or `s` is the end of a
busy interval that the task could not fit before. In the second case that interval ends exactly where `t` starts, the
gap between them has zero length, and no later task can be inserted there, so it remains the task immediately before
`t`. Either way `start = max(ready_time, previous finish)`.

**Corollary.** Every schedule any of the six heuristics can produce is reproduced **exactly** by an append-mode
`(order, assignment)` sequence: order = start times, assignment = the heuristic's processors. This is how GA seeds are
encoded, and it means the heuristic's schedule is a reachable terminal state of the RL environment.

**Claim 3 (dominance, weaker).** For an arbitrary feasible schedule that is not semi-active, the same replay gives every
task a start `≤` its original start. Append mode cannot reproduce such a schedule, only improve on it.

**Can GA and RL represent internal idle gaps?** Yes, in two senses, and no in a third:

- A *forced* gap (a processor waits for a task's predecessor) is representable.
- A gap *filled by another task* is representable, but only if the filling task is placed **before** the task that
  follows the gap. Append mode cannot fill a gap retroactively.
- *Unforced* idle time is not representable. For makespan it is never useful.

**The restriction, stated plainly.** GA, RL and the heuristics have the same set of reachable final schedules for
practical purposes (GA/RL: all semi-active; heuristics: one semi-active schedule each). What differs is the
**construction**: an insertion heuristic may fill a gap after the fact, whereas GA and RL must order the gap-filling
task first. This does not shrink the search space, but it changes how hard good schedules are to find, particularly for
RL, whose policy has to anticipate a gap. It is a property of the proposed methods' design, not a handicap on the
baselines, and it will be listed as a limitation.

**How the experiment separates algorithm quality from expressiveness.**

| Control | What it shows |
|---|---|
| `test_model`: replay of random insertion-built schedules equals the original, array for array | Claims 1(b) and 2 hold on the implementation |
| `test_model`: replay of a deliberately delayed (non-semi-active) schedule starts every task no later, and strictly improves | Claim 3; the restriction is real and is tested |
| `test_heuristics`: on all 500 campaign instances, every heuristic's schedule replays exactly in append mode | The corollary holds for the actual baselines, so each is reachable by GA and RL |
| GA seeded with encoded heuristic schedules (S01 milestone: `decode(encode(H)) == H`) | GA starts at the baseline's exact schedule; any gain is search, not representation |
| Every heuristic also run with `insert=False`, reported as a labelled diagnostic, never as the baseline | How much of the baselines' quality comes from insertion |
| `GA-KEYS-EFT` is labelled as a **restricted** representation | It cannot express every semi-active schedule; no expressiveness claim is made for it |
| If RL loses to `HEFT` | Attributable to the policy: `HEFT`'s schedule is a reachable state |

Consequences:

- One implementation of dependency handling, resource contention and makespan; one cost matrix; one definition of task
  duration (`cost[t, p]`).
- Any sequence of valid `place` calls yields a feasible schedule, so GA and RL can never produce an infeasible one.
- The representation contains an optimal schedule: for makespan, some semi-active schedule is optimal, and every
  semi-active schedule is produced by some `(order, assignment)` sequence in append mode.
- A separate, independently written `validate()` re-checks every schedule from its `(proc, start, finish)` arrays alone.

### 3.2 Components

| # | Component | Module | Responsibility | Inputs → Outputs |
|---|---|---|---|---|
| 1 | Experiment configuration | `configs/*.toml`, loaded in `runner.py` | Sizes, processor counts, classes, algorithms, seeds, repetitions, budgets | TOML → `dict` + `config_hash` |
| 2 | Workload generator | `workloads.py` | Synthetic DAGs and cost matrices; class presets; seed and split discipline; instance hashing | `(family, class, n, m, split, index)` → `Instance` |
| 3 | DAG and resource model | `model.py` | `Instance`, `Schedule`, `ScheduleBuilder`, `validate`, `bounds`, `upward_rank` | — |
| 4 | Baseline schedulers | `heuristics.py` | Task rule × processor rule heuristics, `MINMIN`; registry | `Instance` → `Schedule` |
| 5a | Proposed: GA | `ga.py` | Encode/decode, GA loop, equal-budget controls (random search, hill climb) | `Instance, rng, budget` → `Schedule, trace` |
| 5b | Proposed: RL | `rl.py` | Candidate features, policy network, training loop, greedy inference | train: config → model file; infer: `Instance, model` → `Schedule` |
| 5c | Proposed: adaptive | `adaptive.py` | Workload features, selector training, selection with novelty guard, `TRY-ALL` | train: labelled instances → model file; infer: `Instance, model` → `Schedule` |
| 6 | Execution simulator | `model.py` (`ScheduleBuilder`) | Ready set, processor availability, start/finish times, makespan | `place(t, p)` calls → `Schedule` |
| 7 | Metrics and instrumentation | `runner.py` (raw), `analysis.py` (derived) | Time the scheduler call; record raw values; derive everything else later | — |
| 8 | Experiment runner | `runner.py` | Campaign loop, paired instances, repeats, resume, failure logging, leakage check | config → `results/raw/<campaign>/` |
| 9 | Results storage | `results/raw/<campaign>/` | Append-only `runs.csv`, trace CSVs, `manifest.json`; made read-only at the end | — |
| 10 | Analysis and visualisation | `analysis.py` | `master.csv` (manual's 19 columns), statistics, tables, figures with source data | raw dir → `results/derived/`, `results/figures/` |
| 11 | Validation and testing | `tests/` | Unit, property, integration, and campaign-validation tests | — |

All eleven components from the brief are kept; none needed to be dropped. Components 3 and 6 share one module because the
simulator *is* the resource model's state machine (about 60 lines); separating them would add an interface with one
implementation.

### 3.3 Interfaces

```python
# model.py
@dataclass(frozen=True)
class Instance:
    id: str                 # "layered-irregular-n100-m4-test_id-0007"
    n: int
    m: int
    preds: tuple[tuple[int, ...], ...]
    succs: tuple[tuple[int, ...], ...]
    cost: np.ndarray        # shape (n, m), float64, > 0, sim_tu. Tasks are numbered topologically.
    meta: dict              # family, workload_class, platform, generator params, seed, split, hash

@dataclass(frozen=True)
class Schedule:
    proc: np.ndarray        # (n,) int
    start: np.ndarray       # (n,) float
    finish: np.ndarray      # (n,) float
    # makespan = finish.max()

class ScheduleBuilder:
    def __init__(self, inst: Instance): ...
    ready: list[int]                       # tasks whose predecessors are all placed
    avail: np.ndarray                      # (m,) time each processor becomes free
    def est(self, t: int, p: int, insert: bool = False) -> float   # append: max(avail[p], ready_time[t])
    def eft(self, t: int, p: int, insert: bool = False) -> float
    def place(self, t: int, p: int, insert: bool = False) -> None  # raises if t is not ready
    def done(self) -> bool
    def schedule(self) -> Schedule

def make_instance(id, m, edges, cost, meta=None) -> Instance   # validates; raises ValueError on malformed input
def validate(inst: Instance, s: Schedule) -> list[str]   # [] means valid
def bounds(inst: Instance) -> dict   # serial_best, cp_min, work_lb, lower_bound
def upward_rank(inst: Instance) -> np.ndarray

# Every scheduler, baseline or proposed, is a plain callable with this signature:
def scheduler(inst: Instance, rng: np.random.Generator) -> tuple[Schedule, dict]
# Heuristics also accept insert=False, used only for the labelled append-mode diagnostic.

# workloads.py
def generate(workload_class, n, m, split, index, *, family="layered", work_cv=None, campaign_seed=...) -> Instance
# The dict carries optional counters: fitness_evals, decision_count, decision_time_s,
# selected_policy, fallback_used, trace rows.
```

Learned schedulers are closures over a frozen model file, so they present the same signature.

### 3.4 End-to-end data flow

```
configs/full.toml
   │
   ├─► train-rl        ── workloads(train, val) ─► models/rl_seed{k}.pt + .meta.json + .train_hashes.txt
   ├─► train-selector  ── workloads(train) × 6 heuristics ─► models/selector.joblib + .meta.json
   │
   └─► run ── for each test instance (generated from seed)
              for each algorithm, for each repeat:
                 time [ scheduler(inst, rng) ]  ─► Schedule ─► validate() ─► one row in runs.csv
                                                              └► ga_trace.csv / selector_decisions.csv
           ─► results/raw/<campaign>/{runs.csv, *_trace.csv, manifest.json}   (read-only when finished)

analyze results/raw/<campaign>
   ─► results/derived/master.csv        (manual's 19 columns + extras, all derived values computed here)
   ─► results/derived/summary_*.csv     (tables)
   ─► results/figures/*.{pdf,svg} + *.csv (plot source data)
```

---

## 4. Design decisions and rejected alternatives

| # | Decision | Rejected alternative | Why |
|---|---|---|---|
| D1 | One Python simulator shared by all three sub-problems | C++ simulator (manual lists it for S01) | Defensible for the research questions: all three ask about **schedule quality** (makespan), which is a deterministic function of (instance, schedule) and does not depend on the simulator's language. GA fitness and the RL environment call the simulator in-loop, so a C++ core would need a binding layer, a build step and a second implementation to keep consistent. What the choice **does** affect is measured scheduling/optimization time: it reflects pure Python on an Apple M4 and would be much lower in C++. So evaluation counts are reported next to seconds, and no claim is made about absolute optimization speed. Sizes up to `n = 400` are within reach of Python on this machine; the pilot measures this before the campaign. [OPEN] faculty acceptance. |
| D2 | Simulation only; no OpenMP/CUDA execution | Real task runtime | Manual says "as appropriate". A real runtime for three schedulers in eight days is not feasible solo. Stated as a limitation; never reported as hardware speedup. [OPEN] |
| D3 | Hand-written NumPy GA | Install DEAP | Manual allows "DEAP or equivalent". DEAP is not installed; the GA is about 80 lines; no new dependency. |
| D4 | One list-scheduling builder; heuristics place with gap insertion, GA and RL append | (a) Event-driven non-delay dispatch for heuristics with a separate plan decoder for GA; (b) append-only for everything (first draft) | (a) Two simulators would make the comparison depend on simulator differences, and non-delay dispatch cannot wait for a faster processor. (b) Handicaps fixed-priority heuristics (§3.1). Insertion for GA decode was rejected as unnecessary: append mode already reaches every insertion schedule, and it is cheaper per evaluation. |
| D5 | General cost matrix `cost[t, p]` | Scalar processor speeds | Same code size; also covers CPU–GPU-style affinity where a task is faster on one type and slower on another. |
| D6 | Communication cost omitted | Edge weights and communication delays | Shared-memory model; fewer parameters to justify. `Communication_Time` is recorded as `NA`, not 0. |
| D7 | `HEFT` with insertion-based EFT, mean costs for upward rank, no communication term | Non-insertion variant (first draft) | The non-insertion variant was a weakened strong baseline. Remaining difference from the published algorithm: no communication costs, because the model has none. |
| D8 | RL: per-candidate MLP scorer trained with REINFORCE and a HEFT-rollout baseline | GNN encoder; PPO; DQN | Variable action sets are handled by scoring only valid candidates. Smallest design that can answer the research question; fewer hyperparameters to tune in the time available. |
| D9 | S03: shallow decision tree over 9 features, selecting one of 6 heuristics | Neural selector; per-decision policy switching | A depth-≤4 tree is readable as rules, which the "feature vs selected policy" graph needs. Per-decision switching is omitted; `ADAPTIVE-TOP2` covers "combines". |
| D10 | Raw CSV stores no derived metrics | Write speedup/efficiency at run time | Manual: derived metrics must be computed from raw data. |
| D11 | TOML config via stdlib `tomllib` | YAML | No extra dependency. |
| D12 | Property tests as seeded loops in pytest | hypothesis | Not installed; not needed. |
| D13 | Deterministic task durations | Stochastic durations (estimate ≠ actual) | Keeps makespan a pure function of (instance, schedule), so repetition measures algorithm and instance variation, not simulator noise. Listed as future work. |

---

## 5. Omissions

- **No real-hardware execution** (D2). Scheduling-time numbers are real; makespan numbers are simulated.
- **No communication, synchronization or energy measurement.** The model has none. These CSV fields are `NA`.
- **No warm-up handling for makespan** (deterministic). Warm-up applies only to wall-clock timing: one untimed call per
  algorithm before timed runs.
- **No preemption, no task duplication.**
- **No results database.** CSV files are enough and are what the manual asks for.

---

## 6. Unresolved decisions [OPEN]

1. **Python-only simulator** instead of the C++ simulator the manual lists for S01 (D1).
2. **Simulation only** for S03 instead of OpenMP/CUDA (D2). An optional real-execution replay is described in
   `IMPLEMENTATION_ROADMAP.md` phase 9 and is off by default.
3. **"Use findings from Batches 1–3 and 7"** (S03 objective). Those batches' results are not available here. The design
   uses their *topics* to choose features (granularity → work CV; scheduling regularity → CV and skew; DAG structure →
   critical-path ratio; CPU–GPU → heterogeneity). If you have their actual findings, supply them.
4. **Faculty approval of the scope** (§1.1): CS 15 as the problem statement, and one student covering all three
   sub-problems. Not obtained as far as this project records.
5. **`Student_ID` and `Batch_ID`.** Not guessed. The placeholders `STUDENT_ID_UNCONFIRMED` and `BATCH_ID_UNCONFIRMED`
   are used until you confirm them. They are kept out of the immutable raw data and joined in at analysis time
   (`DATA_SCHEMA.md` §5), so confirming them later does not require rerunning anything.
6. **Literature review** (≥5 papers, ≥3 recent): **not started.** It is a separate task
   (`IMPLEMENTATION_ROADMAP.md` phase L). No citations are made in these docs. HEFT and min-min are named as algorithm
   families only; their references must be verified before they are cited.
