# C++ / OpenMP extension — implementation plan (PLAN ONLY, awaiting approval)

Written 2026-10-17. Nothing in this plan has been implemented or run. No existing file, campaign, model or provenance
record was changed while writing it.

Labels: **[FACT]** checked in the manual, repo or machine · **[DECISION]** proposed design choice · **[RISK]**.

---

## 0. Starting point

| Item | Finding |
|---|---|
| Requirement | [FACT] Confirmed by the student 2026-10-17: C++ and OpenMP are required. |
| Manual, CS 15 tools (p. 15) | [FACT] S01 "Python + DEAP or equivalent; **C++ workload simulator**". S02 "Python + PyTorch". S03 "Python/C++ + **OpenMP**/CUDA as appropriate". |
| Manual, common requirements | [FACT] "execution time, speedup, efficiency, and scalability whenever applicable"; overheads separated "where possible"; "Repeat timing experiments sufficiently"; record "compiler/runtime versions" and "compiler optimization flags and runtime configuration"; "Do not report a speedup without identifying the baseline". |
| Current design | [FACT] One Python simulator (`model.ScheduleBuilder`); makespan in `sim_tu` (simulated); scheduling time in seconds (measured, Python, M4). Deviations D1 (no C++ simulator) and D2 (no OpenMP) in `ARCHITECTURE.md` §4. |
| Accepted campaigns | [FACT] S01 `20261017T044734Z-s01_final-430d8a10`, S03 `20261017T083329Z-s03_final-b8e5be9a`, S02 `20261017T115054Z-s02_final-898ee9e1`; each has 450 instances (360 `test_id`: 4 classes × n ∈ {50, 100, 200} × m ∈ {2, 4, 8}; 90 `test_ood`). |
| Raw precision | [FACT] `runs.csv` stores `makespan_sim` with 17 significant digits (e.g. `2524.213432095829`), so a cross-language comparison can be exact. |
| Re-derivation cost | [FACT] Total timed GA scheduling time in S01 is 0.37 h for 1,350 runs (450 instances × 3 seeds). Median per run: 0.25 s (n = 50) to 3.8 s (n = 400). RL inference: 2.5–50 ms. |
| Toolchain (no installs needed) | [FACT] Homebrew GCC 15.2.0 (`g++-15 -fopenmp`) and Apple clang 21 + Homebrew libomp 21.1.8 both compile and run an OpenMP test program (8 threads). No CMake; `make` is available. No CUDA (Apple M4). |
| Hardware | [FACT] Apple M4: 4 performance + 6 efficiency cores, 16 GB. macOS has no thread-to-core pinning (`OMP_PROC_BIND` has no effect on core type). |

---

## 1. Requirement → sub-problem mapping

| Sub-problem | Manual tool | What will satisfy it | Why it is technically relevant |
|---|---|---|---|
| **S01** Evolutionary | C++ workload simulator | **C1 `schedsim`**: a C++ implementation of the same DAG/cost/list-scheduling model. It evaluates any (placement order, processor assignment) schedule and independently computes the six baseline heuristics. Every accepted S01 makespan is re-evaluated in C++. | The S01 research question is about makespan. The C++ simulator becomes an independent second implementation of the quantity the conclusions rest on. |
| **S01** (measured) | — | **C2 `ompexec`** executes the GA and heuristic schedules on real threads. | Tests whether GA's simulated +1.17% over the best heuristic survives real execution, or falls below measurement resolution. |
| **S02** RL | Python + PyTorch | Training and inference stay in Python/PyTorch (as the manual lists). RL schedules are evaluated by C1 and executed by C2. | Gives measured makespan and utilization for RL vs HEFT; no reimplementation of the policy is needed. |
| **S03** Adaptive | Python/C++ + OpenMP | **C2 `ompexec`**: OpenMP execution of the fixed policies, the adaptive selector's choice, `TRY-ALL`, and an **OpenMP dynamic task runtime** as an additional fixed policy. | S03's manual metrics are makespan, **speedup** and **decision overhead**. Both decision time and execution time are then in measured seconds on the same machine. That makes the end-to-end comparison "adaptive vs fixed" real, replacing the hypothetical break-even `τ*`. |

[DECISION] If the faculty expects C++/OpenMP inside **each** sub-problem's own method (for example a C++ GA), only
S01 would need more: the optional C3 below. Confirm this with the faculty; the plan does not assume it.

**Explicitly rejected** (they would satisfy the letter, not the requirement):
- OpenMP over campaign instances, CSV writing or analysis: bookkeeping, unrelated to the research questions.
- OpenMP-parallel GA fitness evaluation as the *only* OpenMP use: it speeds up the optimizer but says nothing about
  the schedules' execution. It is kept only as optional extension C3.
- Porting GA/RL/selector to C++: changes the accepted methods and their timing. That would require new campaigns.

---

## 2. Components

### C1 — `cpp/schedsim` (C++17, no OpenMP): the workload simulator

| Function | Semantics, matched to the Python core |
|---|---|
| `eval --mode append\|insert` | Replays a placement order with an assignment through a C++ `ScheduleBuilder` identical to `model.py`. Append: `start = max(avail[p], ready_time[t])`. Insert: linear scan of the sorted busy intervals with the same comparisons (`s + c <= a`; `b > s`). |
| `validate` | Independent feasibility check from (proc, start, finish) only, with the same tolerance `1e-9·max(1, |x|)` as `model._tol`. |
| `heuristic NAME --mode` | Independent ports of `FCFS-EAT`, `FCFS-EFT`, `SPT-EFT`, `LPT-EFT`, `HEFT`, `MINMIN`, with the same tie rules (lowest task id, then lowest processor id; MINMIN by (EFT, t, p)). |
| `bounds` | `serial_best`, `cp_min`, `work_lb`, `lower_bound`, as in `model.bounds`. |

Semantic traps that must be matched or explicitly documented (never assumed equal):
- **Mean cost.** `upward_rank` and SPT/LPT use `numpy.mean(axis=1)`, which uses pairwise summation in blocks of 8. A
  naive C++ left-to-right sum can differ in the last bit, which can flip a priority tie. Plan: replicate numpy's
  summation order for m ≤ 16, and test it bit-for-bit. If any instance still differs, it is listed, not hidden.
- **Floating-point contraction.** GCC on arm64 contracts `a*b+c` into FMA by default. Build C1 with
  `-ffp-contract=off -fno-fast-math` so `start + cost` and `max` are the same IEEE operations as in Python.
- **Exact I/O.** All doubles are exchanged as C99 hex floats (`%a` / Python `float.hex()`), so there is no decimal
  rounding.

### C2 — `cpp/ompexec` (C++17 + OpenMP): measured execution

Each task runs a **work-calibrated compute kernel**: a dependent floating-point chain of `round(cost[t, p] · k)`
iterations, writing to a per-task sink so it cannot be optimized away. Here `k` (iterations per `sim_tu`) is
calibrated once per granularity level. The kernel does fixed **work**, not "spin until a time", so measured time
includes real core-speed differences and contention.

| Mode (`Parallel_Model`) | What is parallelized | Synchronization |
|---|---|---|
| `SERIAL` | Nothing: all tasks in topological order on one thread. This is the **speedup baseline T₁**. | none |
| `OMP-STATIC` | `#pragma omp parallel num_threads(m)`. Thread `p` executes processor `p`'s task list from the given schedule (HEFT, GA, RL, ADAPTIVE, …), in its start-time order. Work is `cost[t, p]`. | Per-task completion flags (`std::atomic`, release/acquire). A thread waits until every predecessor of its next task is done. |
| `OMP-TASKS` | The DAG executed by the OpenMP task runtime. Root tasks are created first. When a task finishes, it atomically decrements each successor's predecessor counter and creates the successor as an `omp task` when the counter reaches 0. Work is `cost[t, omp_get_thread_num()]`. | The OpenMP runtime's queues; `taskwait` at the end. |

`OMP-TASKS` is a fixed, heterogeneity-blind dynamic policy, the conventional runtime baseline. It needs no
schedule from Python.

Measured per run (all seconds, `omp_get_wtime`):
- `wall_time_s`: parallel-region entry to exit;
- per task: `start`, `end`, `thread`, from which the following are computed:
  - computation (Σ kernel time);
  - synchronization / dependency wait (thread time spent waiting on predecessor flags);
  - dispatch overhead (`OMP-TASKS`: time from the last predecessor's end to the task's start, minus waiting);
  - idle time and load imbalance per thread;
  - measured utilization.
- Team start-up overhead: an empty parallel region timed separately.
- `peak_rss_kb`.
- Communication time stays `NA`, with the reason recorded: shared memory, and no data is passed along edges in the model.

Granularity levels [DECISION]: 10, 1 and 0.1 µs per `sim_tu`. The mean task (100 `sim_tu`) is then 1 ms, 100 µs or
10 µs. This is the dimension in which scheduling and runtime overhead become visible. It also links to the manual's
granularity question.

### C3 — optional, only if the faculty requires a C++ component inside S01's method

A C++ GA-decode benchmark: fitness evaluations per second, sequential vs `omp parallel for` over the population, for
the same chromosomes. It gives an "optimization time vs threads" curve. It does **not** replace the accepted Python GA
or its timings. Not in the minimum plan.

---

## 3. Architecture and data flow

```
accepted, unchanged:  workloads.py ─► Instance        ga.py / rl.py / adaptive.py / heuristics.py (Python)
                                         │                               │
new  schedlab/interop.py  (python -m schedlab.interop …)                 │
   export-instances ─► out/instances/<id>.txt   (n, m, edges, cost as hex floats, instance_hash)
   rederive         ─► out/schedules/<id>__<method>__<seed>.txt  (proc, placement order, Python start/finish)
                         └─ asserts makespan == accepted runs.csv makespan_sim (exact) before writing
                                         │
new  cpp/ (Makefile; g++-15 -O2 -std=c++17)
   schedsim eval|validate|heuristic|bounds ─► start/finish/makespan (hex floats)
   ompexec  serial|static|tasks --us-per-tu g --reps r --warmup w ─► per-run CSV + per-task trace CSV
                                         │
new  results/raw/<id>-cpp_xval/   cross-language comparison table + manifest
new  results/raw/<id>-omp_exec/   runs.csv (wall-clock, seconds), task_trace.csv, calibration.csv, manifest.json
                                  (binary sha256, compiler version, flags, OMP_* env, host, power source)
                                         │
new  schedlab/exec_analysis.py ─► results/derived/<omp campaign>/master.csv (manual's 19 columns:
        Execution_Time = wall_time_s, Time_Unit = s, Parallel_Model = SERIAL|OMP-STATIC|OMP-TASKS,
        Threads = m, Hardware = Apple M4, Speedup = T1/Tp, Efficiency = Speedup/m) + tables + figures
```

[DECISION] **No existing module is edited.** `__main__.py`, `runner.py` and `analysis.py` stay byte-identical. The
new commands live in `schedlab/interop.py` and `schedlab/exec_analysis.py`. So the S02 post-processing source hashes
still match the tree, and no accepted derived file can be regenerated by accident. File exchange is used instead of
a Python binding: no new dependency and no build step inside Python.

New files only: `cpp/{Makefile, model.hpp, schedsim.cpp, heuristics.hpp, ompexec.cpp, kernel.hpp, io.hpp}`,
`schedlab/interop.py`, `schedlab/exec_analysis.py`, `configs/cpp_xval.toml`, `configs/omp_exec.toml`,
`tests/test_cpp_interop.py`, `tests/test_ompexec.py`. Documentation updates (README, DATA_SCHEMA, report) come later.

---

## 4. Correctness and cross-language validation

| # | Test | Pass condition |
|---|---|---|
| V1 | Format round-trip: Python export → C++ parse → C++ dump → Python | n, m, edge set, every cost bit-identical; recomputed `instance_hash` equal |
| V2 | Append replay: 500 seeded instances × random orders and assignments, plus GA chromosomes | C++ `start`/`finish` arrays equal Python's **bit for bit** |
| V3 | Insertion replay: same, with `insert=True` | bit-identical |
| V4 | Six heuristics × both modes × all 450 campaign instances, computed independently in C++ | proc/start/finish arrays identical; makespan equals every accepted `runs.csv` heuristic row exactly. Any mismatch is reported with its cause (e.g. a tie flipped by mean summation) |
| V5 | Validator agreement: 1,000 mutated schedules (precedence violation, overlap, wrong duration, wrong processor, missing task) | C++ and Python verdicts agree on every case; valid schedules accepted |
| V6 | Re-derived accepted schedules (GA, GA-KEYS-EFT and the other S01 methods with seeds; RL-S0–S2; ADAPTIVE from the saved selector, checked against `decisions.csv`) | Python makespan equals accepted `makespan_sim` exactly; C++ evaluation equals it too. Any non-reproducible row is reported, never replaced |
| V7 | Executor ordering (every `ompexec` run) | Every task's measured start ≥ all predecessors' measured ends; each task ran exactly once; `OMP-STATIC` ran each task on its scheduled thread in schedule order; kernel checksums identical across modes |
| V8 | Thread count | `omp_get_num_threads() == m` inside the region; recorded per run |
| V9 | Kernel calibration | Time linear in iterations (R² ≥ 0.99 per granularity); repeat CV reported; P-core vs E-core speed ratio estimated from per-thread task durations |
| V10 | Regression | The existing 238 tests pass; the three `verify_campaign.py` scripts still report 0 problems; `analyze` on each accepted campaign, written to a scratch directory, gives byte-identical derived CSVs |

The two implementations are called equivalent only for what V1–V6 show, and only on the instances tested.

---

## 5. Minimum new experiments

All runs are sequential (one measurement at a time), on mains power, with no other heavy processes. Seeds and instances
are the accepted ones; no new instances are generated.

| ID | Purpose | Design | Est. compute |
|---|---|---|---|
| X1 | Cross-language reproduction (V4, V6) | All 450 instances; 6 heuristics (both modes); re-derive S01's five seeded methods × 3 seeds, RL-S0–S2 + RL-NOHEFTFEAT, ADAPTIVE / ADAPTIVE-TOP2 / TRY-ALL | GA-family re-derivation ≈ 5 × 0.37 h ≈ 1.9 h (background); everything else < 10 min |
| X2 | Calibration | Kernel at 3 granularities × threads {1, 2, 4, 8} × 30 reps; empty-region overhead | ≈ 5 min |
| X3 | **Measured execution (main)** | 360 `test_id` instances (all 4 classes × n ∈ {50, 100, 200} × m ∈ {2, 4, 8}, the instances' own m) × 3 granularities × methods {`SERIAL`, `FCFS-EAT`, `HEFT` (= SBS), `GA` s0–s2, `GA-KEYS-EFT` s0–s2, `RL-S0`–`S2`, `ADAPTIVE`, `TRY-ALL`'s chosen schedule, `OMP-TASKS`} × 10 timed reps after 2 warm-ups; method order randomized per instance and rep | Coarse level ≈ 37 min (mean parallel run ≈ 29 ms, T₁ ≈ 117 ms); medium ≈ 4 min; fine < 1 min → **≈ 45–60 min** |

Not in the minimum: `test_ood` (its m = 16 exceeds the 10 cores, so it would oversubscribe; it can be run later as a
labelled set), GA-1000 / ADAPTIVE-GA, C3.

Metrics: `Execution_Time` (wall, s); `Speedup = T₁ / T_p`, with the baseline named (`SERIAL`, same kernels);
`Efficiency = Speedup / m`; computation, synchronization, dispatch and idle time; load imbalance; measured
utilization; **simulator gap** = measured / (simulated makespan × µs per `sim_tu`); end-to-end time = decision time +
execution time. For ADAPTIVE, TRY-ALL, GA and RL the decision time is the accepted campaign's measured
`scheduling_time_s`, labelled as such.

Predeclared measured comparisons (Holm across the three; paired Wilcoxon; percentile-bootstrap CIs, as in the
existing analysis):
- **M1 (S01):** measured GA / HEFT execution-time ratio, per granularity. Does the sign agree with the simulated
  ratio, and is it resolvable above run-to-run noise?
- **M2 (S03):** end-to-end ADAPTIVE vs SBS (HEFT) and vs TRY-ALL, per granularity. This replaces the hypothetical
  `τ*` with measured values.
- **M3 (S03 speedup):** OMP-STATIC (HEFT schedule) vs OMP-TASKS speedup over T₁, for m ∈ {2, 4, 8}.

Descriptive (no test): RL / HEFT measured; simulator gap per method and class; Kendall's τ between the simulated and
the measured method ranking per instance.

---

## 6. Runtime estimate

| Work | Estimate |
|---|---|
| C1 + heuristic ports + I/O | ≈ 0.5 day |
| C2 executor + calibration | ≈ 0.5 day |
| `interop.py`, `exec_analysis.py`, tests V1–V10 | ≈ 0.5–1 day |
| X1 + X2 + X3 compute | ≈ 3 h total (≈ 2 h of it background GA re-derivation) |
| Analysis, figures, report and note revision, Word re-measure | ≈ 1 day |
| **Total** | ≈ 3–3.5 working days with review gates. Fits before 30 October 2026, but not with large slips. |

Proposed milestones, each stopping for review:
- **M-A:** C1 + V1–V5.
- **M-B:** re-derivation + V6 (X1).
- **M-C:** C2 + V7–V9 + X2 + a pilot of X3 on 24 instances.
- **M-D:** full X3 + analysis.
- **M-E:** documents.

---

## 7. Report, note and figure changes

| Item | Change |
|---|---|
| Abstract | One sentence on the C++/OpenMP measured layer and its main result; stays 150–200 words |
| §5 Architecture | Short paragraph and table row: C++ simulator, OpenMP executor, file interface |
| §6 Methodology | "Measured execution" paragraph: kernel, granularity, modes, T₁ baseline, repetitions, compiler `g++-15 -O2 -std=c++17 -fopenmp` (and `-ffp-contract=off` for C1), OpenMP runtime version, `OMP_*` settings, no core pinning |
| New §7.8 "Measured execution on the M4" | **Figure 10** measured vs simulated makespan (per method, coloured by granularity); **Figure 11** speedup and efficiency vs threads (OMP-STATIC/HEFT, GA, ADAPTIVE, OMP-TASKS; baseline T₁); **Figure 12** end-to-end time (decision + execution) vs granularity, with an overhead breakdown; **Table 9** cross-language validation summary; **Table 10** M1–M3 results with CIs |
| §7.2 / §7.4 | S03 "speedup" now also reported as measured; simulated speedup kept and labelled |
| §8 Limitations | Emulated heterogeneity; P/E cores without pinning; synthetic kernel (compute-bound, no memory traffic, no data on edges); noise floor vs ~1% effects |
| Technical note | +½ page (now 2 pages, limit 3) |
| Literature | Candidate OpenMP-tasking source (e.g. Ayguadé *et al.*, "The design of OpenMP tasks", IEEE TPDS 2009). Cited **only after** its record is verified |
| DATA_SCHEMA, README | New columns and units; exact build and run commands |
| Audit/checklist | The "Python-only tooling" blocker becomes "C++/OpenMP added; faculty to confirm sufficiency" |

[RISK] The report is already exactly 12 pages. Room must be freed. Proposed: move Appendix A (Traceability, Table 8)
to a companion file, like the literature review, and merge Figures 2a/2b into one panel, plus tighter text in
§7.3–7.5. The page count is re-measured in Word afterwards. Your call (§10).

---

## 8. Status of the existing Python-only results

| Result | Status after the extension |
|---|---|
| All simulated makespan results (S01, S02, S03 headline numbers, Tables 5–7, Figures 1–9) | **Remain primary evidence** for the three research questions, which are about schedule quality. If X1 passes, they are additionally reproduced by the C++ simulator, which closes the S01 "C++ workload simulator" gap. **No campaign rerun is needed.** |
| Scheduling / optimization / inference / decision times (Python, M4) | Remain as measured, labelled "Python implementation". Not re-measured. |
| Simulated speedup / efficiency (`serial_best / makespan`) | Kept, but labelled *simulated*; the manual's speedup metric for S03 will come from X3 (measured, baseline T₁). |
| Hypothetical break-even `τ*` (H4) | Superseded by M2. Kept only as supplementary, or dropped to save space. |
| Results that **must** be reproduced through C++/OpenMP | (a) S01 makespans: through C1 (X1). (b) S03 speedup and decision-overhead trade-off: through C2 (X3). Nothing else. |

Rule throughout: simulated makespan (`sim_tu`) and measured wall time (s) stay in separate columns and figures. The
existing campaigns are never described as having measured hardware speedup.

---

## 9. Risks and limitations

| Risk | Mitigation / how it is reported |
|---|---|
| Run-to-run noise exceeds the 1% effects (GA +1.17%, RL ≈ 1%, ADAPTIVE −0.016%) | Noise floor measured in X2. A comparison with a CI spanning 1 is reported as "not resolvable on this hardware", not as agreement or contradiction |
| P/E heterogeneity, no pinning: with m = 8, some threads run on E-cores, so homogeneous schedules meet heterogeneous hardware | Measured per-thread slowdown reported; this is itself a simulator-gap finding. Not hidden or tuned away |
| `hetero` classes are emulated through iteration counts, not real accelerators | Stated as emulation in methods and limitations; no CPU–GPU claim |
| C++ heuristic differs from Python by a tie | Exact numpy summation replicated; residual mismatches listed per instance |
| A re-derived GA/RL schedule does not reproduce the accepted makespan | Reported; those rows are excluded from X3 with the count stated; accepted data is not touched |
| Compiler removes the kernel or contracts FP | Sink and checksum (V7); `-ffp-contract=off` for C1 |
| Thermal or power drift | Randomized order, warm-ups, power source and time recorded; per-rep rows kept |
| 12-page limit | §7 trimming decision (yours) |
| Faculty wants C++ inside each sub-problem's method | Optional C3 for S01; S02 stays PyTorch per the manual |
| Timeline | Milestones M-A…M-E; X3 can be cut to 2 granularity levels if needed |

---

## 10. Acceptance criteria

1. V1–V5 pass; V4 heuristic makespans equal the accepted `runs.csv` values on all 450 instances. Otherwise every
   mismatch is explained.
2. V6: ≥ 99% of re-derived accepted schedules reproduce exactly; every exception is listed.
3. V7–V9 pass on every X3 run; calibration R² ≥ 0.99.
4. X3 complete: 360 instances × 3 granularities × the listed methods × 10 reps, with no invalid run, or failures logged.
5. Every new speedup names T₁; simulated and measured quantities never share a column or an axis.
6. V10: accepted campaigns, models, manifests, provenance and derived outputs unchanged (sha256 check before and after).
7. Report ≤ 12 pages, note ≤ 3, re-measured in Word; DRAFT labels and identity placeholders kept.

## 11. Decisions needed before implementation

1. Approve C1 + C2 as the minimum (C3 only on a faculty request)?
2. Granularity levels 10 / 1 / 0.1 µs per `sim_tu`?
3. Compiler: GCC 15 (`libgomp`) as primary, or Apple clang + libomp?
4. Page budget: move Appendix A to a companion file and merge Figures 2a/2b?
5. Re-derive all five S01 seeded methods (≈ 1.9 h background), or only GA and GA-KEYS-EFT (≈ 0.75 h)?
