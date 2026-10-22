# M-D — measured execution replay: locked design and analysis plan

Written 2026-10-18 **before launch**. Config: `configs/omp_exec_final.toml` (its sha256 is recorded in the campaign
manifest; the file hashes in its `[lock]` table are checked by the driver at start). Nothing below may be changed
after launch. Deviations, if any, are reported as deviations.

## 1. What is measured

The accepted schedules (re-derived exactly in M-B; `results/raw/20261017T162329Z-rederive-21e353a7`) plus FCFS-EAT
and HEFT. Each is executed on real threads by `cpp/build/ompexec` (M-C) with work-calibrated kernels:

- **Instances:** the 360 paired `test_id` instances (4 classes × n ∈ {50, 100, 200} × m ∈ {2, 4, 8} × 10).
- **Granularities:** 10, 1 and 0.1 µs per `sim_tu`, i.e. a mean task of 1 ms, 100 µs or 10 µs. Iterations per
  `sim_tu` come from the calibration `results/raw/20261017T172332Z-omp_calibration-422f7f41`.
- **Methods:** 15. `SERIAL` (T₁); 13 static schedules (`FCFS-EAT`, `HEFT`, `GA` s0–s2, `GA-KEYS-EFT` s0–s2, `RL-S0`–`S2`,
  `ADAPTIVE`, `TRY-ALL`); and `TASKS` (the OpenMP task runtime).
- **Repetitions:** 2 warm-up passes, then 10 timed passes. Method order is permuted per pass, granularity order per
  instance, and instance order once, all with fixed seeds (config). This spreads drift over all methods.
- **Expected rows:** 194,400 in total, of which 162,000 timed and 16,200 verified/traced (rep 0); 1,890,000 trace rows.

## 2. Metrics and units (kept separate; never added across units)

| Metric | Unit | Definition |
|---|---|---|
| `sim_makespan_tu` | sim_tu | Simulated makespan of the schedule (echoed; computed by the C++ simulator) |
| `wall_s` | s | Measured time from parallel-region entry to exit, including fork/join |
| `compute_s` | s | Σ measured kernel time over tasks |
| `dep_wait_s` (static) | s | Σ time a thread spun waiting for predecessors on other threads |
| `ready_queue_s` (tasks) | s | Σ (task start − time its last predecessor finished). **Includes waiting for a free thread (contention) as well as runtime dispatch; it is not pure scheduler overhead.** |
| `idle_s` | s | Σ over threads (wall − busy) |
| `imbalance` | — | max thread busy / mean thread busy |
| Fork/join cost | s | From calibration only (near-empty region), reported separately |
| Python scheduling time | s | From the accepted campaigns (`scheduling_time_s`), labelled as Python on this host; never re-measured here |

All per-instance statistics use the **median of the 10 timed reps** (`T`), with the **CV across reps** reported
for variation.

## 3. Derived quantities (formulas fixed now)

- **Speedup:** `S = T₁ / T_p`, with `T₁` = the median `SERIAL` time on the same instance and granularity (all tasks
  on one thread, on the processor with the smallest total cost). **Efficiency:** `E = S / m`.
- **Raw simulator gap:** `G_raw = T / (C_sim · u)`, with `u` = µs per `sim_tu` (nominal, from calibration).
  Reported as measured. The ≈ 8 % serial offset seen in the pilot stays in `G_raw` and is listed as a limitation.
- **Calibration-adjusted gap:** `G_adj = T / (C_sim · û)`, with `û = T₁ / serial_best_sim` the *measured* seconds per
  `sim_tu` of a single thread on that instance and granularity. Equivalently `G_adj = G_raw / G_raw(SERIAL)`.
  - Assumption: a kernel iteration costs the same on a lone thread as on a parallel thread.
  - Departures from that (cluster clock drop under load, efficiency cores, contention, fork/join, dependency
    waits) therefore remain in `G_adj`. That is what it is meant to isolate.
  - It is a second view, not a correction: `G_raw` is never replaced.
- **Paired method ratio:** `R = T_A / T_B` per instance (medians); for GA and GA-KEYS-EFT, `T_A` is the mean of the
  three seeds' medians. The simulated counterpart `R_sim = C_sim,A / C_sim,B` is reported next to it.

## 4. Predeclared comparisons

Primary level: 10 µs/`sim_tu` (1 ms tasks, lowest noise in the pilot). Holm correction across the three. The other
two granularities are reported as secondary, with no new tests added.

| ID | Comparison | Simulated expectation (accepted campaigns) |
|---|---|---|
| **M1** | `GA` vs `HEFT`, measured `R` | GA better by ≈ 0.5–1 % |
| **M2** | `ADAPTIVE` vs `HEFT` (= SBS), end-to-end: Python decision/scheduling time (accepted campaign median, per instance) + measured execution | ≈ equal |
| **M3** | `TASKS` (OpenMP runtime) vs static `HEFT`, measured `R` | no simulated counterpart |

Per comparison:
- geometric mean of `R` over the 360 instances, with a 95 % percentile bootstrap CI (10,000 resamples of
  instances, seed 20261018);
- Wilcoxon signed-rank test on `log R`.

**Aggregate resolvability:** an effect is "resolvable in aggregate" if the CI excludes 1 *and* the Holm-adjusted
p < 0.05. Otherwise it is "not resolved".

**Per-instance resolvability (descriptive):**
- noise band `b = 2·sqrt((cv_A² + cv_B²)/10)` on `log R`, using each method's CV across reps on that instance;
- win if `log R < −b`, loss if `log R > b`, tie otherwise;
- win/tie/loss counts are reported as descriptive evidence only, never as proof of superiority.

**Sign agreement** between `R` and `R_sim` is reported for M1 and for RL-S0/HEFT. A simulated improvement is never
reported as a real improvement unless the measured comparison resolves it.

## 5. Descriptive analyses (no tests)

- **Distributions:** per-rep CV by method, granularity and m.
- **Speedup and efficiency:** by method × m × granularity.
- **Simulator gap:** `G_raw` and `G_adj` by method × m × granularity.
- **Thread-count effect:** per-thread slowdown from traces (rep 0) = measured task time ÷ (iterations ÷ calibrated
  iterations per µs), by thread index and m.
- **Overhead decomposition:** dep-wait, idle and ready-queue (labelled as above) share of thread time.
- **Rank agreement:** Kendall τ between simulated and measured ranking of the 13 static methods, per instance.
- **Break-even:** no real-world break-even claim. M2 reports the measured end-to-end time at the three granularities
  only.

## 6. Acceptance criteria

1. **Row counts:** 194,400 rows / 162,000 timed / 16,200 verified; all 360 instances × 3 granularities × 15 methods
   present; no duplicate (instance, granularity, mode, label, rep, warmup) key.
2. **Per-run integrity:** every row has `order_ok`, `thread_ok` and `once_ok` = 1, `threads_seen = threads`, and
   `verify_ok` = 1 where verified.
3. **Trace integrity** (Python, from the trace, rep 0):
   - each task appears exactly once per (instance, granularity, method);
   - start ≥ every predecessor's end;
   - static tasks on their scheduled thread;
   - iterations = `llround(cost·K)`.
4. **Inputs and binaries unchanged:** the locked hashes match before the run, and after it as well. Accepted
   campaigns, models, manifests and provenance are byte-identical to the pre-M-A baseline.
5. **Power:** mains power at launch, as recorded by `pmset`; recorded again at the end.
6. **Tests:** the full suite passes after the run.
7. **Reproducibility:** tables and figures regenerate byte-identically from the saved CSVs into a scratch directory.

If 1–3 fail, or the run is incomplete: stop and report. No automatic rerun, no partial replacement.

## 7. Frozen analysis code

`schedlab/omp_analysis.py` (sha256 `26a1f7f60e1bc33d697e097e59e932c65415dd156a83daf63109f79a9045a28e`) implements §2–§6 and the trace check (criterion 3). It was developed on
the M-C pilot data only (into a scratch directory) and frozen before launch. Pilot values are not results.
