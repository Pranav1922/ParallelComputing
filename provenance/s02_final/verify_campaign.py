"""Independent integrity check of the frozen S02 final campaign, without schedlab.analysis. Read-only except the JSON
report it writes.

    PYTHONPATH=. python3 provenance/s02_final/verify_campaign.py results/raw/<campaign> results/derived/<campaign> out.json
"""
import json
import sys
import tomllib
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import wilcoxon

from schedlab import rl
from schedlab.heuristics import HEURISTICS
from schedlab.runner import RAW_COLUMNS, _short_hash, build_schedulers
from schedlab.workloads import experiment_matrix

raw_dir, derived_dir, out = Path(sys.argv[1]), Path(sys.argv[2]), Path(sys.argv[3])
cfg = tomllib.loads(Path("configs/s02_final.toml").read_text())
manifest = json.loads((raw_dir / "manifest.json").read_text())
text = pd.read_csv(raw_dir / "runs.csv", dtype=str, keep_default_na=False)
raw = pd.read_csv(raw_dir / "runs.csv", float_precision="round_trip")
res, problems = {}, []


def need(cond, msg):
    if not cond:
        problems.append(msg)


need(manifest["config"] == cfg and manifest["config_hash"] == _short_hash(cfg), "config differs from the lock")
need(list(text.columns) == RAW_COLUMNS and not (text == "").any().any(), "header or blank cells")
ids = {m["role"]: m["model_id"] for m in manifest["models"]}
res["manifest_models"] = ids
need(ids == cfg["s02"]["model_ids"], "manifest model ids differ from the pinned ids")
res["power_at_start"] = next(iter(manifest["hardware"].values()))["power_at_start"]
res["power_at_end"] = manifest["power_at_end"]
need("AC Power" in res["power_at_start"] and "AC Power" in res["power_at_end"], "campaign not on AC power")

matrix = experiment_matrix(cfg["workload"], cfg["campaign"]["seed"])
insts = [i for s in cfg["run"]["splits"] for i in matrix[s]]
algos = cfg["run"]["algorithms"]
scheds = build_schedulers(cfg)
res.update(expected_rows=len(insts) * 3 * len(algos), actual_rows=len(raw), instances=int(raw.instance_hash.nunique()),
           status_counts=raw.status.value_counts().to_dict(), rows_by_split=raw.groupby("split").size().to_dict())
need(len(raw) == res["expected_rows"] == manifest["row_count"] and manifest["failed_count"] == int((raw.status != "ok").sum()),
     "row or failure counts")
need(raw.run_uid.is_unique and not raw.duplicated(["instance_hash", "algorithm", "run_id"]).any(), "duplicates")
exp = {i.meta["hash"]: (i.id, i.n, i.m, i.meta["split"], i.meta["label"]) for i in insts}
got = raw.groupby("instance_hash")[["instance_id", "problem_size", "resource_count", "split", "workload_class"]].first()
need(set(got.index) == set(exp) and all(tuple(got.loc[h]) == v for h, v in exp.items()), "instances differ from the matrix")
for a in algos:
    sub = raw[raw.algorithm == a]
    need(len(sub) == 3 * len(insts) and (sub.groupby("instance_hash").run_id.apply(lambda x: tuple(sorted(x))) == (0, 1, 2)).all()
         and sub.algo_seed.isna().all() and sub.algo_config_hash.astype(str).eq(_short_hash(scheds[a][2])).all(),
         f"{a}: repeats, seeds or config hash")
    need(sub.groupby("instance_hash").makespan_sim.nunique().max() == 1, f"{a}: not deterministic across repeats")
s02 = raw[raw.sub_problem == "S02"]
need((s02.model_id.astype(str) == s02.algorithm.map(ids)).all(), "S02 row model ids")
train = set().union(*(set((Path(p) / "train_hashes.txt").read_text().split()) for p in cfg["s02"]["models"].values()))
need(not (set(raw.instance_hash) & train), "leakage: evaluated instance in a training stream")

models = {name: rl.load(path)[0] for name, path in cfg["s02"]["models"].items()}
mism = 0
first = raw[raw.run_id == 0].set_index(["instance_hash", "algorithm"]).makespan_sim
for inst in insts:
    h = inst.meta["hash"]
    for name in HEURISTICS:
        mism += int(first[(h, name)] != HEURISTICS[name](inst, None)[0].makespan)
    for name, m in models.items():
        mism += int(first[(h, name)] != rl.rollout(inst, m["policy"], m["cols"])[0].makespan)
res["rerun_mismatches_heuristics_and_rl"] = mism
need(mism == 0, "re-run differs from raw")

ok = raw[raw.status == "ok"]
per = ok.groupby(["instance_hash", "algorithm"]).makespan_sim.mean().unstack()
per["RL"] = per[["RL-S0", "RL-S1", "RL-S2"]].mean(axis=1)
split = ok.groupby("instance_hash").split.first()
paired = pd.read_csv(derived_dir / "s02_paired.csv")
for scope in ("test_id", "test_ood"):
    idx = split.index[split == scope]
    for a in ("RL", "RL-S0", "RL-S1", "RL-S2", "RL-NOHEFTFEAT"):
        for b in ("HEFT", "FCFS-EAT"):
            r = per.loc[idx, a] / per.loc[idx, b]
            row = paired[(paired.algorithm == a) & (paired.baseline == b) & (paired.split == scope)].iloc[0]
            need(np.isclose(row.ratio_mean, r.mean(), rtol=1e-12) and row.instances == len(idx)
                 and (row.better, row.tie, row.worse) == (int((r < 1 - 1e-12).sum()), int((abs(r - 1) <= 1e-12).sum()),
                                                          int((r > 1 + 1e-12).sum())),
                 f"s02_paired.csv differs from raw for {a} vs {b} on {scope}")
            res[f"{a}_vs_{b}_{scope}_mean_rho"] = float(r.mean())
    a, b = per.loc[idx, "RL"], per.loc[idx, "HEFT"]
    p = float(wilcoxon(a, b, zero_method="wilcox").pvalue)
    res[f"RL_vs_HEFT_{scope}_wilcoxon"] = dict(n=len(idx), n_nonzero=int(((a - b) != 0).sum()), p=p)
    if scope == "test_id":
        row = paired[(paired.algorithm == "RL") & (paired.baseline == "HEFT") & (paired.split == "test_id")].iloc[0]
        need(np.isclose(row.wilcoxon_p, p, rtol=1e-9), "primary Wilcoxon p differs")
res["problems"] = problems
out.write_text(json.dumps(res, indent=2, default=str))
print(json.dumps(res, indent=2, default=str))
sys.exit(1 if problems else 0)
