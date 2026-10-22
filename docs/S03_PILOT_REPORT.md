# S03 Adaptive Workload-Aware Scheduling — Pilot Report

2026-10-17. Pilot only: **no test split was evaluated, and the full S03 campaign has not been run.** All quality
numbers are simulated makespan on the `val` split, which was also used to choose the tree depth and `SBS`, so they
are in-sample for those choices. They are pipeline evidence, not results.

## 1. What was built

- `schedlab/adaptive.py`: the nine workload features of ALGORITHM_DESIGN §5.2; labels (lowest-makespan heuristic,
  ties to the cheaper one); a depth ≤ 4 decision tree fitted on `train` with sample weight `(worst − best) / best`;
  depth, `SBS` and the §5.7 contingency chosen on `val`; the novelty guard (train range ± 10% of its width, fallback
  to `SBS`); the methods `ADAPTIVE`, `ADAPTIVE-TOP2`, `ADAPTIVE-NOGUARD`, `RANDOM-SELECT`, `TRY-ALL`; a leakage guard
  that refuses training instances, and refuses test instances that were used for selection.
- Runner: `[s03]` config section, `model_id` per row, model and its report in `manifest.json`, a new raw side file
  `decisions.csv` (selected policy, candidates, fallback, novelty, the nine features per S03 run). `runs.csv` schema
  unchanged.
- Analysis: `s03_robustness.csv`, `s03_paired.csv` (with gap closed and its bootstrap CI), `s03_selection_by_class.csv`;
  figures G7 (feature vs selected policy), G8 (adaptive vs fixed: quality and measured time), G9 (regret heatmap,
  robustness across workloads); S03 campaign checks.
- CLI: `python3 -m schedlab train-selector --config <cfg>`.
- Fixed in passing: `TRY-ALL` computed features it never used, which showed up as a fake "decision time" in G8. The
  first two pilot runs (`…075426Z…`, `…075435Z…`) are kept as superseded; their makespans are identical to the final
  pilot's.

## 2. Commands and tests

| Command | Result |
|---|---|
| `python3 -m pytest -q` | 215 passed, 0 failed, 0 skipped (14 new in `tests/test_adaptive.py`) |
| `python3 -m schedlab train-selector --config configs/s03_pilot.toml` | model `results/models/s03_selector_v1`, `model_id 820ba281844c513e`; retraining from scratch reproduces the same id |
| `python3 -m schedlab run --config configs/s03_pilot.toml` (twice) | `20261017T075602Z-s03_pilot-eeb28bc3` and `…075611Z…`: 5,940 rows each, 0 not ok, 7.6 s and 7.8 s |
| `python3 -m schedlab analyze results/raw/20261017T075602Z-s03_pilot-eeb28bc3` | campaign checks: all passed |

S01 is untouched: its raw-file hashes match `provenance/s01_final/POSTPROCESSING_PROVENANCE.json`, and `check()`
with the current code still passes on the S01 campaign and the GA pilot. The analysis code hash is now
`df2c795bd4badadd` (S01 was post-processed with `a23e460502a1baf6`; S01 outputs were not regenerated).

## 3. Predeclared pilot criteria (EXPERIMENTAL_METHODOLOGY §7.3)

| # | Result | Evidence |
|---|---|---|
| S03-P1 | **Pass.** P1 validity, P2 lower bound, P5 pipeline, P6 completeness via `check()`; P4: the two runs have identical makespan, busy-time, seed and model columns | `analyze` output; comparison of the two `runs.csv` |
| S03-P2 (= P10) | **Pass.** Selector trains; every decision is a portfolio heuristic; `SBS`–`VBS` gap on `val` = **0.663%**, recorded in `model.json` | `model.json`, `_check_s03` |
| S03-P3 | **Pass.** S03 results equal the selected heuristic run directly; `TRY-ALL` = per-instance best; the one fallback picked `SBS`; NOGUARD never fell back; model ids consistent; no training instance evaluated | `_check_s03` |
| S03-P4 | **Pass.** Training hashes = `train` (1,080), selection hashes = `val` (180), 0 overlap with the 450 test hashes | hash comparison |
| S03-P5 | **Pass (projection).** 180 instances took 7.6 s; 450 test instances, some with n = 400, project to well under 5 minutes | pilot wall time |
| S03-P6 | **Triggered — blocks the full campaign.** Gap 0.663% < 2%, so §5.7 says to add `GA` (1,000 evaluations) to the portfolio. The design does not say how GA's cost is traded against its gain (see §5) | `model.json` |

## 4. Pilot observations (in-sample on `val`; not results)

Trained selector: depth 2 (val mean regret by depth: 1 → 0.663%, **2 → 0.526%**, 3 → 1.04%, 4 → 1.13%, unlimited →
2.11%). Rules: `het_machine ≤ 0.48` → `HEFT`; else `work_cv ≤ 0.63` → `MINMIN`, else `HEFT`. It picked `HEFT` on 171
and `MINMIN` on 9 of 180 instances. Training labels: `HEFT` 763 of 1,080, `FCFS-EAT` 137, `MINMIN` 70, `FCFS-EFT` 68,
`LPT-EFT` 37, `SPT-EFT` 5. Removing the structure features changed nothing (the tree does not use them); removing the
heterogeneity features gives the same `val` regret as always choosing `HEFT` (0.663%).

| Method (val, 180) | Cmax/LB mean | Regret mean | Regret p95 | Share regret ≤ 5% | Worst class (mean regret) | Median time per call (s) |
|---|---|---|---|---|---|---|
| `ADAPTIVE` | 1.1748 | 0.53% | 3.34% | 96.1% | heterogeneous (1.34%) | 0.00055 (decision 0.00016) |
| `ADAPTIVE-TOP2` | 1.1710 | 0.21% | 0.71% | 98.3% | heterogeneous (0.62%) | 0.00081 |
| `SBS` = `HEFT` | 1.1765 | 0.66% | 5.89% | 94.4% | heterogeneous (1.89%) | 0.00038 |
| `TRY-ALL` (= `VBS`) | 1.1681 | 0 | 0 | 100% | — | 0.0026 |
| `RANDOM-SELECT` | 1.3899 | 18.7% | 53.5% | 29.4% | irregular_hetero (36.9%) | 0.00039 |

`ADAPTIVE` vs `SBS`: mean paired improvement 0.13% (ratio CI 0.9972–1.0000), better / tie / worse 6 / 171 / 3, gap
closed 0.20 (CI 0.007–0.39); the Wilcoxon p (0.14) is computed by the pipeline but is in-sample and is not evidence.
`ADAPTIVE-TOP2` closed 0.66 of the gap at about 2× HEFT's time; `TRY-ALL` closes all of it at about 7×.

What this already says: on this workload generator `HEFT` is the label for 71% of training instances and within
0.66% of the per-instance best on `val`, so there is very little for any selector over these six heuristics to gain.

## 5. The triggered contingency (S03-P6) — original analysis, kept as written

§5.7 was predeclared: if the `SBS`–`VBS` gap on `val` is under 2%, add `GA` (1,000 evaluations) to the portfolio so
that the selector decides when the optimiser is worth calling. It triggered. The design leaves one thing open, and it
cannot be filled in without a choice: GA seeded with `HEFT`, `MINMIN` and `FCFS-EAT` is never worse than those
seeds, so with makespan-only labels GA would be the label almost everywhere and the "adaptive" selector would collapse
into "always run GA". A useful label must charge GA's ~1,500× extra time, and makespan (`sim_tu`) and time (s) have no
defensible exchange rate (S01 §D).

Options (none implemented):

1. **Keep the six-heuristic portfolio; record the contingency as triggered and not applied**, with the reason above.
   S03 then answers its research question honestly with "little to gain on these workloads", and S01 already covers
   the optimiser trade-off. *Recommended: no invented parameters, nothing tuned after the fact.*
2. **Add `GA-1000` with a threshold label**: label GA only where its train-split gain over the best heuristic exceeds
   a margin θ, θ chosen on `val`. Adds a parameter whose value is a judgement about cost.
3. **Add `GA-1000` with an explicit hypothetical τ** (seconds per `sim_tu`) and label by `Cmax·τ + T_sched`. The
   result would hold only for that assumed τ.

## 6. Limitations

- **Batches 1–3 and 7**: no findings are available, none were invented. Features come from those batches' topics
  only, so the manual's objective "use findings from Batches 1–3 and 7" is **not** satisfied. Faculty clarification or
  the actual findings are needed.
- Pilot quality numbers are in-sample for depth and `SBS` (both chosen on the same `val` instances).
- Decision overhead (~0.1–0.2 ms) is mostly scikit-learn call overhead on a single sample, measured on battery power.
- Simulation only (no OpenMP/CUDA, which the manual lists for S03); no real-hardware claim.
- Unchanged blockers: identifiers, faculty approval, literature review.

## 7. Next steps (superseded by §8.6)

## 8. Contingency extension: `GA-1000` member with a threshold label (your decision of 2026-10-17, option 2)

The six-heuristic selector (`s03_selector_v1`, `820ba281844c513e`), its config `s03_pilot.toml` and its pilot are
unchanged and remain the **primary** S03 design. Everything in this section is the separately labelled
**contingency extension**. Rules were written into EXPERIMENTAL_METHODOLOGY §7.4 before any extension data were
computed.

### 8.1 Trigger vs label margin (two different thresholds)

- **Trigger (S03, predeclared in ALGORITHM_DESIGN §5.7):** add GA if the `val` gap `mean_i(C_SBS,i / C_VBS,i − 1)`
  over the six heuristics is < 2%. Evaluated on the 180 `val` instances with `SBS` = `HEFT`: 0.663% → triggered.
  Source data: `results/models/s03_selector_v1/model.json`, repeated in the extension's `model.json` `trigger` field.
- **Label margin θ (new, S03 only):** label `GA-1000` where it beats the best heuristic by more than θ (strict).
  θ ∈ {0, 0.5%, 1%, 2%, 5%}, chosen on `val` by GA-call efficiency (§7.4).
- **Not used:** S01's 1.17% GA improvement (test split, 6,000 evaluations) plays no role in either.

### 8.2 What was changed

- `schedlab/adaptive.py`: `GA-1000` member = S01's GA with the locked `s01_final.toml` settings and
  `max_evals = 1000`; `theta_labels`, `ga_table`, `train_selector_ga` (same features, guard, `SBS`, train/val
  instances as the base; refuses anything else); methods `ADAPTIVE-GA` and `GA-1000` (always GA), both seeded 0, 1, 2.
  Measured timings are stored in `model.json` but excluded from the hashed pickle, so model ids depend on data only.
- Runner: optional `[s03] model_ga`; both models in `manifest.json` with their role; extension rows carry the
  extension's `model_id`; S03 GA calls write no S01 trace.
- Analysis: extension checks (members, GA ≤ its seeds, exactly 1,000 evaluations, per-model ids, leakage over both
  models); `s03_ga_extension_overhead.csv`; G8 now shows **mean** as well as median time per call.
- CLI: `train-selector --ga`. Config: `configs/s03_pilot_ga.toml` (= `s03_pilot.toml` + the two methods + `model_ga`).
- Tests: 6 new (221 total, all pass).

### 8.3 Model identifiers

| Model | id | Status |
|---|---|---|
| `s03_selector_v1` | `820ba281844c513e` | primary six-heuristic selector, unchanged; retraining reproduces the id |
| `s03_selector_ga_v1` | `870ab53c17d01909` | **superseded**: its pickle contained measured GA times, so a retrain gave a different id (`32e2dc20…`) although tree, labels and θ table were identical |
| `s03_selector_ga_v2` | `6d83fac40cb5c6ed` | **current extension**; same tree and θ as v1; retraining reproduces the id exactly |

### 8.4 θ selection on `val` (in-sample) and the resulting selector

| θ | depth | GA labels train / val | GA calls on val | val mean regret vs six-VBS | GA-call efficiency |
|---|---|---|---|---|---|
| 0 | 4 | 416 / 62 | 67 | −0.216% | 1.31e-4 |
| 0.5% | 3 | 171 / 26 | 29 | −0.099% | 2.63e-4 |
| 1% | 1 | 125 / 21 | 31 | −0.066% | 2.35e-4 |
| **2%** | 4 | 87 / 15 | 14 | 0.196% | **3.33e-4** |
| 5% | 2 | 32 / 3 | 0 | 0.542% | — (no call) |

`SBS` regret on `val`: 0.663%. θ = 2% maximises gain per GA call; θ = 0 would give the best quality but call GA on
67 of 180 instances. On `val`, `GA-1000` beat the best heuristic on 31% of instances, by 0.35% on average.

### 8.5 Extension pilot results (`results/raw/20261017T082349Z-s03_pilot_ga-8d8bac5a`, `val`, in-sample)

Integrity: 7,020 rows, 0 not ok, campaign checks all passed; the P4 repeat (`…082502Z…`) is identical in simulated
columns, decisions and model ids; every row of the original methods is identical to the primary pilot
(`…075602Z…`); the v2 pilot's simulated columns equal the v1 extension pilot's; extension model hashes = `train` /
`val` exactly, 0 test overlap.

| Method | Cmax/LB mean | Regret mean (vs six-VBS) | Regret p95 | Worst class (mean regret) | vs `SBS`: paired impr. (better/tie/worse) | Gap closed (95% CI) |
|---|---|---|---|---|---|---|
| `ADAPTIVE` (primary) | 1.1748 | 0.526% | 3.34% | heterogeneous (1.34%) | 0.13% (6/171/3) | 0.20 (0.007–0.39) |
| `ADAPTIVE-GA` (extension) | 1.1707 | 0.195% | 2.73% | regular (0.48%) | 0.44% (16/162/2) | 0.69 (0.34–1.05) |
| `GA-1000` (always GA) | 1.1625 | −0.454% | 0.02% | irregular (−0.01%) | 1.07% (102/78/0) | 1.66 (1.30–2.12) |
| `TRY-ALL` | 1.1681 | 0 | 0 | — | 0.63% (52/128/0) | 1 |
| `SBS` = `HEFT` | 1.1765 | 0.663% | 5.89% | heterogeneous (1.89%) | — | — |

Gap closed above 1 means better than the six-heuristic oracle, which GA can be. `ADAPTIVE-GA` called GA on 42 of 540
runs (14 instances × 3 seeds); seed-to-seed spread, mean 0.22% (`ADAPTIVE-GA`), 0.58% (`GA-1000`).

**Overhead (measured seconds, battery power; simulated quality reported separately):**

| n | `ADAPTIVE` mean / median time per call | `ADAPTIVE-GA` mean / median | `GA-1000` mean | GA-call share of `ADAPTIVE-GA` | mean-time ratio vs HEFT: `ADAPTIVE` / `ADAPTIVE-GA` / `GA-1000` |
|---|---|---|---|---|---|
| 50 | 0.27 / 0.26 ms | 5.7 / 0.26 ms | 42 ms | 13% | 1.8 / 38 / 280 |
| 100 | 0.55 / 0.54 ms | 5.0 / 0.51 ms | 90 ms | 5% | 1.5 / 13 / 243 |
| 200 | 1.39 / 1.28 ms | 10.6 / 1.25 ms | 203 ms | 5% | 1.3 / 10 / 192 |

The median call of `ADAPTIVE-GA` costs the same as `ADAPTIVE` (GA is not called); its mean is 10–38× HEFT because
of the GA calls. **[hypothetical]** Break-even against `ADAPTIVE` (methodology §5.3, ∞ where no gain, median over all
instances): ∞ for `ADAPTIVE-GA` (it improves on `ADAPTIVE` on only 7–12% of instances), 0.09–1.27 s per `sim_tu` for
`GA-1000`. No real conversion factor is known, so whether the GA's simulated gain justifies its measured cost is not
decided here: per call, the extension buys about 0.3% mean simulated makespan for about 10× HEFT's mean time;
always-GA buys about 1.1% for about 200–280×.

**Negative or notable findings.** Always calling GA beat every selector on simulated quality, and beat the
six-heuristic oracle; the extension selector sits between `ADAPTIVE` and `GA-1000` on both quality and cost. The
extension was worse than `SBS` on 2 instances. The extension tree is depth 4 with splits on six features and is less
interpretable than the depth-2 base tree. All numbers are in-sample on `val` (θ, depths and `SBS` were chosen there).

### 8.6 Pilot status and next steps

Extension pilot: S03-P1 (incl. P4), P3, P4 pass; P5: 180 `val` instances took 71.5 s, so 450 test instances (some
n = 400, where GA-1000 takes ~0.5 s) project to roughly 5–10 minutes (projection). The full S03 campaign has **not**
been run. Proposed, for your review: `configs/s03_final.toml` = `s03_pilot_ga.toml` with splits `test_id`, `test_ood`,
both models locked (`820ba281844c513e` primary, `6d83fac40cb5c6ed` extension); primary comparison unchanged
(`ADAPTIVE` vs `SBS`, `test_id`); extension results secondary. S02 not started.
