# S01 Evolutionary Task Scheduling — Acceptance Report

Final campaign `20261017T044734Z-s01_final-430d8a10`, analysed 2026-10-17. Everything below is **simulated makespan**
(time unit `sim_tu`) from a list-scheduling simulator with no communication cost, except where it says *measured
seconds*. No real-hardware execution speedup is claimed or demonstrated.

Label key: **[verified]** computed from the frozen raw data and cross-checked; **[pilot]** earlier `val` results, not
evidence for this campaign; **[hypothetical]** depends on an assumed time conversion.

---

## A. Campaign summary [verified]

| Item | Value |
|---|---|
| Locked config | `configs/s01_final.toml` (sha256 `550007b6…a8e5`, config hash `430d8a10`), locked before any test evaluation; `[workload]` and seed equal `full.toml`, `[ga]` equals the untuned pilot settings (test `test_final_s01_config_is_locked_to_the_predeclared_settings`) |
| GA settings | population 60, `max_evals` 6,000, tournament 3, crossover 0.9 (uniform), key σ 0.15, 1 expected mutation per array, 2 elites, seeds `HEFT`, `MINMIN`, `FCFS-EAT`; algorithm seeds 0, 1, 2 |
| Execution code | hash `9a1f83786ce9df0b`; exact snapshot in `provenance/s01_final/execution_snapshot/` |
| Start / end (UTC) | 2026-10-17 04:47:34 → 06:46:01; runner wall time 7,106 s (projection was ≈ 7,100 s) |
| Host | Apple M4, 10 cores, 16 GB, single worker, one thread, **on battery** (84% at launch, 15% at end) |
| Instances | 450 (`test_id` 360 = 4 classes × n {50, 100, 200} × m {2, 4, 8} × 10; `test_ood` 90 = 9 OOD cells × 10) |
| Methods | 11: six heuristics (`FCFS-EAT`, `FCFS-EFT`, `SPT-EFT`, `LPT-EFT`, `HEFT`, `MINMIN`) × 3 timing repeats; five S01 methods (`GA`, `GA-UNSEEDED`, `GA-KEYS-EFT`, `RANDOM-SEARCH`, `HILL-CLIMB`) × 3 algorithm seeds |
| Rows | expected 450 × 11 × 3 = **14,850**; actual **14,850** |
| Failed / timeout / invalid / missing / duplicated | **0 / 0 / 0 / 0 / 0** |
| Budgets | every one of the 6,750 S01 runs used exactly 6,000 evaluations |
| Campaign checks (`analyze`) | all passed |
| Independent check (`provenance/s01_final/verify_campaign.py`, does not use `analysis.py`) | 0 problems: config and per-method config hashes match the lock; instance set and metadata equal the experiment matrix; 3 repeats or seeds per (instance, method); the six heuristics re-run from scratch reproduce every raw makespan exactly; `s01_paired.csv` and the Wilcoxon p-values recomputed directly from `runs.csv` match |
| Test suite | `python3 -m pytest -q` → exit 0, **201 passed, 0 failed, 0 skipped** (includes the new break-even test) |
| Timing outliers | 130 rows flagged (scheduling time > Q3 + 3·IQR within algorithm × size × m); retained, not removed |

No test-split result was used to choose any setting. The primary method, budget and seeds were fixed on 2026-10-17
from `val` pilot evidence before launch.

---

## B. Algorithm comparison [verified]

Per instance, the value of a seeded method is the **mean over its 3 algorithm seeds**; heuristics are deterministic.
Improvement is always paired: `impr_i = (C_base,i − C_alg,i) / C_base,i`, averaged over instances.

### B.1 Overall (all 450 instances)

| Algorithm | Cmax/LB mean (median) | Utilization | Median time per run (measured s) | Paired impr. vs FCFS-EAT | vs HEFT | vs best heuristic | better / tie / worse vs best heuristic |
|---|---|---|---|---|---|---|---|
| `GA` (primary) | 1.153 (1.018) | 0.869 | 0.584 | 19.68% | 1.56% | **1.17%** | 330 / 114 / 6 |
| `GA-KEYS-EFT` (ablation) | 1.122 (1.005) | 0.871 | 1.071 | 21.25% | 3.76% | 3.38% | 353 / 83 / 14 |
| `HILL-CLIMB` (control) | 1.156 (1.018) | 0.874 | 0.604 | 19.45% | 1.29% | 0.90% | 337 / 103 / 10 |
| `RANDOM-SEARCH` (control) | 1.170 (1.025) | 0.861 | 0.504 | 18.75% | 0.28% | −0.13% | 0 / 428 / 22 |
| `GA-UNSEEDED` (ablation) | 1.388 (1.208) | 0.793 | 0.502 | 6.59% | −16.49% | −16.96% | 53 / 32 / 365 |
| `HEFT` | 1.174 (1.030) | 0.866 | 0.0004 | 18.52% | 0 | −0.43% | — |
| `FCFS-EFT` | 1.240 (1.129) | 0.814 | 0.0003 | 14.85% | −5.52% | −5.95% | — |
| `LPT-EFT` | 1.304 (1.203) | 0.783 | 0.0003 | 10.45% | −10.80% | −11.25% | — |
| `MINMIN` | 1.390 (1.334) | 0.689 | 0.0011 | 3.68% | −19.12% | −19.55% | — |
| `SPT-EFT` | 1.479 (1.398) | 0.659 | 0.0003 | −2.23% | −26.33% | −26.80% | — |
| `FCFS-EAT` | 1.588 (1.196) | 0.825 | 0.0003 | 0 | −32.79% | −33.34% | — |

`BEST-HEURISTIC` is the per-instance minimum of the six heuristics: `HEFT` on 326 instances, `FCFS-EAT` 58, `LPT-EFT`
30, `MINMIN` 21, `FCFS-EFT` 13, `SPT-EFT` 2. Speedup (baseline: serial execution on the best single simulated
processor) is in `summary_by_algorithm.csv`; `GA` mean 3.61, `HEFT` 3.57.

### B.2 Predeclared primary comparison: `GA` vs `BEST-HEURISTIC`

Rules (methodology §5.1): paired by instance, GA value = mean of 3 seeds, Wilcoxon signed-rank on paired makespans
(two-sided, zero differences dropped). Predeclared multiplicity plan: a Holm correction over a family of three primary
tests, one per sub-problem (S01 `GA` vs best heuristic, S02 `RL` vs `HEFT`, S03 `ADAPTIVE` vs `SBS`). Only the S01
test exists, so Holm cannot yet be applied in full. The smallest threshold Holm can assign to any member of a
three-test family is α/3 = 0.0167 (its first step, equal to Bonferroni); a p-value below α/3 is therefore below
whatever Holm threshold it eventually receives. That is the only sense in which a correction was applied.

**Analysis population was not specified in advance.** The methodology fixed the comparison, the statistic and the test,
but not whether the primary population is `test_id`, `test_ood` or both. All three populations are therefore reported
below, none is designated primary after the fact, and the three p-values are three analyses of one comparison, which
the predeclared Holm family does not cover. Even with a Bonferroni correction over all nine conceivable tests
(3 populations × 3 sub-problems, α/9 = 0.0056) every p-value below would stay under the threshold; this is a
sensitivity remark, not a predeclared procedure. Because the population was not fixed beforehand, these results are
reported as **descriptive evidence with a predeclared test, not as a confirmatory test**.

| Scope | n (non-zero diffs) | Mean paired impr. | 95% bootstrap CI (impr.) | Median ratio | Geometric-mean impr. | better / tie / worse | Wilcoxon p |
|---|---|---|---|---|---|---|---|
| `test_id` | 360 (283) | 1.33% | 1.07% – 1.60% | 0.9980 | 1.36% | 272 / 83 / 5 | 3.0e-43 |
| `test_ood` | 90 (60) | 0.54% | 0.31% – 0.79% | 0.9997 | 0.55% | 58 / 31 / 1 | 2.2e-10 |
| all | 450 (343) | 1.17% | 0.96% – 1.39% | 0.9984 | 1.20% | 330 / 114 / 6 | 6.2e-52 |

(CI: percentile bootstrap of the mean ratio, 10,000 resamples of instances, seed 20261017, reported here as
`1 − ratio`.)

**Reading this correctly.** The observed mean paired improvement over all 450 instances is **1.169%** (95% CI
0.96%–1.39%). It is the observed result on this generator, these platforms and this simulator, not proof that the GA
is a better scheduler in general. The difference is detectable (p < α/3 in every population) but small: about
1.2% of simulated makespan on average, a median ratio within 0.2% of 1, and zero difference on 114 of 450 instances.
Much of the one-sidedness is structural. `GA` is seeded with `HEFT`, `MINMIN` and `FCFS-EAT`, which are the best
heuristic on 405 of the 450 instances, and it keeps its best-so-far, so on those instances it cannot be worse. The test
therefore mainly shows that the search improves on its seeds often, not that the GA is better than heuristics in
general. GA lost to the best heuristic on 6 instances (by 0.6–5.2%), each one where the best heuristic was an unseeded
one (`LPT-EFT` 3, `FCFS-EFT` 3). The p-value is not an effect size; the effect size is the CI above.

### B.3 Secondary and exploratory comparisons (no significance tests computed)

| Comparison (all 450) | Mean paired impr. (CI) | better / tie / worse |
|---|---|---|
| `GA` vs `HEFT` | 1.56% (1.28 – 1.85%) | 338 / 112 / 0 (cannot be worse: HEFT is a seed) |
| `GA` vs `RANDOM-SEARCH` | 1.29% (1.07 – 1.54%) | 336 / 114 / 0 |
| `GA` vs `HILL-CLIMB` | 0.27% (0.13 – 0.42%) | 190 / 98 / 162 |
| `GA` vs `GA-KEYS-EFT` | −2.43% (−2.82 to −2.07%) | 23 / 84 / 343 |
| `GA` vs `GA-UNSEEDED` | 12.97% (11.77 – 14.25%) | 405 / 32 / 13 |
| `GA-BEST-OF-SEEDS` vs best heuristic (charged 3× time) | 1.57% (1.30 – 1.85%) | 330 / 114 / 6 |

### B.4 By workload class, size and processor count (mean paired improvement vs best heuristic)

| Group | `GA` | `GA-KEYS-EFT` | `HILL-CLIMB` |
|---|---|---|---|
| heterogeneous (`test_id`) | 3.13% | 7.22% | 1.95% |
| irregular_hetero | 1.78% | 6.44% | 1.47% |
| regular | 0.33% | 1.19% | 0.31% |
| irregular | 0.07% | 0.17% | 0.08% |
| ood_size (n = 400, m = 4) | 0.54% | 3.25% | 0.77% |
| ood_procs (n = 200, m = 16) | 0.03% | **−0.36%** | 0.04% |
| ood_struct (fork-join) | 1.12% | 1.73% | 1.21% |
| ood_cv (work CV 3.0) | 0.40% | 0.96% | 0.52% |
| n = 50 / 100 / 200 (`test_id`) | 1.98 / 1.08 / 0.91% | 3.90 / 3.94 / 3.43% | 1.46 / 0.76 / 0.64% |
| m = 2 / 4 / 8 (`test_id`) | 2.59 / 1.04 / 0.35% | 4.43 / 4.67 / 2.17% | 1.14 / 1.02 / 0.71% |

Against `FCFS-EAT` the gains are large on heterogeneous platforms (35–40%) because `FCFS-EAT` ignores processor
speed; they are near zero on `regular` (≈1–2%). That is a property of the weak baseline, not of the GA.

### B.5 Convergence (G2b) and seed variability

- Median evaluation of the last logged improvement (`GA`): 2,380 (n = 50), 3,366 (100), 3,627 (200), 4,932 (400).
  Share of `GA` runs still improving after 5,000 evaluations: 16%, 29%, 31%, 46%. `GA-KEYS-EFT`: 11%, 32%, 52%, 73%.
  So at n ≥ 200 many runs had not converged at the 6,000 budget. The budget was not changed (it was locked).
- `GA-UNSEEDED` stays well above HEFT at n ≥ 200 throughout (median best/HEFT after 6,000 evaluations: 1.040 at n = 100,
  1.199 at n = 200, 1.381 at n = 400). Final medians for `GA`: 0.994, 0.997, 0.999, 0.999 (n = 50 … 400).
- Seed-to-seed spread, `(max − min) / mean` over the 3 seeds per instance: `GA` mean 0.79%, median 0.06%, max 17.8%;
  all three seeds identical on 119 instances. `HILL-CLIMB` mean 0.67%; `GA-KEYS-EFT` 0.99%; `GA-UNSEEDED` 6.0%.
- `RANDOM-SEARCH` gives the same result for all 3 seeds on all 450 instances. Investigated: every one of its 1,350
  runs equals the best of its three seed heuristics, i.e. no uniformly random chromosome ever beat the best seed. The
  three seeds do drive separate RNG streams; this is a finding about blind sampling, not a seeding defect.

---

## C. Statistical definitions

Formulas are in `DATA_SCHEMA.md` §4.1 and tested in `tests/test_analysis_s01.py`. The mean of paired per-instance
improvements (reported above), the geometric-mean improvement, and ratios of aggregate means are different statistics.
For example `GA` vs `FCFS-EAT` over all 450 instances: mean paired improvement 19.68%, geometric-mean improvement
22.56%, while `1 − mean(C_GA/LB) / mean(C_FCFS/LB)` = 27.39% — a ratio of two LB-weighted aggregate means, not a paired
improvement, and not reported as one. Confidence intervals and p-values are given only where computed (B.2, B.3 CIs).

---

## D. Optimization overhead (measured seconds) and quality (simulated) [verified, except τ*]

| n | `GA` median time (s) | `HEFT` median time (s) | Time ratio | `GA` impr. vs HEFT | Share of instances better than HEFT |
|---|---|---|---|---|---|
| 50 | 0.250 | 0.00014 | ≈ 1,730× | 2.48% | 69% |
| 100 | 0.548 | 0.00036 | ≈ 1,510× | 1.42% | 74% |
| 200 | 1.279 | 0.0011 | ≈ 1,200× | 1.08% | 76% |
| 400 | 3.706 | 0.0035 | ≈ 1,100× | 0.96% | 95% |

`GA-KEYS-EFT` takes 1.5–1.9× the GA's time (median 0.47–5.5 s); `GA-BEST-OF-SEEDS` is charged 3× (up to 11 s at n = 400).
These times are measured on one battery-powered laptop in pure Python.

**[hypothetical] Break-even τ\*.** Simulated time units and seconds cannot be compared without a conversion factor τ
(seconds per `sim_tu`), and none is known. τ\*ᵢ = (T_GA,i − T_HEFT,i) / (C_HEFT,i − C_GA,i), ∞ where GA does not beat
HEFT, is the value of τ at which the extra optimization time would equal the simulated saving. Median τ\* for `GA`:
0.034 (n = 50), 0.074 (100), 0.38 (200), 0.63 s/`sim_tu` (400). Mean task work is about 100 `sim_tu`, so GA would pay
off against HEFT on the median instance only if tasks averaged roughly 3–63 s each, under the assumptions that the
simulator's makespan scales linearly to real time and that optimization happens before execution with nothing
overlapped. This is a sensitivity statement, not a measured break-even.

---

## E. Negative results, limitations and reproducibility

**Negative or unexpected results**

1. The restricted ablation `GA-KEYS-EFT` beat the primary `GA` (−2.43% mean paired, GA worse on 343 of 450). This
   repeats the pilot finding. Per the 2026-10-17 decision the primary is unchanged. `GA-KEYS-EFT`'s seeds are re-decoded
   task orders, not the heuristic schedules (ALGORITHM_DESIGN §3.5), so it has no "never worse than seeds" guarantee:
   it was worse than HEFT on 14 instances and its mean was negative on `ood_procs` (m = 16).
2. `GA` adds little over `HILL-CLIMB` with the same mutation, budget and seeds: +0.27% mean, worse on 162 of 450.
   Population and crossover are not shown to matter at this budget.
3. Without heuristic seeds the GA is 17% worse than the best heuristic on average, and worse with size (−45.8% at
   n = 400).
4. `RANDOM-SEARCH` never improved on its seeds.
5. Gains shrink with n and with m (B.4) and are near zero on homogeneous `irregular` workloads and on `ood_procs`.
6. `GA` lost to the best heuristic on 6 instances (B.2).

**Limitations**

- **Battery power.** The whole campaign ran on battery (84% → 15%). Measured times (optimization, scheduling) may
  differ under mains power or on other machines and are not claimed to generalise. 130 timing outliers were flagged
  and kept. Simulated makespans are unaffected (heuristic re-runs reproduce them exactly).
- **Execution vs analysis code.** The campaign ran with code hash `9a1f83786ce9df0b`; the analysis ran with
  `a23e460502a1baf6`. They differ only in `analysis.py` (break-even definition aligned with methodology §5.3 after
  launch). The exact execution snapshot is preserved and its hash matches the manifest
  (`provenance/s01_final/EXECUTION_PROVENANCE.md`).
- **Simulator.** No communication cost, exact cost estimates, free dispatch. All quality results are simulated
  makespan; no measured real-hardware speedup is demonstrated.
- **Structural advantage.** Seeded methods cannot lose to their seeds; comparisons against `HEFT` therefore cannot
  show a loss. The informative comparisons are vs best heuristic, vs the equal-budget controls and vs the ablations.
- **Generalisation.** Instances come from one generator; `test_ood` covers four shifts with 10 instances per cell
  (90 total); per-cell results in B.4 rest on 10–40 instances.
- **Budget not converged** at n ≥ 200 for many runs (B.5).
- **Ablation scope.** The controls ran on all 450 instances (superset of the predeclared 40-instance set). On that
  predeclared subset (`test_id`, n = 100, m = 4): `GA` 0.79% vs best heuristic (31/8/1), `GA-KEYS-EFT` 4.87% (37/3/0),
  `HILL-CLIMB` 0.59% (36/3/1), `RANDOM-SEARCH` −0.11% (0/39/1), `GA-UNSEEDED` −12.0% (0/0/40).

**Reproduce the analysis from the preserved raw data**

```
python3 -m pytest -q
python3 -m schedlab analyze results/raw/20261017T044734Z-s01_final-430d8a10
PYTHONPATH=. python3 provenance/s01_final/verify_campaign.py results/raw/20261017T044734Z-s01_final-430d8a10 results/derived/20261017T044734Z-s01_final-430d8a10 provenance/s01_final/verify_campaign_result.json
```

Outputs: `results/derived/<campaign>/` (`master.csv`, `summary_by_algorithm.csv`, `timing_by_size.csv`,
`s01_paired.csv`, `s01_overhead_quality.csv`) and `results/figures/<campaign>/` (G1, G2a, G2b, G3 as PDF + SVG +
per-instance/per-run CSV + plotted-summary CSV). Every plotted summary was recomputed from its source CSV and matched
(`provenance/s01_final/figure_reproducibility_check.txt`). Hashes: `provenance/s01_final/POSTPROCESSING_PROVENANCE.json`.

**Submission blockers (unchanged by this milestone)**: `Student_ID` / `Batch_ID` are placeholders (`analyze --final`
refuses to export); faculty approval of scope and tooling; literature review not started; Batches 1–3 and 7 findings
unavailable.

## F. Status

**Technical acceptance (accepted by the user, 2026-10-17).** Implementation correctness, campaign integrity,
reproducibility and provenance are verified: 14,850 / 14,850 rows, 0 failures, all integrity checks and 201 tests
passed, every figure regenerates from its saved CSV. This acceptance is about whether the experiment was run and
analysed correctly. It is not a claim about which scheduler is better.

**Scientific conclusions (observed, scope-limited).** On these 450 synthetic test instances, in simulation, the seeded
GA's makespan was on average 1.169% lower than the per-instance best of six heuristics. The comparison is partly
structural (seeded, never worse than its seeds on 405 instances), the analysis population was not predeclared, and the
result does not establish general or real-hardware superiority. The GA costs roughly 1,100–1,730× HEFT's measured
scheduling time. A hill climb with the same budget achieves most of the gain, and the restricted keys-only ablation
achieved more (3.38%), so the evidence does not single out the full GA representation as the best search design.
