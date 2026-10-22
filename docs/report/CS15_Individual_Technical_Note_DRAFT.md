# DRAFT — Individual Member Technical Note (CS15)

> **Draft, not submission-ready.** The manual asks each batch member for a 2–3 page individual technical note. This
> project has **one member covering S01, S02 and S03**, which is **pending faculty approval**; whether one combined
> note or one note per sub-problem is expected must be confirmed with the faculty. Identifiers are placeholders.

| | |
|---|---|
| Student ID | `[STUDENT_ID — PENDING CONFIRMATION]` |
| Batch ID | `[BATCH_ID — PENDING CONFIRMATION]` |
| Sub-problems owned | S01 Evolutionary task scheduling; S02 RL-based scheduling; S03 Adaptive workload-aware scheduler (scope pending approval) |
| Code / data | `schedlab/` (Python), `cpp/` (C++ simulator, OpenMP executor), raw CSVs under `results/raw/`, provenance under `provenance/` |

## 1. Individual contribution

I designed and implemented the shared scheduling core and all three sub-problems:

- **Shared core** (`schedlab/model.py`, `workloads.py`, `heuristics.py`, `runner.py`, `analysis.py`): an execution
  simulator for DAG schedules with gap insertion, an independent schedule validator, a seeded synthetic workload
  generator with content-hash-disjoint train/validation/test/unseen splits, six baseline heuristics (FCFS-EAT,
  FCFS-EFT, SPT-EFT, LPT-EFT, HEFT, MINMIN), a campaign runner writing one raw CSV row per run, and analysis that
  derives the manual's 19-column CSV, tables, figures and integrity checks.
- **S01** (`ga.py`): random-key plus processor-assignment GA with heuristic seeding and equal-budget controls.
- **S03** (`adaptive.py`): nine workload features, decision-tree policy selector with novelty guard, and a separately
  labelled GA contingency extension.
- **S02** (`rl.py`): twelve candidate features, REINFORCE with a HEFT-relative advantage, greedy deterministic policy.
- **C++/OpenMP** (`cpp/schedsim`, `cpp/ompexec`; `interop.py`, `rederive.py`, `ompexec.py`, `omp_analysis.py`): a
  bit-exact C++ workload simulator, exact re-derivation of every accepted search, learned and adaptive schedule, and
  an OpenMP executor (static replay with completion flags, OpenMP tasks, serial baseline) used in a locked measured
  campaign of 194,400 runs with independent trace checks.
- **Methodology:** predeclared hypotheses, primary comparisons and verdict bands; locked configurations with pinned
  model ids; independent verification scripts; execution and post-processing provenance records.

## 2. Method summary

All methods produce static, non-preemptive list schedules for the same synthetic DAGs (4 workload classes; 50, 100,
200 tasks; 2, 4, 8 simulated processors; plus unseen sets with 400 tasks, 16 processors, fork-join DAGs and work CV
3.0), placed through one insertion-capable simulator; the baselines include HEFT [1] and Min-min [2], and the S01
chromosome uses random keys [3]. The S03 selector is evaluated against the single best and virtual best solvers [4].
Quality is simulated makespan, also normalised by a lower bound; speedup is relative to serial execution on the best
single simulated processor; scheduling time is measured in seconds (in the simulation campaigns communication,
synchronization and energy are not modelled: `NA`; in the measured replay, static-mode dependency waiting is recorded
as synchronization time, while communication and energy remain `NA`). Deterministic methods are timed 3 times per instance; stochastic methods run with seeds 0, 1, 2; S02
has 3 training seeds. Each sub-problem has one predeclared primary comparison, tested with a Wilcoxon signed-rank test
[5] on paired makespans, with Holm's correction [6] across the three and bootstrap confidence intervals (percentile method) [7].
The schedules were then executed on real threads (GCC 15.2, OpenMP; Apple M4): 360 instances, 15 methods, mean task
1 ms / 100 µs / 10 µs, 10 repetitions each, speedup against serial execution, three predeclared measured comparisons.

## 3. Key results (held-out data; verified against saved tables)

| | Primary comparison | Result | Interpretation |
|---|---|---|---|
| S01 | GA vs per-instance best heuristic, 450 test instances | mean paired improvement **+1.169%** (CI 0.96–1.39%), 330 / 114 / 6, p = 6.2e-52 | Small, consistent improvement, largely on instances where the GA's seed heuristics were best; ~1,100–1,730× HEFT's scheduling time. An equal-budget hill climber reached +0.90%; the keys-only ablation +3.38% (better than the primary). Analysis population not predeclared |
| S03 | ADAPTIVE vs SBS (HEFT), 360 `test_id` | **−0.016%**, 6 / 342 / 12, p = 0.78, gap closed −0.03 (CI −0.30–0.19) | Null result: no improvement over the best fixed policy. HEFT is within 0.48% of the per-instance oracle, leaving ≤ 0.45% to gain. The GA extension (+0.10%, CI including 0) is reported separately |
| S02 | RL (mean of 3 seeds) vs HEFT, 360 `test_id` | ρ = **1.0097** (CI 1.0034–1.0160), RL worse on 226 / 360, p = 6.8e-6 | Statistically worse than HEFT by ~1%, yet within the predeclared ±2% band → verdict "matches". Improves on FCFS-EAT by ~18% (ρ 0.822). Seed-dependent; generalises to larger DAGs, not to 16 processors or fork-join |
| Measured | GA vs HEFT; ADAPTIVE (incl. decision time) vs HEFT; OpenMP tasks vs static HEFT; 1 ms tasks, 360 `test_id` | ratio **0.984** (CI 0.980–0.988); **1.008**; **1.188**; all Holm-significant | GA's gain survives on real threads in aggregate, mostly within noise per instance and absent at 8 threads; decision overhead makes ADAPTIVE slower; the dynamic runtime is 19% slower; HEFT efficiency 0.42 at 8 threads (consistent with efficiency cores; inferred from task timings, placement not recorded) |

## 4. What I learned

1. A strong cheap heuristic sets a high bar: on deterministic, communication-free DAGs, HEFT left little room for
   selection or learning, and search gains cost three orders of magnitude more time.
2. Controls change conclusions: seeding guarantees "never worse than the seeds", so improvement over the seeds is not
   evidence of evolutionary search; an equal-budget hill climber nearly matched the GA.
3. Statistical and practical significance differ: S02's 1% shortfall is highly significant but inside a predeclared
   practical-equivalence band.
4. Measured noise (≈ 2% per run) is as large as the simulated effects: they show up on hardware only in aggregate,
   and the hardware (efficiency cores at 8 threads) changes the picture the simulator gives.
5. Reproducibility needs engineering: pinned model ids, deterministic training, hash-checked data splits and saved
   execution snapshots caught and documented several issues (e.g. a non-reproducible model id from stored timings,
   transcription errors corrected in `docs/report/ERRATA.md`).

## 5. Limitations

Quality results simulated (no communication costs); the measured replay uses a synthetic kernel on one unpinned M4,
with an ≈ 8% serial calibration offset and host records lost to a driver defect (manifest reconstructed); whether the
C++/OpenMP components meet the tooling requirement is pending faculty confirmation; S01 and S03 timings measured on
battery power; one synthetic generator; three RL training seeds; the S03 objective to use findings from Batches 1–3 and
7 is not met (findings unavailable, none invented).

## 6. References

[1] H. Topcuoglu, S. Hariri, and M.-Y. Wu, "Performance-effective and low-complexity task scheduling for heterogeneous
computing," *IEEE Transactions on Parallel and Distributed Systems*, vol. 13, pp. 260–274, 2002, doi: 10.1109/71.993206.

[2] T. D. Braun *et al.*, "A comparison of eleven static heuristics for mapping a class of independent tasks onto
heterogeneous distributed computing systems," *Journal of Parallel and Distributed Computing*, vol. 61, pp. 810–837,
2001, doi: 10.1006/jpdc.2000.1714.

[3] J. C. Bean, "Genetic algorithms and random keys for sequencing and optimization," *ORSA Journal on Computing*,
vol. 6, pp. 154–160, 1994, doi: 10.1287/ijoc.6.2.154.

[4] P. Kerschke, H. H. Hoos, F. Neumann, and H. Trautmann, "Automated algorithm selection: Survey and perspectives,"
*Evolutionary Computation*, vol. 27, no. 1, pp. 3–45, 2019, doi: 10.1162/evco_a_00242.

[5] F. Wilcoxon, "Individual comparisons by ranking methods," *Biometrics Bulletin*, vol. 1, no. 6, p. 80, 1945,
doi: 10.2307/3001968.

[6] S. Holm, "A simple sequentially rejective multiple test procedure," *Scandinavian Journal of Statistics*, vol. 6,
pp. 65–70, 1979, doi: 10.2307/4615733.

[7] B. Efron and R. Tibshirani, "Bootstrap methods for standard errors, confidence intervals, and other measures of
statistical accuracy," *Statistical Science*, vol. 1, no. 1, pp. 54–75, 1986, doi: 10.1214/ss/1177013815.

Full bibliography of the batch report: `docs/report/references.bib` (IEEE style).
