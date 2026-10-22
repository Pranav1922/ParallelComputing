# S01 final campaign: execution provenance

What ran, as it was at launch. Post-processing (analysis, figures, report) is recorded separately in
`POSTPROCESSING_PROVENANCE.json`. Nothing in `results/raw/20261017T044734Z-s01_final-430d8a10/` is edited by either.

| Item | Value | Source |
|---|---|---|
| Campaign id | `20261017T044734Z-s01_final-430d8a10` | directory name, `manifest.json` |
| Raw directory | `results/raw/20261017T044734Z-s01_final-430d8a10/` (`runs.csv`, `ga_trace.csv`, `manifest.json`, `run.log`; made read-only by the runner on completion) | runner |
| Locked config | `configs/s01_final.toml`, sha256 `550007b6e5dd4a0444393e8543909d103c27bac80fbb953c7f68b6b1b239a8e5`, runner config hash `430d8a10` | `shasum`, `manifest.json` |
| Launch command | `caffeinate -i python3 -m schedlab run --config configs/s01_final.toml` from the repository root | session record |
| Launch time | `started_utc` in `manifest.json` (2026-10-17 04:47:34 UTC) | `manifest.json` |
| Execution code hash | `9a1f83786ce9df0b` (sha256 prefix over `schedlab/*.py`, by `runner.code_hash()`) | `manifest.json` |
| Host | Apple M4, 10 cores, 16 GB, single worker, one thread | `manifest.json` |
| Power | **On battery** at launch (`pmset -g batt`: 84%, discharging). Kept awake with `caffeinate -i`. Measured times may differ under mains power; they are not claimed to generalise to other power states. | `pmset`, session record |

## Execution-code snapshot: recovered exactly

`execution_snapshot/schedlab/` holds the source that produced the campaign. Only `analysis.py` changed after launch:
one edit, aligning the hypothetical break-even `τ*` with methodology §5.3 (`inf` where there is no gain; median over all
instances). That edit was undone on a copy of the current tree, and the copy's hash, computed with the same function,
is `9a1f83786ce9df0b`, identical to the manifest. So the snapshot is the launch code byte for byte, not a reconstruction
by guesswork. `execution_snapshot/s01_final.toml` is a copy of the locked config.

The running process imported `runner`, `ga`, `heuristics`, `model`, `workloads` and `analysis` (for `load_raw` only) at
launch; none of the first five has changed since. The post-launch `analysis.py` edit affects derived outputs only.

Per-file sha256 of the snapshot:

```
e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855  __init__.py
53703f0355b1360f1aa2a814cca06a65a2e2632c0ccd09eaedaf8247ce36ad6f  __main__.py
cf6f245992b4d73c724cdf052493900b3f7cc5752a75590ad2759a103ba8da1c  analysis.py
466a21aa67c8ba68c6d30d2813c55b2bccd8d9b1cc0ed3b9ac7263efc39d5878  ga.py
eb12e82b79bf33c001a0286695be85c277012cc061fe1d6268e451e7dbc54a93  heuristics.py
14e30e4671b6061aec66607a4e573a542a3caf1b4ae5ebafdbbc700d33fbbed3  model.py
c1e4f8d8dd6b2a4838fd3405557fa3c990422a668e6f4edc1cfb88667c2a871e  runner.py
59c748fee82f647d895f56047887c94885c0746768ba8a6103da85b6d42079c4  workloads.py
```

The runner rewrites `manifest.json` once at the end (finish time, counts, wall time), so its sha256 is recorded in
`POSTPROCESSING_PROVENANCE.json` after completion, not here.
