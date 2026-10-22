# S02 Reinforcement-Learning Scheduling — Final Campaign Acceptance Report

Campaign `20261017T115054Z-s02_final-898ee9e1`, run once on 2026-10-17 on AC power. Quality is **simulated makespan**
(`sim_tu`); training time and inference overhead are **measured seconds**; the two are never combined. ρ =
`Cmax_RL / Cmax_HEFT` per instance (< 1 = RL better). Validation numbers are model-development diagnostics (`val`
chose every checkpoint); generalization is judged on `test_id` and `test_ood` only.

---

## A. Campaign summary and integrity [verified]

| Item | Value | Source |
|---|---|---|
| Locked config | `configs/s02_final.toml` (sha256 `077c0d33…c817`, hash `898ee9e1`), lock test | `provenance/s02_final/EXECUTION_PROVENANCE.md` |
| Models (pinned) | `RL-S0` `c827a9f51c512ac4`, `RL-S1` `e83496e27b9d4ef1`, `RL-S2` `1765acd48d43dfde` (seeds 0–2), `RL-NOHEFTFEAT` `a7781d888bca8550` (seed 0, features 4 and 7 removed); predeclared settings, no tuning, no fallback needed | manifest `models`, model dirs |
| Training (one-off, measured) | 930–959 s per model on AC power, 3,000 updates and 48,000 episodes each, shared training stream (`train` split, indices ≥ 1000), 0 overlap with `val`/`test_id`/`test_ood` | `model.json` |
| Splits | `test_id` 360, `test_ood` 90 (`ood_size` n = 400, `ood_procs` m = 16, `ood_struct` fork-join, `ood_cv` CV 3.0) | verify |
| Methods | 10: six heuristics + four RL policies, all deterministic, 3 timing repeats | runs.csv |
| Run | 11:50:54 → 11:52:15 UTC, 80.26 s; AC power at start and end (recorded in the manifest). The first pre-launch check found the host on battery; the launch was held until AC was confirmed | manifest |
| Rows | expected 450 × 10 × 3 = **13,500**; actual **13,500** (`test_id` 10,800, `test_ood` 2,700) | verify |
| Failed / timeout / invalid / duplicate / missing | **0 / 0 / 0 / 0 / 0** | verify, manifest |
| Independent check (`provenance/s02_final/verify_campaign.py`) | 0 problems: config and per-method hashes; pinned ids on every row; determinism across repeats; no training-stream instance evaluated; **every heuristic and every RL schedule re-run from scratch (RL from the saved weights) reproduces its raw makespan**; paired table and primary Wilcoxon recomputed from `runs.csv` | `verify_campaign_result.json` |
| Campaign checks / tests | `analyze`: all passed. `python3 -m pytest -q`: **238 passed**, 0 failed, 0 skipped | provenance |
| Figures | G1, G4, G5, G6 recomputed from their CSVs; G4 equals the four `training_log.csv` files | `figure_reproducibility_check.txt` |
| Code | execution = analysis hash `939d930e96cebafe`; snapshot preserved | provenance |

---

## B. Predeclared primary comparison: `RL` vs `HEFT` on `test_id`

`RL` = per-instance mean makespan over `RL-S0`, `RL-S1`, `RL-S2`. Wilcoxon signed-rank on paired makespans,
two-sided, zero differences dropped. The test and the comparison were predeclared in EXPERIMENTAL_METHODOLOGY §5.1;
the population `test_id` and the seed-mean definition were fixed in the approved S02 plan (2026-10-17) before any S02
data existed — a pre-data specification, not part of the original methodology text.

| Population | n (non-zero) | Mean ρ | 95% bootstrap CI | Median ρ | RL better / tie / worse | Wilcoxon p |
|---|---|---|---|---|---|---|
| **`test_id`** | 360 (326) | **1.0097** | **1.0031 – 1.0163** | 1.0083 | 100 / 34 / 226 | **6.8e-6** |
| `test_ood` (secondary) | 90 (80) | 1.0097 | 0.9994 – 1.0204 | 1.0109 | 21 / 10 / 59 | 0.078 |

**Result.** On held-out in-distribution workloads the trained RL policy (seed mean) produced schedules about **1.0%
longer** than `HEFT` on average; the difference is statistically detectable (p = 6.8e-6, RL worse on 226 of 360).
Against the predeclared verdict bands (ALGORITHM_DESIGN §4.6): "improves" requires the CI below 1 — **not met**;
"matches" requires the CI within [0.98, 1.02] — **met** (1.0031–1.0163). The predeclared verdict is therefore
**"matches HEFT"**, with the explicit qualification that the match is a small but significant shortfall, not
parity.

**Holm family across the three sub-problems (α = 0.05), now complete:**

| Test | Population | p | Holm threshold | Holm-adjusted p | Decision |
|---|---|---|---|---|---|
| S01 `GA` vs best heuristic | `test_id` (population not predeclared; all-450 p = 6.2e-52) | 3.0e-43 | 0.0167 | 9.1e-43 | reject (GA lower) |
| S02 `RL` vs `HEFT` | `test_id` | 6.8e-6 | 0.025 | 1.4e-5 | reject (**RL higher**, i.e. worse) |
| S03 `ADAPTIVE` vs `SBS` | `test_id` | 0.78 | 0.05 | 0.78 | not rejected |

The decisions are the same whichever S01 population is used. A rejection says only that the two methods differ; the
direction and size are in the effect columns.

---

## C. Secondary results (no p-values)

### C.1 Against the other baselines, `test_id` (`s02_paired.csv`)

| Method | Mean ρ vs HEFT (CI) | vs `FCFS-EAT` (CI) | vs best heuristic (CI) | vs HEFT better / tie / worse | Cmax/LB mean | Utilization |
|---|---|---|---|---|---|---|
| `RL` (seed mean) | 1.010 (1.003–1.016) | **0.822 (0.803–0.841)** | 1.014 (1.008–1.020) | 100 / 34 / 226 | — | — |
| `RL-S0` | **0.999 (0.992–1.006)** | 0.813 (0.794–0.833) | 1.003 (0.997–1.010) | 146 / 40 / 174 | 1.176 | 0.858 |
| `RL-S1` | 1.002 (0.995–1.009) | 0.814 (0.795–0.833) | 1.006 (1.000–1.013) | 147 / 47 / 166 | 1.181 | 0.844 |
| `RL-S2` | 1.028 (1.021–1.036) | 0.838 (0.818–0.858) | 1.033 (1.026–1.040) | 85 / 39 / 236 | 1.211 | 0.818 |
| `RL-NOHEFTFEAT` | 1.036 (1.025–1.047) | 0.840 (0.820–0.860) | 1.040 (1.029–1.052) | 115 / 19 / 226 | 1.217 | 0.822 |
| `HEFT` | 1 | — | — | — | 1.181 | 0.895 |
| `FCFS-EAT` | — | 1 | — | — | 1.581 | 0.852 |

- **vs the conventional heuristic (manual's question):** RL improves on `FCFS-EAT` by about 18% (CI of the ratio
  below 1 for every seed and the ablation) — the §4.6 "improves over FCFS" criterion is **met**.
- **vs the strong heuristic:** two seeds match `HEFT` (CIs include 1); one seed is 2.8% worse.
- **RL ρ by size / processors / class (`test_id`):** n = 50 / 100 / 200: 1.014 / 1.010 / 1.005; m = 2 / 4 / 8:
  **0.973** / 1.017 / 1.039; heterogeneous **0.984**, irregular 1.011, regular 1.017, irregular_hetero 1.026. RL
  beats HEFT on average with 2 processors and on the heterogeneous class, and loses as m grows.
- **Seed stability (§4.6):** per-seed mean ρ 0.999, 1.002, 1.028 (range 0.029, sd 0.016). Per-seed verdicts:
  `RL-S0` matches, `RL-S1` matches, `RL-S2` does not improve (CI 1.021–1.036 lies outside [0.98, 1.02]). The seeds
  disagree, so per §4.6 the answer is reported as **seed-dependent**.
- **Ablation:** removing the HEFT-like features (rank, earliest-finish) costs about 3.7 points of ρ for the same
  seed (1.036 vs 0.999): the trained policy relies substantially on HEFT's own quantities.

### C.2 Generalization to unseen workloads (`s02_generalization.csv`)

Δ = mean ρ on the OOD set − mean ρ on `test_id`; "generalises" (§4.6) = upper CI bound of Δ ≤ 0.02 **and** RL still
beats `FCFS-EAT` there.

| `RL` (seed mean) | n | ρ OOD | Δ (95% CI) | Beats `FCFS-EAT` | Verdict |
|---|---|---|---|---|---|
| `ood_size` (n = 400) | 40 | **0.983** | −0.027 (−0.042 – −0.012) | yes | **generalises** |
| `ood_cv` (CV 3.0) | 10 | 1.014 | +0.004 (−0.008 – 0.018) | yes | **generalises** |
| `ood_procs` (m = 16) | 20 | 1.034 | +0.024 (0.003 – 0.049) | yes | does not generalise |
| `ood_struct` (fork-join) | 20 | 1.038 | +0.028 (0.009 – 0.049) | yes | does not generalise |

Per seed: `RL-S0` and `RL-S1` generalise only to `ood_size`; `RL-S2` to `ood_size` and `ood_cv`; the ablation only to
`ood_size`. On larger DAGs RL beats `HEFT`; on many more processors and on a new DAG structure it degrades
(consistent with the m-trend above). `ood_cv` has only 10 instances.

### C.3 Overhead (measured seconds; AC power; `s02_overhead.csv`)

| n | RL median time per instance | per decision | HEFT median | ratio |
|---|---|---|---|---|
| 50 | 2.5 ms | 50 µs | 0.14 ms | ~17–18× |
| 100 | 5.7 ms | 57 µs | 0.36 ms | ~16× |
| 200 | 16–17 ms | 80–86 µs | 1.07 ms | ~15–16× |
| 400 | 50–56 ms | 125–139 µs | 3.3 ms | ~15–17× |

One-off training: ~16 minutes and 48,000 episodes per policy (930–959 s). Inference is 12–18× HEFT's scheduling
time; with RL at best matching HEFT in quality, no break-even calculation is meaningful and none is claimed.

---

## D. Learning diagnostics (validation; development only)

From `docs/S02_PILOT_REPORT.md` §9: all three seeds "learned" under §4.6 on `val` (best checkpoint below update 0 with
CI below 0, and mean makespan below `FCFS-EAT`); best `val` ρ 1.006 / 1.000 / 1.029 (ablation 1.035). Held-out
`test_id` ρ (0.999 / 1.002 / 1.028 / 1.036) is close to the `val` values: checkpoint selection on `val` did not
inflate the in-distribution result noticeably. Batch returns were still rising at update 3,000: the predeclared
budget, not convergence, ended training. Behaviour-cloning fallback: not triggered for any model.

---

## E. Findings, limitations and status

**Answer to the research question** ("Can RL scheduling improve over a conventional heuristic after training?"),
on this generator and simulator: **yes over the conventional `FCFS-EAT` (~18% shorter simulated makespan), no over
the strong `HEFT`**, which the trained policy matches within the predeclared ±2% band but trails by about 1% (p =
6.8e-6), seed-dependently, while costing ~16× its scheduling time plus ~16 minutes of training per policy.

**Negative or unexpected results**

1. Primary: RL significantly *worse* than HEFT on `test_id` (small effect); the "matches" verdict is a band
   statement, not equality.
2. One of three seeds is clearly worse (2.8%); results depend on the training seed.
3. Degradation with more processors (m = 8, 16) and on fork-join structure; does not generalise to `ood_procs` or
   `ood_struct`.
4. Strong reliance on HEFT-like features (ablation +3.7 points).
5. Training had not converged at 3,000 updates; no tuning was done by design (decision 2), so the result reflects the
   predeclared settings, not RL's ceiling.

**Positive or notable:** RL beat HEFT with 2 processors (ρ 0.973), on the heterogeneous class (0.984) and on unseen
larger DAGs (n = 400, ρ 0.983).

**Limitations**

- Simulation only (no communication costs, exact estimates); no real-hardware claim.
- Three training seeds characterise training variance only roughly.
- `ood_cv` has 10 instances; other OOD cells 20–40.
- The S02 test population was fixed in the approved plan, not in the original methodology; the S01 population was
  never predeclared (S01 report §B.2).
- Outstanding, unchanged: findings from Batches 1–3 and 7 unavailable (S03 objective unmet); faculty approval of
  scope (one person, S01–S03) and tooling; literature review not started; `Student_ID` / `Batch_ID` placeholders.

**Reproduce from the preserved raw data**

```
python3 -m pytest -q
python3 -m schedlab analyze results/raw/20261017T115054Z-s02_final-898ee9e1
PYTHONPATH=. python3 provenance/s02_final/verify_campaign.py results/raw/20261017T115054Z-s02_final-898ee9e1 results/derived/20261017T115054Z-s02_final-898ee9e1 provenance/s02_final/verify_campaign_result.json
```

Outputs: `results/derived/<campaign>/` (`master.csv`, `summary_by_algorithm.csv`, `timing_by_size.csv`,
`s02_paired.csv`, `s02_generalization.csv`, `s02_overhead.csv`) and `results/figures/<campaign>/` (G1, G4 training
reward and validation ratio, G5 makespan vs method, G6 generalization; PDF, SVG, source CSVs). Hashes:
`provenance/s02_final/POSTPROCESSING_PROVENANCE.json`.

**Status.** Technical: campaign complete and verified (13,500 / 13,500 rows, 0 failures, all checks, 238 tests,
figures reproducible, provenance recorded, AC power throughout). Scientific: RL improves over the conventional
heuristic but not over HEFT. S01 and S03 data, all pilots and all models preserved. Awaiting your review.
