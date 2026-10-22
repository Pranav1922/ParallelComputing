"""Independent integrity check of the frozen S03 final campaign, without schedlab.analysis. Read-only except the
JSON report it writes.

    PYTHONPATH=. python3 provenance/s03_final/verify_campaign.py results/raw/<campaign> results/derived/<campaign> out.json
"""
import json
import sys
import tomllib
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import wilcoxon

from schedlab import adaptive
from schedlab.heuristics import HEURISTICS
from schedlab.runner import DECISION_COLUMNS, RAW_COLUMNS, _short_hash, build_schedulers
from schedlab.workloads import experiment_matrix

raw_dir, derived_dir, out = Path(sys.argv[1]), Path(sys.argv[2]), Path(sys.argv[3])
cfg = tomllib.loads(Path("configs/s03_final.toml").read_text())
manifest = json.loads((raw_dir / "manifest.json").read_text())
text = pd.read_csv(raw_dir / "runs.csv", dtype=str, keep_default_na=False)
raw = pd.read_csv(raw_dir / "runs.csv", float_precision="round_trip")
dec = pd.read_csv(raw_dir / "decisions.csv", float_precision="round_trip")
res, problems = {}, []


def need(cond, msg):
    if not cond:
        problems.append(msg)


need(manifest["config"] == cfg, "manifest config differs from configs/s03_final.toml")
need(manifest["config_hash"] == _short_hash(cfg), "config hash mismatch")
need(list(text.columns) == RAW_COLUMNS and list(dec.columns) == DECISION_COLUMNS, "header differs")
need(not (text == "").any().any(), "blank cells in runs.csv")
ids = {m["role"]: m["model_id"] for m in manifest["models"]}
res["manifest_models"] = ids
need(ids == {"model": cfg["s03"]["model_id"], "model_ga": cfg["s03"]["model_ga_id"]}, "manifest model ids differ from the pinned ids")

matrix = experiment_matrix(cfg["workload"], cfg["campaign"]["seed"])
insts = [i for s in cfg["run"]["splits"] for i in matrix[s]]
algos = cfg["run"]["algorithms"]
scheds = build_schedulers(cfg)
seeded = {a for a in algos if len(scheds[a]) > 3}
res.update(expected_rows=len(insts) * 3 * len(algos), actual_rows=len(raw), instances_expected=len(insts),
           instances_actual=int(raw.instance_hash.nunique()), methods=len(algos),
           status_counts=raw.status.value_counts().to_dict(),
           rows_by_split=raw.groupby("split").size().to_dict())
need(len(raw) == res["expected_rows"] and manifest["row_count"] == len(raw), "row count differs")
need(manifest["failed_count"] == int((raw.status != "ok").sum()), "manifest failed_count differs")
need(raw.run_uid.is_unique and not raw.duplicated(["instance_hash", "algorithm", "run_id"]).any(), "duplicate rows")
exp = {i.meta["hash"]: (i.id, i.n, i.m, i.meta["split"], i.meta["label"]) for i in insts}
got = raw.groupby("instance_hash")[["instance_id", "problem_size", "resource_count", "split", "workload_class"]].first()
need(set(got.index) == set(exp) and all(tuple(got.loc[h]) == v for h, v in exp.items()), "instances differ from the matrix")
for a in algos:
    sub = raw[raw.algorithm == a]
    need((sub.groupby("instance_hash").run_id.apply(lambda x: tuple(sorted(x))) == (0, 1, 2)).all() and len(sub) == 3 * len(insts),
         f"{a}: not 3 rows per instance")
    if a in seeded:
        need((sub.groupby("instance_hash").algo_seed.apply(lambda x: tuple(sorted(x))) == (0, 1, 2)).all(), f"{a}: seeds")
    else:
        need(sub.algo_seed.isna().all(), f"{a}: unexpected seed")
    need(sub.algo_config_hash.astype(str).eq(_short_hash(scheds[a][2])).all(), f"{a}: config hash")
s03 = raw[raw.sub_problem == "S03"]
want = np.where(s03.algorithm.isin(adaptive.GA_METHODS), ids["model_ga"], ids["model"])
need((s03.model_id.astype(str).to_numpy() == want).all(), "S03 row model ids wrong")
need(set(dec.run_uid) == set(raw[(raw.sub_problem == "S03") & (raw.status == "ok")].run_uid), "decisions coverage")

# heuristics re-run from scratch; ADAPTIVE / ADAPTIVE-GA decisions re-derived from the saved models
base, _ = adaptive.load(cfg["s03"]["model"])
ext, _ = adaptive.load(cfg["s03"]["model_ga"])
d = dec.merge(raw[["run_uid", "algorithm", "instance_hash", "makespan_sim"]], on="run_uid")
mism_h = mism_d = 0
for inst in insts:
    h = inst.meta["hash"]
    r = raw[raw.instance_hash == h]
    for name in HEURISTICS:
        mism_h += int(not (r[r.algorithm == name].makespan_sim == HEURISTICS[name](inst, None)[0].makespan).all())
    for method, b in (("ADAPTIVE", base), ("ADAPTIVE-NOGUARD", base), ("ADAPTIVE-GA", ext)):
        pick = adaptive.select(b, inst, guard=method != "ADAPTIVE-NOGUARD")["picks"][0]
        mism_d += int(not (d[(d.instance_hash == h) & (d.algorithm == method)].selected == pick).all())
res.update(heuristic_rerun_mismatches=mism_h, decision_rederive_mismatches=mism_d)
need(mism_h == 0 and mism_d == 0, "re-run or re-derived decisions differ from raw")

# primary comparison, recomputed directly: ADAPTIVE vs SBS on test_id
ok = raw[raw.status == "ok"]
per = ok.groupby(["instance_hash", "algorithm"]).makespan_sim.mean().unstack()
lb = ok.groupby("instance_hash").lower_bound_sim.first()
split = ok.groupby("instance_hash").split.first()
sbs = base["sbs"]
vbs = per[list(HEURISTICS)].min(axis=1)
for scope in ("test_id", "test_ood"):
    idx = split.index[split == scope]
    a, s, v = per.loc[idx, "ADAPTIVE"], per.loc[idx, sbs], vbs[idx]
    ratio = a / s
    gap = ((s / lb[idx]).mean() - (a / lb[idx]).mean()) / ((s / lb[idx]).mean() - (v / lb[idx]).mean())
    nz = int(((a - s) != 0).sum())
    res[f"ADAPTIVE_vs_SBS_{scope}"] = dict(
        n=len(idx), n_nonzero=nz, mean_paired_improvement=float(1 - ratio.mean()),
        better=int((ratio < 1 - 1e-12).sum()), tie=int((abs(ratio - 1) <= 1e-12).sum()), worse=int((ratio > 1 + 1e-12).sum()),
        gap_closed=float(gap), wilcoxon_p=float(wilcoxon(a, s, zero_method="wilcox").pvalue) if nz else None)
    t = pd.read_csv(derived_dir / "s03_paired.csv")
    row = t[(t.algorithm == "ADAPTIVE") & (t.baseline == "SBS") & (t.split == scope)].iloc[0]
    need(np.isclose(row.improvement_mean, res[f"ADAPTIVE_vs_SBS_{scope}"]["mean_paired_improvement"], rtol=0, atol=1e-12)
         and np.isclose(row.gap_closed, gap, rtol=1e-12)
         and (nz == 0 or np.isclose(row.wilcoxon_p, res[f"ADAPTIVE_vs_SBS_{scope}"]["wilcoxon_p"], rtol=1e-9)),
         f"s03_paired.csv differs from direct recomputation on {scope}")
res["problems"] = problems
out.write_text(json.dumps(res, indent=2, default=str))
print(json.dumps(res, indent=2, default=str))
sys.exit(1 if problems else 0)
