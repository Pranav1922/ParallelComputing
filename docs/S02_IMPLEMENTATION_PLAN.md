# S02 Reinforcement-Learning Scheduling — Implementation Plan (for review; nothing implemented)

Status 2026-10-17: **plan approved by the user** with all three decisions as proposed (insertion placement; no
hyperparameter tuning; training and the final campaign on mains power, recorded in the manifest). Implementation and
the pilot follow; the full three-seed training and the final campaign wait for review of the pilot.

**Fallback settings, fixed before the pilot (§4.7 named the method but no numbers).** Behaviour-cloning warm start,
used only if a seed's best checkpoint does not beat its own update-0 validation ρ: cross-entropy on HEFT's chosen
`(t, p)` at every step of HEFT's own trajectory (highest upward rank, ties lowest id; earliest insertion finish, ties
lowest processor), 16 training-stream instances per update, 200 updates, Adam at the same learning rate 3e-4, then
REINFORCE with the predeclared settings. Values copied from the REINFORCE settings where possible; 200 updates is a
judgement chosen now, not tuned. Recorded in model metadata if used. The design baseline is
`ALGORITHM_DESIGN.md` §4 (written in the architecture phase); this plan makes it implementable, lists what changes, and
fixes the pilot. Items marked **[DECISION]** need your approval.

Manual (S02): *Can RL scheduling improve over a conventional heuristic after training?* Objectives: define
state/action/reward; train on representative workloads; test on unseen workloads. Metrics: makespan, utilization,
inference overhead, generalization. Graphs: training reward; makespan vs method; generalization performance.
Tools: Python + PyTorch (installed: torch 2.11.0, CPU).

---

## 1. Environment (reuses `model.ScheduleBuilder`, the validated simulator)

| Element | Definition |
|---|---|
| Episode | Schedule one instance from empty to complete: exactly `n` decisions |
| State | The builder (placed tasks, `avail`, `ready`, `ready_time`, busy intervals) plus the instance; encoded per candidate (§2) |
| Action | One pair `(t, p)`, `t` in the ready set, `p` any processor — joint task selection and resource assignment |
| Valid actions | Only valid pairs are enumerated; softmax over that list. Invalid actions cannot be sampled: no masking, no penalty |
| Transition | `builder.place(t, p, insert=…)`; deterministic |
| Termination | All tasks placed |
| Validity | Every produced schedule goes through the independent `validate()`, as for every other method |

**[DECISION 1] Placement mode.** §4.1 specified append mode. All six heuristics, and therefore `HEFT`, use gap
insertion, so an append-only RL agent would be compared against a baseline with a strictly richer placement rule.
Proposed: **insertion** (`insert=True`), the same placement rule as every baseline, so the comparison isolates the
decision policy. Cost: the probe shows insertion is ~1.0–1.7× append per episode (up to 1.7× at n = 400).

## 2. Candidate features and policy (as §4.2–4.3)

Twelve scale-free features per candidate (cost ratio to the task's best processor, relative cost, task size,
normalised upward rank, out-degree, start wait, finish relative to the best candidate, idle gap created, ready-time
offset, fraction placed, ready-set size / m, load imbalance). Features 4 (rank) and 7 (EFT) are HEFT's own quantities,
so the policy can imitate HEFT; this is disclosed, and the ablation `RL-NOHEFTFEAT` drops them and is retrained once.
With insertion, features 6–8 use the insertion `est`/`eft`. Policy: MLP 12 → 64 → 64 → 1 (ReLU), scores all
candidates in one batch, softmax; CPU, `torch.set_num_threads(1)`.

## 3. Reward and training

- Return `G = −Cmax / LB` at episode end (no shaping). Baseline `b = −Cmax_HEFT / LB` on the same instance;
  advantage `A = (Cmax_HEFT − Cmax) / LB`, standardised within the batch. Loss `−Σ log π · A − β·H`. REINFORCE, Adam.
- Predeclared settings (§4.4): learning rate 3e-4, 16 episodes per update, β = 0.01, gradient clip 1.0, validation
  every 100 updates, up to 3,000 updates **or** a 45-minute wall-clock cap per training seed, 3 training seeds
  (0, 1, 2), all reported.
- **[DECISION 2] No hyperparameter tuning.** Proposed: the settings above are used as predeclared; `val` is used
  only for checkpoint selection and for the §4.7 fallback decision. Any tuning would itself be done on `val` only and
  recorded, but tuning REINFORCE well within the time box is unrealistic and invites selection on noise.
- Fallback (§4.7, predeclared): if a seed's best checkpoint does not beat its own update-0 validation score, a
  behaviour-cloning warm start from `HEFT`'s decisions (cross-entropy on HEFT's chosen pair) is applied before
  REINFORCE, recorded in model metadata and reported.

## 4. Data separation

| Data | Used for | Mechanism |
|---|---|---|
| Training stream | gradient updates only | `generate(class, n, m, "train", index)` with **indices ≥ 1,000** (disjoint from the S03 selector's 0–29 by construction), cell drawn uniformly from the 36 in-distribution cells (4 classes × n {50, 100, 200} × m {2, 4, 8}); same stream for all training seeds (seeds differ in initialisation and action sampling) |
| `val` (180, the existing split) | checkpoint selection (greedy mean `ρ = Cmax_RL / Cmax_HEFT`), §4.7 fallback decision, P9 | fixed set |
| `test_id` (360), `test_ood` (90) | final evaluation only | never generated by the trainer |
| Guards | Every generated training instance's hash is checked against the `val`, `test_id` and `test_ood` hash sets (abort on a hit); each model stores its training hashes; evaluation refuses any instance in them (as S03's `assert_no_leakage`) | code + test |

OOD sets (n = 400; m = 16; fork-join; CV 3.0) are never seen in training, so they test generalization in size,
resources, structure and cost variability.

## 5. Baselines and comparisons

- **Primary (predeclared, §5.1):** `RL` vs `HEFT` on **`test_id`**, `RL` = per-instance mean over the 3 training
  seeds; Wilcoxon signed-rank on paired makespans, two-sided; third member of the Holm family (S01 GA vs best
  heuristic p = 6e-52 on all 450 / 3e-43 on `test_id`; S03 ADAPTIVE vs SBS p = 0.78). Effect size: mean `ρ` with 95%
  bootstrap CI and the §4.6 verdict bands ("improves" CI < 1; "matches" CI within [0.98, 1.02]).
- **Secondary:** vs `FCFS-EAT` (the manual's "conventional heuristic"), vs every other heuristic and the per-instance
  best heuristic; per-seed results; generalization gap `Δ = mean ρ_OOD − mean ρ_ID` per OOD set with CI (§4.6);
  `RL-NOHEFTFEAT` ablation; seed stability.
- **Overhead:** measured inference seconds per instance and per decision vs `HEFT`'s scheduling time; model load
  time once; one-off training time and episodes reported next to it, with amortisation stated only for an explicit
  hypothetical τ. Simulated makespan and seconds are never combined otherwise.

## 6. Repository changes (reusing the existing infrastructure)

| File | Change |
|---|---|
| `schedlab/rl.py` (new) | features, policy, episode rollout, REINFORCE trainer with validation/checkpointing, BC warm start, greedy scheduler entry point `(inst, rng) → (Schedule, info)` with `decision_time_s`, leakage guard |
| `schedlab/runner.py` | `[s02]` config section; registers `RL-S0`, `RL-S1`, `RL-S2` (and `RL-NOHEFTFEAT`) as **deterministic** methods with 3 timing repeats, each pinned to its model id (same pin guard as S03). No change to `runs.csv` |
| `schedlab/analysis.py` | S02 checks (RL schedules valid, model ids match the manifest, no training instance evaluated, greedy determinism across repeats); `s02_paired.csv` (per seed and seed-mean `RL`), `s02_generalization.csv`, overhead table; figures G4 (training return and validation ρ vs updates, 3 seeds), G5 (Cmax/LB by method), G6 (ρ on `test_id` vs each OOD set) with source CSVs |
| `schedlab/__main__.py` | `train-rl --config … --seed k` |
| `tests/test_rl.py` (new) | below |
| `configs/s02_pilot.toml`, later `configs/s02_final.toml` (locked, model ids pinned) | |
| Model dirs `results/models/s02_rl_seed{k}/` | `policy.pt`, `model.json` (settings, best update, timings under `measured`, excluded from the id), `training_log.csv` (update, episodes, elapsed s, mean return, batch mean ρ, val ρ), `train_hashes.txt`; read-only, never overwritten; `model_id` = sha256 prefix of the saved weights |

**Tests (`tests/test_rl.py`):** features finite, deterministic, invariant to the cost unit; candidate list = exactly
the valid pairs; random and greedy policies always yield `validate()`-clean schedules; insertion matches the builder;
greedy decoding deterministic; trainer refuses non-train instances and aborts on a hash in `val`/test; same seed and
settings → identical weights after k updates (training determinism); advantage sign (beating HEFT → positive);
checkpoint = best validation ρ; BC warm start reproduces HEFT's choices on a toy instance at high accuracy; runner
integration with pinned ids; S02 analysis tables and figure CSVs recompute; config-lock test for the final config.

## 7. Pilot (on `val` only; acceptance criteria fixed now)

Pilot training: training seed 0, the real training stream, validation on the full `val` split every 50 updates,
**300 updates** (or 15 minutes). Pilot campaign: six heuristics + `RL-PILOT` on `val` (in-sample for checkpoint
selection; pipeline evidence, not results). Run twice for determinism.

| # | Criterion (pass/fail) |
|---|---|
| S02-P1 | Core P1, P2, P5, P6 on the pilot campaign; P4: two pilot campaigns identical in simulated columns |
| S02-P2 | Training determinism: retraining 20 updates from the same seed gives byte-identical weights |
| S02-P3 (= P9) | Best checkpoint's mean `val ρ` is lower than at update 0 |
| S02-P4 | Leakage: 0 training hashes in `val`/`test_id`/`test_ood`; evaluation refuses a training instance |
| S02-P5 | Projected full S02 cost (training 3 seeds + ablation, plus the campaign) from measured pilot rates ≤ the time box in §8 |
| S02-P6 | Every RL schedule valid; inference time per decision measured |

If S02-P3 fails, the §4.7 fallback (BC warm start) is applied **in the pilot** and the pilot re-run, before any
full training. Diagnostics (not pass/fail): episodes/s per size, validation curve, seed-0 `ρ` by class.

## 8. Runtime estimate

**Probe, not a measurement of S02** (2026-10-17, existing simulator + a 12→64→64→1 MLP, 2 of 12 features
computed): one sampled episode with backward pass took ~14 ms (n = 50, m = 2), 27 ms (100, 4), 83 ms (200, 8) with
insertion; 108 ms at (200, 16) and 228 ms at (400, 4). With all twelve features, assume ~1.5–2× the environment part.

| Part | Estimate |
|---|---|
| One update (16 episodes, mixed cells) | ~1–2 s |
| 3,000 updates | 50–100 min → the **45-min cap binds**: ~1,400–2,700 updates per seed |
| Validation (180 greedy episodes, ~30 per run) | ~5–10 s each → ~3–5 min per seed, inside the cap |
| Training, 3 seeds + `RL-NOHEFTFEAT` | 4 × 45 min = **~3 h** |
| Final campaign: 450 instances × (6 heuristics + 4 RL models) × 3 repeats | ~10–20 min |
| Pilot (300 updates + 2 pilot campaigns on `val`) | ~15–25 min |

**[DECISION 3] Power.** The machine is on battery (51% now). Three hours of training will not finish on battery, and
battery-mode timings were already a caveat for S01 and S03. Proposed: run full training and the final campaign **on
mains power**, and record the power state in the manifests.

## 9. Risks

- REINFORCE with a single terminal reward over 50–200 decisions has high variance; within 45 minutes it may not beat
  HEFT. S03 showed HEFT within 0.5% of the best of six heuristics on this generator, so the ceiling for "improves" is
  narrow. The likely honest outcomes are "matches" or "does not improve"; both are reportable answers.
- Features 4 and 7 make imitation of HEFT easy; the ablation measures how much the result depends on them.
- Training on the train stream and selecting checkpoints on `val` share the generator; the OOD sets measure the
  resulting optimism.
- Three training seeds characterise variance only roughly (already listed in methodology §8).
- Deviation from methodology §6's generic pilot (200 updates on n = 20): replaced by real cells and the real `val`
  split, as done for S03.

## 10. Outstanding (not changed by S02)

Findings from Batches 1–3 and 7 unavailable (S03 objective unmet); faculty approval of scope (one person, S01–S03 +
S02) and tooling (simulation only); literature review not started; `Student_ID` / `Batch_ID` placeholders.

## 11. Proposed order after approval

1. `rl.py` + `test_rl.py` (environment, features, determinism, guards). 2. Trainer + pilot training (seed 0).
3. Runner/analysis integration + pilot campaign twice. 4. Pilot report → your review. 5. Only then: full training
(3 seeds + ablation, mains power), lock `s02_final.toml` with pinned ids, run once, acceptance report.
