# S02 Reinforcement-Learning Scheduling — Pilot Report

2026-10-17. Pilot only. **No held-out test or unseen-workload instance was evaluated**; the full three-seed training
and the final campaign have not been run. `val` is used for checkpoint selection, so every `val` number here is a
model-development diagnostic, not evidence of performance or generalization. Makespans are simulated (`sim_tu`);
times are measured seconds (mains power).

## 1. What was implemented

| File | Content |
|---|---|
| `schedlab/rl.py` (new) | 12 candidate features over valid `(ready task, processor)` pairs; insertion placement via the existing `ScheduleBuilder` (decision 1); policy MLP 12 → 64 → 64 → 1; rollouts (greedy, sampled, HEFT-following); terminal reward `G = −Cmax/LB`, HEFT-relative advantage, batch standardisation; REINFORCE with entropy bonus and gradient clipping, predeclared settings, no tuning (decision 2); best-`val`-ρ checkpointing (update 0 included); predeclared BC fallback; `RL-NOHEFTFEAT` ablation flag; training stream `train` split, indices ≥ 1000, hash-checked against `val`/`test_id`/`test_ood`; model id = sha256 of the weights only; leakage refusal at inference; `torch.use_deterministic_algorithms(True)`, one thread |
| `schedlab/runner.py` | `[s02] models` / `model_ids`: each policy is its own deterministic method (training seeds and ablation stay separate), ids pinned; power source recorded at start and end of every campaign (decision 3) |
| `schedlab/analysis.py` | S02 checks (model ids, no training-stream instance evaluated, n decisions per run); `s02_paired.csv`, `s02_generalization.csv` (only with both test splits), `s02_overhead.csv`; figures G4 (training curves), G5 (makespan by method), G6 (ρ by class / OOD set) with source CSVs |
| `schedlab/__main__.py` | `train-rl --config --seed --out [--ablation] [--bc]`; power recorded in the model's `measured` metadata |
| `tests/test_rl.py` (new) | 13 tests (below) |
| `configs/s02_pilot.toml` | pilot: real workload matrix, `[s02_train]` changes only `max_updates` 300, `time_cap_s` 900, `val_every` 50 |
| `docs/S02_IMPLEMENTATION_PLAN.md` | approval recorded; BC fallback numbers fixed before the pilot (200 updates, batch 16, lr 3e-4) |

## 2. Commands and tests

| Command | Result |
|---|---|
| `python3 -m pytest -q` | **236 passed**, 0 failed, 0 skipped (13 new) |
| `caffeinate -i python3 -m schedlab train-rl --config configs/s02_pilot.toml --seed 0 --out results/models/s02_pilot_seed0` | 300 updates, 4,800 episodes, **97.4 s**, AC power (52% → 55%), model **`580faad134361f1a`** |
| two 20-update retrains (scratch, `val_every` 10) | identical weights `83ce9e2c643707d8` both times |
| `python3 -m schedlab run --config configs/s02_pilot.toml` (twice) | `20261017T090051Z-s02_pilot-04ee0d92`, `…090101Z…`: 3,780 rows each, 0 not ok, 6.9 s each, AC power |
| `python3 -m schedlab analyze results/raw/20261017T090051Z-s02_pilot-04ee0d92` | campaign checks: all passed |

New tests: candidates are exactly the valid pairs; features finite, deterministic, time-unit invariant; random and
greedy rollouts valid; greedy deterministic, ties to the first candidate; **HEFT's decisions inside the RL
environment reproduce the HEFT baseline schedule exactly** (same simulator and insertion rule); reward/advantage signs
(A > 0 exactly when RL beats HEFT, A = G − b) and standardisation; validation must be `val`; held-out collision
aborts training; training stream is `train`, index ≥ 1000, disjoint from all 1,710 matrix instances; training
determinism and best-checkpoint selection; ablation drops 2 features, BC flag recorded; BC objective reproduces HEFT
on a toy instance; tampered weights rejected; training instances refused at inference; pilot config lock; runner and
analysis with two seed models and pinned ids.

## 3. Predeclared pilot criteria (plan §7)

| # | Result | Evidence |
|---|---|---|
| S02-P1 | **Pass.** Validity, lower bound, pipeline, completeness via `check()`; P4: the two pilot campaigns have identical makespan, busy-time, model-id, validity and status columns | analyze; comparison of `runs.csv` |
| S02-P2 | **Pass.** Training determinism: two independent 20-update runs → byte-identical weights (`83ce9e2c…`), identical training-stream hashes and per-update returns. (A first attempt with `val_every` 50 only validated update 0, so it compared initial weights; it was repeated with `val_every` 10) | scratch model dirs |
| S02-P3 (= P9) | **Pass.** Best checkpoint `val` ρ 1.257 (update 300) < update 0's 5.393 | `model.json`, `training_log.csv` |
| S02-P4 | **Pass.** 4,800 training hashes, all unique, 0 overlap with `train` (selector's), `val`, `test_id`, `test_ood`; inference refuses a training instance | hash comparison |
| S02-P5 | **Pass (projection, below).** | measured rates |
| S02-P6 | **Pass.** All 540 RL schedules valid; inference time measured | runs.csv, `s02_overhead.csv` |

**Fallback status: not triggered.** The predeclared trigger (best checkpoint no better than update 0) did not fire,
so behaviour cloning was not applied and nothing was changed.

## 4. Learning diagnostics (val, in-sample for checkpoint selection)

Validation ρ = mean `Cmax_RL / Cmax_HEFT`, greedy: update 0 → 5.39; 50 → 1.52; 100 → 1.37; 150 → 1.31; 200 → 1.257;
250 → 1.261; 300 → **1.257** (best). The batch return rose from about −2.65 to −2.05 (G4); the curve was flattening
between updates 200 and 300.

| Pilot policy vs (val, 180) | Mean ρ | 95% CI | better / tie / worse |
|---|---|---|---|
| `HEFT` | 1.257 | 1.222 – 1.294 | 9 / 2 / 169 |
| `FCFS-EAT` | 1.010 | 0.967 – 1.054 | 82 / 2 / 96 |
| best heuristic | 1.264 | 1.230 – 1.300 | 5 / 2 / 173 |
| `SPT-EFT` | 0.995 | 0.978 – 1.013 | 107 / 1 / 72 |
| `MINMIN` | 1.058 | 1.039 – 1.078 | 60 / 1 / 119 |

Mean Cmax/LB 1.468 (`HEFT` 1.177, `FCFS-EAT` 1.608); utilization 0.705 (`HEFT` 0.897). ρ vs HEFT by n: 1.27 / 1.27 /
1.24 (50 / 100 / 200); by m: 1.09 / 1.28 / 1.40 (2 / 4 / 8); by class: regular 1.13, heterogeneous 1.16,
irregular_hetero 1.32, irregular 1.41.

Against the full-campaign criterion of ALGORITHM_DESIGN §4.6 ("learned" = beats update 0 **and** mean makespan below
`FCFS-EAT` on `val`), this 300-update policy would **not** count as learned: its `FCFS-EAT` ratio CI includes 1. That
criterion applies to the full 3,000-update runs, not to the pilot, and is not used to change anything here.

## 5. Overhead and runtime (measured vs projected)

**Measured:** training 0.32 s per update (16 episodes, mixed cells; 300 updates and 7 validations in 97 s), about 3–6×
faster than the plan's 1–2 s projection. Inference (`s02_overhead.csv`): median 2.5 / 5.5 / 13.7 ms per instance at
n = 50 / 100 / 200, i.e. 50–69 µs per decision, **13–17× HEFT's** median scheduling time.

**Projection for the full S02 campaign** (from these rates; assumption: per-update cost scales as measured, mains power):

| Part | Projection |
|---|---|
| One seed, 3,000 updates + 30 validations | ~16–20 min (the 45-min cap would not bind) |
| 3 seeds + `RL-NOHEFTFEAT` | ~65–80 min |
| Final campaign: 450 × (6 heuristics + 4 RL models) × 3 = 13,500 rows | ~2–4 min (n = 400 OOD inference ~30–60 ms) |
| Total | **~1.2–1.5 h** (plan's estimate was ~3.5 h) |

## 6. Primary comparison and Holm family — what the records support

- Predeclared in EXPERIMENTAL_METHODOLOGY §5.1 (architecture phase): Wilcoxon on paired makespans for three primary
  comparisons, `GA` vs best heuristic, `RL` vs `HEFT`, `ADAPTIVE` vs `SBS`, with Holm across the three. §5.1 did
  **not** name the test population for any of them.
- S01: population not predeclared; reported for `test_id`, `test_ood` and all (S01 report §B.2).
- S03: population `test_id` fixed in methodology §7.3 on 2026-10-17, before the S03 pilot ran.
- S02: population **`test_id`**, with `RL` = mean over the three seed models, fixed in the S02 plan on 2026-10-17
  (approved before any S02 code or data). This is a pre-data specification in the approved plan, not a
  registration in the original methodology, and it should be described that way.
- The Wilcoxon p in the pilot (1.4e-28, RL worse than HEFT on `val`) is a pipeline diagnostic, in-sample, not a
  member of the Holm family.

## 7. Limitations

- Pilot policy is far worse than `HEFT` on `val` (+26%) and only on par with `FCFS-EAT`; the final verdict will depend
  on whether 3,000 updates close that gap. With predeclared settings and no tuning, "does not improve" is a likely and
  valid outcome.
- The fallback trigger is weak in practice: an untrained policy is so poor (ρ 5.4) that almost any training beats it.
  It is applied exactly as predeclared and not reinterpreted.
- Features 4 and 7 encode HEFT's quantities; the ablation will quantify reliance on them.
- `val` results are in-sample for checkpoint selection; no generalization claim is made.
- S01/S03 caveats unchanged (battery-measured timings there); S02 runs so far were on mains power.
- Outstanding: Batches 1–3 and 7 findings unavailable; faculty approval of scope and tooling; literature review not
  started; identifier placeholders.

## 8. Proposed next step (for your review)

Train `RL-S0`, `RL-S1`, `RL-S2` (seeds 0–2) and `RL-NOHEFTFEAT` (seed 0, ablation) with the predeclared full settings
(3,000 updates / 45 min, `val_every` 100) on mains power; apply the BC fallback to a seed only if its trigger fires;
then lock `configs/s02_final.toml` with the four model ids pinned and run the final campaign once on `test_id` and
`test_ood`.

---

## 9. Full training (approved 2026-10-17) — validation diagnostics only

Config `configs/s02_train.toml`: the predeclared `rl.SETTINGS` with **no overrides** (lock test
`test_full_training_config_uses_the_predeclared_settings_unchanged`). Commands, run sequentially under `caffeinate -i`
on **AC power** (recorded in each `model.json`): `python3 -m schedlab train-rl --config configs/s02_train.toml
--seed {0,1,2} --out results/models/s02_rl_seed{0,1,2}` and `--seed 0 --ablation --out
results/models/s02_rl_noheftfeat_seed0`. A first launch failed before training anything (shell quoting: every run
exited with an argument error; no directory was created) and was relaunched with explicit arguments.

| Method | Model id | Wall time (measured) | Updates / episodes / stop | Best update | `val` ρ at update 0 → best (95% CI) | Paired Δρ best − update 0 (CI) | ρ vs `FCFS-EAT` (CI) | vs `HEFT` better / tie / worse | §4.6 "learned" |
|---|---|---|---|---|---|---|---|---|---|
| `RL-S0` | `c827a9f51c512ac4` | 947 s (10:37–10:53 UTC) | 3,000 / 48,000 / max_updates | 1,200 | 5.393 → **1.006** (0.995–1.018) | −4.86 – −3.93 | 0.810 (0.782–0.838) | 76 / 18 / 86 | yes |
| `RL-S1` | `e83496e27b9d4ef1` | 959 s | 3,000 / 48,000 / max_updates | 2,000 | 1.916 → **1.000** (0.990–1.011) | −1.11 – −0.74 | 0.806 (0.777–0.834) | 77 / 21 / 82 | yes |
| `RL-S2` | `1765acd48d43dfde` | 930 s | 3,000 / 48,000 / max_updates | 3,000 | 1.299 → **1.029** (1.018–1.041) | −0.32 – −0.22 | 0.831 (0.801–0.861) | 38 / 17 / 125 | yes |
| `RL-NOHEFTFEAT` (ablation, seed 0) | `a7781d888bca8550` | 947 s | 3,000 / 48,000 / max_updates | 600 | 2.158 → **1.035** (1.019–1.053) | −1.23 – −1.02 | 0.831 (0.803–0.859) | 60 / 7 / 113 | yes |

All values on the 180 `val` instances, which chose each checkpoint: in-sample, model-development diagnostics.
ρ = `Cmax_RL / Cmax_HEFT` (greedy); CIs are 10,000-resample bootstraps over instances. The update-0 network was
recreated from its seed for the paired difference. "Learned" (§4.6: best beats update 0 with CI below 0 **and** mean
makespan below `FCFS-EAT`) holds for **3 of 3** seeds, so RL counts as having learned on `val`.

- **Fallback:** not triggered for any run (every best checkpoint beat its update 0); no behaviour cloning applied.
- **Time budget:** no run reached the 45-min cap; total 63 min for all four (pilot-based projection 65–80 min).
- **Integrity:** each model loads and its recomputed weight hash equals its `model_id`; all four used the same
  training stream (identical `train_hashes.txt`, 48,000 unique hashes, sha256 `de1124a8…`); 0 overlap with the
  selector's `train` instances, `val`, `test_id` or `test_ood`. Cross-run determinism: `RL-S0`'s first 300 updates
  reproduce the pilot run exactly (identical returns and batch ρ; val ρ at update 300 = 1.25661248602438 in both).
- **Curves** (G4, `results/figures/s02_training/g4_training_curves.{pdf,svg,csv}`): val ρ falls steeply in the first
  ~500 updates, then slowly (S0: 1.095 @ 500, 1.052 @ 2,000, 1.016 @ 3,000). Batch returns were **still rising at
  update 3,000** for all four runs: training had not converged within the predeclared budget.
- **Ablation:** without the HEFT-like features, best val ρ 1.035 vs 1.006 for the same seed with them.

**Not shown here, by design:** any `test_id` or `test_ood` result. The final campaign will use exactly these four model
ids, pinned.

**Proposed `configs/s02_final.toml` (not created):** `[workload]` and seed as `full.toml`; splits `test_id`,
`test_ood`; algorithms the six heuristics + `RL-S0`, `RL-S1`, `RL-S2`, `RL-NOHEFTFEAT`; 3 timing repeats; `[s02]
models` and `model_ids` pinning the four ids above; a lock test. Expected rows 450 × 10 × 3 = **13,500**; projected
runtime a few minutes. Primary: `RL` (mean of `RL-S0..S2`) vs `HEFT` on `test_id`, Wilcoxon, §4.6 verdict bands;
secondary: `FCFS-EAT` and other heuristics, per-seed results, ablation, generalization Δ per OOD set.
