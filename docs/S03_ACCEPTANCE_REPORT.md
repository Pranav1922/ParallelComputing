# S03 Adaptive Workload-Aware Scheduling — Final Campaign Acceptance Report

Campaign `20261017T083329Z-s03_final-b8e5be9a`, run once on 2026-10-17. All quality numbers are **simulated
makespan** (`sim_tu`) from the list-scheduling simulator; times are *measured seconds* on one battery-powered laptop.
No real-hardware speedup is claimed. Validation-pilot numbers are not evidence of generalization and are quoted only
where the contrast with test results is informative.

---

## A. Campaign summary and integrity [verified]

| Item | Value | Source |
|---|---|---|
| Locked config | `configs/s03_final.toml` (sha256 `2a4698c8…2f40`, hash `b8e5be9a`); identical to the reviewed `s03_pilot_ga.toml` except name, splits and pinned model ids (lock test) | `provenance/s03_final/EXECUTION_PROVENANCE.md` |
| Models | primary `s03_selector_v1` = `820ba281844c513e`; extension `s03_selector_ga_v2` = `6d83fac40cb5c6ed`; both fitted on `train`, selected on `val`; not retrained, re-selected or retuned | manifest `models` |
| Splits | `test_id` 360 (4 classes × n {50, 100, 200} × m {2, 4, 8} × 10), `test_ood` 90 (`ood_size` n = 400 / m = 4 × 4 classes, `ood_procs` m = 16 × 2, `ood_struct` fork-join × 2, `ood_cv` CV 3.0 × 1; 10 each) | `verify_campaign_result.json` |
| Methods | 13: six heuristics; `ADAPTIVE`, `ADAPTIVE-TOP2`, `ADAPTIVE-NOGUARD`, `TRY-ALL` (3 timing repeats); `RANDOM-SELECT`, `ADAPTIVE-GA`, `GA-1000` (seeds 0, 1, 2) | runs.csv |
| Run | 08:33:29 → 08:37:27 UTC, 237.25 s wall (projection was 4–10 min); single worker; battery 56% at launch | manifest |
| Rows | expected 450 × 39 = **17,550**; actual **17,550** (`test_id` 14,040, `test_ood` 3,510) | verify |
| Failed / timeout / invalid / duplicate / missing | **0 / 0 / 0 / 0 / 0** | verify, manifest |
| Independent check (`provenance/s03_final/verify_campaign.py`, no `analysis.py`) | 0 problems: config and per-method hashes; model ids per row; 3 repeats or seeds per (instance, method); decisions cover every S03 run; all six heuristics re-run from scratch reproduce every raw makespan; every `ADAPTIVE`, `ADAPTIVE-NOGUARD` and `ADAPTIVE-GA` decision re-derived from the saved models matches `decisions.csv`; primary statistics recomputed directly and equal to `s03_paired.csv` | `verify_campaign_result.json` |
| Campaign checks (`analyze`) | all passed (incl. S03 invariants: results equal the selected heuristic, `TRY-ALL` = per-instance best, GA calls ≤ their seeds with exactly 1,000 evaluations, fallbacks → `SBS`, no training instance evaluated) | analyze output |
| Tests | `python3 -m pytest -q` → **223 passed, 0 failed, 0 skipped** | provenance |
| Figures | G1, G7, G8 (quality and times), G9 recomputed from their saved CSVs: all match | `figure_reproducibility_check.txt` |
| Timing outliers | 448 rows flagged (Q3 + 3·IQR rule), retained | master.csv |
| Code | execution and analysis hash identical, `a7017e19fb7d8d13`; snapshot preserved | provenance |

No result from `test_id` or `test_ood` was used to train, select, tune or change anything.

---

## B. Predeclared primary comparison: `ADAPTIVE` vs `SBS` on `test_id` [verified]

`SBS` = `HEFT`, the fixed heuristic with the lowest mean `Cmax/LB` on `val` (fixed in model `820ba281844c513e`).
Test: Wilcoxon signed-rank on paired makespans, two-sided, zero differences dropped; member of the three-test Holm
family (S01 GA vs best heuristic, this test, S02 RL vs HEFT).

| Population | n (non-zero) | Mean paired impr. `(C_SBS − C_AD)/C_SBS` | 95% bootstrap CI (ratio) | better / tie / worse | Gap closed (95% CI) | Wilcoxon p |
|---|---|---|---|---|---|---|
| **`test_id` (primary)** | 360 (18) | **−0.016%** | 0.9991 – 1.0010 | 6 / 342 / 12 | **−0.03** (−0.30 – 0.19) | **0.78** |
| `test_ood` (secondary) | 90 (0) | 0 | 1 – 1 | 0 / 90 / 0 | 0 | not computable (all ties) |

**Result: no detectable difference.** The adaptive selector made a different choice from `SBS` on 18 of 360
in-distribution instances (all `MINMIN` on the heterogeneous class), was better on 6 and worse on 12, and closed none
of the gap to the per-instance oracle. H3 ("the adaptive selector has lower mean normalised makespan than the single
best fixed policy"; gap-closed CI above 0) **is not supported**: the CI includes 0. With the Holm family applied, the
test is non-significant at any threshold. On the validation pilot the same comparison had looked mildly positive
(+0.13%, gap closed 0.20, in-sample); that did not carry over to held-out data.

Reference points on `test_id`: `SBS` regret vs the per-instance best heuristic is 0.48% (mean), so even a perfect
selector over these six heuristics could gain at most 0.45% (`TRY-ALL` vs `SBS`: +0.45%, 70 / 290 / 0). The
best fixed policy in hindsight on `test_id` is also `HEFT`, so `BEST-FIXED-HINDSIGHT` = `SBS`.

---

## C. All methods (secondary and exploratory; no p-values)

### C.1 `test_id` (360 instances)

| Method | Cmax/LB mean | Speedup mean | Regret mean | Regret p95 | Share regret ≤ 5% | Worst class (mean regret) | Median time / call (s) | Median decision (s) |
|---|---|---|---|---|---|---|---|---|
| **`ADAPTIVE`** (primary) | 1.181 | 3.502 | 0.491% | 3.15% | 96.1% | heterogeneous (0.94%) | 0.00054 | 0.00015 |
| `SBS` = `HEFT` | 1.180 | 3.502 | 0.480% | 3.19% | 96.4% | heterogeneous (0.90%) | 0.00037 | — |
| `ADAPTIVE-NOGUARD` | 1.181 | 3.502 | 0.491% | 3.15% | 96.1% | heterogeneous (0.94%) | 0.00051 | 0.00012 |
| `ADAPTIVE-TOP2` | 1.177 | 3.510 | 0.184% | 0.39% | 98.6% | irregular_hetero (0.37%) | 0.00081 | 0.00012 |
| `TRY-ALL` (= `VBS`) | 1.175 | 3.513 | 0 | 0 | 100% | — | 0.0025 | — |
| `RANDOM-SELECT` | 1.359 | 3.094 | 15.4% | 47.9% | 28.1% | irregular_hetero (22.9%) | 0.00038 | — |
| `ADAPTIVE-GA` (extension) | 1.179 | 3.504 | 0.372% | 3.15% | 96.4% | irregular_hetero (0.86%) | 0.00053 | 0.00013 |
| `GA-1000` (always GA) | 1.169 | 3.522 | −0.422% | 0 | 99.7% | irregular (−0.02%) | 0.090 | — |
| `FCFS-EFT` | 1.252 | 3.298 | 6.31% | 21.5% | 55.3% | irregular_hetero (11.7%) | 0.00030 | — |
| `LPT-EFT` | 1.318 | 3.109 | 11.8% | 31.7% | 28.6% | irregular_hetero (14.8%) | 0.00028 | — |
| `MINMIN` | 1.391 | 2.959 | 18.7% | 52.9% | 26.7% | irregular (32.8%) | 0.00097 | — |
| `SPT-EFT` | 1.483 | 2.761 | 26.3% | 64.4% | 6.1% | irregular (38.0%) | 0.00029 | — |
| `FCFS-EAT` | 1.581 | 2.859 | 31.7% | 104.9% | 39.7% | irregular_hetero (67.1%) | 0.00029 | — |

Regret = `C_alg / C_VBS − 1`, `VBS` = per-instance best of the six heuristics (negative for GA, which can beat it).
Speedup baseline: serial execution on the best single simulated processor. Source: `s03_robustness.csv`.

Paired vs `SBS` on `test_id` (`s03_paired.csv`): `ADAPTIVE-TOP2` +0.28% (56 / 304 / 0, gap closed 0.59, CI
0.40–0.76); `ADAPTIVE-GA` +0.10% (22 / 332 / 6, gap closed 0.25, CI −0.20–0.66); `GA-1000` +0.87% (199 / 161 / 0,
gap closed 1.91); `RANDOM-SELECT` −14.9%. `ADAPTIVE` vs the other fixed heuristics: `FCFS-EAT` +18.3%
(308 / 14 / 38), `FCFS-EFT` +5.0% (290 / 14 / 56), `LPT-EFT` +9.4%, `SPT-EFT` +18.9%, `MINMIN` +13.6% — large
because those policies are weak on this generator, not because selection helps: `HEFT` alone gets the same.

### C.2 `test_ood` — unseen workloads (90 instances, secondary)

| Method | Cmax/LB mean | Regret mean | Regret p95 | Worst OOD cell (mean regret) | Median time / call (s) |
|---|---|---|---|---|---|
| `ADAPTIVE` | 1.146 | 0.233% | 1.86% | ood_size/heterogeneous (1.74%) | 0.0016 |
| `SBS` = `HEFT` | 1.146 | 0.233% | 1.86% | ood_size/heterogeneous (1.74%) | 0.0013 |
| `ADAPTIVE-TOP2` | 1.144 | 0.137% | 1.05% | ood_size/heterogeneous (1.13%) | 0.0026 |
| `TRY-ALL` | 1.142 | 0 | 0 | — | 0.0134 |
| `ADAPTIVE-GA` | 1.146 | 0.233% | 1.86% | ood_size/heterogeneous (1.74%) | 0.0015 |
| `GA-1000` | 1.142 | −0.051% | 0 | ood_size/heterogeneous (0.13%) | 0.202 |

On unseen workloads `ADAPTIVE` and `ADAPTIVE-GA` both behaved exactly like `SBS` (90 / 90 ties): the novelty guard
sent most of them to `SBS`, and on the rest the tree also chose `HEFT` (§D). The fixed heuristics' weaknesses grow
out of distribution: `FCFS-EAT` mean regret 39.9%, `SPT-EFT` 65.0% and `MINMIN` 63.4% on `ood_cv` (G9).

---

## D. Policy behaviour and the novelty guard [verified, `s03_selection_by_class.csv`, `decisions.csv`]

| Split / group | `ADAPTIVE` picks (instances) | Guard fired | `ADAPTIVE-GA` picks |
|---|---|---|---|
| `test_id` heterogeneous (90) | HEFT 72, MINMIN 18 | 0 | HEFT 74, GA 15, MINMIN 1 |
| `test_id` irregular (90) | HEFT 90 | 0 | HEFT 90 |
| `test_id` irregular_hetero (90) | HEFT 90 | 1 | HEFT 77, GA 9, FCFS-EFT 4 |
| `test_id` regular (90) | HEFT 90 | 0 | HEFT 85, FCFS-EAT 5 |
| `ood_size` (40) | HEFT 40 | **40 (100%)** | HEFT 40 (guard) |
| `ood_struct` (20) | HEFT 20 | **19 (95%)** | HEFT 20 |
| `ood_procs` (20) | HEFT 20 | 0 | HEFT 20 |
| `ood_cv` (10) | HEFT 10 | 0 | HEFT 10 |

The guard (training range ± 10%) fired on 0.28% of `test_id` runs and 65.6% of `test_ood` runs: every n = 400
instance (outside the `log_n` range) and 19 of 20 fork-join instances. Without the guard, the tree also picked
`HEFT` on all 90 OOD instances (`ADAPTIVE-NOGUARD`), so on this test the guard changed nothing in makespan; whether
it protects against harmful extrapolation is not demonstrated here. Tree rules (G7): `het_machine ≤ 0.48` → `HEFT`;
else `work_cv ≤ 0.63` → `MINMIN`, else `HEFT`.

---

## E. Contingency extension: `ADAPTIVE-GA` and `GA-1000` (secondary)

Trigger: ALGORITHM_DESIGN §5.7 (`val` SBS–VBS gap 0.663% < 2%). θ = 2% chosen on `val` by GA-call efficiency
(EXPERIMENTAL_METHODOLOGY §7.4). Unrelated to S01's 1.17% result.

- `ADAPTIVE-GA` vs `ADAPTIVE`: `test_id` +0.11% mean (26 / 325 / 9); `test_ood` 0 (90 ties: the guard and the tree
  never called GA there). Vs `SBS` on `test_id`: +0.10%, gap-closed CI −0.20–0.66 (includes 0). On `val` the same
  comparison had been +0.44% (in-sample).
- `GA-1000` (always GA): best quality of all methods on both splits (`test_id` +0.87% vs `SBS`, never worse; `test_ood`
  +0.28%, never worse), as expected for an optimiser seeded with three of the heuristics.

**Overhead, measured seconds** (`s03_ga_extension_overhead.csv`; simulated quality reported separately):

| n | `ADAPTIVE` mean time / call | `ADAPTIVE-GA` mean / median | GA-call share | `GA-1000` mean | mean-time ratio vs HEFT (`ADAPTIVE` / `ADAPTIVE-GA` / `GA-1000`) | `ADAPTIVE-GA` / `GA-1000` paired impr. vs `ADAPTIVE` |
|---|---|---|---|---|---|---|
| 50 | 0.28 ms | 4.1 / 0.26 ms | 9.2% | 41 ms | 1.9 / 28 / 282 | +0.25% / +1.47% |
| 100 | 0.54 ms | 6.7 / 0.51 ms | 6.7% | 87 ms | 1.5 / 19 / 244 | +0.18% / +0.64% |
| 200 | 1.42 ms | 5.5 / 1.29 ms | 2.1% | 203 ms | 1.3 / 5.1 / 186 | −0.12% / +0.38% |
| 400 | 3.67 ms | 3.6 / 3.6 ms | 0% | 521 ms | 1.1 / 1.1 / 155 | 0 / +0.41% |

**[hypothetical]** Break-even τ\* against `ADAPTIVE` (∞ where no gain; median over all instances): ∞ for
`ADAPTIVE-GA` at every size (it beats `ADAPTIVE` on at most 10% of instances); for `GA-1000` 0.05 s/`sim_tu` (n = 50),
0.26 (n = 100), ∞ at n = 200 and 400 (fewer than half the instances improve). No calibration between simulated time
units and seconds exists, so no real-world break-even is claimed. Measured facts only: the extension buys about 0.1%
mean simulated makespan in-distribution for 5–28× HEFT's mean time; always-GA buys about 0.4–1.5% for 155–282×.

---

## F. Findings, limitations and status

**Answer to the research question** ("Can an adaptive scheduler outperform a fixed scheduling policy across diverse
workloads?"), on this generator and simulator: **not against the best fixed policy.** The adaptive selector beat
every weak fixed policy by large margins, but `HEFT`, chosen on validation data, was within 0.48% of the per-instance
oracle in-distribution and 0.23% out of distribution, and the selector did not improve on it (−0.016%, p = 0.78). The
only methods that improved on `SBS` did so by spending more scheduling time: running the top two heuristics (+0.28%,
about 2× HEFT's median time), all six (+0.45%, about 7×), or calling GA every time (+0.87%, 155–282× HEFT's mean time
depending on n).

**Negative or unexpected results**

1. Primary comparison null; gap closed −0.03 (CI −0.30–0.19); 12 of the 18 non-`HEFT` choices were worse.
2. Validation-pilot gains (+0.13% primary, +0.44% extension) did not hold on test data: in-sample optimism.
3. On unseen workloads the selector degenerated to `SBS` (guard on 66%, tree picked `HEFT` on the rest).
4. The extension's θ-selected GA calls helped little in-distribution and not at all out of distribution.
5. 448 timing outliers flagged (battery operation, sub-millisecond calls).

**Limitations**

- **Batches 1–3 and 7: unavailable.** No findings from them were used or invented; features derive from those
  batches' topics only. The manual's objective "use findings from Batches 1–3 and 7" is **not met**; faculty
  clarification or the actual findings are required.
- Simulation only; the manual lists "OpenMP/CUDA as appropriate" for S03. No real-hardware gain is shown. Needs
  faculty acceptance.
- One workload generator; the dominance of `HEFT` is a property of it (no communication costs, the cost model used).
  Other generators or communication-heavy DAGs could give selection more room.
- Measured times on battery power; decision time (~0.1–0.2 ms) is mostly scikit-learn per-call overhead.
- `test_ood` has 10 instances per cell; `ood_cv` is one cell.
- The Holm family is still incomplete (S02 not run).

**Reproduce from the preserved raw data**

```
python3 -m pytest -q
python3 -m schedlab analyze results/raw/20261017T083329Z-s03_final-b8e5be9a
PYTHONPATH=. python3 provenance/s03_final/verify_campaign.py results/raw/20261017T083329Z-s03_final-b8e5be9a results/derived/20261017T083329Z-s03_final-b8e5be9a provenance/s03_final/verify_campaign_result.json
```

Outputs: `results/derived/<campaign>/` (`master.csv`, `summary_by_algorithm.csv`, `timing_by_size.csv`,
`s03_robustness.csv`, `s03_paired.csv`, `s03_selection_by_class.csv`, `s03_ga_extension_overhead.csv`) and
`results/figures/<campaign>/` (G1, G7 feature vs selected policy, G8 adaptive vs fixed, G9 robustness heatmap; PDF,
SVG and source CSVs). Hashes: `provenance/s03_final/POSTPROCESSING_PROVENANCE.json`.

**Submission blockers (unchanged):** `Student_ID` / `Batch_ID` placeholders; faculty approval of scope (one person,
S01–S03) and tooling; literature review not started; Batches 1–3 and 7 findings unavailable.

**Status.**

- **Technical acceptance — accepted by the user on 2026-10-17.** Campaign complete and verified (17,550 / 17,550
  rows, 0 failures, all checks, 223 tests, figures reproducible, provenance recorded). This acceptance concerns the
  correctness of the experiment and analysis only.
- **Scientific outcome — not a success for the primary hypothesis.** `ADAPTIVE` (the primary method) did **not**
  outperform `SBS`: −0.016% on `test_id`, p = 0.78, gap-closed CI including 0. H3 is not supported. `ADAPTIVE-GA`
  remains a separate contingency extension and does not replace the primary method or its result.
- **Outstanding:** findings from Batches 1–3 and 7 unavailable (the manual's first S03 objective is not met);
  faculty approval of scope and tooling; literature review not started; identifiers are placeholders.
- S01 and S03 campaigns are complete and are not to be modified or rerun; all raw data, pilots, models and provenance
  are preserved.
