# DRAFT — not submission-ready

> **Status:** draft for review, 2026-10-18. Not submission-ready: faculty approval of the one-person scope is pending,
> and so is confirmation that the added C++/OpenMP components meet the tooling requirement; `Student_ID` and
> `Batch_ID` are placeholders; the findings from Batches 1–3 and 7 required by S03 are unavailable; full texts of [6],
> [7], [10], [16] were not read and [5] only partly. See `SUBMISSION_CHECKLIST.md`.
> The manual requires submission as a Word document; this Markdown draft is the content source for it.

| | |
|---|---|
| Course | BCSE412L Parallel Computing, Fall Semester 2026-27, Slot C1+TC1 |
| Case study | CS15 — AI-Based and Adaptive Scheduling (S01, S02, S03) |
| Batch ID | `[BATCH_ID — PENDING CONFIRMATION]` |
| Student ID(s) | `[STUDENT_ID — PENDING CONFIRMATION]` (single-member batch covering S01, S02 and S03 — **subject to faculty approval**) |

---

## 1. Title

**How Much Can AI-Based Scheduling Gain over a Strong List Heuristic? A Controlled Comparison of Evolutionary,
Reinforcement-Learning and Adaptive DAG Schedulers in Simulation and Measured OpenMP Execution**

## 2. Abstract

DAG scheduling on heterogeneous processors is NP-hard, and AI-based schedulers are often reported to beat list
heuristics. We test three on one shared, validated simulator with identical synthetic workloads: a genetic algorithm
seeded with heuristic schedules (S01), a REINFORCE policy that assigns ready tasks to processors (S02), and a
decision-tree selector over six heuristics (S03), against FCFS and HEFT on 360 held-out and 90 unseen-workload
instances, with predeclared tests and Holm correction. The GA reduced simulated makespan by 1.17% versus the
per-instance best heuristic (p = 6.2e-52) at about 1,100–1,730× HEFT's scheduling time; an equal-budget hill climber
nearly matched it. The selector did not improve on the best fixed policy (−0.016%, p = 0.78). The RL policy beat FCFS
by about 18% but trailed HEFT by 1.0%. A C++ simulator reproduced 41,850 accepted makespans exactly, and executing the
schedules with OpenMP on an Apple M4 confirmed the GA's gain in aggregate (1.6% faster than HEFT, 95% CI 1.2–2.0%),
showed an OpenMP task runtime 19% slower than a static HEFT schedule, and found efficiency falling to 0.42 at eight
threads. HEFT remains near the ceiling of cheap scheduling. *(≈ 190 words)*

## 3. Introduction and literature review

### 3.1 Motivation

A parallel program expressed as a task DAG runs only as fast as its schedule allows: the order in which ready tasks
start and the processor each one runs on decide the makespan, the processor utilization, and therefore the speedup
over serial execution. Finding an optimal schedule is NP-complete in the general case [1], [2], so practical systems
use fast list heuristics. On heterogeneous platforms (CPUs plus accelerators with task-dependent speed-ups) the choice of
processor matters as much as task order, and the case study's guiding question applies directly: *can
workload-aware or learning-based scheduling improve over fixed scheduling policies?* CS15 asks it in three forms:
search (S01), learning (S02) and selection (S03).

### 3.2 Literature review

**DAG list scheduling and heterogeneous heuristics.** Kwok and Ahmad [1] surveyed and classified 27 static
algorithms for scheduling directed task graphs on multiprocessors and describe the vocabulary used here: task
priority, processor selection, insertion into idle slots, and evaluation on random graphs. Topcuoglu, Hariri and Wu
[2] introduced HEFT (Heterogeneous Earliest-Finish-Time) and CPOP for a bounded number of heterogeneous processors,
designed to give good schedules at low scheduling time. In this project HEFT is implemented as upward-rank task
priority with earliest-finish-time processor selection and insertion into idle slots (ALGORITHM_DESIGN §2). Braun *et al.* [3] compared eleven static heuristics for
mapping independent tasks onto heterogeneous machines under common assumptions. In their study a GA gave the best
mappings in every case, and its best solution always came from a population seeded with the Min-min solution, while
the much cheaper Min-min came close to the best at a very small execution time. These works
motivate our baseline set, which pairs FCFS (the manual's conventional baseline) with HEFT and Min-min as strong,
cheap references. *Limitation for our purpose:* they compare heuristics against each other; they do not ask how much
of the remaining gap to optimal a search or learning method can close per unit of scheduling time.

**Evolutionary scheduling.** Hou, Ansari and Ren [4] applied a genetic algorithm to multiprocessor scheduling and
compared it with list scheduling and optimal schedules on random task graphs. Bean [5] presented a genetic algorithm
with random keys for sequencing and optimization problems, including multiple-machine scheduling — the representation
idea our S01 GA builds on (in our decoder, keys set the priority among ready tasks, so every chromosome decodes to a
precedence-feasible schedule). Among recent work, Sulaiman *et al.* [6] proposed hybrid
GA/list heuristics (HHG, HTDG) that improve the initial population with two guided chromosomes and reported better
average makespan than two GAs and two list heuristics (HEFT and PEFT). Jiang *et al.* [7] proposed a real-relative
encoding whose every chromosome decodes to a precedence-valid schedule, simplifying the genetic operators.
*Limitations relative to our question (from the abstracts):* comparisons are made against other metaheuristics and
heuristics, but the reviewed abstracts do not report equal-budget non-evolutionary search controls (random search,
hill climbing), and guided seeding — which [6] uses to improve quality — also makes "never worse than the seeds" a
property of the construction rather than evidence of search. [6]'s abstract reports better average running time than
its counterparts; how that time compares with HEFT's could not be checked, as the full text was not accessible.

**Reinforcement-learning scheduling.** Mao *et al.* [8] (Decima) showed that learned policies can schedule
DAG-structured data-processing jobs and improved average job completion time by at least 21% over hand-tuned
heuristics in their cluster setting. Grinsztajn *et al.* [9] (READYS) combined graph convolutional networks with an
actor-critic method for dynamic DAG scheduling on CPU/GPU platforms. In simulation it performed similarly to HEFT when
task durations were nearly deterministic, outperformed HEFT as duration noise grew, and transferred from small
training graphs to larger ones. Zhadan *et al.* [10] used multi-agent RL to choose a heuristic rule adaptively
at each scheduling step and reported an average 5.32% gain over the best baseline (DONF) on random DAGs.
*Limitations relative to our question:* gains are reported in settings with stochastic durations, cluster dynamics or
step-level rule switching, against baselines whose placement rules and overheads differ; the RL policy's own
inference overhead and training cost are not the headline metric (for [10], from its abstract). Notably, READYS's clearest gains over HEFT
appear only once durations are stochastic [9]. Whether a policy trained on a deterministic, communication-free model
beats an insertion-based HEFT on held-out instances is not answered by the reviewed work.

**Workload-aware and adaptive scheduling (algorithm selection).** Rice [11] formalised the algorithm selection
problem: choose, from instance features, the algorithm expected to perform best. Kerschke *et al.* [12] surveyed
automated algorithm selection and its relation to configuration, scheduling and portfolios; the standard references
for evaluating a selector are the single best solver (SBS) and the virtual best solver (VBS, the per-instance
oracle); a selector is judged by how much of the SBS–VBS gap it closes, which we adopt. Uzunoglu *et al.* [13] used learning-to-rank models to select, per instance, among learning-augmented construction
heuristics for a serial-batch scheduling problem. Selection beat the single best heuristic in every size group (mean
relative improvement over the worst compared method, 6.42% vs 2.23%), and GA improvement of the selected solutions
raised it to 39.19%. *Limitation relative to our question:* algorithm selection pays off when no single algorithm dominates; how
large the SBS–VBS gap actually is for DAG list heuristics on a given workload distribution, and whether a selector
recovers it at negligible decision cost, has to be measured, not assumed.

**Evaluation methodology.** Comparing several AI methods against shared baselines raises multiplicity: we use one
predeclared primary comparison per sub-problem with Holm's sequentially rejective correction [14] across the three;
each primary comparison is a Wilcoxon signed-rank test [15] on paired makespans, and effect sizes carry bootstrap
confidence intervals (percentile method) [16].

### 3.3 Research gap

Across the reviewed work, AI-based schedulers are usually evaluated in isolation, against other metaheuristics or
heuristics, on the authors' own models, and with improvements reported as headline percentages. Four questions are
rarely answered together and on the same footing: (i) *how much* a search, learning or selection method improves on
the strongest cheap heuristic **on identical instances under the same placement rule**; (ii) whether that improvement
survives **controls** (equal-budget search, unseeded search, oracle and single-best references) and **held-out and
unseen workloads**; (iii) what it **costs** in measured scheduling time; and (iv) whether simulated differences **survive execution
on real threads**. This case study answers all four for one shared simulator and a measured OpenMP replay, with predeclared hypotheses, primary comparisons and verdict bands, and reports null and
negative results with the same weight as positive ones.

## 4. Problem statements, research questions and hypotheses

**Common problem.** Given a DAG of `n` tasks with a cost matrix `cost[t, p]` (time of task `t` on processor `p`) and
`m` processors, find a feasible non-preemptive schedule minimising the makespan `Cmax`. No communication cost is
modelled. Times are in simulated time units (`sim_tu`); mean task work is 100 `sim_tu`.

Table 1 — sub-problems, the manual's research questions and the hypotheses predeclared in the architecture phase
(`docs/ARCHITECTURE.md`).

| Sub-problem (manual) | Research question (manual) | Predeclared hypothesis (ARCHITECTURE.md, architecture phase) |
|---|---|---|
| S01 Evolutionary task scheduling | Can evolutionary optimization reduce makespan compared with baseline heuristics? | **H1** GA produces lower makespan than FCFS and than the best heuristic on the same instances. **H1b** its improvement shrinks where heuristics are close to the lower bound; optimization time grows with `n`. |
| S02 RL-based scheduling | Can RL scheduling improve over a conventional heuristic after training? | **H2** after training, the greedy RL policy matches or beats HEFT on unseen in-distribution instances. **H2b** RL degrades on out-of-distribution workloads more than heuristics do. |
| S03 Adaptive workload-aware scheduler | Can an adaptive scheduler outperform a fixed scheduling policy across diverse workloads? | **H3** the selector has lower mean normalised makespan than the single best fixed policy (gap-closed CI above 0). **H3b** it does so at lower scheduling cost than running all policies (`TRY-ALL`). |
| All | — | **H4** once scheduling overhead is charged, the ranking of methods depends on the task time scale. |

**Role of each part (manual: baseline / main dimension / optimization-adaptation).** The shared core and baseline
heuristics establish the problem and algorithmic behaviour; S01 measures how far per-instance search can push below
the heuristics (the quality dimension) and at what optimization cost; S02 asks whether that search can be replaced by
a learned constructive policy; S03 asks whether choosing among cheap fixed policies per workload is enough.

## 5. System architecture and shared scheduling model

A Python package, `schedlab`, implements the schedulers, workloads, runner and analysis, and two C++ programs (`cpp/`)
add an independent workload simulator and an OpenMP executor; each sub-problem lives in one module, and all share the
same simulator, workloads, baselines, runner and analysis (Table 2).

Table 2 — modules of the shared `schedlab` package and their responsibilities.

| Module | Responsibility |
|---|---|
| `model.py` | `Instance`, `ScheduleBuilder` (the execution simulator: precedence, processor availability, optional insertion into idle gaps), an **independent schedule validator**, lower bound `LB = max(critical path at fastest costs, total min work / m)` and the speedup baseline `serial_best` |
| `workloads.py` | seeded synthetic DAG and cost-matrix generator, content hashing, split separation |
| `heuristics.py` | six baselines: `FCFS-EAT`, `FCFS-EFT`, `SPT-EFT`, `LPT-EFT`, `HEFT` (upward rank + insertion EFT), `MINMIN`; all insertion-based |
| `ga.py` (S01) | random-key + processor-assignment GA, `GA-KEYS-EFT` ablation, `GA-UNSEEDED`, `RANDOM-SEARCH`, `HILL-CLIMB` controls |
| `rl.py` (S02) | 12 candidate features, REINFORCE trainer, greedy policy |
| `adaptive.py` (S03) | 9 workload features, decision-tree selector with novelty guard, `GA-1000` contingency extension |
| `runner.py`, `analysis.py` | one raw CSV row per (instance, method, repeat or seed); derived metrics, tables, figures, campaign checks |
| `cpp/schedsim` (C++17) | workload simulator: independent port of `model.py` and the six heuristics, bit-exact (hex-float I/O, numpy's summation order, no FMA contraction) |
| `cpp/ompexec` (C++17, OpenMP) | runs a schedule on `m` threads (static replay with acquire/release completion flags; OpenMP tasks as dynamic baseline; serial T1) with work-calibrated compute kernels and a per-task trace |
| `interop.py`, `rederive.py`, `ompexec.py`, `omp_analysis.py`, `omp_master.py` | file interface to the C++ programs, exact re-derivation of accepted schedules, measured-campaign driver, analysis and 19-column CSV |

Every schedule from every method passes through the same validator before its row is accepted, and every derived
metric is recomputed from raw columns. The manual's 19-column CSV (`master.csv`) is produced for every campaign, with
`Execution_Time` = simulated makespan and `Scheduling_Time` = measured seconds; how every overhead category is treated
is given in Table 3 (§6); the measured replay has its own `master.csv` with `Execution_Time` in seconds. The
architecture diagram is in `docs/architecture_diagram.mmd`; every table and figure is traced to its source file in
`docs/report/TRACEABILITY.md`.

## 6. Experimental methodology

**Common experimental environment.** Apple M4 (4 performance + 6 efficiency cores), 16 GB RAM, macOS 27.2 (arm64); Python 3.12.9, NumPy 2.4.4,
SciPy 1.17.1, scikit-learn 1.8.0, PyTorch 2.11.0 (CPU, one thread), pandas 3.0.2, Matplotlib 3.10.8. Single worker
process, one thread per scheduler call; timing with `perf_counter_ns` around the scheduler call only. S01 and S03
ran on battery power; S02 training and its final campaign ran on mains power (recorded in the manifests). No GPU was
used (PyTorch ran on the CPU), so GPU memory and GPU driver versions are not applicable. Python runtime: one worker
process, one thread (`torch.set_num_threads(1)`), deterministic PyTorch algorithms, fixed seeds. C++ components:
Homebrew GCC 15.2, `-O2 -std=c++17 -ffp-contract=off -fno-fast-math`, `-fopenmp` (libgomp, `_OPENMP` 201511);
`OMP_DYNAMIC=false`, default wait policy, no thread pinning (`OMP_PROC_BIND` unset).

**Parallel strategy.** The parallelism studied is task-level parallelism of a DAG on `m` simulated processors: every
method produces a static, non-preemptive schedule that assigns each task one processor and a start time, respecting
precedence, so independent tasks on different processors execute concurrently; on `hetero` platforms processors
differ in speed per task. All methods place tasks through the same insertion-capable simulator and the same
independent validator. The schedulers themselves are sequential programs; experiments run in one worker process with
one thread so that measured scheduling times are not distorted by contention. In the measured replay (§7.8) the same
schedules run on real threads: thread `p` executes processor `p`'s tasks in schedule order and waits on per-task
completion flags for predecessors on other threads; an OpenMP task runtime that creates each task when its last
predecessor finishes is the dynamic baseline.

**Repetitions and seeds.** These are distinct. Deterministic methods (the six heuristics; `ADAPTIVE`,
`ADAPTIVE-TOP2`, `ADAPTIVE-NOGUARD`, `TRY-ALL`; each trained RL policy) are run **3 times per instance as timing
repetitions**, with identical makespans asserted. Stochastic methods (S01's five search methods, `RANDOM-SELECT`,
`ADAPTIVE-GA`, `GA-1000`) are run **once per algorithm seed, with seeds 0, 1 and 2**, and are averaged over seeds per
instance. S02 has **3 training seeds** (0, 1, 2) plus one ablation model (seed 0), each trained once. Rows: S01
14,850, S03 17,550, S02 13,500.

**Workloads.** Layered random DAGs with four classes: `regular` (work CV 0.1, equal layer widths, homogeneous
processors), `irregular` (CV 1.5, irregular widths, homogeneous), `heterogeneous` (CV 0.5, CPUs plus accelerators,
`hetero`), `irregular_hetero` (CV 1.5, irregular, `hetero`). In-distribution sizes `n` ∈ {50, 100, 200} and processor
counts `m` ∈ {2, 4, 8} (three problem sizes, three resource configurations). Unseen workloads (`test_ood`): `ood_size`
(n = 400), `ood_procs` (m = 16), `ood_struct` (fork-join DAGs), `ood_cv` (work CV 3.0).

**Splits** (content-hash disjoint, verified at every campaign start): `train` 1,080 (S03 labels; S02 used a separate
stream of 48,000 training-split instances), `val` 180 (all model and parameter choices), `test_id` 360 and `test_ood`
90 (final evaluation, run once per sub-problem with locked configurations and pinned model ids).

**Metrics.** Makespan (simulated), normalised makespan `Cmax/LB` (≥ 1), speedup `serial_best/Cmax` (baseline: all
tasks run sequentially on the single best simulated processor), efficiency `speedup/m`, utilization
`Σ busy time / (m·Cmax)`, measured scheduling/optimization/decision/inference time (seconds), paired improvement
`(C_base − C_alg)/C_base` and ratio `ρ = C_alg/C_base` per instance, regret vs the per-instance best heuristic.

**Statistics.** Paired by instance; seeded methods averaged over seeds per instance; 95% bootstrap CIs (percentile method)
[16] (10,000 resamples of instances); one Wilcoxon signed-rank test [15] per sub-problem for the predeclared primary
comparison; Holm correction across the three [14]. Secondary comparisons have CIs but no p-values. Timing outliers
(above Q3 + 3·IQR within algorithm × n × m) are flagged, never removed.

**Measured execution (C++/OpenMP).** All 360 `test_id` instances × 15 methods (`SERIAL` = T1; 13 schedules: FCFS-EAT,
HEFT, GA and GA-KEYS-EFT seeds 0–2, RL-S0–S2, ADAPTIVE, TRY-ALL; OpenMP tasks) × 3 task granularities (mean task
1 ms, 100 µs, 10 µs) × 10 timed repetitions after 2 warm-ups: 194,400 runs, 54 min, mains power. A task runs a compute
kernel of llround(cost · u · 813.1) iterations, u = µs per `sim_tu` (calibrated; linearity R² 0.9997); instance, granularity and method
order were randomized with fixed seeds. The schedules are the accepted ones, re-derived exactly (10,350 runs, 0
differences), and the C++ simulator reproduced every accepted heuristic and re-derived makespan bit for bit. Per
instance the median of the 10 repetitions is used; speedup = T1/Tp. Design, three predeclared comparisons (primary at
1 ms tasks, Holm) and acceptance criteria were locked before launch (`docs/MD_ANALYSIS_PLAN.md`).

**Overheads (Table 3).** In the simulation campaigns only scheduling-side costs are measured and task execution is
simulated; the OpenMP replay measures execution; quantities that are not modelled are `NA`, never 0.

Table 3 — treatment of computation, communication, synchronization, scheduling, data-movement and other overheads.

| Quantity | Status | Where recorded |
|---|---|---|
| Computation (task execution) | Simulated, `sim_tu`; measured seconds in the OpenMP replay | `Execution_Time` (makespan; replay: wall time); busy time in raw `busy_time_sim` / `compute_s` |
| Scheduling / optimization / decision / inference | Measured, seconds (wall clock, one thread) | `Scheduling_Time` per run; decision or inference part in `Decision_Time` (S03, S02) |
| Training (S02 policies, S03 selectors) | Measured once per model, seconds | `measured` block of each model's `model.json` (not per row) |
| Communication | Not modelled (DAG model has no data-transfer costs) | `Communication_Time` = `NA` |
| Synchronization | Campaigns: not measured (implicit in the simulated makespan). Replay: dependency waiting measured per run; fork/join ≈ 8 / 14 / 47 µs at 2 / 4 / 8 threads (calibration) | Replay `Synchronization_Time` (static mode); otherwise `NA` |
| Runtime queueing (OpenMP tasks) | Measured; includes waiting for a free thread (contention), not only dispatch | replay `Ready_Queue_Time_incl_contention` |
| Data movement | Not modelled | not recorded (`NA`) |
| Memory | Measured: process-wide peak RSS, an upper bound per run | `Memory_Use` (kB) |
| Energy | Unavailable | `Energy_if_available` = `NA` |

Table 4 — per-sub-problem configuration, controls, primary comparison and final campaign.

| | S01 | S03 | S02 |
|---|---|---|---|
| Proposed method | `GA`: random keys + processor per task, population 60, 6,000 evaluations, tournament 3, uniform crossover 0.9, Gaussian key mutation σ 0.15, 2 elites, seeded with HEFT, MINMIN, FCFS-EAT; 3 algorithm seeds | `ADAPTIVE`: depth-2 decision tree over 9 workload features, trained on `train`, depth and SBS chosen on `val`, novelty guard → SBS | `RL`: MLP 12→64→64→1 scoring every valid (ready task, processor) pair; REINFORCE with HEFT-relative advantage, 3,000 updates × 16 episodes, best `val` checkpoint; 3 training seeds |
| Controls / ablations | `GA-KEYS-EFT`, `GA-UNSEEDED`, `RANDOM-SEARCH`, `HILL-CLIMB` (equal budget) | `ADAPTIVE-TOP2`, `ADAPTIVE-NOGUARD`, `RANDOM-SELECT`, `TRY-ALL`; extension `ADAPTIVE-GA`, `GA-1000` | `RL-NOHEFTFEAT` (rank and EFT features removed) |
| Primary comparison | `GA` vs per-instance best heuristic | `ADAPTIVE` vs `SBS` (= `HEFT`, chosen on `val`), `test_id` | `RL` (seed mean) vs `HEFT`, `test_id` |
| Final campaign | `20261017T044734Z-s01_final-430d8a10`: 14,850 rows, 7,106 s | `20261017T083329Z-s03_final-b8e5be9a`: 17,550 rows, 237 s | `20261017T115054Z-s02_final-898ee9e1`: 13,500 rows, 80 s (+ 4 × ~16 min training) |
| Failures | 0 | 0 | 0 |

## 7. Results and discussion

### 7.1 Combined results (identical `test_id` instances, n = 360)

Table 5 — mean over instances (seed-averaged per instance) on the 360 in-distribution test instances. `Cmax/LB` and
speedup are simulated (baseline for speedup: serial on best single processor); time is the measured median seconds
per call (S01 and S03 on battery power, S02 on mains). Heuristic makespans are identical across the three campaigns
(verified on all 2,700 instance–heuristic pairs). Source: `results/derived/<campaign>/master.csv`.

| Method | Part | Cmax/LB | Speedup | Efficiency | Utilization | Time (s) |
|---|---|---|---|---|---|---|
| `FCFS-EAT` (conventional baseline) | base | 1.581 | 2.859 | 0.682 | 0.852 | 0.0003 |
| `HEFT` (strong baseline; `SBS`) | base | 1.180 | 3.502 | 0.813 | 0.895 | 0.0004 |
| `MINMIN` | base | 1.391 | 2.959 | 0.705 | 0.716 | 0.0010 |
| `GA` (6,000 evals) | S01 | 1.157 | 3.546 | 0.830 | 0.900 | 0.563 |
| `GA-KEYS-EFT` (ablation) | S01 | 1.123 | 3.634 | 0.850 | 0.900 | 1.000 |
| `HILL-CLIMB` (control) | S01 | 1.162 | 3.541 | 0.825 | 0.904 | 0.592 |
| `ADAPTIVE` | S03 | 1.181 | 3.502 | 0.813 | 0.890 | 0.0005 |
| `TRY-ALL` (oracle over six) | S03 | 1.175 | 3.514 | 0.818 | 0.891 | 0.0025 |
| `ADAPTIVE-GA` (extension) | S03 | 1.179 | 3.504 | 0.815 | 0.893 | 0.0005 |
| `RL-S0` / `RL-S1` / `RL-S2` | S02 | 1.176 / 1.181 / 1.211 | 3.484 / 3.477 / 3.377 | 0.821 / 0.819 / 0.796 | 0.858 / 0.844 / 0.818 | 0.006 |
| `RL-NOHEFTFEAT` (ablation) | S02 | 1.217 | 3.352 | 0.797 | 0.822 | 0.005 |

Efficiency on heterogeneous platforms can exceed what `m` identical processors allow, because the speedup baseline
is a single processor while tasks run on their preferred device; values are comparable across methods, not with 1.

### 7.2 Predeclared primary comparisons

Table 6 — primary comparisons. ρ = `C_method / C_baseline` per instance (< 1 favours the method); Wilcoxon
signed-rank on paired makespans; Holm correction over the three tests. Sources: `s01_paired.csv`,
`s03_paired.csv`, `s02_paired.csv`.

| Sub-problem | Comparison | Population (n) | Mean paired improvement or ρ | 95% CI | better / tie / worse | p | Holm |
|---|---|---|---|---|---|---|---|
| S01 | `GA` vs best heuristic | all test (450)† | **+1.169%** | +0.96% – +1.39% | 330 / 114 / 6 | 6.2e-52 | reject |
| S03 | `ADAPTIVE` vs `SBS` | `test_id` (360) | **−0.016%** | ratio 0.9991 – 1.0012 | 6 / 342 / 12 | 0.78 | not rejected |
| S02 | `RL` vs `HEFT` | `test_id` (360) | **ρ = 1.0097** (RL 0.97% longer) | 1.0034 – 1.0160 | 100 / 34 / 226 | 6.8e-6 | reject (RL worse) |

† S01's analysis population was not specified in advance; `test_id` gives +1.33% (CI 1.07–1.60%, p = 3.0e-43) and
`test_ood` +0.54% (p = 2.2e-10). The Holm decisions are the same for every S01 population (adjusted p: S01 ≤ 9.1e-43,
S02 1.4e-5, S03 0.78). S03's population was fixed before its pilot; S02's in the approved S02 plan before any S02
data; both were predeclared before the respective test evaluation.

### 7.3 S01 — Evolutionary task scheduling

The GA's mean improvement over the per-instance best of six heuristics was **1.169%** (Table 6): a detectable but
small effect, with ties on 114 of 450 instances. Two design facts bound its interpretation. First, the GA is seeded
with HEFT, MINMIN and FCFS-EAT and keeps its best-so-far schedule, so it cannot be worse than those seeds; they were
the best heuristic on 405 of 450 instances. The test therefore mostly shows that search improves on its seeds; the 6
losses all occurred where an unseeded heuristic (LPT-EFT or FCFS-EFT) was best. Second, the comparison is in
simulated time while the GA's cost is real: median optimization time 0.25 s (n = 50) to 3.7 s (n = 400), i.e.
~1,100–1,730× HEFT's scheduling time (Figure 2a).

The controls are the more informative result (Table 7). An equal-budget hill climber using the same mutation and seeds
reached 0.90% (GA ahead by only 0.27%, better on 190 and worse on 162 instances), so population and crossover add
little at this budget. Random sampling never improved on its seeds. Unseeded, the GA was 17% worse than the best
heuristic. The restricted ablation `GA-KEYS-EFT`, which evolves only task priorities and places each task with
append-mode EFT, beat the primary GA (3.38% vs 1.17%; GA worse on 343 of 450). Its seeds are re-decoded task orders,
not the heuristic schedules, so it carries no "never worse than seeds" guarantee; its advantage is that a much
smaller search space is easier to search with 6,000 evaluations. The primary method was fixed before the test run
and was not changed after seeing this.

Table 7 — S01 controls and ablations vs the per-instance best heuristic, all 450 test instances (`s01_paired.csv`).

| Method | Mean paired improvement | 95% CI (ratio) | better / tie / worse |
|---|---|---|---|
| `GA` (primary) | +1.169% | 0.9861 – 0.9904 | 330 / 114 / 6 |
| `GA-KEYS-EFT` | +3.375% | 0.9622 – 0.9702 | 353 / 83 / 14 |
| `HILL-CLIMB` | +0.899% | 0.9892 – 0.9928 | 337 / 103 / 10 |
| `RANDOM-SEARCH` | −0.134% | 1.0007 – 1.0021 | 0 / 428 / 22 |
| `GA-UNSEEDED` | −16.958% | 1.1494 – 1.1913 | 53 / 32 / 365 |

H1 is supported against FCFS (+19.7%) and, narrowly and largely by construction, against the best heuristic. H1b is
supported: the improvement over HEFT shrank from 2.5% at n = 50 to 1.0% at n = 400 while optimization time grew
(Figure 2a), and gains concentrated on heterogeneous classes (Figure 3). Convergence traces (Figure 2b) show many
large-instance runs still improving at 6,000 evaluations.

*Figures (S01, campaign `20261017T044734Z-s01_final-430d8a10`, PDF/SVG + CSV in `results/figures/<campaign>/`):*
**Figure 1** `g1_makespan_vs_size` — DAG size vs simulated makespan / lower bound, per class × processor count, median
and IQR over instances. **Figure 2a** `g2_opt_time_vs_size` — measured optimization time (s, log) vs DAG size.
**Figure 2b** `g2_convergence` — best-so-far simulated makespan / HEFT vs fitness evaluations. **Figure 3**
`g3_improvement_by_class` — paired improvement vs FCFS-EAT and vs best heuristic by workload class and OOD set.

### 7.4 S03 — Adaptive workload-aware scheduling

The primary result is **null** (Table 6): `ADAPTIVE` differed from `SBS` (HEFT) on only 18 of 360 in-distribution
instances, all in the heterogeneous class where the tree chose MINMIN, and was better on 6 and worse on 12; gap closed
−0.03 (95% CI −0.30 to 0.19). H3 is **not supported**. The reason is structural: HEFT was the best heuristic on 71% of
training instances and within 0.48% of the per-instance oracle on `test_id`, so even a perfect selector over these six
heuristics could gain at most 0.45% (`TRY-ALL` vs `SBS`). H3b is trivially satisfied (decision ~0.15 ms, total call
0.5 ms vs 2.5 ms for `TRY-ALL`) but moot, since there is no quality gain to buy. The only methods that improved on
`SBS` spent more scheduling time: running the tree's top two picks (+0.28%), all six (+0.45%), or always calling GA
(+0.87%).

On unseen workloads (`test_ood`), the novelty guard fell back to SBS on 66% of instances (all n = 400 and 19 of 20
fork-join instances), and on the rest the tree also chose HEFT, so `ADAPTIVE` equalled `SBS` on all 90. Fixed
policies' weaknesses grew out of distribution (e.g. MINMIN mean regret 63% on `ood_cv`; Figure 6), which is where a
selector *could* matter, but HEFT was not among the weak ones.

**Contingency extension (secondary).** A predeclared rule (SBS–VBS gap on `val` < 2%; observed 0.66%) added a
1,000-evaluation GA as a seventh option, with a validation-chosen margin θ = 2%. `ADAPTIVE-GA` improved on `SBS` by
0.10% on `test_id` (gap-closed CI −0.20–0.66, includes 0) and not at all on `test_ood`, at 5–28× HEFT's mean time;
always-`GA-1000` improved by 0.87% at 155–282×. These are reported separately from the primary method.

*Figures (S03, campaign `20261017T083329Z-s03_final-b8e5be9a`):* **Figure 4** `g7_feature_vs_policy` — workload
features (`het_machine`, `work_skew`) vs selected policy, with tree thresholds. **Figure 5** `g8_adaptive_vs_fixed`
— simulated makespan / LB by policy and measured time per call. **Figure 6** `g9_regret_heatmap` — mean regret by
workload class / OOD set × policy, worst class marked (robustness across workloads).

### 7.5 S02 — Reinforcement-learning scheduling

All three training seeds learned on validation data (each beat its own untrained network with a CI below 0 and beat
FCFS-EAT), in about 16 minutes and 48,000 episodes each, without the predeclared behaviour-cloning fallback (Figure
7). On held-out `test_id`, RL improved on the conventional heuristic by about 18% (ρ vs FCFS-EAT 0.822, CI
0.802–0.841) but **trailed HEFT by 0.97%** (Table 6). This is the case where statistical and practical conclusions
must be kept apart: the difference from HEFT is statistically significant (p = 6.8e-6; RL worse on 226 of 360), and
the predeclared practical verdict is "**matches**", because the whole CI (1.0034–1.0160) lies inside the ±2%
equivalence band fixed before testing. It does *not* lie below 1, so "improves" is not met. H2 is supported in its
"matches" form only, and seed-dependently: seeds 0 and 1 have CIs including 1 (ρ 0.999 and 1.002), seed 2 is 2.8%
worse.

Patterns (Figure 9): RL beat HEFT with 2 processors (ρ 0.973) and on the heterogeneous class (0.984), and lost as `m`
grew (1.039 at m = 8). Out of distribution it generalised (Δρ upper CI ≤ 0.02 and still beating FCFS) to larger DAGs
(`ood_size`, ρ 0.983) and higher work variability (`ood_cv`), but not to 16 processors (`ood_procs`, 1.034) or
fork-join structure (`ood_struct`, 1.038), which partly supports H2b. Removing the HEFT-like features cost 3.7 points
of ρ for the same seed: the policy leans on HEFT's own quantities. Inference cost ~50–140 µs per decision, 12–18×
HEFT's scheduling time, plus one-off training.

*Figures (S02, campaign `20261017T115054Z-s02_final-898ee9e1`):* **Figure 7** `g4_training_curves` — training
reward (−Cmax/LB) and validation ρ vs updates, 3 seeds + ablation. **Figure 8** `g5_makespan_by_method` — simulated
makespan / LB by method, `test_id` and `test_ood`. **Figure 9** `g6_rho_by_group` — ρ = Cmax_RL / Cmax_HEFT by class
and OOD set (generalization performance).

### 7.6 Scalability

All values in this subsection are simulated makespans on `test_id` unless noted, from `master.csv` and the paired
tables. **Resource count.** Simulated speedup grows with `m` but efficiency falls: HEFT 1.91 / 3.30 / 5.30 speedup and
0.95 / 0.82 / 0.66 efficiency at `m` = 2 / 4 / 8 (GA 1.98 / 3.34 / 5.32; FCFS-EAT 1.67 / 2.79 / 4.12), because the
DAGs' parallelism is limited. The room for improvement over the best heuristic shrinks as `m` grows, and all three
methods follow it: the GA's gain over the best heuristic is 2.59 / 1.04 / 0.35%; the oracle headroom over SBS that S03
could exploit (`TRY-ALL` vs HEFT) is 0.96 / 0.31 / 0.09%; RL's ratio to HEFT worsens from 0.973 to 1.017 and 1.039, and
to 1.034 on the unseen 16-processor set. **Problem size.** HEFT's `Cmax/LB` rises slowly with `n` (1.144 / 1.180 /
1.217 at `n` = 50 / 100 / 200), while the GA's gain over the best heuristic falls (1.98 / 1.08 / 0.91%) and its measured
optimization time rises from 0.25 s to 3.7 s (`n` = 50 → 400, all test instances). RL's ratio to HEFT is 1.014 /
1.010 / 1.005 and 0.983 at the unseen `n` = 400. S03's measured decision time grows from 0.10 to 0.19 ms over
`n` = 50 → 200, and RL inference costs 50–140 µs per decision. So larger DAGs raise the cost of search much faster than
its benefit, and more processors leave every method less to gain over HEFT. Measured on real threads (§7.8),
efficiency falls faster than simulated: HEFT 0.96 / 0.79 / 0.42 at `m` = 2 / 4 / 8 with 1 ms tasks.

### 7.7 Comparative discussion

The three approaches converge on one finding: **on these workloads HEFT sits close to the ceiling of what cheap
methods can reach, and every gain beyond it was bought with scheduling time.** Selection among heuristics had at most
0.45% to gain and recovered none of it; a learned constructive policy reproduced HEFT-level quality within 1% at
~16× its cost; only explicit search (S01) went below HEFT, by ~1–3% depending on the representation, at three orders
of magnitude more time. This agrees with the literature's reasons for HEFT's prominence — good schedules at low
scheduling cost [2] — and qualifies the reported gains of learning and adaptive methods [8]–[10], [13]: those were
obtained with stochastic durations, dynamic clusters, step-level rule switching or different problem classes, none of
which our deterministic, communication-free model contains. The S01 controls also caution against reading seeded-GA
improvements [6] as evidence of evolutionary search specifically: here a hill climber with the same seeds did almost as
well, and a smaller representation did better. Measured execution (§7.8) adds two points: the GA's small advantage
carries over to real threads in aggregate, and once decision time is counted the adaptive methods lose more as tasks
shrink (ADAPTIVE +0.8% end-to-end at 1 ms tasks, +27% at 10 µs; TRY-ALL +10% to ×4.2). That supports H4 in this
measured form, for three task sizes on one host; no general break-even point is claimed.

### 7.8 Measured execution with C++/OpenMP

Figure 10 and Table 8 report the replay; all values are measured wall-clock seconds on the M4 unless marked simulated.
Repetition noise (CV over the 10 runs) was 1.9% median at 1 ms tasks and 3.5% at 10 µs, comparable to the 0.5–2%
differences under test. **M1:** GA schedules ran 1.6% faster than HEFT's (simulated 1.8%), resolvable in aggregate but
a tie within noise on 240 of 360 instances; the advantage matched simulation at `m` = 2 (0.964 vs 0.964) and vanished
at `m` = 8 (0.999). **M2:** ADAPTIVE executed HEFT's schedule on 342 instances; with its Python decision time added it
was 0.8% slower end-to-end. **M3:** the OpenMP task runtime was 19% slower than the static HEFT schedule, and faster on
about half the instances only at `m` = 8. Speedup saturated beyond four threads (HEFT 1.93 / 3.15 / 3.39) because
39–51% of the threads at `m` = 8 (39% at 1 ms tasks) ran more than 1.3× slower than calibrated (consistent with
efficiency cores; inferred from timings, placement not recorded), raising dependency waiting to 19–28% of thread time. With the ≈ 8% serial calibration offset taken out, simulation predicted
the measured time within 3% at `m` ≤ 4 with tasks of 100 µs or more, and underestimated it 1.5–2.4× at `m` = 8.

Table 8 — measured comparisons at 1 ms mean task (primary: M1–M3, Holm) and selected descriptive ratios; ratio =
geometric mean over the 360 instances of per-instance medians (< 1 favours the method); win / tie / loss uses a
per-instance noise band. Source: `results/derived/20261018T015324Z-omp_exec_final-9c4c1f9b/comparisons.csv`.

| Comparison | Measured ratio | 95% CI | Simulated | win / tie / loss | Holm p |
|---|---|---|---|---|---|
| M1 `GA` vs `HEFT` | 0.984 | 0.980 – 0.988 | 0.982 | 115 / 240 / 5 | 2.3e-20 |
| M2 `ADAPTIVE` vs `HEFT`, incl. decision time | 1.008 | 1.006 – 1.011 | 1.000 | 12 / 239 / 109 | 1.2e-18 |
| M3 OpenMP tasks vs static `HEFT` | 1.188 | 1.160 – 1.216 | — | 60 / 66 / 234 | 6.1e-31 |
| `GA-KEYS-EFT` vs `HEFT` | 0.961 | 0.955 – 0.966 | 0.957 | 191 / 159 / 10 | — |
| `RL-S0` vs `HEFT` | 0.999 | 0.991 – 1.006 | 0.997 | 102 / 163 / 95 | — |
| `TRY-ALL` vs `HEFT`, incl. decision time | 1.103 | 1.095 – 1.112 | 0.995 | 2 / 46 / 312 | — |

*Figures (MD, campaign `20261018T015324Z-omp_exec_final-9c4c1f9b`):* **Figure 10** `md1_speedup_vs_threads`,
`md2_simulator_gap` — measured speedup vs threads; measured / predicted time, raw and calibration-adjusted.

## 8. Limitations and threats to validity

- **Simulation and one measured host.** The quality results are simulated makespans (no communication cost, exact
  cost estimates, free dispatch). The replay runs a synthetic compute kernel (no memory traffic, no data on edges;
  `hetero` emulated by iteration counts) on one unpinned Apple M4, so its `m` = 8 results reflect this core mix; raw
  gaps include an ≈ 8% serial calibration offset; M2 adds Python decision times measured in another process; the
  replay's host records at start and end were lost to a driver defect (manifest reconstructed from recomputable
  values, `docs/MD_ACCEPTANCE_REPORT.md` §2). Whether the C++/OpenMP components meet the tooling requirement is
  **pending faculty confirmation**.
- **One synthetic generator.** HEFT's near-dominance may be a property of this generator (no communication, the cost
  model used). Communication-heavy DAGs or real task traces could leave more room for selection and learning.
- **Measurement.** Scheduling times are wall-clock on one laptop; S01 and S03 ran on battery power (84% → 15% during
  S01), so their measured times may differ under mains power. Timing outliers were flagged and kept: S01 130 of 14,850
  rows (0.9%; median 1.35× the group median, maximum 86×), S03 448 of 17,550 (2.6%; median 2.84×, maximum 212×), S02 23
  of 13,500 (0.2%; median 1.81×, maximum 2.4×). In S03 most outliers reflect which policy a run executed, not noise:
  83% of `ADAPTIVE-GA` outliers are runs that called the GA (5% of its runs), and every `RANDOM-SELECT` outlier drew
  MINMIN (17% of its runs). The lower rate in S02 coincides with mains power, but the campaigns run different methods,
  so power is not isolated as the cause. Simulated makespans are unaffected by power state (heuristic re-runs
  reproduce them exactly).
- **Statistics.** S01's analysis population was not predeclared; the S02 population was fixed in the approved plan
  rather than the original methodology. Three RL seeds characterise training variance only roughly. OOD cells have 10–40
  instances (`ood_cv` 10).
- **Design-induced effects.** Seeded methods cannot lose to their seeds; comparisons against seeds are not evidence.
  RL training ended at the predeclared budget while returns were still rising; no hyperparameter tuning was done by
  design.
- **Scope and inputs.** One student covered all three sub-problems — **pending faculty approval**. The S03 objective
  "use findings from Batches 1–3 and 7" is **not met**: those findings were unavailable; features were chosen from those
  batches' topics only, and no findings were invented.
- **Literature.** Full texts were read for [1], [4], [8], [12], [13] and partly for [2], [3], [5], [9]; [6], [7],
  [10], [16] were checked at abstract level and [11], [14], [15] at metadata level.

## 9. Conclusion and future research directions

On a shared, validated simulator with identical held-out workloads: **evolutionary search** reduced simulated
makespan below the best heuristic by a small, consistent margin (1.17%) at ~10³× the scheduling time, with an
equal-budget hill climber nearly as good and a keys-only GA better; **adaptive selection** among six heuristics did not
improve on the best fixed policy (−0.016%, p = 0.78); **reinforcement learning** clearly improved on FCFS (~18%) and
matched HEFT within the predeclared ±2% band while trailing it by a statistically significant 1%. So: yes, AI-based
scheduling improves over a conventional fixed policy; no, it did not improve over a strong fixed policy without paying
substantially more scheduling time. Executed with OpenMP on real threads, the GA's simulated gain held in aggregate
(1.6%) but not per instance or at eight threads, and decision overhead made adaptive selection slower end-to-end.

Future directions:
1. **Communication-aware and stochastic models** — add data-transfer costs and duration noise, where the reviewed RL
   work reports its advantages [9], and re-test whether HEFT's dominance persists.
2. **Heterogeneity-aware execution** — model the host's performance and efficiency cores (or pin threads where the
   OS allows), add memory traffic and data movement to the kernel, and repeat the replay on other machines.
3. **Cheaper search** — keys-only or hybrid representations, and compiled fitness evaluation, to move the GA's
   quality–time trade-off; and S03 selection between a heuristic and a short search, labelled by an explicit time
   budget.
4. **Better RL state** — graph-neural encoders and longer or tuned training (on validation data), with the ablation
   showing how much is learned beyond HEFT's features.
5. **Workload diversity for selection** — workload classes where no single heuristic dominates, and the Batches 1–3 and
   7 findings once available.

## 10. References

[1] Y.-K. Kwok and I. Ahmad, "Static scheduling algorithms for allocating directed task graphs to multiprocessors,"
*ACM Computing Surveys*, vol. 31, pp. 406–471, 1999, doi: 10.1145/344588.344618.

[2] H. Topcuoglu, S. Hariri, and M.-Y. Wu, "Performance-effective and low-complexity task scheduling for heterogeneous
computing," *IEEE Transactions on Parallel and Distributed Systems*, vol. 13, pp. 260–274, 2002, doi:
10.1109/71.993206.

[3] T. D. Braun *et al.*, "A comparison of eleven static heuristics for mapping a class of independent tasks onto
heterogeneous distributed computing systems," *Journal of Parallel and Distributed Computing*, vol. 61, pp. 810–837,
2001, doi: 10.1006/jpdc.2000.1714.

[4] E. Hou, N. Ansari, and H. Ren, "A genetic algorithm for multiprocessor scheduling," *IEEE Transactions on
Parallel and Distributed Systems*, vol. 5, pp. 113–120, 1994, doi: 10.1109/71.265940.

[5] J. C. Bean, "Genetic algorithms and random keys for sequencing and optimization," *ORSA Journal on Computing*,
vol. 6, pp. 154–160, 1994, doi: 10.1287/ijoc.6.2.154.

[6] M. Sulaiman, Z. Halim, M. Lebbah, M. Waqas, and S. Tu, "An evolutionary computing-based efficient hybrid task
scheduling approach for heterogeneous computing environment," *Journal of Grid Computing*, vol. 19, no. 1, Art. 11,
2021, doi: 10.1007/s10723-021-09552-4.

[7] J. Jiang, Z. Sun, R. Lu, L. Pan, and Z. Peng, "Real relative encoding genetic algorithm for workflow scheduling in
heterogeneous distributed computing systems," *IEEE Transactions on Parallel and Distributed Systems*, vol. 36, no. 1,
pp. 1–14, 2025, doi: 10.1109/TPDS.2024.3492210.

[8] H. Mao, M. Schwarzkopf, S. B. Venkatakrishnan, Z. Meng, and M. Alizadeh, "Learning scheduling algorithms for data
processing clusters," in *Proc. ACM SIGCOMM*, 2019, pp. 270–288, doi: 10.1145/3341302.3342080.

[9] N. Grinsztajn, O. Beaumont, E. Jeannot, and P. Preux, "READYS: A reinforcement learning based strategy for
heterogeneous dynamic scheduling," in *Proc. IEEE Int. Conf. Cluster Computing (CLUSTER)*, 2021, pp. 70–81, doi:
10.1109/Cluster48925.2021.00031.

[10] A. Zhadan *et al.*, "Multi-agent reinforcement learning-based adaptive heterogeneous DAG scheduling," *ACM
Transactions on Intelligent Systems and Technology*, vol. 14, no. 5, pp. 1–26, 2023, doi: 10.1145/3610300.

[11] J. R. Rice, "The algorithm selection problem," *Advances in Computers*, vol. 15, pp. 65–118, 1976, doi:
10.1016/S0065-2458(08)60520-3.

[12] P. Kerschke, H. H. Hoos, F. Neumann, and H. Trautmann, "Automated algorithm selection: Survey and perspectives,"
*Evolutionary Computation*, vol. 27, no. 1, pp. 3–45, 2019, doi: 10.1162/evco_a_00242.

[13] A. Uzunoglu, C. Gahm, and A. Tuma, "Machine learning based algorithm selection and genetic algorithms for
serial-batch scheduling," *Computers & Operations Research*, vol. 173, Art. 106827, 2025, doi:
10.1016/j.cor.2024.106827.

[14] S. Holm, "A simple sequentially rejective multiple test procedure," *Scandinavian Journal of Statistics*, vol. 6,
pp. 65–70, 1979, doi: 10.2307/4615733.

[15] F. Wilcoxon, "Individual comparisons by ranking methods," *Biometrics Bulletin*, vol. 1, no. 6, p. 80, 1945,
doi: 10.2307/3001968.

[16] B. Efron and R. Tibshirani, "Bootstrap methods for standard errors, confidence intervals, and other measures of
statistical accuracy," *Statistical Science*, vol. 1, no. 1, pp. 54–75, 1986, doi: 10.1214/ss/1177013815.

