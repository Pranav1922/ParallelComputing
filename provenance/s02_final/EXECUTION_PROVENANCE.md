# S02 final campaign: execution provenance

What ran, as it was at launch. Post-processing is recorded separately in `POSTPROCESSING_PROVENANCE.json`. Nothing in
`results/raw/20261017T115054Z-s02_final-898ee9e1/` is edited by either.

| Item | Value | Source |
|---|---|---|
| Campaign id | `20261017T115054Z-s02_final-898ee9e1` | directory, manifest |
| Raw files | `runs.csv`, `manifest.json`, `run.log`, `ga_trace.csv` and `decisions.csv` (header only: no S01/S03 runs); read-only | runner |
| Locked config | `configs/s02_final.toml`, sha256 `077c0d336622e7c07e412d69ceaaff3031cc092521a2510ced211d5b8ddfc817`, runner hash `898ee9e1`; lock test `test_final_s02_config_is_locked` | shasum, manifest |
| Pinned models | `RL-S0` `c827a9f51c512ac4` (`results/models/s02_rl_seed0`), `RL-S1` `e83496e27b9d4ef1`, `RL-S2` `1765acd48d43dfde`, `RL-NOHEFTFEAT` `a7781d888bca8550`; trained on the shared training stream (48,000 instances, `train` split, indices ≥ 1000), checkpoints chosen on `val`; 0 test hashes in any stream; read-only; runner refuses a mismatching id | model dirs, manifest `models` |
| Pre-launch checks | 10 methods as locked; 450 test instances; 13,500 expected rows; no prior `s02_final`; 238 tests passed. A first pre-launch check found the host **on battery**; the launch was held until AC power was connected and confirmed | session record |
| Launch | 2026-10-17 11:50:54 UTC, `caffeinate -i python3 -m schedlab run --config configs/s02_final.toml`; finished 11:52:15 UTC; runner wall time 80.26 s; run once | manifest |
| Power | **AC power** at start and end (`power_at_start`, `power_at_end` in the manifest), per decision 3 | manifest |
| Execution code | hash `939d930e96cebafe`; byte-exact snapshot taken immediately before launch in `execution_snapshot/` (with the config), read-only; recomputes to `939d930e96cebafe` | manifest, snapshot |
| Host | Apple M4, 10 cores, 16 GB, single worker, one thread (`torch.set_num_threads(1)`) | manifest |
