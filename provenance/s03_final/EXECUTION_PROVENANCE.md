# S03 final campaign: execution provenance

What ran, as it was at launch. Post-processing is recorded separately in `POSTPROCESSING_PROVENANCE.json`. Nothing
in `results/raw/20261017T083329Z-s03_final-b8e5be9a/` is edited by either.

| Item | Value | Source |
|---|---|---|
| Campaign id | `20261017T083329Z-s03_final-b8e5be9a` | directory name, `manifest.json` |
| Raw files | `runs.csv`, `decisions.csv`, `ga_trace.csv` (header only: no S01 runs), `manifest.json`, `run.log`; read-only | runner |
| Locked config | `configs/s03_final.toml`, sha256 `2a4698c8da4ad039aa209cfe7867deb37f86172f8d01be5d2f8e220ba45c2f40`, runner config hash `b8e5be9a`; checked by `test_final_s03_config_is_locked_to_the_reviewed_pilot` | `shasum`, manifest |
| Pinned models | primary `results/models/s03_selector_v1`, `820ba281844c513e` (pickle sha256 `820ba281…79fd`); extension `results/models/s03_selector_ga_v2`, `6d83fac40cb5c6ed` (pickle sha256 `6d83fac4…d4c7`). The runner refuses to start if a loaded id differs from the pin. Both fitted on `train` (1,080), selected on `val` (180); 0 test hashes in either | `model.json`, manifest `models` |
| Pre-launch checks | 13 methods with settings as reviewed; 450 test instances (360 `test_id`, 90 `test_ood`, 9 OOD cells × 10); 17,550 expected rows; no prior `s03_final` campaign; 223 tests passed | session record |
| Launch | 2026-10-17 08:33:29 UTC, `caffeinate -i python3 -m schedlab run --config configs/s03_final.toml`; finished 08:37:27 UTC; runner wall time 237.25 s | manifest |
| Execution code | hash `a7017e19fb7d8d13`; byte-exact snapshot taken immediately before launch in `execution_snapshot/` (with a copy of the config), read-only; its hash recomputes to `a7017e19fb7d8d13` | manifest, snapshot |
| Host | Apple M4, 10 cores, 16 GB, single worker, one thread, **on battery** (56% at launch). Measured times may differ under mains power and are not claimed to generalise | `pmset`, manifest |
| Run once | Yes. No rerun, no failed rows, nothing removed | manifest `failed_count` 0 |
