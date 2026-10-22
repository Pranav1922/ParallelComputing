# Campaign and pilot index

Status of every directory under `results/raw/`. Raw directories are never edited or deleted; superseded ones are
kept and marked here only.

| Raw directory | Config | Status |
|---|---|---|
| `20261011T164953Z-pilot-5fff7b4a` | `pilot.toml` | M2 heuristics pilot (`val`). Current for M2 |
| `20261011T164954Z-cost_probe-b0c3d3cf` | `cost_probe.toml` | M2 cost probe (`val`) |
| `20261011T165803Z-ga_pilot-3955b13e` | `ga_pilot.toml` | S01 GA pilot (`val`) |
| `20261017T044734Z-s01_final-430d8a10` | `s01_final.toml` | **S01 final campaign (test). Accepted 2026-10-17.** Provenance: `provenance/s01_final/` |
| `20261017T075426Z-s03_pilot-eeb28bc3` | `s03_pilot.toml` | **Superseded** (TRY-ALL computed unused features, inflating its decision time). Makespans identical to the current pilot |
| `20261017T075435Z-s03_pilot-eeb28bc3` | `s03_pilot.toml` | **Superseded** (same reason; was the P4 repeat) |
| `20261017T075602Z-s03_pilot-eeb28bc3` | `s03_pilot.toml` | **Current six-heuristic S03 pilot** (primary reference), model `s03_selector_v1` (`820ba281844c513e`) |
| `20261017T075611Z-s03_pilot-eeb28bc3` | `s03_pilot.toml` | P4 repeat of the above (identical simulated columns) |
| `20261017T080717Z-s03_pilot_ga-b259633d` | `s03_pilot_ga.toml` (then `model_ga = s03_selector_ga_v1`) | **Superseded**: extension model v1 had a non-reproducible id (measured times in the pickle). Simulated results identical to the current extension pilot |
| `20261017T080830Z-s03_pilot_ga-b259633d` | same | **Superseded** (P4 repeat of the above) |
| `20261017T082349Z-s03_pilot_ga-8d8bac5a` | `s03_pilot_ga.toml` (`model_ga = s03_selector_ga_v2`) | **Current contingency-extension pilot**, models `820ba281844c513e` + `6d83fac40cb5c6ed` |
| `20261017T082502Z-s03_pilot_ga-8d8bac5a` | same | P4 repeat of the above (identical) |
| `20261017T090051Z-s02_pilot-04ee0d92` | `s02_pilot.toml` | **Current S02 pilot** (`val`), model `s02_pilot_seed0` (`580faad134361f1a`) |
| `20261017T090101Z-s02_pilot-04ee0d92` | same | P4 repeat of the above (identical) |
| `20261017T115054Z-s02_final-898ee9e1` | `s02_final.toml` | **S02 final campaign (test_id + test_ood), run once 2026-10-17, AC power.** Provenance: `provenance/s02_final/`; report `docs/S02_ACCEPTANCE_REPORT.md` |
| `20261017T083329Z-s03_final-b8e5be9a` | `s03_final.toml` | **S03 final campaign (test_id + test_ood), run once 2026-10-17.** Provenance: `provenance/s03_final/`; report `docs/S03_ACCEPTANCE_REPORT.md` |

Models (`results/models/`, read-only): `s03_selector_v1` — six-heuristic selector, primary. `s03_selector_ga_v1` (`870ab53c17d01909`) —
superseded extension. `s03_selector_ga_v2` (`6d83fac40cb5c6ed`) — current contingency extension with the `GA-1000`
member (EXPERIMENTAL_METHODOLOGY §7.4); see `docs/S03_PILOT_REPORT.md` §8.
`s02_pilot_seed0` (`580faad134361f1a`) — S02 pilot policy (seed 0, 300 updates); not one of the final models.
`s02_rl_seed0` (`c827a9f51c512ac4`), `s02_rl_seed1` (`e83496e27b9d4ef1`), `s02_rl_seed2` (`1765acd48d43dfde`), `s02_rl_noheftfeat_seed0` (`a7781d888bca8550`) — final S02 models (full training, 2026-10-17), to be pinned in `s02_final.toml`.
