# M-D acceptance report — measured C++/OpenMP execution replay

**Status:** completed 2026-10-18; awaiting review. One defect (missing manifest, §2) was handled as you instructed.

| | |
|---|---|
| Campaign | `results/raw/20261018T015324Z-omp_exec_final-9c4c1f9b` (sealed, read-only) |
| Locked config | `configs/omp_exec_final.toml` (sha256 `fdceb800…88cb7f`) |
| Analysis plan (written before launch) | `docs/MD_ANALYSIS_PLAN.md` (sha256 `574d38d5…4a75c8`) |
| Analysis code (frozen before launch) | `schedlab/omp_analysis.py` (sha256 `26a1f7f6…45a28e`, unchanged) |
| Derived tables | `results/derived/20261018T015324Z-omp_exec_final-9c4c1f9b/` |
| Figures | `results/figures/20261018T015324Z-omp_exec_final-9c4c1f9b/md{1,2,3}_*.{pdf,svg,csv}` |

All times are **measured wall-clock seconds** on an Apple M4 (4 performance + 6 efficiency cores, macOS, GCC 15.2
`libgomp`), unless labelled `sim_tu` (simulated). Pilot observations from M-C are not used as results here.

## 1. Run

- **Launch and power.** Launched once, on mains power. The operator's `pmset` read "Now drawing from 'AC Power'"
  immediately before launch, and the driver's own AC check passed (it refuses to start otherwise). The driver's exact
  power strings at start and end were lost (§2). Power was AC again when checked after the run.
- **Lock.** All 12 locked hashes (binary, C++ sources, driver, core modules, calibration, re-derivation, instance
  config) matched at launch and still matched after the run. The run's `execution_snapshot/` is byte-identical to them.
- **Runtime.** 3,227 s (53.8 min) to the last instance, from the driver's progress log. The directory was created at
  01:53:24 UTC and `runs.csv` was last written at 02:47:11 UTC. The plan projected about 55 min.
- **Size.** 194,400 rows: 162,000 timed, 32,400 warm-up and 16,200 verified/traced. 1,890,000 per-task trace rows.

## 2. Defect and how it was handled (deviation)

**What happened.** After every measurement was written and both data files were closed, the driver raised
`TypeError: dict() got multiple values for keyword argument 'config_sha256'`. `execute()` records the instance
config's hash under that key, and `run_final()` passed the locked config's hash under the same key. As a result:
- no `manifest.json` was written;
- the built-in post-run checks did not run;
- the files were not sealed.

The dry test before launch had replaced `execute()` with a stub, so it never reached this line.

**Handling, as you instructed:**
- **No rerun, and no data file modified.** `manifest.json` was written afterwards, labelled `"RECONSTRUCTED": true`,
  from recomputable values only: the lock, config, inputs, binary version, checks, output hashes, and the timing
  from the log.
- **Lost fields** (listed in the manifest): the host dictionaries at start and end (including exact power strings),
  the exact `perf_counter` total, and the original manifest time. Host hardware is recorded again at reconstruction,
  labelled as such.
- **Kept beside the data:** the driver's verbatim stdout (`driver_stdout.log`, ending in the traceback) and the
  reconstruction script.
- **Driver fixed after the run.**
  - The extra keys are now `locked_config_*`.
  - `execute()` now rejects a clashing key **before** measuring.
  - Two regression tests were added.
  - The executed driver is the locked one preserved in `execution_snapshot/`. The fix changes `schedlab/ompexec.py`,
    so the config's lock no longer matches the current tree. That is intended: this config must not be run again.
- **Directory sealed.** All 14 output files are read-only and match `post_run.output_sha256`.

## 3. Integrity (acceptance criteria 1–7)

| # | Criterion | Result |
|---|---|---|
| 1 | Rows / timed / verified; coverage; duplicates | 194,400 / 162,000 / 16,200 = expected; 360/360 instances (set equal to the config's `test_id`), 180 rows in every one of 1,080 (instance, granularity) cells; 0 duplicate keys |
| 2 | Per-run flags | `order_ok`, `thread_ok`, `once_ok` = 1 and `threads_seen` = `threads` on all 194,400 rows; `verify_ok` = 1 on all 16,200 verified rows; no missing wall times |
| 3 | Independent trace check (Python, from the trace) | 16,200 traced runs, 1,890,000 rows: **0 problems** (exactly once, precedence, placement, prescribed iterations). On tampered data the checker reports placement, task-set and iteration errors |
| 4 | Inputs and accepted artifacts unchanged | Lock matched before and after. Every pre-M-A file is byte-identical (504 files: accepted campaigns, models, manifests, provenance, configs, docs). The three accepted `verify_campaign.py` runs: 0 problems, identical to the stored results |
| 5 | Power | AC at launch (driver check + operator `pmset`); exact strings lost (§2) |
| 6 | Tests | 261 passed (full suite, after the run) |
| 7 | Reproducibility | Tables and figures regenerated into a scratch directory are **byte-identical** (CSV, PDF, SVG) |

The only files changed since M-C are `schedlab/ompexec.py` (the locked `final` entry point, then the post-run fix)
and `tests/test_ompexec.py` (the regression tests).

## 4. Repeated-measurement variation

Each statistic below is the **CV across the 10 timed reps** of one (instance, granularity, method), with
quantiles taken over all of them.

| Mean task | 10th pct | median | 90th pct | 99th pct |
|---|---|---|---|---|
| 1 ms | 0.19 % | 1.85 % | 7.2 % | 19 % |
| 100 µs | 0.28 % | 2.17 % | 8.9 % | 32 % |
| 10 µs | 0.62 % | 3.49 % | 18 % | 42 % |

Median CV by method at 1 ms tasks:
- `SERIAL`: 0.85 %;
- static `HEFT`: 1.03 %;
- `GA`: 1.02 %;
- `TASKS` (the dynamic OpenMP runtime): 5.2 %, by far the noisiest.

The per-instance noise band of §4 of the plan is 1.6–1.8 % for GA vs HEFT and 3.6 % for TASKS vs HEFT at 1 ms tasks.

## 5. Predeclared comparisons (primary level: 1 ms tasks, Holm across M1–M3)

Each ratio is the geometric mean over the 360 instances of the per-instance medians, with a 95 % percentile
bootstrap CI. A ratio below 1 means faster than HEFT.

| ID | Comparison | Measured ratio [95 % CI] | Holm p | Simulated ratio | Per instance (win / tie / loss) | Verdict |
|---|---|---|---|---|---|---|
| M1 | GA vs HEFT, execution | **0.984** [0.980, 0.988] | 2.3 × 10⁻²⁰ | 0.982 | 115 / 240 / 5 | **Resolvable in aggregate** (≈ 1.6 % faster); mostly **not resolvable per instance** (240 ties) |
| M2 | ADAPTIVE vs HEFT, end-to-end (Python decision + measured execution) | **1.008** [1.006, 1.011] | 1.2 × 10⁻¹⁸ | 1.000 (identical schedule on 342/360) | 12 / 239 / 109 | **ADAPTIVE is slower end-to-end**; the measured execution alone is equal (0.9997 [0.997, 1.002], not resolved) |
| M3 | TASKS (OpenMP runtime) vs static HEFT | **1.188** [1.160, 1.216] | 6.1 × 10⁻³¹ | — | 60 / 66 / 234 | **The dynamic runtime is ≈ 19 % slower** |

Notes on the three comparisons:
- **M1, sign agreement.** Measured and simulated agree on the sign on 77 % of the instances where the schedules
  differ (61 identical schedules excluded). The measured and simulated aggregates agree closely by thread count:
  - m = 2: 0.964 measured vs 0.964 simulated;
  - m = 4: 0.989 vs 0.986;
  - m = 8: **0.999 vs 0.996**. GA's small simulated gain at m = 8 is not present in the measurements.
- **M2.** The Python decision time is the accepted S03 campaign's median for the same instance: ADAPTIVE
  0.27–1.29 ms, HEFT 0.14–1.05 ms, by n. It was measured in a different process on the same host, as labelled in
  the plan.
- **M3.** TASKS is faster than HEFT on 12.5 % of instances at m = 2, 9.2 % at m = 4 and **49 %** at m = 8. Its
  geometric-mean ratio is 1.188, 1.274 and 1.107 at m = 2, 4 and 8.

Secondary granularities (not tested; descriptive only):

| Comparison | 1 ms | 100 µs | 10 µs |
|---|---|---|---|
| GA / HEFT | 0.984 | 0.986 | 0.989 |
| ADAPTIVE / HEFT, end-to-end | 1.008 | **1.068** | **1.267** |
| TRY-ALL / HEFT, end-to-end | 1.103 | 1.805 | 4.185 |
| TASKS / HEFT | 1.188 | 1.179 | 1.190 |
| GA-KEYS-EFT / HEFT | 0.961 | 0.955 | 0.960 |
| RL-S0 / HEFT | 0.999 (CI includes 1) | 0.987 | 0.982 |
| FCFS-EAT / HEFT | 1.241 | 1.233 | 1.191 |

What these show:
- **Decision overhead grows in relative terms** as tasks get shorter. The measured end-to-end results never favour
  ADAPTIVE or TRY-ALL over HEFT.
- **This is not a break-even analysis.** No real-world break-even point is claimed: these are three measured task
  sizes on one host, with Python decision times.
- **RL-S0 is ambiguous.** At 1 ms it is unresolved (simulated 0.997). At finer granularity its measured ratio falls
  below 1 while the CI excludes 1. That is larger than its simulated advantage, so it may be a timing interaction
  rather than schedule quality. It is reported as observed, not as an RL improvement.

## 6. Measured speedup and efficiency (baseline T₁ = SERIAL, same instance and granularity)

Median over instances.

| Method | m = 2 | m = 4 | m = 8 | Efficiency (m = 2 / 4 / 8) |
|---|---|---|---|---|
| HEFT (1 ms) | 1.93 | 3.15 | 3.39 | 0.96 / 0.79 / 0.42 |
| HEFT (100 µs) | 1.95 | 3.12 | 3.12 | 0.98 / 0.78 / 0.39 |
| HEFT (10 µs) | 1.88 | 2.85 | **2.06** | 0.94 / 0.71 / 0.26 |
| GA s0 (1 ms) | 1.96 | 3.21 | 3.40 | |
| GA-KEYS-EFT s0 (1 ms) | 1.96 | 3.42 | 3.47 | |
| RL-S0 (1 ms) | 1.95 | 3.29 | 3.27 | |
| ADAPTIVE (1 ms) | 1.92 | 3.15 | 3.44 | |
| FCFS-EAT (1 ms) | 1.80 | 2.38 | 2.57 | |
| TASKS (1 ms) | 1.51 | 2.26 | 3.00 | |

**Thread-count effect (negative finding).**
- **m = 4 → 8.** Going from 4 to 8 threads adds at most about 8 % speedup at 1 ms tasks, nothing at 100 µs, and
  *reduces* speedup at 10 µs (2.85 → 2.06).
- **Efficiency cores.** From the traces, the median per-thread task slowdown relative to calibration is:
  - 1.10 at m = 2 and 1.11 at m = 4;
  - at m = 8, a median of 1.13–1.32 with a 90th percentile of **2.03**. 39–51 % of the threads at m = 8 run more than
    1.3× slower. These are almost certainly efficiency cores; threads cannot be pinned on macOS.
- **What it means.** A schedule built for 8 equal processors therefore meets about 4 fast and 4 slow cores. Static
  dependency waiting rises from 1 % (m = 2) to 19–28 % (m = 8) of thread time, and imbalance from 1.00 to
  1.37–1.51.
- **Fork/join cost** (calibration): about 8 µs for 2 threads, 14 µs for 4 and 47 µs for 8. That is comparable to a
  whole 10 µs task.

## 7. Simulator vs hardware

Median over instances for the HEFT schedule.

**Raw gap** `G_raw = T / (C_sim · u)`, with u the nominal µs per `sim_tu`:

| Mean task | m = 2 | m = 4 | m = 8 |
|---|---|---|---|
| 1 ms | 1.10 | 1.12 | 1.71 |
| 100 µs | 1.10 | 1.13 | 1.90 |
| 10 µs | 1.12 | 1.21 | 2.62 |

`SERIAL` itself has `G_raw` = 1.07–1.09. This is the **serial calibration offset**: short kernel calls run slower
than the long-run calibration. It stays in `G_raw` and is not subtracted.

**Calibration-adjusted gap** `G_adj = G_raw / G_raw(SERIAL)`. The assumption, stated before the run, is that a
lone thread is the reference.

| Mean task | m = 2 | m = 4 | m = 8 |
|---|---|---|---|
| 1 ms | 1.02 | 1.03 | 1.54 |
| 100 µs | 1.02 | 1.03 | 1.71 |
| 10 µs | 1.05 | 1.12 | 2.38 |

So at m ≤ 4 with tasks of 100 µs or more, the simulator predicts the measured parallel time to within about 3 %
after the serial offset. At m = 8 it underestimates by 1.5–2.4×.

**Ranking.** Kendall's τ between the simulated and measured ranking of the 13 static methods, median per instance:

| Mean task | m = 2 | m = 4 | m = 8 |
|---|---|---|---|
| 1 ms | 0.78 | 0.88 | 0.44 |
| 10 µs | 0.52 | 0.59 | 0.21 |

Simulated orderings carry over well at m ≤ 4 and poorly at m = 8 or with tiny tasks.

## 8. What this does and does not support

- **Resolvable in aggregate:**
  - GA (≈ 1.6 %) and GA-KEYS-EFT (≈ 4 %) execute faster than HEFT schedules on this host, close to their simulated
    advantages, except at m = 8.
  - FCFS-EAT is ≈ 20–24 % slower.
  - The OpenMP dynamic runtime is ≈ 19 % slower than a precomputed HEFT schedule.
  - ADAPTIVE and TRY-ALL lose end-to-end once Python decision time is counted.
- **Not resolvable per instance** for differences under about 2 %. Most GA-vs-HEFT instances are ties within noise.
  The win counts are descriptive, not proof of superiority.
- **Not claimed:**
  - no real-world break-even point;
  - no RL improvement from the fine-granularity observations;
  - no hardware speedup for the earlier Python campaigns. Their makespans remain simulated quality results, and these
    measurements are a separate layer.

## 9. Limitations

- **Single host, unpinned.** One M4 machine; macOS assigns threads to performance or efficiency cores freely.
  The m = 8 results are specific to this core mix.
- **Synthetic kernel.** A compute-bound floating-point chain: no memory traffic, no data passed along DAG edges
  (communication time NA), no cache effects. `hetero` classes are emulated through iteration counts.
- **Serial calibration offset (≈ 8 %).** It is in all raw gaps; `G_adj` assumes lone-thread speed is the reference.
- **Mixed-process end-to-end comparison.** M2 adds Python decision times measured in another process (the S03
  campaign) to C++ execution times.
- **Lost host metadata.** Start and end host records, including the exact power strings, were lost (§2).
- **Wait policy.** OpenMP's default (spin then sleep) is used. Its wake-up cost is part of `wall_s` and of the
  fork/join figures.
- **What `ready_queue_s` includes.** In tasks mode it covers waiting for a free thread (contention), not only runtime
  dispatch.
- **Cosmetic figure defect.** In Figure md3, the tick labels for ADAPTIVE overlap (the analysis code is frozen; fix
  in M-E).

## 10. Not done (for review)

- **Report and note.** The integrated report and technical note are not updated yet (milestone M-E), and the page
  budget is not checked.
- **Nothing else.** No new experiment was run, no accepted result was changed, and nothing was committed.
